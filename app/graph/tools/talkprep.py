"""
TalkPrep LangGraph tools — full 6-stage workflow exposed to the gateway agent.

All blocking I/O is wrapped in asyncio.to_thread() so the async event loop
is never blocked even when talkmaster calls SQLite or runs LLM chains.
"""

import asyncio
import os
from typing import Optional

from langchain_core.tools import tool
from app.logger import setup_logger

logger = setup_logger().bind(name="tool.talkprep")

# Configurable jwlinker DB path (#8)
JWLINKER_DB_PATH: Optional[str] = os.getenv("JWLINKER_DB_PATH") or None


def _siyuan_doc_url(doc_id: str) -> str:
    """Build a clickable SiYuan URL for a document ID."""
    base = os.getenv("SIYUAN_PUBLIC_URL", "http://localhost:6806")
    return f"{base}/stage/build/desktop/?id={doc_id}"


# ── Helpers ─────────────────────────────────────────────────────────

def _get_talkmaster_session():
    """Open a talkmaster DB session (sync — call from thread)."""
    from talkmaster.config import get_settings
    from talkmaster.database import get_engine, get_session
    settings = get_settings()
    engine = get_engine(settings.db_path)
    return get_session(engine), engine


# ── Stage Gates (deterministic, zero AI) ─────────────────────────────

def _gate_talk_exists(session, talk_id: int) -> str | None:
    """Gate: talk must exist. Return error string or None."""
    from talkmaster.database import Talk
    if not session.query(Talk).filter_by(id=talk_id).first():
        return (
            f"⛔ Talk ID `{talk_id}` not found.\n"
            "Run `talkmaster_status` to see imported talks, "
            "or `list_publications` → `import_talk` to get started."
        )
    return None


def _gate_revision_exists(session, revision_name: str) -> str | None:
    """Gate: revision must exist. Return error string or None."""
    from talkmaster.database import Revision
    if not session.query(Revision).filter_by(version_name=revision_name).first():
        return (
            f"⛔ Revision `{revision_name}` not found.\n"
            "Create one first: `create_revision <talk_id> <version_name> <audience>`"
        )
    return None


def _gate_section_developed(session, revision_name: str) -> str | None:
    """Gate: at least one section must be developed before evaluation."""
    from talkmaster.database import Revision, StructureNode
    rev = session.query(Revision).filter_by(version_name=revision_name).first()
    if not rev:
        return _gate_revision_exists(session, revision_name)
    developed = (
        session.query(StructureNode)
        .filter_by(revision_id=rev.id, content_is_developed=True)
        .count()
    )
    if developed == 0:
        return (
            f"⛔ No sections have been developed yet for `{revision_name}`.\n"
            "Develop at least one section before evaluating:\n"
            "`develop_section <revision_name> <section_title>`"
        )
    return None


def _gate_evaluation_done(session, revision_name: str) -> str | None:
    """Gate: evaluation must have been run before rehearsal/export."""
    from talkmaster.database import Revision, EvaluationScore
    rev = session.query(Revision).filter_by(version_name=revision_name).first()
    if not rev:
        return _gate_revision_exists(session, revision_name)
    count = session.query(EvaluationScore).filter_by(revision_id=rev.id).count()
    if count == 0:
        return (
            f"⛔ No evaluation scores found for `{revision_name}`.\n"
            "Run evaluation first: `evaluate_talk <revision_name>`"
        )
    return None


def _gate_rehearsal_done(session, revision_name: str) -> str | None:
    """Gate: at least one rehearsal session must exist before export."""
    from talkmaster.database import Revision, RehearsalRecord
    rev = session.query(Revision).filter_by(version_name=revision_name).first()
    if not rev:
        return _gate_revision_exists(session, revision_name)
    count = session.query(RehearsalRecord).filter_by(revision_id=rev.id).count()
    if count == 0:
        return (
            f"⛔ Complete at least one rehearsal session before exporting.\n"
            "Start rehearsal: `rehearsal_cue <revision_name>`"
        )
    return None


# ── Stage 0: Status & Help ───────────────────────────────────────────

