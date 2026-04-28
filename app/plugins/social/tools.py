"""Social-Code Plugin — Native Hermes Simulation Tools.

Replaces the HTTP proxy stub with 7 tools that Hermes calls during
social skills training. State is persisted via RiveBot user variables,
ensuring per-user isolation (verified: RiveScript scopes vars by user_id).

Architecture:
  - When AI is available: Hermes calls these tools during its agent loop
  - When AI is unavailable: RiveBot triggers offline.py directly (golden set mode)
"""

import json
import logging
import os
from typing import Any, Dict

import httpx

from app.plugins import register_tool
from app.plugins.social.offline import (
    analyze_response_offline,
    compute_trust_delta,
    detect_sentiment,
    generate_offline_response,
)
from app.plugins.social.scenarios import (
    format_scenario_whatsapp,
    get_scenario,
    load_scenarios,
)
from app.plugins.social.mastery import (
    record_drill,
    get_session_stats,
    FSRS_LABELS,
)

logger = logging.getLogger(__name__)

RIVEBOT_URL = os.getenv("RIVEBOT_URL", "http://127.0.0.1:8087")

# ════════════════════════════════════════════════════════════════════════════
#  RiveBot State Persistence Helpers
# ════════════════════════════════════════════════════════════════════════════


def _get_urn(args: dict = None, **kw) -> str:
    """Extract the user URN from the invocation context.

    Priority:
      1. args['user_id'] — set by /v1/tools/ adapter (RapidPro flow webhooks)
      2. Hermes _current_urn — set during Hermes agent loop
      3. Fallback to 'user'
    """
    # Check args dict first (flow webhook path — tools adapter injects user_id)
    if args and isinstance(args, dict):
        uid = args.get("user_id", "")
        if uid and uid != "rivebot":
            return uid

    # Check Hermes context variable (agent loop path)
    try:
        from app.hermes.engine import _current_urn
        urn = _current_urn.get()
        if urn:
            return urn
    except Exception:
        pass
    return "user"


def _set_sim_var(urn: str, var: str, value: str) -> bool:
    """Persist a simulation variable in RiveBot (per-user, per-persona)."""
    try:
        httpx.post(
            f"{RIVEBOT_URL}/set-var",
            json={
                "persona": "social-code",
                "user": urn,
                "var": f"sim_{var}",
                "value": str(value),
            },
            timeout=2.0,
        )
        return True
    except Exception as e:
        logger.warning("Failed to set sim var %s for %s: %s", var, urn, e)
        return False


def _get_sim_var(urn: str, var: str, default: str = "") -> str:
    """Read a simulation variable from RiveBot (auto-prefixed with sim_)."""
    return _get_rivebot_var(urn, f"sim_{var}", default)


def _get_rivebot_var(urn: str, var: str, default: str = "") -> str:
    """Read any RiveBot user variable (no prefix manipulation)."""
    try:
        resp = httpx.get(
            f"{RIVEBOT_URL}/get-var",
            params={
                "persona": "social-code",
                "user": urn,
                "var": var,
            },
            timeout=2.0,
        )
        val = resp.json().get("value", default)
        return val if val != "undefined" else default
    except Exception:
        return default


# ════════════════════════════════════════════════════════════════════════════
#  Hermes-Registered Simulation Tools
# ════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="sim_update_mood",
    description="Update the persona's mood during a social simulation.",
    trigger="",
)
def sim_update_mood(args: dict, **kw) -> str:
    """Update mood state and persist via RiveBot."""
    urn = _get_urn(args)
    new_mood = args.get("new_mood", "Neutral")
    internal = args.get("internal_thought", "")
    reason = args.get("reason", "")

    _set_sim_var(urn, "mood", new_mood)
    _set_sim_var(urn, "monologue", internal[:200])

    logger.info("[social] %s mood → %s (%s)", urn, new_mood, reason)
    return f"Mood updated to: {new_mood}"


@register_tool(
    name="sim_update_trust",
    description="Adjust trust score based on user's social behavior.",
    trigger="",
)
def sim_update_trust(args: dict, **kw) -> str:
    """Adjust trust and persist."""
    urn = _get_urn(args)
    change = int(args.get("trust_change", 0))
    reason = args.get("reason", "")

    current = int(_get_sim_var(urn, "trust", "20"))
    new_trust = max(0, min(100, current + change))
    _set_sim_var(urn, "trust", str(new_trust))

    direction = "gained" if change > 0 else "lost"
    logger.info("[social] %s trust %s %d → %d (%s)", urn, direction, current, new_trust, reason)
    return f"Trust score: {current} → {new_trust} ({'+' if change >= 0 else ''}{change})"


