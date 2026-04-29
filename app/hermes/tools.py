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


def _palace_wing() -> str:
    """Derive tenant-scoped wing name from current URN."""
    urn = _current_urn.get()
    if urn:
        return f"wing_{urn.split(':')[-1].lstrip('+')}"
    return "default"


def diary_write(args: dict, **kw) -> str:
    """Write an agent diary entry (reflection journal)."""
    from mempalace.mcp_server import tool_diary_write
    result = tool_diary_write(
        agent_name="hermes",
        entry=args.get("entry", ""),
        topic=args.get("topic", "general"),
        wing=_palace_wing(),
    )
    return str(result)


def diary_read(args: dict, **kw) -> str:
    """Read recent agent diary entries."""
    from mempalace.mcp_server import tool_diary_read
    result = tool_diary_read(
        agent_name="hermes",
        last_n=args.get("last_n", 10),
        wing=_palace_wing(),
    )
    return str(result)


def kg_query(args: dict, **kw) -> str:
    """Query knowledge graph for entity relationships."""
    from mempalace.mcp_server import tool_kg_query
    result = tool_kg_query(
        entity=args.get("entity", ""),
        as_of=args.get("as_of"),
        direction=args.get("direction", "both"),
    )
    return str(result)


def kg_add(args: dict, **kw) -> str:
    """Add a relationship triple to the knowledge graph."""
    from mempalace.mcp_server import tool_kg_add
    result = tool_kg_add(
        subject=args.get("subject", ""),
        predicate=args.get("predicate", ""),
        object=args.get("object", ""),
        source_closet=args.get("source", "hermes"),
    )
    return str(result)


def kg_invalidate(args: dict, **kw) -> str:
    """Mark a knowledge graph fact as outdated/incorrect."""
    from mempalace.mcp_server import tool_kg_invalidate
    result = tool_kg_invalidate(
        subject=args.get("subject", ""),
        predicate=args.get("predicate", ""),
        object=args.get("object", ""),
    )
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

DIARY_WRITE_SCHEMA = {
    "name": "diary_write",
    "description": (
        "Write an agent diary entry — your reflection journal. Use after sessions to record "
        "what happened, what you learned, and what matters. Entries are scoped to the current user."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "entry": {"type": "string", "description": "The diary entry content."},
            "topic": {"type": "string", "description": "Topic tag (e.g. 'crm', 'talkprep', 'general')."},
        },
        "required": ["entry"]
    }
}

DIARY_READ_SCHEMA = {
    "name": "diary_read",
    "description": "Read recent diary entries to recall what you've been working on and reflecting about.",
    "parameters": {
        "type": "object",
        "properties": {
            "last_n": {"type": "integer", "description": "Number of recent entries to return (default 10)."},
        },
    }
}

KG_QUERY_SCHEMA = {
    "name": "kg_query",
    "description": (
        "Query the knowledge graph for relationships about an entity. Returns triples like "
        "'Marie works-with Jean' or 'Project-X uses Python'. Use for relationship questions "
        "that SiYuan page attributes can't answer."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "entity": {"type": "string", "description": "The entity name to query."},
            "direction": {"type": "string", "enum": ["both", "outgoing", "incoming"], "description": "Relationship direction."},
        },
        "required": ["entity"]
    }
}

KG_ADD_SCHEMA = {
    "name": "kg_add",
    "description": (
        "Add a relationship triple to the knowledge graph. Format: subject-predicate-object. "
        "Example: kg_add(subject='Marie', predicate='works-with', object='Jean'). "
        "Use for relationships between entities. For entity properties, use SiYuan attrs instead."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "predicate": {"type": "string", "description": "Relationship verb (e.g. 'works-with', 'lives-in', 'manages')."},
            "object": {"type": "string"},
        },
        "required": ["subject", "predicate", "object"]
    }
}

KG_INVALIDATE_SCHEMA = {
    "name": "kg_invalidate",
    "description": "Mark a knowledge graph triple as outdated or incorrect. The fact remains in history but is no longer active.",
    "parameters": {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "predicate": {"type": "string"},
            "object": {"type": "string"},
        },
        "required": ["subject", "predicate", "object"]
    }
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


def _handle_siyuan_list_docs(args: dict, **kw) -> str:
    """List documents in a SiYuan notebook path."""
    import json
    from app.hooks.siyuan_tools import siyuan_list_docs
    results = siyuan_list_docs(
        notebook=args.get("notebook", ""),
        path=args.get("path", "/"),
    )
    return json.dumps({"documents": results}, ensure_ascii=False)


def _handle_siyuan_create_notebook(args: dict, **kw) -> str:
    """Create a new SiYuan notebook."""
    import json
    from app.hooks.siyuan_tools import siyuan_create_notebook
    nb_id = siyuan_create_notebook(name=args.get("name", ""))
    if nb_id:
        return json.dumps({"notebook_id": nb_id})
    return json.dumps({"error": "Failed to create notebook."})