@tool
async def get_talkprep_help() -> str:
    """Return an onboarding guide for new TalkPrep users.

    Returns:
        A formatted guide explaining available commands and workflow stages.
    """
    return (
        "🎙️ *TalkPrep Coach — Available Commands*\n\n"
        "*Stage 1 — Import*\n"
        "• `list_publications` — show available publications\n"
        "• `list_topics <pub_code>` — list topics in a publication\n"
        "• `import_talk <pub_code> <topic> <theme>` — import a talk\n\n"
        "*Stage 2 — Revision*\n"
        "• `create_revision <talk_id> <version_name> <audience>` — create a revision\n"
        "• `select_active_talk <talk_id>` — switch active talk\n\n"
        "*Stage 3 — Development*\n"
        "• `develop_section <revision> <section_title>` — AI-develop a section\n\n"
        "*Stage 4 — Evaluation*\n"
        "• `evaluate_talk <revision>` — score against the S-38 rubric\n"
        "• `get_evaluation_scores <revision>` — view scores by category\n\n"
        "*Stage 5 — Rehearsal*\n"
        "• `rehearsal_cue <revision>` — get delivery coaching cues\n\n"
        "*Stage 6 — Export*\n"
        "• `export_talk_summary <revision>` — assemble final manuscript\n\n"
        "*Study Tools*\n"
        "• `generate_anki_deck <pub_code>` — create Anki flashcards\n"
        "• `push_to_siyuan <pub_code>` — export to SiYuan notebook\n\n"
        "• `talkmaster_status` — view all imported talks\n"
        "• `cost_report` — view LLM token usage for this session\n"
        "• Upload a `.jwpub` file as a WhatsApp attachment to import publications\n"
    )


@tool
async def talkmaster_status() -> str:
    """Check the current talkmaster status: imported talks, revisions.

    Returns:
        A summary table of imported talks and their revisions.
    """
    def _sync():
        from talkmaster.database import Talk, Revision
        session, engine = _get_talkmaster_session()
        try:
            talks = session.query(Talk).all()
            if not talks:
                return (
                    "No talks imported yet.\n"
                    "Use `list_publications` to browse available publications,\n"
                    "then `import_talk` to get started."
                )
            lines = ["*Imported Talks:*"]
            for t in talks:
                revs = session.query(Revision).filter_by(talk_id=t.id).all()
                rev_names = ", ".join(r.version_name for r in revs) or "no revisions"
                lines.append(f"• [{t.id}] *{t.name}* — {t.theme}\n  Revisions: {rev_names}")
            return "\n".join(lines)
        finally:
            session.close()
            engine.dispose()

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"talkmaster_status failed: {e}")
        return f"Error checking status: {e}"


@tool
async def select_active_talk(talk_id: int) -> str:
    """Select a talk as the active context for subsequent operations.

    Args:
        talk_id: Numeric ID of the talk (from talkmaster_status).

    Returns:
        Confirmation with talk name and available revisions.
    """
    def _sync():
        from talkmaster.database import Talk, Revision
        session, engine = _get_talkmaster_session()
        try:
            talk = session.query(Talk).filter_by(id=talk_id).first()
            if not talk:
                return f"Talk ID {talk_id} not found. Run `talkmaster_status` to see available talks."
            revs = session.query(Revision).filter_by(talk_id=talk_id).all()
            rev_info = (
                ", ".join(r.version_name for r in revs)
                if revs else "none — create one with `create_revision`"
            )
            return (
                f"✅ Active talk set:\n"
                f"• ID: {talk.id}\n"
                f"• Name: {talk.name}\n"
                f"• Theme: {talk.theme}\n"
                f"• Revisions: {rev_info}"
            )
        finally:
            session.close()
            engine.dispose()

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"select_active_talk failed: {e}")
        return f"Error selecting talk: {e}"


# ── Stage 1: Import ──────────────────────────────────────────────────

@tool
async def list_publications() -> str:
    """List all available JW publications in the jwlinker database.

    Returns:
        A formatted list of publications with codes and topic counts.
    """
    def _sync():
        from talkmaster.bridge import list_jwlinker_publications
        pubs = list_jwlinker_publications(JWLINKER_DB_PATH)
        if not pubs:
            return (
                "No publications found.\n"
                "Run `jwlinker extract-jwpub <file>` on the server first."
            )
        lines = [f"• *{p['code']}* ({p['language']}) — {p['topic_count']} topics" for p in pubs]
        return "📚 *Available publications:*\n" + "\n".join(lines)

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"list_publications failed: {e}")
        return f"Error listing publications: {e}"