@register_tool(
    name="sim_update_dossier",
    description="Record a fact learned about the user.",
    trigger="",
)
def sim_update_dossier(args: dict, **kw) -> str:
    """Record a fact in the simulation dossier."""
    urn = _get_urn(args)
    key = args.get("key", "unknown")
    value = args.get("value", "")

    # Dossier is stored as a JSON string in RiveBot
    raw = _get_sim_var(urn, "dossier", "{}")
    try:
        dossier = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        dossier = {}

    dossier[key] = value
    _set_sim_var(urn, "dossier", json.dumps(dossier, ensure_ascii=False))

    logger.info("[social] %s dossier: %s = %s", urn, key, value)
    return f"Dossier updated: {key} = {value}"


@register_tool(
    name="sim_assess_boredom",
    description="Set the persona's engagement/boredom level.",
    trigger="",
)
def sim_assess_boredom(args: dict, **kw) -> str:
    """Set boredom level."""
    urn = _get_urn(args)
    level = max(0, min(10, int(args.get("boredom_level", 0))))
    reason = args.get("reason", "")

    _set_sim_var(urn, "boredom", str(level))

    status = "fascinated" if level < 3 else "engaged" if level < 6 else "bored" if level < 9 else "leaving"
    logger.info("[social] %s boredom %d (%s) — %s", urn, level, status, reason)
    return f"Boredom: {level}/10 ({status})"


@register_tool(
    name="sim_trigger_distraction",
    description="Introduce an environmental distraction.",
    trigger="",
)
def sim_trigger_distraction(args: dict, **kw) -> str:
    """Trigger an environmental distraction."""
    urn = _get_urn(args)
    level = max(0, min(10, int(args.get("distraction_level", 0))))
    source = args.get("source", "unknown")

    _set_sim_var(urn, "distraction", str(level))
    _set_sim_var(urn, "distraction_src", source[:100])

    logger.info("[social] %s distraction: %s (level %d)", urn, source, level)
    return f"Distraction triggered: {source} (Level {level})"


@register_tool(
    name="sim_grade_response",
    description="Grade the user's social skill response.",
    trigger="",
)
def sim_grade_response(args: dict, **kw) -> str:
    """Grade the user's response and format for WhatsApp."""
    skill = int(args.get("skill_score", 50))
    warmth = int(args.get("warmth_score", 50))
    critique = args.get("critique", "")
    better = args.get("better_version", "")
    wit = args.get("wit_mechanic", "None")

    # Format scorecard for WhatsApp
    skill_emoji = "🟢" if skill >= 80 else "🟡" if skill >= 60 else "🔴"
    warmth_emoji = "🟢" if warmth >= 80 else "🟡" if warmth >= 60 else "🔴"

    card = (
        f"📊 *Social Skills Scorecard*\n\n"
        f"{skill_emoji} *Skill*: {skill}/100\n"
        f"{warmth_emoji} *Warmth*: {warmth}/100\n"
    )
    if wit and wit != "None":
        card += f"🎭 *Wit*: {wit} mechanic detected\n"
    if critique:
        card += f"\n💡 *Feedback:* {critique}\n"
    if better:
        card += f"\n✨ *Try this:* _{better}_"

    return card


@register_tool(
    name="sim_get_scenario",
    description="Fetch a training scenario from the golden set.",
    trigger="",
)
def sim_get_scenario(args: dict, **kw) -> str:
    """Load a random golden-set scenario and format it."""
    urn = _get_urn(args)
    difficulty = int(args.get("difficulty", 1))

    # Get language from RiveBot context (stored as 'lang', not 'sim_lang')
    lang = _get_rivebot_var(urn, "lang", "en")
    if not lang or lang == "undefined":
        lang = "en"

    scenario = get_scenario(difficulty=difficulty, lang=lang)
    if not scenario:
        return "No scenarios available at this difficulty level."

    # Store current scenario context for grading reference
    _set_sim_var(urn, "current_context", scenario["context"][:200])
    _set_sim_var(urn, "current_cue", scenario["cue"][:200])
    _set_sim_var(urn, "current_persona", scenario["target_persona"])
    _set_sim_var(urn, "difficulty", str(difficulty))

    # Store golden ideal_links for use during grading
    import json as _json
    ideal_links = scenario.get("ideal_links", [])
    if ideal_links:
        _set_sim_var(urn, "ideal_links", _json.dumps(ideal_links)[:500])

    return format_scenario_whatsapp(scenario)


