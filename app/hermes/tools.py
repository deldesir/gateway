import logging
from tools.registry import registry
from app.hermes.engine import _current_urn
import app.hermes.schemas as schemas
from app.graph.tools import rapidpro, mocks, talkprep, forms, upload, system, config
import app.plugins.social.schemas as social_schemas
import app.plugins.social.tools as social

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
    registry.register("start_crm_ops", "rapidpro", schemas.START_CRM_OPS, rapidpro.start_crm_ops)
    registry.register("send_crm_help", "rapidpro", schemas.SEND_CRM_HELP, rapidpro.send_crm_help)

    # CRM Layer 2 Direct Commands (ADR-011 T2)
    registry.register("crm_list_groups", "rapidpro", schemas.CRM_LIST_GROUPS, rapidpro.crm_list_groups)
    registry.register("crm_lookup_contact", "rapidpro", schemas.CRM_LOOKUP_CONTACT, rapidpro.crm_lookup_contact)
    registry.register("crm_org_info", "rapidpro", schemas.CRM_ORG_INFO, rapidpro.crm_org_info)
    registry.register("crm_create_group", "rapidpro", schemas.CRM_CREATE_GROUP, rapidpro.crm_create_group)

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

    # System Operations (ADR-011 migration)
    registry.register("macro_reset", "system", schemas.MACRO_RESET, system.macro_reset)
    registry.register("macro_debug", "system", schemas.MACRO_DEBUG, system.macro_debug)
    registry.register("macro_noai", "system", schemas.MACRO_NOAI, system.macro_noai)
    registry.register("macro_noai_global", "system", schemas.MACRO_NOAI_GLOBAL, system.macro_noai_global)
    registry.register("macro_noai_status", "system", schemas.MACRO_NOAI_STATUS, system.macro_noai_status)
    registry.register("macro_enableai", "system", schemas.MACRO_ENABLEAI, system.macro_enableai)
    registry.register("macro_enableai_global", "system", schemas.MACRO_ENABLEAI_GLOBAL, system.macro_enableai_global)
    registry.register("macro_reload", "system", schemas.MACRO_RELOAD, system.macro_reload)
    registry.register("macro_health", "system", schemas.MACRO_HEALTH, system.macro_health)
    registry.register("macro_skills", "system", schemas.MACRO_SKILLS, system.macro_skills)
    registry.register("macro_flow", "system", schemas.MACRO_FLOW, system.macro_flow)

    # Config Operations (ADR-011 migration)
    registry.register("macro_persona", "config", schemas.MACRO_PERSONA, config.macro_persona)
    registry.register("macro_channel", "config", schemas.MACRO_CHANNEL, config.macro_channel)
    registry.register("macro_admin", "config", schemas.MACRO_ADMIN, config.macro_admin)
    registry.register("macro_global", "config", schemas.MACRO_GLOBAL, config.macro_global)
    registry.register("macro_label", "config", schemas.MACRO_LABEL, config.macro_label)

    # Social-Code Simulation Tools (ADR-014)
    registry.register("sim_update_mood", "social", social_schemas.SIM_UPDATE_MOOD, social.sim_update_mood)
    registry.register("sim_update_trust", "social", social_schemas.SIM_UPDATE_TRUST, social.sim_update_trust)
    registry.register("sim_update_dossier", "social", social_schemas.SIM_UPDATE_DOSSIER, social.sim_update_dossier)
    registry.register("sim_assess_boredom", "social", social_schemas.SIM_ASSESS_BOREDOM, social.sim_assess_boredom)
    registry.register("sim_trigger_distraction", "social", social_schemas.SIM_TRIGGER_DISTRACTION, social.sim_trigger_distraction)
    registry.register("sim_grade_response", "social", social_schemas.SIM_GRADE_RESPONSE, social.sim_grade_response)
    registry.register("sim_get_scenario", "social", social_schemas.SIM_GET_SCENARIO, social.sim_get_scenario)
    registry.register("sim_drill_grade", "social", social_schemas.SIM_DRILL_GRADE, social.sim_drill_grade)
    registry.register("sim_freetext", "social", social_schemas.SIM_FREETEXT, social.sim_freetext)
    registry.register("sim_set_language", "social", social_schemas.SIM_SET_LANGUAGE, social.sim_set_language)
    registry.register("sim_session_summary", "social", social_schemas.SIM_SESSION_SUMMARY, social.sim_session_summary)
    registry.register("sim_toggle_ai", "social", social_schemas.SIM_TOGGLE_AI, social.sim_toggle_ai)

    _registered = True
    logger.info("Registered 54 native Hermes-compatible tools globally.")

def get_hermes_tools() -> dict:
    """Return the global registry dict if anything needs to introspect it."""
    if not _registered:
        register_all_tools()
    return registry._tools