@tool
async def list_topics(pub_code: str) -> str:
    """List all topics (talk outlines) for a given publication code.

    Args:
        pub_code: Publication code, e.g. 's-34', 'lmd', 'scl'.

    Returns:
        Formatted list of available topics with categories.
    """
    def _sync():
        from talkmaster.bridge import list_jwlinker_topics
        topics = list_jwlinker_topics(pub_code, db_path=JWLINKER_DB_PATH)
        if not topics:
            return f"No topics found for '{pub_code}'. Check the code with `list_publications`."
        lines = [f"• *{t['name']}* — category: {t['category']}" for t in topics[:30]]
        suffix = f"\n_(showing first 30 of {len(topics)})_" if len(topics) > 30 else ""
        return f"📋 *Topics in '{pub_code}':*\n" + "\n".join(lines) + suffix

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"list_topics failed: {e}")
        return f"Error listing topics: {e}"


@tool
async def import_talk(pub_code: str, topic_name: str, theme: str, language: str = "en") -> str:
    """Import a talk outline from a JW Library publication into talkmaster.

    Args:
        pub_code: Publication code (e.g., 's-34', 'lmd').
        topic_name: Exact or partial topic name to search for.
        theme: Theme or title for this talk preparation session.
        language: Language code (e.g., 'en', 'fr', 'cr').

    Returns:
        Confirmation with imported talk details and its new ID.
    """
    def _sync():
        from talkmaster.bridge import import_from_jwlinker, save_imported_talk
        talk = import_from_jwlinker(
            pub_code=pub_code,
            topic_name=topic_name,
            talk_theme=theme,
            language=language,
            db_path=JWLINKER_DB_PATH,
        )
        talk_id = save_imported_talk(talk)
        sections = len(talk.outline)
        points = sum(len(s.discussion_points) for s in talk.outline)
        return (
            f"✅ *Talk imported successfully!*\n"
            f"• ID: `{talk_id}` _(use this to create revisions)_\n"
            f"• Name: {talk.talk_metadata.name}\n"
            f"• Theme: {theme}\n"
            f"• Sections: {sections} | Points: {points}\n\n"
            f"Next: `create_revision {talk_id} version-1 <audience>`"
        )

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"import_talk failed: {e}")
        return f"Error importing talk: {e}"


# ── Stage 2: Revision ────────────────────────────────────────────────

@tool
async def create_revision(
    talk_id: int,
    version_name: str,
    audience_description: str = "General congregation audience",
) -> str:
    """Create a new revision of a talk with an audience persona and golden thread.

    Args:
        talk_id: ID of the imported talk (from talkmaster_status or import_talk).
        version_name: Unique name for this revision (e.g., 'version-1', 'young-adults').
        audience_description: Description of the target audience for this revision.

    Returns:
        Confirmation with revision details and next steps.
    """
    def _sync():
        from talkmaster.database import Talk, Revision, AudiencePersona
        from talkmaster.repositories import create_talk_structure
        session, engine = _get_talkmaster_session()
        try:
            # ── Stage gate: talk must exist ───────────────────────────────
            gate = _gate_talk_exists(session, talk_id)
            if gate:
                return gate

            talk = session.query(Talk).filter_by(id=talk_id).first()

            # Check for duplicate version name
            existing = session.query(Revision).filter_by(
                talk_id=talk_id, version_name=version_name
            ).first()
            if existing:
                return f"Revision '{version_name}' already exists for this talk. Choose a different name."

            persona = AudiencePersona(
                talk_id=talk_id,
                description=audience_description,
            )
            session.add(persona)
            session.flush()

            revision = Revision(
                talk_id=talk_id,
                version_name=version_name,
                audience_persona_id=persona.id,
            )
            session.add(revision)
            session.commit()

            return (
                f"✅ *Revision '{version_name}' created!*\n"
                f"• Talk: {talk.name}\n"
                f"• Audience: {audience_description}\n\n"
                f"Next: develop each section with\n"
                f"`develop_section {version_name} <section_title>`"
            )
        finally:
            session.close()
            engine.dispose()

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"create_revision failed: {e}")
        return f"Error creating revision: {e}"


# ── Stage 3: Section Development ────────────────────────────────────