def _handle_siyuan_create_doc(args: dict, **kw) -> str:
    """Create a new document in a SiYuan notebook."""
    import json
    from app.hooks.siyuan_tools import siyuan_create_doc, siyuan_doc_url
    doc_id = siyuan_create_doc(
        notebook=args.get("notebook", ""),
        path=args.get("path", ""),
        markdown=args.get("markdown", ""),
    )
    if doc_id:
        return json.dumps({"doc_id": doc_id, "url": siyuan_doc_url(doc_id)})
    return json.dumps({"error": "Failed to create document."})


def _handle_siyuan_update_block(args: dict, **kw) -> str:
    """Update a block's content."""
    import json
    from app.hooks.siyuan_tools import siyuan_update_block
    ok = siyuan_update_block(
        block_id=args.get("block_id", ""),
        markdown=args.get("markdown", ""),
    )
    return json.dumps({"success": ok})


def _handle_siyuan_append_block(args: dict, **kw) -> str:
    """Append content to a SiYuan page."""
    import json
    from app.hooks.siyuan_tools import siyuan_append_block, siyuan_doc_url
    block_id = siyuan_append_block(
        notebook=args.get("notebook", ""),
        path=args.get("path", ""),
        markdown=args.get("markdown", ""),
    )
    if block_id:
        return json.dumps({"block_id": block_id, "url": siyuan_doc_url(block_id)})
    return json.dumps({"error": "Failed to append block."})


def _handle_siyuan_set_attrs(args: dict, **kw) -> str:
    """Set custom attributes on a block."""
    import json
    from app.hooks.siyuan_tools import siyuan_set_attrs
    ok = siyuan_set_attrs(
        block_id=args.get("block_id", ""),
        attrs=args.get("attrs", {}),
    )
    return json.dumps({"success": ok})


def _handle_siyuan_get_attrs(args: dict, **kw) -> str:
    """Get attributes of a block."""
    import json
    from app.hooks.siyuan_tools import siyuan_get_attrs
    attrs = siyuan_get_attrs(block_id=args.get("block_id", ""))
    return json.dumps({"attrs": attrs}, ensure_ascii=False)


def _handle_siyuan_sql_query(args: dict, **kw) -> str:
    """Execute a read-only SQL query."""
    import json
    from app.hooks.siyuan_tools import siyuan_sql_query
    results = siyuan_sql_query(sql=args.get("sql", ""))
    return json.dumps({"results": results}, ensure_ascii=False)


def _handle_siyuan_delete_block(args: dict, **kw) -> str:
    """Delete a block."""
    import json
    from app.hooks.siyuan_tools import siyuan_delete_block
    ok = siyuan_delete_block(block_id=args.get("block_id", ""))
    return json.dumps({"success": ok})


def _handle_siyuan_rename_doc(args: dict, **kw) -> str:
    """Rename a document."""
    import json
    from app.hooks.siyuan_tools import siyuan_rename_doc
    ok = siyuan_rename_doc(
        doc_id=args.get("doc_id", ""),
        title=args.get("title", ""),
    )
    return json.dumps({"success": ok})


def _handle_siyuan_init_wiki(args: dict, **kw) -> str:
    """Bootstrap a new LLM Wiki in SiYuan."""
    import json
    from app.hooks.siyuan_tools import siyuan_init_wiki, siyuan_doc_url
    result = siyuan_init_wiki(
        name=args.get("name", "Wiki"),
        domain=args.get("domain", "General knowledge"),
        tags=args.get("tags", ""),
    )
    # Inject clickable URLs for each created document
    for key in ("schema_id", "index_id", "log_id"):
        if result.get(key):
            result[f"{key.replace('_id', '_url')}"] = siyuan_doc_url(result[key])
    if result.get("directories"):
        result["directory_urls"] = {
            path: siyuan_doc_url(doc_id)
            for path, doc_id in result["directories"].items()
            if doc_id
        }
    return json.dumps(result, ensure_ascii=False)


def _handle_siyuan_get_backlinks(args: dict, **kw) -> str:
    """Get backlinks (inbound references) for a document."""
    import json
    from app.hooks.siyuan_tools import siyuan_get_backlinks
    results = siyuan_get_backlinks(doc_id=args.get("doc_id", ""))
    return json.dumps({"backlinks": results, "count": len(results)}, ensure_ascii=False)


def _handle_siyuan_get_children(args: dict, **kw) -> str:
    """Get child blocks of a block."""
    import json
    from app.hooks.siyuan_tools import siyuan_get_children
    children = siyuan_get_children(block_id=args.get("block_id", ""))
    return json.dumps({"children": children}, ensure_ascii=False)


