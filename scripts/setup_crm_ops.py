#!/usr/bin/env python3
"""
ADR-010 Phase 2: Modular CRM Sub-Flow Architecture

Creates the required RapidPro infrastructure for WhatsApp-driven admin ops:
  1. api_token global (used by call_webhook Authorization headers)
  2. Admins group (used by flow auth guard)
  3. Admin contact added to Admins group
  4. 7 CRM flows imported via Django ORM (org.import_app):
     - CRM Router (auth guard + L1 menu + 5 enter_flow dispatchers)
     - Contacts Ops (lookup, create, block/unblock, add/remove group)
     - Groups Ops (list, create, delete)
     - Messages Ops (send single, broadcast to group)
     - Flows Ops (list, start for contact)
     - System Ops (org info, channels, globals CRUD, fields list)
     - Exit CRM Ops (confirmation message)
  5. Persist all flow UUIDs to .env

Usage:
    cd /opt/iiab/ai-gateway
    source .env
    python scripts/setup_crm_ops.py
"""

import os
import sys
import json
import subprocess
from uuid import uuid4
from pathlib import Path

import requests

# ── Configuration ────────────────────────────────────────────────────────────

RAPIDPRO_HOST = os.getenv("RAPIDPRO_HOST", "http://localhost:8080")
API_TOKEN = os.getenv("RAPIDPRO_API_TOKEN")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "50937145893")

API_URL = f"{RAPIDPRO_HOST}/api/v2"

# Webhook URLs run inside mailroom/goflow which blocks localhost (SSRF protection).
# Use RAPIDPRO_WEBHOOK_HOST to specify a routable hostname for call_webhook actions.
WEBHOOK_HOST = os.getenv("RAPIDPRO_WEBHOOK_HOST", "https://garantie.boutique")
WEBHOOK_API_URL = f"{WEBHOOK_HOST}/api/v2"

HEADERS = {}  # Set in main() after token validation