@tool
async def develop_section(revision_name: str, section_title: str) -> str:
    """AI-develop a single section of a talk revision.

    Args:
        revision_name: Name of the active revision (e.g., 'version-1').
        section_title: Title of the section to develop (partial match OK).

    Returns:
        Confirmation or status of the developed section.
    """
    def _sync():
        from talkmaster.siyuan import generation
        session, engine = _get_talkmaster_session()
        try:
            # ── Stage gate: revision must exist ──────────────────────────
            gate = _gate_revision_exists(session, revision_name)
            if gate:
                return gate

            result = generation.develop_section(
                version_name=revision_name,
                db=session,
                section_title=section_title,
            )
            if result:
                # Truncate for WhatsApp readability
                preview = result[:400] + "…" if len(result) > 400 else result
                return f"✅ *Section '{section_title}' developed:*\n\n_{preview}_"
            return f"⚠️ Could not develop '{section_title}'. Check the section title."
        finally:
            session.close()
            engine.dispose()

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"develop_section failed: {e}")
        return f"Error developing section: {e}"


# ── Stage 4: Evaluation ──────────────────────────────────────────────

@tool
async def evaluate_talk(revision_name: str) -> str:
    """Evaluate a talk revision against the 53-point S-38 rubric.

    Args:
        revision_name: Name of the revision to evaluate.

    Returns:
        Trigger confirmation — scores available via get_evaluation_scores.
    """
    def _sync():
        from talkmaster.database import Revision
        from talkmaster.siyuan import generation
        session, engine = _get_talkmaster_session()
        try:
            # ── Stage gate: must have developed at least one section ──────
            gate = _gate_section_developed(session, revision_name)
            if gate:
                return gate

            rev = session.query(Revision).filter_by(version_name=revision_name).first()
            if not rev:
                return f"Revision '{revision_name}' not found."
            result = generation.review_cohesion(version_name=revision_name, db=session)
            return (
                f"✅ *Evaluation started for '{revision_name}'*\n"
                f"S-38 rubric analysis running…\n"
                f"Use `get_evaluation_scores {revision_name}` to view results."
            )
        finally:
            session.close()
            engine.dispose()

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"evaluate_talk failed: {e}")
        return f"Error evaluating talk: {e}"


@tool
async def get_evaluation_scores(revision_name: str) -> str:
    """Get S-38 rubric evaluation scores for a talk revision.

    Args:
        revision_name: Name of the revision to get scores for.

    Returns:
        Scores broken down by S-38 category with coaching tips.
    """
    def _sync():
        from talkmaster.database import Revision, EvaluationScore, EvaluationPoint
        session, engine = _get_talkmaster_session()
        try:
            rev = session.query(Revision).filter_by(version_name=revision_name).first()
            if not rev:
                return f"Revision '{revision_name}' not found."

            scores = (
                session.query(EvaluationScore)
                .join(EvaluationPoint)
                .filter(EvaluationScore.revision_id == rev.id)
                .all()
            )
            if not scores:
                return (
                    f"No scores yet for '{revision_name}'.\n"
                    f"Run `evaluate_talk {revision_name}` first."
                )

            # Group by category
            by_cat: dict = {}
            for s in scores:
                cat = s.evaluation_point.category
                by_cat.setdefault(cat, []).append(s.score)

            lines = [f"📊 *Scores for '{revision_name}':*"]
            total, count = 0, 0
            for cat, cat_scores in sorted(by_cat.items()):
                avg = sum(cat_scores) / len(cat_scores)
                bar = "█" * int(avg / 10) + "░" * (10 - int(avg / 10))
                lines.append(f"• {cat}: {bar} {avg:.0f}/100")
                total += sum(cat_scores)
                count += len(cat_scores)

            overall = total / count if count else 0
            lines.append(f"\n*Overall: {overall:.0f}/100*")

            if overall < 60:
                lines.append("💡 Focus on Content & Logic and Vocal Delivery first.")
            elif overall < 80:
                lines.append("💡 Good foundation — work on Audience Connection.")
            else:
                lines.append("🌟 Excellent! Ready to rehearse.")

            return "\n".join(lines)
        finally:
            session.close()
            engine.dispose()

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"get_evaluation_scores failed: {e}")
        return f"Error fetching scores: {e}"


# ── Stage 5: Rehearsal ───────────────────────────────────────────────