@register_tool(
    name="sim_drill_grade",
    description="Grade a user's drill response using offline analysis + state tracking. "
                "Called by the RapidPro flow webhook — not by Hermes directly.",
    trigger="",  # No RiveBot trigger — webhook-only
)
def sim_drill_grade(args: dict, **kw) -> str:
    """Full grading pipeline for flow webhooks.

    Unlike sim_grade_response (which accepts pre-computed scores from the LLM),
    this tool actually analyzes the user's text:
      1. Reads current scenario context from RiveBot state
      2. Runs offline keyword grading
      3. Updates mood and trust via RiveBot state
      4. Returns formatted WhatsApp scorecard
    """
    urn = _get_urn(args)
    user_input = args.get("user_input", args.get("critique", ""))

    if not user_input:
        return "⚠️ No response received."

    # ── Read current state from RiveBot ──
    context = _get_sim_var(urn, "current_context", "a social situation")
    current_mood = _get_sim_var(urn, "mood", "Neutral")
    current_trust = int(_get_sim_var(urn, "trust", "20"))
    current_boredom = int(_get_sim_var(urn, "boredom", "0"))
    lang = _get_rivebot_var(urn, "lang", "en") or "en"

    # ── Read golden ideal_links from state (stored during scenario load) ──
    import json as _json
    ideal_links_raw = _get_sim_var(urn, "ideal_links", "")
    golden_ideal = None
    golden_explanation = None
    if ideal_links_raw and ideal_links_raw != "undefined":
        try:
            ideal_links = _json.loads(ideal_links_raw)
            if ideal_links and isinstance(ideal_links, list):
                link = ideal_links[0]  # Primary ideal response
                golden_ideal = link.get("link_text", "")
                golden_explanation = link.get("explanation", "")
        except (ValueError, KeyError):
            pass

    # ── Grade with offline engine ──
    grade = analyze_response_offline(context, user_input, lang)
    skill = grade["score"]
    warmth = grade["warmth_score"]

    # ── Update mood & trust ──
    sentiment = detect_sentiment(user_input, lang)
    trust_delta = compute_trust_delta(user_input, current_trust, lang)
    new_trust = max(0, min(100, current_trust + trust_delta))

    from app.plugins.social.offline import MOOD_TRANSITIONS
    new_mood = MOOD_TRANSITIONS.get((current_mood, sentiment), current_mood)

    word_count = len(user_input.split())
    new_boredom = max(0, min(10, current_boredom + (1 if word_count < 4 else -1)))

    # ── Persist updated state ──
    _set_sim_var(urn, "mood", new_mood)
    _set_sim_var(urn, "trust", str(new_trust))
    _set_sim_var(urn, "boredom", str(new_boredom))

    # ── FSRS mastery tracking ──
    scenario_key = _get_sim_var(urn, "current_cue", "")[:80] or "unknown"
    app_slug = _get_sim_var(urn, "app", "")
    difficulty = int(_get_sim_var(urn, "difficulty", "1"))
    fsrs_result = record_drill(
        user_urn=urn,
        scenario_key=scenario_key,
        app_slug=app_slug,
        difficulty=difficulty,
        skill=skill,
        warmth=warmth,
        lang=lang,
    )

    # ── Format scorecard ──
    skill_emoji = "🟢" if skill >= 80 else "🟡" if skill >= 60 else "🔴"
    warmth_emoji = "🟢" if warmth >= 80 else "🟡" if warmth >= 60 else "🔴"
    trust_dir = "📈" if trust_delta > 0 else "📉" if trust_delta < 0 else "➡️"
    fsrs_emoji = {1: "🔴", 2: "🟠", 3: "🟢", 4: "✨"}.get(fsrs_result["rating"], "⚪")

    card = (
        f"📊 *Scorecard*\n\n"
        f"{skill_emoji} *Skill*: {skill}/100\n"
        f"{warmth_emoji} *Warmth*: {warmth}/100\n"
        f"{trust_dir} *Trust*: {current_trust} → {new_trust} ({'+' if trust_delta >= 0 else ''}{trust_delta})\n"
        f"😊 *Mood*: {current_mood} → {new_mood}\n"
        f"{fsrs_emoji} *Review*: {fsrs_result['label']} (next {fsrs_result['interval_text']})\n"
    )

    if grade.get("critique"):
        card += f"\n{grade['critique']}\n"

    # Use golden ideal_links (expert-crafted) over template-generated suggestions
    if golden_ideal:
        card += f"\n✨ *Try this:* _{golden_ideal}_\n"
        if golden_explanation:
            card += f"💡 _{golden_explanation}_\n"
    elif grade.get("better_version"):
        card += f"\n✨ *Try this:* _{grade['better_version']}_\n"

    if new_boredom >= 8:
        card += "\n⚠️ The persona is getting bored! Try asking questions or sharing something personal."

    logger.info(
        "[social] %s drill grade: skill=%d warmth=%d trust=%d→%d mood=%s→%s fsrs=%s",
        urn, skill, warmth, current_trust, new_trust, current_mood, new_mood,
        fsrs_result['label'],
    )

    return card


