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


# ── Helpers ─────────────────────────────────────────────────────────

def _get_talkmaster_session():
    """Open a talkmaster DB session (sync — call from thread)."""
    from talkmaster.config import get_settings
    from talkmaster.database import get_engine, get_session
    settings = get_settings()
    engine = get_engine(settings.db_path)
    return get_session(engine), engine


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
        "• `talkmaster_status` — view all imported talks\n"
        "• `cost_report` — view LLM token usage for this session\n"
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
            talk = session.query(Talk).filter_by(id=talk_id).first()
            if not talk:
                return f"Talk ID {talk_id} not found. Run `talkmaster_status`."

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
                model=os.getenv("LLM_MODEL", "openai/custom_ai"),
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
            result = generation.assemble_manuscript(
                version_name=revision_name,
                db=session,
                source="ai",
            )
            if result:
                return (
                    f"✅ *Manuscript assembled for '{revision_name}'*\n"
                    f"SiYuan doc ID: `{result}`\n\n"
                    f"Your AI-developed manuscript is ready. "
                    f"Open SiYuan to review and finalize."
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