@tool
async def rehearsal_cue(revision_name: str) -> str:
    """Generate AI delivery coaching cues for rehearsal of a talk revision.

    Args:
        revision_name: Name of the revision to rehearse.

    Returns:
        Personalized delivery cues: pacing, pauses, emphasis, eye contact.
    """
    def _sync():
        from talkmaster.database import Revision, RehearsalRecord
        from talkmaster.llm import completion
        import datetime

        session, engine = _get_talkmaster_session()
        try:
            # ── Stage gate: evaluation must have been done ────────────────
            gate = _gate_evaluation_done(session, revision_name)
            if gate:
                return gate

            rev = session.query(Revision).filter_by(version_name=revision_name).first()
            if not rev:
                return f"Revision '{revision_name}' not found."

            # Pull rehearsal count for progression
            rehearsal_count = (
                session.query(RehearsalRecord)
                .filter_by(revision_id=rev.id)
                .count()
            )

            prompt = (
                f"You are a JW public speaking coach. The speaker is doing rehearsal "
                f"#{rehearsal_count + 1} of their talk revision '{revision_name}'.\n\n"
                f"Give 5 short, actionable delivery coaching tips covering:\n"
                f"1. Opening — how to establish eye contact immediately\n"
                f"2. Pacing — when to slow down for impact\n"
                f"3. Pausing — where to pause for effect (cite a specific point if possible)\n"
                f"4. Vocal modulation — how to vary tone\n"
                f"5. Closing — how to make the conclusion memorable\n\n"
                f"Be specific, warm, and concise. Each tip max 2 sentences."
            )

            response = completion(
                model=os.getenv("LLM_MODEL", "custom_ai"),
                messages=[{"role": "user", "content": prompt}],
                api_base=os.getenv("OPENAI_API_BASE", "http://localhost:4000"),
                api_key=os.getenv("OPENAI_API_KEY", ""),
            )

            cues = response.choices[0].message.content

            # Log rehearsal record
            record = RehearsalRecord(
                revision_id=rev.id,
                rehearsal_date=datetime.datetime.utcnow(),
                notes=f"AI cues generated (rehearsal #{rehearsal_count + 1})",
            )
            session.add(record)
            session.commit()

            return (
                f"🎤 *Rehearsal #{rehearsal_count + 1} cues for '{revision_name}':*\n\n"
                f"{cues}"
            )
        finally:
            session.close()
            engine.dispose()

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"rehearsal_cue failed: {e}")
        return f"Error generating rehearsal cues: {e}"


# ── Stage 6: Export ──────────────────────────────────────────────────

@tool
async def export_talk_summary(revision_name: str) -> str:
    """Assemble and export the final talk manuscript summary.

    Args:
        revision_name: Name of the revision to export.

    Returns:
        A condensed version of the full manuscript for review.
    """
    def _sync():
        from talkmaster.siyuan import generation
        session, engine = _get_talkmaster_session()
        try:
            # ── Stage gate: must have rehearsed at least once ─────────────
            gate = _gate_rehearsal_done(session, revision_name)
            if gate:
                return gate

            result = generation.assemble_manuscript(
                version_name=revision_name,
                db=session,
                source="ai",
            )
            if result:
                siyuan_url = _siyuan_doc_url(result)
                return (
                    f"✅ *Manuscript assembled for '{revision_name}'*\n"
                    f"• View in SiYuan: {siyuan_url}\n\n"
                    f"Your AI-developed manuscript is ready.\n\n"
                    f"📌 *Next steps:*\n"
                    f"• `generate_anki_deck` — create flashcards for memorization\n"
                    f"• `push_to_siyuan` — export study materials to SiYuan"
                )
            return f"⚠️ Could not assemble manuscript for '{revision_name}'."
        finally:
            session.close()
            engine.dispose()

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"export_talk_summary failed: {e}")
        return f"Error exporting manuscript: {e}"


# ── Cost Reporting ───────────────────────────────────────────────────

@tool
async def cost_report() -> str:
    """Show LLM token usage and estimated cost for the current talkmaster session.

    Returns:
        Token counts and estimated USD cost for this preparation session.
    """
    def _sync():
        from talkmaster.llm import get_session_usage
        usage = get_session_usage()
        return (
            f"💰 *Session LLM Usage:*\n"
            f"• Prompt tokens: {usage.prompt_tokens:,}\n"
            f"• Completion tokens: {usage.completion_tokens:,}\n"
            f"• Total: {usage.total_tokens:,}\n"
            f"• Est. cost: ~${usage.estimated_cost_usd:.4f} USD"
        )

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"cost_report failed: {e}")
        return f"Error fetching usage: {e}"


# ── JWLinker Integration ─────────────────────────────────────────────