def _handle_siyuan_get_hpath(args: dict, **kw) -> str:
    """Resolve block ID to human-readable path."""
    import json
    from app.hooks.siyuan_tools import siyuan_get_hpath, siyuan_doc_url
    block_id = args.get("block_id", "")
    hpath = siyuan_get_hpath(block_id=block_id)
    if hpath:
        return json.dumps({"hpath": hpath, "url": siyuan_doc_url(block_id)})
    return json.dumps({"error": "Block not found."})


def _handle_siyuan_remove_doc(args: dict, **kw) -> str:
    """Delete a document permanently."""
    import json
    from app.hooks.siyuan_tools import siyuan_remove_doc
    ok = siyuan_remove_doc(doc_id=args.get("doc_id", ""))
    return json.dumps({"success": ok})


def _handle_siyuan_upsert_page(args: dict, **kw) -> str:
    """Create or update a wiki page by path."""
    import json
    from app.hooks.siyuan_tools import siyuan_upsert_page, siyuan_doc_url
    page_id = siyuan_upsert_page(
        notebook=args.get("notebook", ""),
        path=args.get("path", ""),
        markdown=args.get("markdown", ""),
    )
    if page_id:
        return json.dumps({
            "page_id": page_id,
            "url": siyuan_doc_url(page_id),
            "message": f"Page upserted at {args.get('path', '')}",
        })
    return json.dumps({"error": "Failed to upsert page."})


def _handle_siyuan_lint(args: dict, **kw) -> str:
    """Run wiki quality rules and return a structured report."""
    import json
    from app.hooks.siyuan_tools import siyuan_lint
    report = siyuan_lint(notebook=args.get("notebook", ""))
    return json.dumps(report, ensure_ascii=False)


def _handle_crm_lookup_enriched(args: dict, **kw) -> str:
    """Layer 2 contact lookup enriched with SiYuan person page data.

    After RapidPro returns contact basics, searches the SiYuan wiki for a
    matching /people/ page. If no page exists and admin is looking up the
    contact, auto-creates a stub person page.
    """
    import json
    from app.graph.tools.rapidpro import crm_lookup_contact
    from app.hooks.siyuan_tools import (
        siyuan_search, siyuan_read_doc, siyuan_upsert_page,
        siyuan_set_attrs, siyuan_doc_url,
    )

    # Step 1: Standard RapidPro lookup
    rp_result = crm_lookup_contact(args, **kw)

    # Step 2: Try to find a matching SiYuan person page
    phone = args.get("phone", "").strip().lstrip("+").lstrip("0")
    if not phone:
        return rp_result

    # Try to parse contact name from RapidPro result
    contact_name = ""
    try:
        # RapidPro lookup returns formatted text, try to extract name
        if "👤 *" in rp_result:
            contact_name = rp_result.split("👤 *")[1].split("*")[0].strip()
    except (IndexError, AttributeError):
        pass

    # Step 2: SiYuan enrichment (best-effort — fails gracefully if SiYuan is down)
    try:
        wiki_info = ""
        search_query = contact_name if contact_name and contact_name != "_(no name)_" else phone
        if search_query:
            results = siyuan_search(search_query, limit=3)
            person_page = None
            for r in results:
                hpath = r.get("hpath", "")
                if "/people/" in hpath:
                    person_page = r
                    break

            if person_page:
                doc_id = person_page.get("id", "")
                page_content = siyuan_read_doc(doc_id)
                page_url = siyuan_doc_url(doc_id)
                wiki_info = (
                    f"\n\n📓 *Wiki Page:*\n"
                    f"{page_url}\n"
                    f"{page_content[:300] if page_content else '(empty)'}"
                )
            elif contact_name and contact_name != "_(no name)_":
                # Auto-create a stub person page
                from datetime import date
                today = date.today().isoformat()
                slug = contact_name.lower().replace(" ", "-")
                stub_md = (
                    f"# {contact_name}\n\n"
                    f"📱 whatsapp:{phone}\n\n"
                    f"*Auto-created from CRM lookup on {today}.*\n"
                )
                # Try to create in the first wiki notebook that has /people/
                page_id = siyuan_upsert_page("Life", f"/people/{slug}", stub_md)
                if not page_id:
                    for nb_name in ("Wiki", "IIAB", "PersonalCRM"):
                        page_id = siyuan_upsert_page(nb_name, f"/people/{slug}", stub_md)
                        if page_id:
                            break

                if page_id:
                    siyuan_set_attrs(page_id, {
                        "type": "person",
                        "tags": "auto-created",
                        "last-contact": today,
                        "created": today,
                        "updated": today,
                    })
                    wiki_info = (
                        f"\n\n📓 *Wiki Page Created:*\n"
                        f"{siyuan_doc_url(page_id)}\n"
                        f"_(auto-created stub — add birthday, notes, circle)_"
                    )

        return rp_result + wiki_info
    except Exception:
        # SiYuan unreachable or error — return unenriched result
        logger.debug("SiYuan enrichment skipped (service unavailable or error)")
        return rp_result