@register_tool(
    name="sim_freetext",
    description="Handle free-text input that doesn't match a menu option. "
                "Routes to RiveBot first; if no match, forwards to Hermes.",
    trigger="",
)
def sim_freetext(args: dict, **kw) -> str:
    """Conversational fallback for unrecognized menu input.

    Architecture: RiveBot first (deterministic), Hermes second (AI).
    Always returns the user to the menu they were on.
    """
    urn = _get_urn(args)
    user_input = args.get("user_input", "").strip()

    if not user_input:
        return "❓ I didn't catch that. Please pick an option from the menu."

    # 1. Try RiveBot first (deterministic match)
    try:
        resp = httpx.post(
            f"{RIVEBOT_URL}/reply",
            json={"persona": "social-code", "user": urn, "message": user_input},
            timeout=3.0,
        )
        rivebot_reply = resp.json().get("reply", "").strip()

        # RiveBot returns empty or its catchall "I don't understand" for non-matches
        if rivebot_reply and "i don't" not in rivebot_reply.lower() and len(rivebot_reply) > 5:
            return f"💬 {rivebot_reply}\n\n_Pick an option from the menu to continue._"
    except Exception as e:
        logger.debug("[sim_freetext] RiveBot unavailable: %s", e)

    # 2. Fall back to Hermes AI (lightweight direct LLM call)
    try:
        import google.generativeai as genai
        import os
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(os.getenv("LLM_MODEL", "gemini-2.0-flash"))
            resp = model.generate_content(
                f"You are a social skills training assistant on WhatsApp. "
                f"Answer the user's question briefly (2-3 sentences max). "
                f"User said: {user_input}",
            )
            ai_reply = resp.text.strip() if resp.text else ""
            if ai_reply:
                return f"🤖 {ai_reply}\n\n_Pick an option from the menu to continue._"
    except Exception as e:
        logger.debug("[sim_freetext] LLM unavailable: %s", e)

    # 3. Final fallback
    return "❓ I didn't understand that. Please pick an option from the menu, or type *exit* to leave."


@register_tool(
    name="sim_set_language",
    description="Set the user's preferred language for Social-Code training.",
    trigger="",
)
def sim_set_language(args: dict, **kw) -> str:
    """Persist language preference for drill scenarios and feedback."""
    urn = _get_urn(args)
    lang_input = args.get("language", args.get("lang", "en")).strip().lower()

    # Normalize input to ISO code
    LANG_MAP = {
        "english": "en", "en": "en",
        "kreyòl": "ht", "kreol": "ht", "kreyol": "ht", "ht": "ht",
        "español": "es", "espanol": "es", "spanish": "es", "es": "es",
        "français": "fr", "francais": "fr", "french": "fr", "fr": "fr",
    }
    lang = LANG_MAP.get(lang_input, "en")
    lang_names = {"en": "English", "ht": "Kreyòl", "es": "Español", "fr": "Français"}

    # Persist in RiveBot state
    try:
        httpx.post(
            f"{RIVEBOT_URL}/set-var",
            json={"persona": "social-code", "user": urn, "var": "lang", "value": lang},
            timeout=2.0,
        )
    except Exception as e:
        logger.warning("[sim_set_language] Failed: %s", e)
        return "⚠️ Could not save language preference."

    return f"🌐 Language set to *{lang_names.get(lang, lang)}*.\n\nScenarios and feedback will now be in {lang_names.get(lang, lang)}."


@register_tool(
    name="sim_session_summary",
    description="Show a summary of the current training session.",
    trigger="",
)
def sim_session_summary(args: dict, **kw) -> str:
    """Aggregate session stats from the drill history database."""
    urn = _get_urn(args)
    stats = get_session_stats(urn, since_minutes=120)

    if stats["rounds"] == 0:
        return "📊 No drills completed in this session yet. Pick an app and start training!"

    avg_emoji = "🟢" if stats["avg_score"] >= 80 else "🟡" if stats["avg_score"] >= 60 else "🔴"

    return (
        f"📊 *Session Summary*\n\n"
        f"🔢 *Rounds*: {stats['rounds']}\n"
        f"{avg_emoji} *Avg Score*: {stats['avg_score']}/100\n"
        f"⚡ *Avg Skill*: {stats['avg_skill']}/100\n"
        f"💚 *Avg Warmth*: {stats['avg_warmth']}/100\n\n"
        f"_Type *train* to continue practicing!_"
    )