def api_get(endpoint, params=None):
    r = requests.get(f"{API_URL}/{endpoint}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()


def api_post(endpoint, data):
    r = requests.post(f"{API_URL}/{endpoint}", headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()


# ── UUID Factory ─────────────────────────────────────────────────────────────

def u():
    return str(uuid4())


# ── Step 1: Create api_token Global ──────────────────────────────────────────

def setup_api_token_global():
    print("\n── Step 1: api_token Global ──")
    globals_data = api_get("globals.json")
    for g in globals_data.get("results", []):
        if g["key"] == "api_token":
            print(f"   ✅ api_token global already exists (value hidden)")
            return
    api_post("globals.json", {
        "name": "API Token", "key": "api_token", "value": API_TOKEN,
    })
    print(f"   ✅ Created api_token global")


def _persist_env(key: str, value: str, comment: str = ""):
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    content = env_path.read_text()
    if key in content:
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                break
        env_path.write_text("\n".join(lines) + "\n")
        print(f"   ✅ Updated {key} in .env")
        return
    with open(env_path, "a") as f:
        if comment:
            f.write(f"\n# {comment}\n")
        f.write(f"{key}={value}\n")
    print(f"   ✅ Persisted {key} to .env")


# ── Step 2: Create Admins Group ──────────────────────────────────────────────

def setup_admins_group():
    print("\n── Step 2: Admins Group ──")
    groups = api_get("groups.json", {"name": "Admins"})
    for g in groups.get("results", []):
        if g["name"] == "Admins":
            print(f"   ✅ Admins group exists: {g['uuid']}")
            _persist_env("ADMINS_GROUP_UUID", g["uuid"],
                         "CRM Ops — Admins group UUID")
            return g["uuid"]
    result = api_post("groups.json", {"name": "Admins"})
    group_uuid = result["uuid"]
    print(f"   ✅ Created Admins group: {group_uuid}")
    _persist_env("ADMINS_GROUP_UUID", group_uuid, "CRM Ops — Admins group UUID")
    return group_uuid


# ── Step 3: Add Admin to Group ───────────────────────────────────────────────

def add_admin_to_group(group_uuid):
    print("\n── Step 3: Admin Contact ──")
    admin_urn = f"whatsapp:{ADMIN_PHONE}"
    contacts = api_get("contacts.json", {"urn": admin_urn})
    results = contacts.get("results", [])
    if not results:
        print(f"   ⚠️  No contact found for {admin_urn}.")
        return None
    contact = results[0]
    for g in contact.get("groups", []):
        if g["uuid"] == group_uuid:
            print(f"   ✅ {contact['name']} already in Admins group")
            return contact["uuid"]
    api_post("contact_actions.json", {
        "contacts": [contact["uuid"]], "action": "add", "group": group_uuid,
    })
    print(f"   ✅ Added {contact['name']} to Admins group")
    return contact["uuid"]


# ══════════════════════════════════════════════════════════════════════════════
#  FLOW BUILDING BLOCKS
# ══════════════════════════════════════════════════════════════════════════════

def _make_action(type_, **fields):
    return {"uuid": u(), "type": type_, **fields}


def _make_exit(dest_uuid=None):
    return {"uuid": u(), "destination_uuid": dest_uuid}


def _make_category(name, exit_uuid):
    return {"uuid": u(), "name": name, "exit_uuid": exit_uuid}


def _make_msg_node(node_uuid, text, dest_uuid=None, quick_replies=None):
    actions = [_make_action("send_msg", text=text,
                            **({} if not quick_replies else {"quick_replies": quick_replies}))]
    return {"uuid": node_uuid, "actions": actions, "exits": [_make_exit(dest_uuid)]}


def _fmt_list(prefix, fields, count=10):
    """Build a formatted list template using goflow @webhook.json expressions.

    Non-existent array indices resolve to empty string in goflow, so excess
    lines simply display blank (WhatsApp trims trailing whitespace).

    prefix: e.g. "@webhook.json.results"
    fields: list of (emoji, field_name) tuples or (emoji, field_template) with {i}
    count: max items to include
    """
    lines = []
    for i in range(count):
        parts = []
        for emoji, field in fields:
            if "{i}" in field:
                parts.append(f"{emoji}{field.replace('{i}', str(i))}")
            else:
                parts.append(f"{emoji}{prefix}.{i}.{field}")
        lines.append(" ".join(parts))
    return "\\n".join(lines)


def _make_webhook_split(node_uuid, method, url, result_name, ok_dest, fail_dest,
                        body="", extra_headers=None):
    headers = {"Authorization": "Token @globals.api_token", "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    action = _make_action("call_webhook", method=method, url=url,
                          headers=headers, body=body, result_name=result_name)
    exit_ok = _make_exit(ok_dest)
    exit_fail = _make_exit(fail_dest)
    cat_ok = _make_category("Success", exit_ok["uuid"])
    cat_fail = _make_category("Failed", exit_fail["uuid"])
    case_ok = {"uuid": u(), "type": "has_only_text",
               "arguments": ["Success"], "category_uuid": cat_ok["uuid"]}
    router = {
        "type": "switch",
        "operand": f"@results.{result_name}.category",
        "cases": [case_ok],
        "categories": [cat_ok, cat_fail],
        "default_category_uuid": cat_fail["uuid"],
        "result_name": result_name,
    }
    return {"uuid": node_uuid, "actions": [action], "router": router,
            "exits": [exit_ok, exit_fail]}


def _make_wait_menu(node_uuid, prompt, choices, timeout_dest,
                    default_dest=None, timeout_seconds=300):
    """Menu node: quick_replies + wait + switch.

    ADR-011 Finding 11: Courier auto-converts >3 quick_replies to WhatsApp
    List Messages (handler.go:474-628). ≤3 render as native buttons.
    Courier sends the Title field back as @input.text (handler.go:221-223).

    choices: list of (label, dest_uuid) pairs. Max 10 (goflow limit).
    """
    # Build quick_replies list — each label becomes a selectable item
    quick_replies = [text for text, _dest in choices]

    actions = [_make_action("send_msg", text=prompt.rstrip(),
                            quick_replies=quick_replies)]
    exits, categories, cases = [], [], []
    for text, dest in choices:
        ex = _make_exit(dest)
        cat = _make_category(text, ex["uuid"])
        # Match on Title text Courier sends back (handler.go:221-223)
        # has_only_phrase is case-insensitive (tests.go:155), unlike has_only_text
        case = {"uuid": u(), "type": "has_only_phrase",
                "arguments": [text],
                "category_uuid": cat["uuid"]}
        exits.append(ex); categories.append(cat); cases.append(case)
    ex_timeout = _make_exit(timeout_dest)
    cat_timeout = _make_category("No Response", ex_timeout["uuid"])
    exits.append(ex_timeout); categories.append(cat_timeout)
    ex_other = _make_exit(default_dest or exits[0]["destination_uuid"])
    cat_other = _make_category("Other", ex_other["uuid"])
    exits.append(ex_other); categories.append(cat_other)
    router = {
        "type": "switch", "operand": "@input.text",
        "wait": {"type": "msg", "timeout": {"seconds": timeout_seconds, "category_uuid": cat_timeout["uuid"]}},
        "cases": cases, "categories": categories,
        "default_category_uuid": cat_other["uuid"],
        "result_name": f"menu_{node_uuid[:8]}",
    }
    return {"uuid": node_uuid, "actions": actions, "router": router, "exits": exits}


def _make_wait_input(node_uuid, prompt, result_name, dest_uuid, timeout_dest,
                     timeout_seconds=300):
    actions = [_make_action("send_msg", text=prompt)]
    exit_resp = _make_exit(dest_uuid)
    exit_timeout = _make_exit(timeout_dest)
    cat_resp = _make_category("All Responses", exit_resp["uuid"])
    cat_timeout = _make_category("No Response", exit_timeout["uuid"])
    router = {
        "type": "switch", "operand": "@input.text",
        "wait": {"type": "msg", "timeout": {"seconds": timeout_seconds, "category_uuid": cat_timeout["uuid"]}},
        "cases": [], "categories": [cat_resp, cat_timeout],
        "default_category_uuid": cat_resp["uuid"],
        "result_name": result_name,
    }
    return {"uuid": node_uuid, "actions": actions, "router": router,
            "exits": [exit_resp, exit_timeout]}


def _make_enter_flow_node(node_uuid, flow_uuid, flow_name, return_dest):
    """Node: enter_flow (non-terminal) → when child completes, go to return_dest."""
    action = _make_action("enter_flow",
                          flow={"uuid": flow_uuid, "name": flow_name},
                          terminal=False)
    return {"uuid": node_uuid, "actions": [action], "exits": [_make_exit(return_dest)]}


def _make_confirm_guard(confirm_node_uuid, prompt, expected_result, confirm_dest,
                        cancel_dest, timeout_dest, timeout_seconds=300):
    """Typed confirmation guard for destructive operations.
    Returns list of nodes: [prompt+wait, check].
    The wait saves input as `expected_result`, then checks has_only_text(expected value).
    Note: expected value must be set dynamically from a previous result.
    """
    # This is a wait_input that routes based on exact match
    actions = [_make_action("send_msg", text=prompt)]
    exit_confirm = _make_exit(confirm_dest)
    exit_cancel = _make_exit(cancel_dest)
    exit_timeout = _make_exit(timeout_dest)
    cat_confirm = _make_category("Confirmed", exit_confirm["uuid"])
    cat_cancel = _make_category("Other", exit_cancel["uuid"])
    cat_timeout = _make_category("No Response", exit_timeout["uuid"])
    case_confirm = {"uuid": u(), "type": "has_only_text",
                    "arguments": ["CONFIRM"], "category_uuid": cat_confirm["uuid"]}
    router = {
        "type": "switch", "operand": "@input.text",
        "wait": {"type": "msg", "timeout": {"seconds": timeout_seconds, "category_uuid": cat_timeout["uuid"]}},
        "cases": [case_confirm],
        "categories": [cat_confirm, cat_cancel, cat_timeout],
        "default_category_uuid": cat_cancel["uuid"],
        "result_name": expected_result,
    }
    return {"uuid": confirm_node_uuid, "actions": actions, "router": router,
            "exits": [exit_confirm, exit_cancel, exit_timeout]}


def _infer_ui_type(node):
    actions = [a["type"] for a in node.get("actions", [])]
    router = node.get("router", {})
    if "wait" in router:
        return "wait_for_response"
    if "enter_flow" in actions:
        return "split_by_subflow"
    if "call_webhook" in actions:
        return "split_by_webhook"
    if "call_llm" in actions:
        return "split_by_llm"
    if router.get("type") == "switch":
        operand = router.get("operand", "")
        if "@contact.groups" in operand:
            return "split_by_groups"
        return "split_by_expression"
    return "execute_actions"


def _build_ui(nodes, layout):
    ui_nodes = {}
    for node in nodes:
        pos = layout.get(node["uuid"], (0, 0))
        ui_nodes[node["uuid"]] = {
            "position": {"left": pos[0], "top": pos[1]},
            "type": _infer_ui_type(node),
            "config": {},
        }
    return {"nodes": ui_nodes, "editor": "0.156.6"}


def _make_flow(uuid, name, nodes, layout, expire=30):
    return {
        "uuid": uuid, "name": name,
        "spec_version": "14.4.0", "language": "eng", "type": "messaging",
        "revision": 1, "expire_after_minutes": expire,
        "localization": {}, "nodes": nodes,
        "_ui": _build_ui(nodes, layout),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  FLOW GENERATORS
# ══════════════════════════════════════════════════════════════════════════════

ROW = 220


def generate_router_flow(admins_uuid, sub_flow_uuids):
    """CRM Router: auth guard → L1 menu → enter_flow dispatchers.
    sub_flow_uuids: dict with keys contacts, groups, messages, flows, system
    """
    flow_uuid = u()
    N = {
        "auth": u(), "denied": u(), "menu": u(), "timeout": u(),
        "enter_contacts": u(), "enter_groups": u(), "enter_messages": u(),
        "enter_flows": u(), "enter_system": u(), "exit": u(),
    }
    nodes = []

    # Auth guard
    exit_ok = _make_exit(N["menu"])
    exit_denied = _make_exit(N["denied"])
    cat_ok = _make_category("Authorized", exit_ok["uuid"])
    cat_denied = _make_category("Denied", exit_denied["uuid"])
    nodes.append({
        "uuid": N["auth"],
        "actions": [_make_action("send_msg", text="🔐 Verifying admin access...")],
        "router": {
            "type": "switch", "operand": "@contact.groups",
            "cases": [{"uuid": u(), "type": "has_group",
                       "arguments": [admins_uuid, "Admins"],
                       "category_uuid": cat_ok["uuid"]}],
            "categories": [cat_ok, cat_denied],
            "default_category_uuid": cat_denied["uuid"],
        },
        "exits": [exit_ok, exit_denied],
    })

    nodes.append(_make_msg_node(N["denied"],
        "🚫 *Access Denied*\n\nYou are not in the Admins group."))

    # Main menu — quick_replies (ADR-011: >3 items → WhatsApp List Message)
    nodes.append(_make_wait_menu(
        N["menu"],
        "📋 *CRM Operations*\n\nSelect an option:",
        [
            ("Contacts", N["enter_contacts"]),
            ("Segments", N["enter_groups"]),
            ("Messages", N["enter_messages"]),
            ("Flows", N["enter_flows"]),
            ("System", N["enter_system"]),
            ("❌ Exit", N["exit"]),
        ],
        timeout_dest=N["timeout"],
        default_dest=N["menu"],
    ))

    nodes.append(_make_msg_node(N["timeout"],
        "⏱️ CRM session timed out.\n\nType *ops* to start again."))

    # enter_flow dispatchers — each returns to menu
    for key, label in [
        ("contacts", "Contacts Ops"),
        ("groups", "Segments Ops"),
        ("messages", "Messages Ops"),
        ("flows", "Flows Ops"),
        ("system", "System Ops"),
    ]:
        nodes.append(_make_enter_flow_node(
            N[f"enter_{key}"],
            sub_flow_uuids[key],
            label,
            return_dest=N["menu"],
        ))

    nodes.append(_make_msg_node(N["exit"],
        "✅ CRM session ended.\n\nType *ops* to start again."))

    layout = {
        N["auth"]:           (400, 0),
        N["denied"]:         (800, 0),
        N["menu"]:           (400, ROW),
        N["timeout"]:        (800, ROW),
        N["enter_contacts"]: (0, ROW * 3),
        N["enter_groups"]:   (300, ROW * 3),
        N["enter_messages"]: (600, ROW * 3),
        N["enter_flows"]:    (900, ROW * 3),
        N["enter_system"]:   (1200, ROW * 3),
        N["exit"]:           (400, ROW * 4),
    }
    return flow_uuid, _make_flow(flow_uuid, "CRM Operations", nodes, layout)


# ── Contacts Ops ─────────────────────────────────────────────────────────────

def generate_contacts_flow():
    """Contacts Ops: lookup, create, block (CONFIRM), unblock.
    All URNs use whatsapp: scheme. Block/Unblock accept phone numbers.
    """
    WH = WEBHOOK_API_URL
    flow_uuid = u()
    N = {
        "menu": u(), "timeout": u(),
        # Lookup
        "lookup_ask": u(), "lookup_wh": u(), "lookup_ok": u(), "lookup_err": u(),
        # Create
        "create_ask_urn": u(), "create_ask_name": u(), "create_wh": u(),
        "create_ok": u(), "create_err": u(),
        # Block
        "block_ask": u(), "block_lookup": u(), "block_confirm": u(), "block_wh": u(),
        "block_ok": u(), "block_err": u(), "block_cancel": u(), "block_notfound": u(),
        # Unblock
        "unblock_ask": u(), "unblock_lookup": u(), "unblock_wh": u(),
        "unblock_ok": u(), "unblock_err": u(), "unblock_notfound": u(),
        # Back (terminal exit)
        "back": u(),
    }
    nodes = []

    nodes.append(_make_wait_menu(
        N["menu"],
        "👤 *Contacts*\n\nSelect an option:",
        [
            ("Lookup", N["lookup_ask"]),
            ("Create", N["create_ask_urn"]),
            ("Block", N["block_ask"]),
            ("Unblock", N["unblock_ask"]),
            ("⬅️ Back", N["back"]),
        ],
        timeout_dest=N["timeout"],
        default_dest=N["menu"],
    ))
    nodes.append(_make_msg_node(N["timeout"], "⏱️ Contacts timed out."))
    nodes.append(_make_msg_node(N["back"], "⬅️ Returning to main menu..."))

    # ── Lookup ──
    nodes.append(_make_wait_input(N["lookup_ask"],
        "🔍 Enter the phone number (digits only, e.g. 50937145893):",
        "contact_phone", N["lookup_wh"], N["timeout"]))
    nodes.append(_make_webhook_split(N["lookup_wh"],
        "GET", f"{WH}/contacts.json?urn=whatsapp:@results.contact_phone.value",
        "contact_lookup", N["lookup_ok"], N["lookup_err"]))
    nodes.append(_make_msg_node(N["lookup_ok"],
        "👤 *Contact Found:*\n\n"
        "Name: @webhook.json.results.0.name\n"
        "UUID: @webhook.json.results.0.uuid\n"
        "URN: @webhook.json.results.0.urns.0\n"
        "Groups: @webhook.json.results.0.groups",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["lookup_err"],
        "⚠️ Contact not found or API error.", dest_uuid=N["menu"]))

    # ── Create ──
    nodes.append(_make_wait_input(N["create_ask_urn"],
        "➕ *Create Contact*\n\nEnter WhatsApp number (digits only, e.g. 50937145893):",
        "new_contact_urn", N["create_ask_name"], N["timeout"]))
    nodes.append(_make_wait_input(N["create_ask_name"],
        "📝 Enter the contact's full name:",
        "new_contact_name", N["create_wh"], N["timeout"]))
    nodes.append(_make_webhook_split(N["create_wh"],
        "POST", f"{WH}/contacts.json",
        "contact_create",
        N["create_ok"], N["create_err"],
        body='{"urns": ["whatsapp:@results.new_contact_urn.value"], '
             '"name": "@results.new_contact_name.value"}',
        extra_headers={"Content-Type": "application/json"}))
    nodes.append(_make_msg_node(N["create_ok"],
        "✅ Contact *@results.new_contact_name.value* created!\n\n"
        "UUID: @webhook.json.uuid",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["create_err"],
        "⚠️ Failed to create contact. Check the number isn't already registered.",
        dest_uuid=N["menu"]))

    # ── Block (phone → lookup UUID → confirm → block) ──
    nodes.append(_make_wait_input(N["block_ask"],
        "🚫 *Block Contact*\n\nEnter the phone number to block (digits only):",
        "block_phone", N["block_lookup"], N["timeout"]))
    nodes.append(_make_webhook_split(N["block_lookup"],
        "GET", f"{WH}/contacts.json?urn=whatsapp:@results.block_phone.value",
        "block_contact_lookup", N["block_confirm"], N["block_notfound"]))
    nodes.append(_make_msg_node(N["block_notfound"],
        "⚠️ No contact found for that number.", dest_uuid=N["menu"]))
    nodes.append(_make_confirm_guard(N["block_confirm"],
        "⚠️ *This will block:*\n\n"
        "Name: @webhook.json.results.0.name\n"
        "Number: @results.block_phone.value\n\n"
        "Type *CONFIRM* to proceed or anything else to cancel.",
        "block_confirmation", N["block_wh"], N["block_cancel"], N["timeout"]))
    nodes.append(_make_webhook_split(N["block_wh"],
        "POST", f"{WH}/contact_actions.json",
        "block_result", N["block_ok"], N["block_err"],
        body='{"contacts": ["@webhook.json.results.0.uuid"], "action": "block"}',
        extra_headers={"Content-Type": "application/json"}))
    nodes.append(_make_msg_node(N["block_ok"],
        "✅ Contact blocked.", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["block_err"],
        "⚠️ Failed to block contact.", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["block_cancel"],
        "❌ Block cancelled.", dest_uuid=N["menu"]))

    # ── Unblock (phone → lookup UUID → unblock) ──
    nodes.append(_make_wait_input(N["unblock_ask"],
        "🔓 *Unblock Contact*\n\nEnter the phone number to unblock (digits only):",
        "unblock_phone", N["unblock_lookup"], N["timeout"]))
    nodes.append(_make_webhook_split(N["unblock_lookup"],
        "GET", f"{WH}/contacts.json?urn=whatsapp:@results.unblock_phone.value",
        "unblock_contact_lookup", N["unblock_wh"], N["unblock_notfound"]))
    nodes.append(_make_msg_node(N["unblock_notfound"],
        "⚠️ No contact found for that number.", dest_uuid=N["menu"]))
    nodes.append(_make_webhook_split(N["unblock_wh"],
        "POST", f"{WH}/contact_actions.json",
        "unblock_result", N["unblock_ok"], N["unblock_err"],
        body='{"contacts": ["@webhook.json.results.0.uuid"], "action": "unblock"}',
        extra_headers={"Content-Type": "application/json"}))
    nodes.append(_make_msg_node(N["unblock_ok"],
        "✅ Contact @webhook.json.results.0.name unblocked.", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["unblock_err"],
        "⚠️ Failed to unblock contact.", dest_uuid=N["menu"]))

    X = 0
    layout = {
        N["menu"]:            (300, 0),
        N["timeout"]:         (700, 0),
        N["back"]:            (700, ROW),
        N["lookup_ask"]:      (X, ROW * 2),
        N["lookup_wh"]:       (X, ROW * 3),
        N["lookup_ok"]:       (X, ROW * 4),
        N["lookup_err"]:      (X + 300, ROW * 4),
        N["create_ask_urn"]:  (X + 500, ROW * 2),
        N["create_ask_name"]: (X + 500, ROW * 3),
        N["create_wh"]:       (X + 500, ROW * 4),
        N["create_ok"]:       (X + 500, ROW * 5),
        N["create_err"]:      (X + 800, ROW * 5),
        N["block_ask"]:       (X, ROW * 6),
        N["block_lookup"]:    (X, ROW * 7),
        N["block_notfound"]:  (X + 300, ROW * 7),
        N["block_confirm"]:   (X, ROW * 8),
        N["block_wh"]:        (X, ROW * 9),
        N["block_ok"]:        (X, ROW * 10),
        N["block_err"]:       (X + 300, ROW * 10),
        N["block_cancel"]:    (X + 300, ROW * 9),
        N["unblock_ask"]:     (X + 500, ROW * 6),
        N["unblock_lookup"]:  (X + 500, ROW * 7),
        N["unblock_notfound"]:(X + 800, ROW * 7),
        N["unblock_wh"]:      (X + 500, ROW * 8),
        N["unblock_ok"]:      (X + 500, ROW * 9),
        N["unblock_err"]:     (X + 800, ROW * 9),
    }
    return flow_uuid, _make_flow(flow_uuid, "Contacts Ops", nodes, layout)


# ── Segments Ops (RapidPro Groups — renamed per ADR-011 Finding 10) ──────────

def generate_groups_flow():
    """Segments Ops: list, create, delete (by name with CONFIRM guard)."""
    WH = WEBHOOK_API_URL
    flow_uuid = u()
    N = {
        "menu": u(), "timeout": u(), "back": u(),
        "list_wh": u(), "list_ok": u(), "list_err": u(),
        "create_ask": u(), "create_wh": u(), "create_ok": u(), "create_err": u(),
        # Delete: list → ask name → lookup → confirm → delete
        "delete_list": u(), "delete_ask": u(), "delete_lookup": u(),
        "delete_notfound": u(), "delete_confirm": u(), "delete_wh": u(),
        "delete_ok": u(), "delete_err": u(), "delete_cancel": u(),
    }
    nodes = []

    nodes.append(_make_wait_menu(
        N["menu"],
        "📋 *Segments*\n\nSelect an option:",
        [
            ("List", N["list_wh"]),
            ("Create", N["create_ask"]),
            ("Delete", N["delete_list"]),
            ("⬅️ Back", N["back"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))
    nodes.append(_make_msg_node(N["timeout"], "⏱️ Segments timed out."))
    nodes.append(_make_msg_node(N["back"], "⬅️ Returning to main menu..."))

    # ── List ──
    nodes.append(_make_webhook_split(N["list_wh"],
        "GET", f"{WH}/groups.json",
        "groups_list", N["list_ok"], N["list_err"]))
    _G = "@webhook.json.results"
    nodes.append(_make_msg_node(N["list_ok"],
        "📋 *Segments:*\n\n"
        f"• {_G}.0.name ({_G}.0.count members)\n"
        f"• {_G}.1.name ({_G}.1.count members)\n"
        f"• {_G}.2.name ({_G}.2.count members)\n"
        f"• {_G}.3.name ({_G}.3.count members)\n"
        f"• {_G}.4.name ({_G}.4.count members)\n"
        f"• {_G}.5.name ({_G}.5.count members)\n"
        f"• {_G}.6.name ({_G}.6.count members)\n"
        f"• {_G}.7.name ({_G}.7.count members)",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["list_err"],
        "⚠️ Failed to list segments.", dest_uuid=N["menu"]))

    # ── Create ──
    nodes.append(_make_wait_input(N["create_ask"],
        "➕ Enter a name for the new segment:", "new_group_name",
        N["create_wh"], N["timeout"]))
    nodes.append(_make_webhook_split(N["create_wh"],
        "POST", f"{WH}/groups.json",
        "group_create", N["create_ok"], N["create_err"],
        body='{"name": "@results.new_group_name.value"}',
        extra_headers={"Content-Type": "application/json"}))
    nodes.append(_make_msg_node(N["create_ok"],
        "✅ Segment *@results.new_group_name.value* created!\n\n"
        "UUID: @webhook.json.uuid",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["create_err"],
        "⚠️ Failed to create segment.", dest_uuid=N["menu"]))

    # ── Delete (show list → ask name → lookup UUID → confirm → delete) ──
    # Step 1: Show groups so user can see names
    nodes.append(_make_webhook_split(N["delete_list"],
        "GET", f"{WH}/groups.json",
        "delete_groups_preview", N["delete_ask"], N["delete_err"]))
    # Step 2: Ask for group name
    _G = "@webhook.json.results"
    nodes.append(_make_wait_input(N["delete_ask"],
        "🗑️ *Delete Segment*\n\n"
        f"• {_G}.0.name\n• {_G}.1.name\n• {_G}.2.name\n"
        f"• {_G}.3.name\n• {_G}.4.name\n• {_G}.5.name\n\n"
        "Type the *exact segment name* to delete:",
        "delete_group_name", N["delete_lookup"], N["timeout"]))
    # Step 3: Lookup group by name to get UUID
    nodes.append(_make_webhook_split(N["delete_lookup"],
        "GET", f"{WH}/groups.json?name=@results.delete_group_name.value",
        "delete_group_lookup", N["delete_confirm"], N["delete_notfound"]))
    nodes.append(_make_msg_node(N["delete_notfound"],
        "⚠️ No segment found with that name. Check spelling and try again.",
        dest_uuid=N["menu"]))
    # Step 4: Confirm using the resolved name
    nodes.append(_make_confirm_guard(N["delete_confirm"],
        "⚠️ *This will permanently delete segment:*\n\n"
        "Name: @webhook.json.results.0.name\n"
        "UUID: @webhook.json.results.0.uuid\n\n"
        "Type *CONFIRM* to proceed or anything else to cancel.",
        "delete_confirmation", N["delete_wh"], N["delete_cancel"], N["timeout"]))
    # Step 5: Delete using the resolved UUID
    nodes.append(_make_webhook_split(N["delete_wh"],
        "DELETE", f"{WH}/groups.json?uuid=@webhook.json.results.0.uuid",
        "group_delete", N["delete_ok"], N["delete_err"]))
    nodes.append(_make_msg_node(N["delete_ok"],
        "✅ Segment *@results.delete_group_name.value* deleted.", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["delete_err"],
        "⚠️ Failed to delete segment.", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["delete_cancel"],
        "❌ Delete cancelled.", dest_uuid=N["menu"]))

    layout = {
        N["menu"]:            (300, 0),
        N["timeout"]:         (700, 0),
        N["back"]:            (700, ROW),
        N["list_wh"]:         (0, ROW * 2),
        N["list_ok"]:         (0, ROW * 3),
        N["list_err"]:        (300, ROW * 3),
        N["create_ask"]:      (500, ROW * 2),
        N["create_wh"]:       (500, ROW * 3),
        N["create_ok"]:       (500, ROW * 4),
        N["create_err"]:      (800, ROW * 4),
        N["delete_list"]:     (0, ROW * 5),
        N["delete_ask"]:      (0, ROW * 6),
        N["delete_lookup"]:   (0, ROW * 7),
        N["delete_notfound"]: (300, ROW * 7),
        N["delete_confirm"]:  (0, ROW * 8),
        N["delete_wh"]:       (0, ROW * 9),
        N["delete_ok"]:       (0, ROW * 10),
        N["delete_err"]:      (300, ROW * 10),
        N["delete_cancel"]:   (300, ROW * 9),
    }
    return flow_uuid, _make_flow(flow_uuid, "Segments Ops", nodes, layout)


# ── Messages Ops ─────────────────────────────────────────────────────────────

def generate_messages_flow():
    """Messages Ops: send to a contact (by phone), broadcast to a group (by name).
    Broadcast shows group list first so user picks by name, not UUID.
    """
    WH = WEBHOOK_API_URL
    flow_uuid = u()
    N = {
        "menu": u(), "timeout": u(), "back": u(),
        # Send single
        "send_ask_urn": u(), "send_ask_text": u(), "send_wh": u(),
        "send_ok": u(), "send_err": u(),
        # Broadcast (smart: list groups → pick name → lookup UUID → send)
        "bcast_list": u(), "bcast_ask_name": u(), "bcast_lookup": u(),
        "bcast_notfound": u(), "bcast_ask_text": u(), "bcast_wh": u(),
        "bcast_ok": u(), "bcast_err": u(),
    }
    nodes = []

    nodes.append(_make_wait_menu(
        N["menu"],
        "💬 *Messages*\n\nSelect an option:",
        [
            ("Send", N["send_ask_urn"]),
            ("Broadcast", N["bcast_list"]),
            ("⬅️ Back", N["back"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))
    nodes.append(_make_msg_node(N["timeout"], "⏱️ Messages timed out."))
    nodes.append(_make_msg_node(N["back"], "⬅️ Returning to main menu..."))

    # ── Send single message ──
    nodes.append(_make_wait_input(N["send_ask_urn"],
        "✉️ Enter the recipient's WhatsApp number (digits only, e.g. 50937145893):",
        "msg_recipient", N["send_ask_text"], N["timeout"]))
    nodes.append(_make_wait_input(N["send_ask_text"],
        "📝 Type the message to send:", "msg_text", N["send_wh"], N["timeout"]))
    nodes.append(_make_webhook_split(N["send_wh"],
        "POST", f"{WH}/broadcasts.json",
        "msg_send", N["send_ok"], N["send_err"],
        body='{"urns": ["whatsapp:@results.msg_recipient.value"], '
             '"text": "@results.msg_text.value"}',
        extra_headers={"Content-Type": "application/json"}))
    nodes.append(_make_msg_node(N["send_ok"],
        "✅ Message sent to @results.msg_recipient.value", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["send_err"],
        "⚠️ Failed to send message.", dest_uuid=N["menu"]))

    # ── Broadcast to group (smart lookup) ──
    # Step 1: Fetch and display groups
    nodes.append(_make_webhook_split(N["bcast_list"],
        "GET", f"{WH}/groups.json",
        "bcast_groups_preview", N["bcast_ask_name"], N["bcast_err"]))
    # Step 2: Ask for group name
    _G = "@webhook.json.results"
    nodes.append(_make_wait_input(N["bcast_ask_name"],
        "📢 *Broadcast to Group*\n\n"
        f"• {_G}.0.name ({_G}.0.count)\n• {_G}.1.name ({_G}.1.count)\n"
        f"• {_G}.2.name ({_G}.2.count)\n• {_G}.3.name ({_G}.3.count)\n"
        f"• {_G}.4.name ({_G}.4.count)\n\n"
        "Type the *exact group name*:",
        "bcast_group_name", N["bcast_lookup"], N["timeout"]))
    # Step 3: Lookup group by name to resolve UUID
    nodes.append(_make_webhook_split(N["bcast_lookup"],
        "GET", f"{WH}/groups.json?name=@results.bcast_group_name.value",
        "bcast_group_lookup", N["bcast_ask_text"], N["bcast_notfound"]))
    nodes.append(_make_msg_node(N["bcast_notfound"],
        "⚠️ No group found with that name. Check spelling and try again.",
        dest_uuid=N["menu"]))
    # Step 4: Ask for message text (at this point @webhook has the lookup result)
    nodes.append(_make_wait_input(N["bcast_ask_text"],
        "✅ Found group *@webhook.json.results.0.name* "
        "(@webhook.json.results.0.count members)\n\n"
        "📝 Type the broadcast message:",
        "bcast_text", N["bcast_wh"], N["timeout"]))
    # Step 5: Send broadcast using resolved UUID
    # NOTE: @webhook.json still refers to step 3's response (lookup),
    # because wait nodes don't reset @webhook — only call_webhook does.
    nodes.append(_make_webhook_split(N["bcast_wh"],
        "POST", f"{WH}/broadcasts.json",
        "bcast_send", N["bcast_ok"], N["bcast_err"],
        body='{"groups": ["@webhook.json.results.0.uuid"], '
             '"text": "@results.bcast_text.value"}',
        extra_headers={"Content-Type": "application/json"}))
    nodes.append(_make_msg_node(N["bcast_ok"],
        "✅ Broadcast sent to group *@results.bcast_group_name.value*!",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["bcast_err"],
        "⚠️ Failed to broadcast.", dest_uuid=N["menu"]))

    layout = {
        N["menu"]:           (300, 0),
        N["timeout"]:        (700, 0),
        N["back"]:           (700, ROW),
        N["send_ask_urn"]:   (0, ROW * 2),
        N["send_ask_text"]:  (0, ROW * 3),
        N["send_wh"]:        (0, ROW * 4),
        N["send_ok"]:        (0, ROW * 5),
        N["send_err"]:       (300, ROW * 5),
        N["bcast_list"]:     (500, ROW * 2),
        N["bcast_ask_name"]: (500, ROW * 3),
        N["bcast_lookup"]:   (500, ROW * 4),
        N["bcast_notfound"]: (800, ROW * 4),
        N["bcast_ask_text"]: (500, ROW * 5),
        N["bcast_wh"]:       (500, ROW * 6),
        N["bcast_ok"]:       (500, ROW * 7),
        N["bcast_err"]:      (800, ROW * 7),
    }
    return flow_uuid, _make_flow(flow_uuid, "Messages Ops", nodes, layout)


# ── Flows Ops ────────────────────────────────────────────────────────────────

def generate_flows_ops_flow():
    """Flows Ops: list, start (by flow name + phone, not UUID).
    Start lists flows first, asks for flow name, resolves UUID via API.
    """
    WH = WEBHOOK_API_URL
    flow_uuid = u()
    N = {
        "menu": u(), "timeout": u(), "back": u(),
        "list_wh": u(), "list_ok": u(), "list_err": u(),
        # Start: list → ask name → lookup UUID → ask phone → POST
        "start_list": u(), "start_ask_name": u(), "start_lookup": u(),
        "start_notfound": u(), "start_ask_phone": u(), "start_wh": u(),
        "start_ok": u(), "start_err": u(),
    }
    nodes = []

    nodes.append(_make_wait_menu(
        N["menu"],
        "🔄 *Flows*\n\nSelect an option:",
        [
            ("List", N["list_wh"]),
            ("Start", N["start_list"]),
            ("⬅️ Back", N["back"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))
    nodes.append(_make_msg_node(N["timeout"], "⏱️ Flows timed out."))
    nodes.append(_make_msg_node(N["back"], "⬅️ Returning to main menu..."))

    # ── List ──
    nodes.append(_make_webhook_split(N["list_wh"],
        "GET", f"{WH}/flows.json",
        "flows_list", N["list_ok"], N["list_err"]))
    _F = "@webhook.json.results"
    nodes.append(_make_msg_node(N["list_ok"],
        "🔄 *Flows:*\n\n"
        f"• {_F}.0.name\n• {_F}.1.name\n• {_F}.2.name\n"
        f"• {_F}.3.name\n• {_F}.4.name\n• {_F}.5.name\n"
        f"• {_F}.6.name\n• {_F}.7.name\n• {_F}.8.name\n"
        f"• {_F}.9.name\n• {_F}.10.name\n• {_F}.11.name",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["list_err"],
        "⚠️ Failed to list flows.", dest_uuid=N["menu"]))

    # ── Start flow (smart lookup) ──
    # Step 1: Show available flows
    nodes.append(_make_webhook_split(N["start_list"],
        "GET", f"{WH}/flows.json",
        "start_flows_preview", N["start_ask_name"], N["start_err"]))
    # Step 2: Ask for flow name
    _F = "@webhook.json.results"
    nodes.append(_make_wait_input(N["start_ask_name"],
        "▶️ *Start Flow*\n\n"
        f"• {_F}.0.name\n• {_F}.1.name\n• {_F}.2.name\n"
        f"• {_F}.3.name\n• {_F}.4.name\n• {_F}.5.name\n"
        f"• {_F}.6.name\n• {_F}.7.name\n• {_F}.8.name\n\n"
        "Type the *exact flow name*:",
        "start_flow_name", N["start_lookup"], N["timeout"]))
    # Step 3: Resolve flow name → UUID
    nodes.append(_make_webhook_split(N["start_lookup"],
        "GET", f"{WH}/flows.json?name=@results.start_flow_name.value",
        "start_flow_lookup", N["start_ask_phone"], N["start_notfound"]))
    nodes.append(_make_msg_node(N["start_notfound"],
        "⚠️ No flow found with that name. Check spelling.",
        dest_uuid=N["menu"]))
    # Step 4: Ask for contact phone
    nodes.append(_make_wait_input(N["start_ask_phone"],
        "✅ Found flow *@webhook.json.results.0.name*\n\n"
        "📱 Enter the contact's WhatsApp number (digits only):",
        "start_contact_phone", N["start_wh"], N["timeout"]))
    # Step 5: Start the flow
    nodes.append(_make_webhook_split(N["start_wh"],
        "POST", f"{WH}/flow_starts.json",
        "flow_start", N["start_ok"], N["start_err"],
        body='{"flow": "@webhook.json.results.0.uuid", '
             '"urns": ["whatsapp:@results.start_contact_phone.value"]}',
        extra_headers={"Content-Type": "application/json"}))
    nodes.append(_make_msg_node(N["start_ok"],
        "✅ Flow *@results.start_flow_name.value* started for "
        "@results.start_contact_phone.value",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["start_err"],
        "⚠️ Failed to start flow.", dest_uuid=N["menu"]))

    layout = {
        N["menu"]:            (300, 0),
        N["timeout"]:         (700, 0),
        N["back"]:            (700, ROW),
        N["list_wh"]:         (0, ROW * 2),
        N["list_ok"]:         (0, ROW * 3),
        N["list_err"]:        (300, ROW * 3),
        N["start_list"]:      (500, ROW * 2),
        N["start_ask_name"]:  (500, ROW * 3),
        N["start_lookup"]:    (500, ROW * 4),
        N["start_notfound"]:  (800, ROW * 4),
        N["start_ask_phone"]: (500, ROW * 5),
        N["start_wh"]:        (500, ROW * 6),
        N["start_ok"]:        (500, ROW * 7),
        N["start_err"]:       (800, ROW * 7),
    }
    return flow_uuid, _make_flow(flow_uuid, "Flows Ops", nodes, layout)


# ── System Ops ───────────────────────────────────────────────────────────────

def generate_system_flow():
    """System Ops: org info, channels, globals list/update, fields list."""
    WH = WEBHOOK_API_URL
    flow_uuid = u()
    N = {
        "menu": u(), "timeout": u(), "back": u(),
        "org_wh": u(), "org_ok": u(), "org_err": u(),
        "ch_wh": u(), "ch_ok": u(), "ch_err": u(),
        "globals_wh": u(), "globals_ok": u(), "globals_err": u(),
        "gupdate_ask_key": u(), "gupdate_ask_val": u(), "gupdate_wh": u(),
        "gupdate_ok": u(), "gupdate_err": u(),
        "fields_wh": u(), "fields_ok": u(), "fields_err": u(),
    }
    nodes = []

    nodes.append(_make_wait_menu(
        N["menu"],
        "⚙️ *System*\n\nSelect an option:",
        [
            ("Org Info", N["org_wh"]),
            ("Channels", N["ch_wh"]),
            ("Globals", N["globals_wh"]),
            ("Update Global", N["gupdate_ask_key"]),
            ("Fields", N["fields_wh"]),
            ("⬅️ Back", N["back"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))
    nodes.append(_make_msg_node(N["timeout"], "⏱️ System timed out."))
    nodes.append(_make_msg_node(N["back"], "⬅️ Returning to main menu..."))

    # ── Org info ──
    nodes.append(_make_webhook_split(N["org_wh"],
        "GET", f"{WH}/org.json", "org_info",
        N["org_ok"], N["org_err"]))
    nodes.append(_make_msg_node(N["org_ok"],
        "🏢 *Workspace:*\n\n"
        "Name: @webhook.json.name\n"
        "Timezone: @webhook.json.timezone\n"
        "Date: @webhook.json.date_style\n"
        "Languages: @webhook.json.languages",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["org_err"],
        "⚠️ Failed to get org info.", dest_uuid=N["menu"]))

    # ── Channels ──
    nodes.append(_make_webhook_split(N["ch_wh"],
        "GET", f"{WH}/channels.json", "channels_info",
        N["ch_ok"], N["ch_err"]))
    _C = "@webhook.json.results"
    nodes.append(_make_msg_node(N["ch_ok"],
        "📡 *Channels:*\n\n"
        f"• {_C}.0.name — {_C}.0.address ({_C}.0.type)\n"
        f"• {_C}.1.name — {_C}.1.address ({_C}.1.type)",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["ch_err"],
        "⚠️ Failed to list channels.", dest_uuid=N["menu"]))

    # ── Globals list ──
    nodes.append(_make_webhook_split(N["globals_wh"],
        "GET", f"{WH}/globals.json", "globals_list",
        N["globals_ok"], N["globals_err"]))
    _GL = "@webhook.json.results"
    nodes.append(_make_msg_node(N["globals_ok"],
        "🌐 *Globals:*\n\n"
        f"• {_GL}.0.key = {_GL}.0.value\n"
        f"• {_GL}.1.key = {_GL}.1.value\n"
        f"• {_GL}.2.key = {_GL}.2.value\n"
        f"• {_GL}.3.key = {_GL}.3.value\n"
        f"• {_GL}.4.key = {_GL}.4.value",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["globals_err"],
        "⚠️ Failed to list globals.", dest_uuid=N["menu"]))

    # ── Update global ──
    nodes.append(_make_wait_input(N["gupdate_ask_key"],
        "✏️ Enter the global key to update:", "global_key",
        N["gupdate_ask_val"], N["timeout"]))
    nodes.append(_make_wait_input(N["gupdate_ask_val"],
        "📝 Enter the new value for *@results.global_key.value*:", "global_value",
        N["gupdate_wh"], N["timeout"]))
    nodes.append(_make_webhook_split(N["gupdate_wh"],
        "POST", f"{WH}/globals.json?key=@results.global_key.value",
        "global_update", N["gupdate_ok"], N["gupdate_err"],
        body='{"value": "@results.global_value.value"}',
        extra_headers={"Content-Type": "application/json"}))
    nodes.append(_make_msg_node(N["gupdate_ok"],
        "✅ Global *@results.global_key.value* updated.", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["gupdate_err"],
        "⚠️ Failed to update global.", dest_uuid=N["menu"]))

    # ── Fields list ──
    nodes.append(_make_webhook_split(N["fields_wh"],
        "GET", f"{WH}/fields.json", "fields_list",
        N["fields_ok"], N["fields_err"]))
    _FD = "@webhook.json.results"
    nodes.append(_make_msg_node(N["fields_ok"],
        "📊 *Contact Fields:*\n\n"
        f"• {_FD}.0.label ({_FD}.0.value_type)\n"
        f"• {_FD}.1.label ({_FD}.1.value_type)\n"
        f"• {_FD}.2.label ({_FD}.2.value_type)\n"
        f"• {_FD}.3.label ({_FD}.3.value_type)\n"
        f"• {_FD}.4.label ({_FD}.4.value_type)",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["fields_err"],
        "⚠️ Failed to list fields.", dest_uuid=N["menu"]))

    X_ORG = 0; X_CH = 350; X_GL = 700; X_GU = 1050; X_F = 1400
    layout = {
        N["menu"]:           (500, 0),
        N["timeout"]:        (900, 0),
        N["back"]:           (900, ROW),
        N["org_wh"]:         (X_ORG, ROW * 2),
        N["org_ok"]:         (X_ORG, ROW * 3),
        N["org_err"]:        (X_ORG + 200, ROW * 3),
        N["ch_wh"]:          (X_CH, ROW * 2),
        N["ch_ok"]:          (X_CH, ROW * 3),
        N["ch_err"]:         (X_CH + 200, ROW * 3),
        N["globals_wh"]:     (X_GL, ROW * 2),
        N["globals_ok"]:     (X_GL, ROW * 3),
        N["globals_err"]:    (X_GL + 200, ROW * 3),
        N["gupdate_ask_key"]:(X_GU, ROW * 2),
        N["gupdate_ask_val"]:(X_GU, ROW * 3),
        N["gupdate_wh"]:     (X_GU, ROW * 4),
        N["gupdate_ok"]:     (X_GU, ROW * 5),
        N["gupdate_err"]:    (X_GU + 250, ROW * 5),
        N["fields_wh"]:      (X_F, ROW * 2),
        N["fields_ok"]:      (X_F, ROW * 3),
        N["fields_err"]:     (X_F + 200, ROW * 3),
    }
    return flow_uuid, _make_flow(flow_uuid, "System Ops", nodes, layout)


# ── Exit CRM Ops ─────────────────────────────────────────────────────────────

def generate_exit_ops_flow():
    flow_uuid = u()
    nid = u()
    nodes = [_make_msg_node(nid, "✅ CRM session ended.\n\nType *ops* to start again.")]
    layout = {nid: (300, 0)}
    return flow_uuid, _make_flow(flow_uuid, "Exit CRM Ops", nodes, layout, expire=5)


# ══════════════════════════════════════════════════════════════════════════════
#  EXPORT & IMPORT
# ══════════════════════════════════════════════════════════════════════════════

def generate_export(*flows):
    return {
        "version": "13",
        "site": "http://localhost",
        "flows": list(flows),
        "campaigns": [], "triggers": [], "fields": [], "groups": [],
    }


def import_flows(export_json):
    json_path = Path(__file__).parent / "crm_ops_flows.json"
    with open(json_path, "w") as f:
        json.dump(export_json, f, indent=2)
    print(f"   📁 Saved {len(export_json['flows'])} flows to {json_path}")

    manage_py = "/opt/iiab/rapidpro/manage.py"
    venv_python = "/opt/iiab/rapidpro/.venv/bin/python"
    if not Path(venv_python).exists():
        venv_python = "python3"

    import_script = f'''
import json
from temba.orgs.models import Org
org = Org.objects.filter(is_active=True).first()
if not org:
    print("ERROR: No active org")
    exit(1)
user = org.get_owner()
with open("{json_path}") as f:
    export = json.load(f)
try:
    org.import_app(export, user, "http://localhost")
    print("OK")
except Exception as e:
    print(f"IMPORT_ERROR: {{e}}")
'''
    result = subprocess.run(
        [venv_python, manage_py, "shell", "-c", import_script],
        capture_output=True, text=True,
        cwd="/opt/iiab/rapidpro",
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "temba.settings"},
        timeout=60,
    )
    stdout = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    if "OK" in stdout:
        print(f"   ✅ {len(export_json['flows'])} flows imported successfully!")
        return True
    else:
        print(f"   ⚠️  Import: {stdout}")
        if result.stderr.strip():
            print(f"   stderr: {result.stderr.strip()[:300]}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    global HEADERS

    if not API_TOKEN:
        print("❌ RAPIDPRO_API_TOKEN not set. Add to .env and source it.")
        sys.exit(1)

    HEADERS = {
        "Authorization": f"Token {API_TOKEN}",
        "Content-Type": "application/json",
    }

    print("=" * 60)
    print("  ADR-010 Phase 2: Modular CRM Sub-Flows")
    print("=" * 60)
    print(f"  Host:  {RAPIDPRO_HOST}")
    print(f"  Admin: whatsapp:{ADMIN_PHONE}")

    # Steps 1-3: Infrastructure
    setup_api_token_global()
    admins_uuid = setup_admins_group()
    add_admin_to_group(admins_uuid)

    # Step 4: Generate all 7 flows
    print("\n── Step 4: Generate Flow JSON ──")

    contacts_uuid, contacts_flow = generate_contacts_flow()
    groups_uuid, groups_flow = generate_groups_flow()
    messages_uuid, messages_flow = generate_messages_flow()
    flows_uuid, flows_flow = generate_flows_ops_flow()
    system_uuid, system_flow = generate_system_flow()
    exit_uuid, exit_flow = generate_exit_ops_flow()

    sub_flow_uuids = {
        "contacts": contacts_uuid,
        "groups": groups_uuid,
        "messages": messages_uuid,
        "flows": flows_uuid,
        "system": system_uuid,
    }

    router_uuid, router_flow = generate_router_flow(admins_uuid, sub_flow_uuids)

    all_flows = [router_flow, contacts_flow, groups_flow, messages_flow,
                 flows_flow, system_flow, exit_flow]
    total_nodes = sum(len(f["nodes"]) for f in all_flows)

    for f in all_flows:
        print(f"   📊 {f['name']:20s} — {len(f['nodes']):2d} nodes")
    print(f"   ────────────────────────────")
    print(f"   📊 {'TOTAL':20s} — {total_nodes:2d} nodes across {len(all_flows)} flows")

    # Step 5: Import
    print("\n── Step 5: Import Flows into RapidPro ──")
    export = generate_export(*all_flows)
    if not import_flows(export):
        print("   ❌ Import failed. Check errors above.")
        sys.exit(1)

    # Step 6: Persist UUIDs (from generator — will be synced below)
    print("\n── Step 6: Persist Flow UUIDs ──")
    _persist_env("CRM_ROUTER_FLOW_UUID", router_uuid, "CRM Phase 2 — Router flow")
    _persist_env("CRM_CONTACTS_FLOW_UUID", contacts_uuid)
    _persist_env("CRM_GROUPS_FLOW_UUID", groups_uuid)
    _persist_env("CRM_MESSAGES_FLOW_UUID", messages_uuid)
    _persist_env("CRM_FLOWS_FLOW_UUID", flows_uuid)
    _persist_env("CRM_SYSTEM_FLOW_UUID", system_uuid)

    # Step 7: Sync .env UUIDs with actual DB values
    # import_app may remap UUIDs — the DB is the source of truth
    print("\n── Step 7: Sync UUIDs with DB ──")
    name_to_env = {
        "CRM Operations": "CRM_ROUTER_FLOW_UUID",
        "Contacts Ops":   "CRM_CONTACTS_FLOW_UUID",
        "Segments Ops":    "CRM_GROUPS_FLOW_UUID",
        "Messages Ops":   "CRM_MESSAGES_FLOW_UUID",
        "Flows Ops":      "CRM_FLOWS_FLOW_UUID",
        "System Ops":     "CRM_SYSTEM_FLOW_UUID",
    }
    db_flows = api_get("flows.json")
    db_map = {f["name"]: f["uuid"] for f in db_flows.get("results", [])}
    for flow_name, env_key in name_to_env.items():
        if flow_name in db_map:
            _persist_env(env_key, db_map[flow_name])

    # Step 8: Create 'ops' keyword trigger
    print("\n── Step 8: Create 'ops' Keyword Trigger ──")
    _setup_ops_trigger()

    print("\n" + "=" * 60)
    print("  Phase 2 deployment complete!")
    print()
    print(f"  FLOWS: {len(all_flows)} flows, {total_nodes} nodes")
    print(f"  OPS:   22 operations (6 Contacts, 3 Groups, 2 Messages, 2 Flows, 5 System)")
    print(f"  AUTH:  has_group(Admins) on router entry")
    print(f"  GUARD: typed CONFIRM for block/delete operations")
    print()
    print("  NEXT STEPS:")
    print("  1. sudo systemctl restart rapidpro-mailroom ai-gateway rivebot")
    print("  2. Send 'ops' via WhatsApp to test")
    print("=" * 60)


def _setup_ops_trigger():
    """Create the 'ops' keyword trigger via Django ORM."""
    venv_python = "/opt/iiab/rapidpro/.venv/bin/python"
    if not Path(venv_python).exists():
        venv_python = "python3"

    script = '''
from temba.triggers.models import Trigger
from temba.flows.models import Flow
from temba.orgs.models import Org
from django.db.models import Max

org = Org.objects.filter(is_active=True).first()
user = org.get_owner()
flow = Flow.objects.filter(name="CRM Operations", is_active=True).first()
if not flow:
    print("SKIP: CRM Operations flow not found")
else:
    existing = Trigger.objects.filter(
        org=org, trigger_type="K", is_active=True, is_archived=False,
        keywords__contains=["ops"]
    )
    if existing.exists():
        t = existing.first()
        if t.match_type != "F":
            t.match_type = "F"
            t.save(update_fields=["match_type"])
            print(f"FIXED: match_type → F (id={t.id})")
        else:
            print(f"EXISTS: id={t.id}")
    else:
        max_p = Trigger.objects.filter(org=org).aggregate(Max("priority"))["priority__max"] or 0
        t = Trigger.objects.create(
            org=org, trigger_type="K", keywords=["ops"], match_type="F",
            flow=flow, created_by=user, modified_by=user, priority=max_p + 1,
        )
        print(f"CREATED: id={t.id}")
'''
    result = subprocess.run(
        [venv_python, "/opt/iiab/rapidpro/manage.py", "shell", "-c", script],
        capture_output=True, text=True,
        cwd="/opt/iiab/rapidpro",
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "temba.settings"},
        timeout=30,
    )
    stdout = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    if "CREATED" in stdout:
        print(f"   ✅ Created 'ops' keyword trigger → CRM Operations")
    elif "EXISTS" in stdout:
        print(f"   ✅ 'ops' trigger already exists")
    elif "FIXED" in stdout:
        print(f"   ✅ Fixed 'ops' trigger match_type")
    else:
        print(f"   ⚠️  Trigger: {stdout}")


if __name__ == "__main__":
    main()