def _handle_siyuan_dashboard(args: dict, **kw) -> str:
    """Generate an on-demand dashboard from SiYuan wiki data."""
    import json
    from app.hooks.siyuan_tools import siyuan_dashboard
    result = siyuan_dashboard(
        dashboard_type=args.get("dashboard_type", ""),
        notebook=args.get("notebook", "Life"),
    )
    # Return the formatted dashboard text directly if available
    if "dashboard" in result:
        return result["dashboard"]
    return json.dumps(result, ensure_ascii=False)


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
    registry.register("crm_lookup_contact", "rapidpro", schemas.CRM_LOOKUP_CONTACT, _handle_crm_lookup_enriched)
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
    registry.register("diary_write", "mempalace", DIARY_WRITE_SCHEMA, diary_write)
    registry.register("diary_read", "mempalace", DIARY_READ_SCHEMA, diary_read)
    registry.register("kg_query", "mempalace", KG_QUERY_SCHEMA, kg_query)
    registry.register("kg_add", "mempalace", KG_ADD_SCHEMA, kg_add)
    registry.register("kg_invalidate", "mempalace", KG_INVALIDATE_SCHEMA, kg_invalidate)

    # SiYuan Read Tools (close the write-only gap)
    registry.register("siyuan_search", "siyuan", schemas.SIYUAN_SEARCH, _handle_siyuan_search)
    registry.register("siyuan_read", "siyuan", schemas.SIYUAN_READ, _handle_siyuan_read)

    # SiYuan Wiki Tools (LLM Wiki pattern — Karpathy's compounding KB)
    registry.register("siyuan_list_docs", "siyuan", schemas.SIYUAN_LIST_DOCS, _handle_siyuan_list_docs)
    registry.register("siyuan_create_notebook", "siyuan", schemas.SIYUAN_CREATE_NOTEBOOK, _handle_siyuan_create_notebook)
    registry.register("siyuan_create_doc", "siyuan", schemas.SIYUAN_CREATE_DOC, _handle_siyuan_create_doc)
    registry.register("siyuan_update_block", "siyuan", schemas.SIYUAN_UPDATE_BLOCK, _handle_siyuan_update_block)
    registry.register("siyuan_append_block", "siyuan", schemas.SIYUAN_APPEND_BLOCK, _handle_siyuan_append_block)
    registry.register("siyuan_set_attrs", "siyuan", schemas.SIYUAN_SET_ATTRS, _handle_siyuan_set_attrs)
    registry.register("siyuan_get_attrs", "siyuan", schemas.SIYUAN_GET_ATTRS, _handle_siyuan_get_attrs)
    registry.register("siyuan_sql_query", "siyuan", schemas.SIYUAN_SQL_QUERY, _handle_siyuan_sql_query)
    registry.register("siyuan_delete_block", "siyuan", schemas.SIYUAN_DELETE_BLOCK, _handle_siyuan_delete_block)
    registry.register("siyuan_rename_doc", "siyuan", schemas.SIYUAN_RENAME_DOC, _handle_siyuan_rename_doc)
    registry.register("siyuan_init_wiki", "siyuan", schemas.SIYUAN_INIT_WIKI, _handle_siyuan_init_wiki)

    # SiYuan Wiki Navigation & Maintenance (gap-closing)
    registry.register("siyuan_get_backlinks", "siyuan", schemas.SIYUAN_GET_BACKLINKS, _handle_siyuan_get_backlinks)
    registry.register("siyuan_get_children", "siyuan", schemas.SIYUAN_GET_CHILDREN, _handle_siyuan_get_children)
    registry.register("siyuan_get_hpath", "siyuan", schemas.SIYUAN_GET_HPATH, _handle_siyuan_get_hpath)
    registry.register("siyuan_remove_doc", "siyuan", schemas.SIYUAN_REMOVE_DOC, _handle_siyuan_remove_doc)
    registry.register("siyuan_upsert_page", "siyuan", schemas.SIYUAN_UPSERT_PAGE, _handle_siyuan_upsert_page)
    registry.register("siyuan_lint", "siyuan", schemas.SIYUAN_LINT, _handle_siyuan_lint)
    registry.register("siyuan_dashboard", "siyuan", schemas.SIYUAN_DASHBOARD, _handle_siyuan_dashboard)

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
    logger.info("Registered 77 native Hermes-compatible tools globally.")

def get_hermes_tools() -> dict:
    """Return the global registry dict if anything needs to introspect it."""
    if not _registered:
        register_all_tools()
    return registry._tools
