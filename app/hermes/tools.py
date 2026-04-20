import logging
from tools.registry import registry
from app.hermes.engine import _current_urn
import app.hermes.schemas as schemas
from app.graph.tools import rapidpro, mocks, talkprep, forms, upload

logger = logging.getLogger(__name__)

# ── MemPalace tools (new in V2) ─────────────────────────────────────────────

def search_memory(args: dict, **kw) -> str:
    """Search the user's memory palace for relevant past conversations."""
    from mempalace.mcp_server import tool_search

    query = args.get("query", "")
    wing = args.get("wing")

    urn = _current_urn.get()
    if urn:
        wing = f"wing_{urn.split(':')[-1].lstrip('+')}"

    result = tool_search(query=query, wing=wing, limit=5)
    return str(result)


def store_memory(args: dict, **kw) -> str:
    """Store a fact or note in the user's memory palace."""
    from mempalace.mcp_server import tool_add_drawer

    urn = _current_urn.get()
    wing = f"wing_{urn.split(':')[-1].lstrip('+')}" if urn else "default"

    content = args.get("content", "")
    room = args.get("room", "general")

    result = tool_add_drawer(content=content, wing=wing, room=room)
    return str(result)


def recall_memory(args: dict, **kw) -> str:
    """Get the status and overview of the memory palace."""
    from mempalace.mcp_server import tool_status
    result = tool_status()
    return str(result)


SEARCH_MEMORY_SCHEMA = {
    "name": "search_memory",
    "description": "Search the user's memory palace for relevant past conversations.",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"]
    }
}

STORE_MEMORY_SCHEMA = {
    "name": "store_memory",
    "description": "Store a fact or note in the user's memory palace.",
    "parameters": {
        "type": "object",
        "properties": {"content": {"type": "string"}, "room": {"type": "string"}},
        "required": ["content"]
    }
}

RECALL_MEMORY_SCHEMA = {
    "name": "recall_memory",
    "description": "Get the status and overview of the memory palace.",
    "parameters": {"type": "object", "properties": {}}
}

# ── SiYuan read tool handlers ───────────────────────────────────────────────

def _handle_siyuan_search(args: dict, **kw) -> str:
    """Search the SiYuan knowledge wiki."""
    import json
    from app.hooks.siyuan_tools import siyuan_search

    results = siyuan_search(
        query=args.get("query", ""),
        notebook=args.get("notebook"),
    )
    if not results:
        return json.dumps({"message": "No results found.", "results": []})
    return json.dumps({"results": results}, ensure_ascii=False)


def _handle_siyuan_read(args: dict, **kw) -> str:
    """Read a SiYuan document by block ID."""
    import json
    from app.hooks.siyuan_tools import siyuan_read_doc

    content = siyuan_read_doc(doc_id=args.get("doc_id", ""))
    if content is None:
        return json.dumps({"error": "Document not found or unreadable."})
    return json.dumps({"content": content}, ensure_ascii=False)


# ── Tool registration ───────────────────────────────────────────────────────

_registered = False

def register_all_tools() -> None:
    """Register all V2 native tools globally via hermes_agent."""
    global _registered
    if _registered:
        return

    # RapidPro Tools
    registry.register("fetch_dossier", "rapidpro", schemas.FETCH_DOSSIER, rapidpro.fetch_dossier)
    registry.register("start_flow", "rapidpro", schemas.START_FLOW, rapidpro.start_flow)

    # Mocks Tools
    registry.register("check_stock", "mocks", schemas.CHECK_STOCK, mocks.check_stock)
    registry.register("order_delivery", "mocks", schemas.ORDER_DELIVERY, mocks.order_delivery)
    registry.register("schedule_viewing", "mocks", schemas.SCHEDULE_VIEWING, mocks.schedule_viewing)

    # Forms Tools
    registry.register("submit_form", "forms", schemas.SUBMIT_FORM, forms.submit_form)

    # Upload Tools
    registry.register("upload_jwpub", "upload", schemas.UPLOAD_JWPUB, upload.upload_jwpub)

    # TalkPrep Tools
    registry.register("get_talkprep_help", "talkprep", schemas.GET_TALKPREP_HELP, talkprep.get_talkprep_help)
    registry.register("talkmaster_status", "talkprep", schemas.TALKMASTER_STATUS, talkprep.talkmaster_status)
    registry.register("select_active_talk", "talkprep", schemas.SELECT_ACTIVE_TALK, talkprep.select_active_talk)
    registry.register("list_publications", "talkprep", schemas.LIST_PUBLICATIONS, talkprep.list_publications)
    registry.register("list_topics", "talkprep", schemas.LIST_TOPICS, talkprep.list_topics)
    registry.register("import_talk", "talkprep", schemas.IMPORT_TALK, talkprep.import_talk)
    registry.register("create_revision", "talkprep", schemas.CREATE_REVISION, talkprep.create_revision)
    registry.register("develop_section", "talkprep", schemas.DEVELOP_SECTION, talkprep.develop_section)
    registry.register("evaluate_talk", "talkprep", schemas.EVALUATE_TALK, talkprep.evaluate_talk)
    registry.register("get_evaluation_scores", "talkprep", schemas.GET_EVALUATION_SCORES, talkprep.get_evaluation_scores)
    registry.register("rehearsal_cue", "talkprep", schemas.REHEARSAL_CUE, talkprep.rehearsal_cue)
    registry.register("export_talk_summary", "talkprep", schemas.EXPORT_TALK_SUMMARY, talkprep.export_talk_summary)
    registry.register("cost_report", "talkprep", schemas.COST_REPORT, talkprep.cost_report)
    registry.register("generate_anki_deck", "talkprep", schemas.GENERATE_ANKI_DECK, talkprep.generate_anki_deck)
    registry.register("push_to_siyuan", "talkprep", schemas.PUSH_TO_SIYUAN, talkprep.push_to_siyuan)

    # MemPalace Tools
    registry.register("search_memory", "mempalace", SEARCH_MEMORY_SCHEMA, search_memory)
    registry.register("store_memory", "mempalace", STORE_MEMORY_SCHEMA, store_memory)
    registry.register("recall_memory", "mempalace", RECALL_MEMORY_SCHEMA, recall_memory)

    # SiYuan Read Tools (close the write-only gap)
    registry.register("siyuan_search", "siyuan", schemas.SIYUAN_SEARCH, _handle_siyuan_search)
    registry.register("siyuan_read", "siyuan", schemas.SIYUAN_READ, _handle_siyuan_read)

    _registered = True
    logger.info("Registered 25 native Hermes-compatible tools globally.")

def get_hermes_tools() -> dict:
    """Return the global registry dict if anything needs to introspect it."""
    if not _registered:
        register_all_tools()
    return registry._tools
