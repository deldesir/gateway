"""
TalkPrep LangGraph tools — exposes talkmaster capabilities to the gateway agent.

These tools allow a WhatsApp user to interact with talkmaster's talk-preparation
workflow via the AI Gateway persona engine.
"""

from langchain_core.tools import tool
from app.logger import setup_logger

logger = setup_logger().bind(name="tool.talkprep")


@tool
def list_publications(db_path: str = "") -> str:
    """List all available JW publications in the jwlinker database.

    Args:
        db_path: Optional path to jwlinker database. Leave empty for default.

    Returns:
        A formatted list of publications with codes and topic counts.
    """
    try:
        from talkmaster.bridge import list_jwlinker_publications

        pubs = list_jwlinker_publications(db_path or None)
        if not pubs:
            return "No publications found. Run 'jwlinker extract-jwpub <file>' first."
        lines = [f"- {p['code']} ({p['language']}) — {p['topic_count']} topics" for p in pubs]
        return "Available publications:\n" + "\n".join(lines)
    except Exception as e:
        logger.error(f"list_publications failed: {e}")
        return f"Error listing publications: {e}"


@tool
def list_topics(pub_code: str) -> str:
    """List all topics (talk outlines) for a given publication.

    Args:
        pub_code: Publication code (e.g., 's34', 'lmd', 'scl').

    Returns:
        A formatted list of available topics/talks.
    """
    try:
        from talkmaster.bridge import list_jwlinker_topics

        topics = list_jwlinker_topics(pub_code)
        if not topics:
            return f"No topics found for publication '{pub_code}'."
        lines = [f"- {t['name']} (category: {t['category']})" for t in topics]
        return f"Topics in '{pub_code}':\n" + "\n".join(lines)
    except Exception as e:
        logger.error(f"list_topics failed: {e}")
        return f"Error listing topics: {e}"


@tool
def import_talk(pub_code: str, topic_name: str, theme: str, language: str = "en") -> str:
    """Import a talk from jwlinker's database into talkmaster for preparation.

    Args:
        pub_code: Publication code (e.g., 's-34', 'lmd').
        topic_name: Exact or partial topic name to search for.
        theme: Theme or title for this talk.
        language: Language code (e.g., 'en', 'fr', 'cr').

    Returns:
        Confirmation with imported talk details.
    """
    try:
        from talkmaster.bridge import import_from_jwlinker, save_imported_talk

        talk = import_from_jwlinker(
            pub_code=pub_code,
            topic_name=topic_name,
            talk_theme=theme,
            language=language,
        )
        talk_id = save_imported_talk(talk)
        sections = len(talk.outline)
        points = sum(len(s.discussion_points) for s in talk.outline)
        return (
            f"✅ Talk imported successfully!\n"
            f"- Name: {talk.talk_metadata.name}\n"
            f"- Theme: {theme}\n"
            f"- Sections: {sections}\n"
            f"- Discussion points: {points}\n"
            f"- DB ID: {talk_id}"
        )
    except Exception as e:
        logger.error(f"import_talk failed: {e}")
        return f"Error importing talk: {e}"


@tool
def develop_section(revision_name: str, section_title: str) -> str:
    """Develop a single section of a talk revision using AI.

    Args:
        revision_name: Name of the active revision.
        section_title: Title of the section to develop.

    Returns:
        The developed section content or status.
    """
    try:
        from talkmaster.siyuan import generation
        from talkmaster.database import get_engine, get_session
        from talkmaster.config import get_settings

        settings = get_settings()
        engine = get_engine(settings.db_path)
        session = get_session(engine)

        try:
            result = generation.develop_section(
                version_name=revision_name,
                db=session,
                section_title=section_title,
            )
            if result:
                return f"✅ Section '{section_title}' developed successfully."
            return f"⚠️ Could not develop section '{section_title}'."
        finally:
            session.close()
            engine.dispose()
    except Exception as e:
        logger.error(f"develop_section failed: {e}")
        return f"Error developing section: {e}"


@tool
def talkmaster_status() -> str:
    """Check the current talkmaster status: active revision, sections, scores.

    Returns:
        A summary of the current talkmaster state.
    """
    try:
        from talkmaster.database import get_engine, get_session, Talk
        from talkmaster.config import get_settings

        settings = get_settings()
        engine = get_engine(settings.db_path)
        session = get_session(engine)

        try:
            talks = session.query(Talk).all()
            if not talks:
                return "No talks imported yet. Use import_talk first."
            lines = [f"- [{t.id}] {t.name} — theme: {t.theme}" for t in talks]
            return f"Imported talks ({len(talks)}):\n" + "\n".join(lines)
        finally:
            session.close()
            engine.dispose()
    except Exception as e:
        logger.error(f"talkmaster_status failed: {e}")
        return f"Error checking status: {e}"