def _get_jwlinker_cards(pub_code: str, topic_name: Optional[str] = None,
                        language: str = "Haitian", locale: str = "CR"):
    """Fetch parsed cards from jwlinker DB for a given publication.

    Returns a list of AnkiCard objects. Reuses jwlinker's existing
    get_cards_for_generate() pipeline with a synthetic args namespace.
    """
    from types import SimpleNamespace
    from jwlinker.commands.db import get_cards_for_generate

    args = SimpleNamespace(
        pub=pub_code,
        lang_id=None,
        language=language,
        locale=locale,
        format=None,
        category=None,
        topic=topic_name,
        verbose=False,
        stories_as_cards=False,
    )
    return get_cards_for_generate(args)


@tool
async def generate_anki_deck(pub_code: str, topic_name: Optional[str] = None) -> str:
    """Generate an Anki flashcard deck (.apkg) from a JW publication in the database.

    The deck is saved and a download URL is returned so the user can
    fetch the .apkg file directly. If no topic is specified, all topics
    for the publication are included.

    Args:
        pub_code: Publication code (e.g., 's34', 'lmd', 'scl').
        topic_name: Optional topic name filter (partial match OK).

    Returns:
        Download URL for the generated .apkg file, or an error message.
    """
    def _sync():
        from jwlinker.exporters.anki import AnkiExporter
        from jwlinker.core.linker import Linker

        cards = _get_jwlinker_cards(pub_code, topic_name)
        if not cards:
            return f"⚠️ No cards found for publication '{pub_code}'" + (
                f" topic '{topic_name}'" if topic_name else ""
            ) + ". Run `jwlinker extract-jwpub` on the server first."

        linker = Linker(language="Haitian", locale="CR")
        deck_name = f"JW Study: {pub_code}"
        if topic_name:
            deck_name += f" — {topic_name}"
        exporter = AnkiExporter(root_deck_name=deck_name)
        exporter.add_cards(cards, linker, {})

        filename = f"jwlinker_{pub_code}{'_' + topic_name.replace(' ', '_') if topic_name else ''}.apkg"
        output_path = f"/tmp/{filename}"
        exporter.export(output_path)

        # Build download URL using gateway base
        gateway_base = os.getenv("GATEWAY_PUBLIC_URL", "http://localhost:8086")
        download_url = f"{gateway_base}/downloads/{filename}"

        return (
            f"✅ *Anki deck generated!*\n"
            f"• Cards: {len(cards)}\n"
            f"• Deck: {deck_name}\n"
            f"• Download: {download_url}\n\n"
            f"Open the link to download the .apkg file, "
            f"then import it into Anki."
        )

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"generate_anki_deck failed: {e}")
        return f"Error generating Anki deck: {e}"


@tool
async def push_to_siyuan(pub_code: str, topic_name: Optional[str] = None) -> str:
    """Push JW publication content to SiYuan as a structured document tree.

    Creates a two-level tree (sections → lessons) with scripture links and
    spaced-repetition flashcards. Requires SIYUAN_NOTEBOOK_ID env var.

    Args:
        pub_code: Publication code (e.g., 's34', 'lmd', 'scl').
        topic_name: Optional topic name filter (partial match OK).

    Returns:
        SiYuan root document ID, or an error message.
    """
    def _sync():
        import re
        from jwlinker.exporters.siyuan import SiYuanExporter

        notebook_id = os.getenv("SIYUAN_NOTEBOOK_ID")
        if not notebook_id:
            return "⚠️ SIYUAN_NOTEBOOK_ID not set. Configure it in the .env file."

        cards = _get_jwlinker_cards(pub_code, topic_name)
        if not cards:
            return f"⚠️ No cards found for publication '{pub_code}'" + (
                f" topic '{topic_name}'" if topic_name else ""
            ) + ". Run `jwlinker extract-jwpub` on the server first."

        # Format pub code for display (s34 → S-34)
        m = re.match(r'^([a-zA-Z]+)(\d+)$', pub_code)
        display_code = f"{m.group(1).upper()}-{m.group(2)}" if m else pub_code.upper()
        root_name = f"{display_code}_CR"

        exporter = SiYuanExporter(
            notebook_id=notebook_id,
            root_name=root_name,
            language="Haitian",
            locale="CR",
        )
        exporter.add_cards(cards)
        root_id = exporter.export(replace=False)

        siyuan_url = _siyuan_doc_url(root_id)
        return (
            f"✅ *Pushed to SiYuan!*\n"
            f"• Cards: {len(cards)}\n"
            f"• View: {siyuan_url}\n\n"
            f"Tap the link to open the document tree in SiYuan."
        )

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error(f"push_to_siyuan failed: {e}")
        return f"Error pushing to SiYuan: {e}"
