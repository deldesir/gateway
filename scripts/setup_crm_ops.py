#!/usr/bin/env python3
"""
ADR-010: CRM Operations — RapidPro Setup Script

Creates the required RapidPro infrastructure for WhatsApp-driven admin ops:
  1. api_token global (used by call_webhook Authorization headers)
  2. Admins group (used by flow auth guard)
  3. Admin contact added to Admins group
  4. CRM Operations flow + Exit CRM Ops flow (programmatic JSON generation)
  5. Import flows into RapidPro via Django ORM (org.import_app)
  6. Persist CRM_OPS_FLOW_UUID to .env

Usage:
    cd /opt/iiab/ai-gateway
    source .env
    python scripts/setup_crm_ops.py

After running, restart services:
    sudo systemctl restart rapidpro-mailroom ai-gateway rivebot
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
HEADERS = {}  # Set in main() after token validation


def api_get(endpoint, params=None):
    """GET from RapidPro API."""
    r = requests.get(f"{API_URL}/{endpoint}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()


def api_post(endpoint, data):
    """POST to RapidPro API."""
    r = requests.post(f"{API_URL}/{endpoint}", headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()


# ── UUID Factory ─────────────────────────────────────────────────────────────

def u():
    """Generate a new UUID v4 string."""
    return str(uuid4())


# ── Step 1: Create api_token Global ──────────────────────────────────────────

def setup_api_token_global():
    """Create or verify the api_token global variable."""
    print("\n── Step 1: api_token Global ──")

    globals_data = api_get("globals.json")
    for g in globals_data.get("results", []):
        if g["key"] == "api_token":
            print(f"   ✅ api_token global already exists (value hidden)")
            return

    api_post("globals.json", {
        "name": "API Token",
        "key": "api_token",
        "value": API_TOKEN,
    })
    print(f"   ✅ Created api_token global")


def _persist_env(key: str, value: str, comment: str = ""):
    """Append a key=value to .env if not already present."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    content = env_path.read_text()
    if key in content:
        # Update existing value
        lines = content.splitlines()
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                updated = True
                break
        if updated:
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
    """Create the Admins group and return its UUID."""
    print("\n── Step 2: Admins Group ──")

    groups = api_get("groups.json", {"name": "Admins"})
    for g in groups.get("results", []):
        if g["name"] == "Admins":
            print(f"   ✅ Admins group exists: {g['uuid']}")
            _persist_env("ADMINS_GROUP_UUID", g["uuid"],
                         "CRM Ops — Admins group UUID (for has_group() flow auth guard)")
            return g["uuid"]

    result = api_post("groups.json", {"name": "Admins"})
    group_uuid = result["uuid"]
    print(f"   ✅ Created Admins group: {group_uuid}")
    _persist_env("ADMINS_GROUP_UUID", group_uuid,
                 "CRM Ops — Admins group UUID (for has_group() flow auth guard)")
    return group_uuid


# ── Step 3: Add Admin to Group ───────────────────────────────────────────────

def add_admin_to_group(group_uuid):
    """Ensure the admin contact is in the Admins group."""
    print("\n── Step 3: Admin Contact ──")

    admin_urn = f"whatsapp:{ADMIN_PHONE}"

    contacts = api_get("contacts.json", {"urn": admin_urn})
    results = contacts.get("results", [])

    if not results:
        print(f"   ⚠️  No contact found for {admin_urn}. Create one in RapidPro first.")
        return None

    contact = results[0]
    contact_uuid = contact["uuid"]

    for g in contact.get("groups", []):
        if g["uuid"] == group_uuid:
            print(f"   ✅ {contact['name']} already in Admins group")
            return contact_uuid

    api_post("contact_actions.json", {
        "contacts": [contact_uuid],
        "action": "add",
        "group": group_uuid,
    })
    print(f"   ✅ Added {contact['name']} to Admins group")
    return contact_uuid


# ── Step 4: Generate Flow JSON ───────────────────────────────────────────────

def _infer_ui_type(node):
    """Infer the flow editor UI node type from the node structure."""
    actions = [a["type"] for a in node.get("actions", [])]
    router = node.get("router", {})
    has_wait = "wait" in router

    if has_wait:
        return "wait_for_response"
    if "call_webhook" in actions:
        return "split_by_webhook"
    if "call_llm" in actions:
        return "split_by_llm"
    if router.get("type") == "switch":
        operand = router.get("operand", "")
        if "@contact.groups" in operand:
            return "split_by_groups"
        if "@input" in operand or "@results" in operand:
            return "split_by_expression"
        return "split_by_expression"
    return "execute_actions"


def _generate_ui(nodes):
    """Auto-generate _ui metadata with grid-layout node positions.

    The flow editor requires _ui.nodes.<uuid>.position for each node,
    otherwise the flow won't render visually.
    """
    COL_WIDTH = 300
    ROW_HEIGHT = 220
    COLS = 3  # nodes per row

    ui_nodes = {}
    for i, node in enumerate(nodes):
        col = i % COLS
        row = i // COLS
        ui_nodes[node["uuid"]] = {
            "position": {
                "left": col * COL_WIDTH,
                "top": row * ROW_HEIGHT,
            },
            "type": _infer_ui_type(node),
            "config": {},
        }

    return {"nodes": ui_nodes, "editor": "0.156.6"}


def _make_action(type_, **fields):
    """Create an action dict with a fresh UUID."""
    return {"uuid": u(), "type": type_, **fields}


def _make_exit(dest_uuid=None):
    """Create an exit dict."""
    return {"uuid": u(), "destination_uuid": dest_uuid}


def _make_category(name, exit_uuid):
    """Create a category dict."""
    return {"uuid": u(), "name": name, "exit_uuid": exit_uuid}


def _make_msg_node(node_uuid, text, quick_replies=None, dest_uuid=None):
    """Simple node: send_msg → single exit."""
    actions = [_make_action("send_msg", text=text,
                            **({"quick_replies": quick_replies} if quick_replies else {}))]
    exit_ = _make_exit(dest_uuid)
    return {"uuid": node_uuid, "actions": actions, "exits": [exit_]}


def _make_webhook_split(node_uuid, method, url, result_name, ok_dest, fail_dest,
                        body="", extra_headers=None):
    """Node: call_webhook + switch on result category (Success/Failed)."""
    headers = {"Authorization": "Token @globals.api_token", "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)

    action = _make_action("call_webhook", method=method, url=url,
                          headers=headers, body=body, result_name=result_name)

    exit_ok = _make_exit(ok_dest)
    exit_fail = _make_exit(fail_dest)

    cat_ok = _make_category("Success", exit_ok["uuid"])
    cat_fail = _make_category("Failed", exit_fail["uuid"])

    case_ok = {
        "uuid": u(), "type": "has_only_text",
        "arguments": ["Success"], "category_uuid": cat_ok["uuid"]
    }

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


def _make_wait_menu(node_uuid, prompt, replies, choices, timeout_dest,
                    default_dest=None, timeout_seconds=300):
    """Node: send_msg with quick_replies + wait for response + switch on input.

    choices: list of (text, dest_uuid) pairs — matched with has_any_word
    """
    actions = [_make_action("send_msg", text=prompt, quick_replies=replies)]

    exits = []
    categories = []
    cases = []

    for text, dest in choices:
        ex = _make_exit(dest)
        cat = _make_category(text, ex["uuid"])
        case = {"uuid": u(), "type": "has_any_word",
                "arguments": [text.lower().replace("❌", "").strip()],
                "category_uuid": cat["uuid"]}
        exits.append(ex)
        categories.append(cat)
        cases.append(case)

    # Timeout category
    ex_timeout = _make_exit(timeout_dest)
    cat_timeout = _make_category("No Response", ex_timeout["uuid"])
    exits.append(ex_timeout)
    categories.append(cat_timeout)

    # Other / default
    ex_other = _make_exit(default_dest or exits[0]["destination_uuid"])
    cat_other = _make_category("Other", ex_other["uuid"])
    exits.append(ex_other)
    categories.append(cat_other)

    router = {
        "type": "switch",
        "operand": "@input.text",
        "wait": {
            "type": "msg",
            "timeout": {"seconds": timeout_seconds, "category_uuid": cat_timeout["uuid"]},
        },
        "cases": cases,
        "categories": categories,
        "default_category_uuid": cat_other["uuid"],
        "result_name": f"menu_{node_uuid[:8]}",
    }

    return {"uuid": node_uuid, "actions": actions, "router": router, "exits": exits}


def _make_wait_input(node_uuid, prompt, result_name, dest_uuid, timeout_dest,
                     timeout_seconds=300):
    """Node: send_msg + wait for free text input → single exit."""
    actions = [_make_action("send_msg", text=prompt)]

    exit_response = _make_exit(dest_uuid)
    exit_timeout = _make_exit(timeout_dest)

    cat_response = _make_category("All Responses", exit_response["uuid"])
    cat_timeout = _make_category("No Response", exit_timeout["uuid"])

    router = {
        "type": "switch",
        "operand": "@input.text",
        "wait": {
            "type": "msg",
            "timeout": {"seconds": timeout_seconds, "category_uuid": cat_timeout["uuid"]},
        },
        "cases": [],
        "categories": [cat_response, cat_timeout],
        "default_category_uuid": cat_response["uuid"],
        "result_name": result_name,
    }

    return {"uuid": node_uuid, "actions": actions, "router": router,
            "exits": [exit_response, exit_timeout]}


def generate_crm_ops_flow(admins_group_uuid):
    """Generate the complete CRM Operations flow JSON.

    Structure:
    - Auth guard (has_group check)
    - Main menu (L1): Contacts | Groups | Messages | System | Exit
    - Contacts sub-menu: Lookup | Block (with confirm) | Back
    - Groups sub-menu: List | Create | Back
    - Messages sub-menu: Send single | Back
    - System sub-menu: Org info | Channels | Back
    - Timeout on every wait → expiry message → end
    - All webhooks split on Success/Failed
    """

    flow_uuid = u()

    # ── Define stable node UUIDs ──
    N = {
        "auth":           u(),
        "denied":         u(),
        "menu_l1":        u(),
        "timeout":        u(),
        # Contacts
        "contacts_menu":  u(),
        "contacts_ask":   u(),
        "contacts_lookup": u(),
        "contacts_show":  u(),
        "contacts_err":   u(),
        # Groups
        "groups_menu":    u(),
        "groups_list":    u(),
        "groups_show":    u(),
        "groups_err":     u(),
        "groups_ask":     u(),
        "groups_create":  u(),
        "groups_ok":      u(),
        "groups_fail":    u(),
        # System
        "system_menu":    u(),
        "system_org":     u(),
        "system_org_show": u(),
        "system_org_err": u(),
        "system_channels": u(),
        "system_ch_show": u(),
        "system_ch_err":  u(),
        # Messages
        "msg_menu":       u(),
        "msg_ask_urn":    u(),
        "msg_ask_text":   u(),
        "msg_send":       u(),
        "msg_ok":         u(),
        "msg_err":        u(),
    }

    nodes = []

    # ── Node: Auth Guard ──
    exit_ok = _make_exit(N["menu_l1"])
    exit_denied = _make_exit(N["denied"])
    cat_ok = _make_category("Authorized", exit_ok["uuid"])
    cat_denied = _make_category("Denied", exit_denied["uuid"])

    auth_case = {
        "uuid": u(), "type": "has_group",
        "arguments": [admins_group_uuid, "Admins"],
        "category_uuid": cat_ok["uuid"],
    }

    nodes.append({
        "uuid": N["auth"],
        "actions": [_make_action("send_msg", text="🔐 Verifying admin access...")],
        "router": {
            "type": "switch",
            "operand": "@contact.groups",
            "cases": [auth_case],
            "categories": [cat_ok, cat_denied],
            "default_category_uuid": cat_denied["uuid"],
        },
        "exits": [exit_ok, exit_denied],
    })

    # ── Node: Denied ──
    nodes.append(_make_msg_node(N["denied"],
        "🚫 Access denied. You must be in the Admins group to use CRM Operations."))

    # ── Node: Timeout ──
    nodes.append(_make_msg_node(N["timeout"],
        "⏱️ CRM session timed out (5 min inactivity).\n\nType *ops menu* to start again."))

    # ── Node: Main Menu (L1) ──
    nodes.append(_make_wait_menu(
        N["menu_l1"],
        "🗂️ *CRM Operations*\n\nSelect a category:",
        ["👤 Contacts", "📋 Groups", "💬 Messages", "⚙️ System", "❌ Exit"],
        [
            ("Contacts", N["contacts_menu"]),
            ("Groups", N["groups_menu"]),
            ("Messages", N["msg_menu"]),
            ("System", N["system_menu"]),
            ("Exit", None),  # None = terminal
        ],
        timeout_dest=N["timeout"],
        default_dest=N["menu_l1"],
    ))

    # ══════════════════════════════════════════════════════════════════════
    # CONTACTS SUB-MENU
    # ══════════════════════════════════════════════════════════════════════

    nodes.append(_make_wait_menu(
        N["contacts_menu"],
        "👤 *Contacts*\n\n🔍 Lookup — search by phone\n⬅️ Back — return to main menu",
        ["🔍 Lookup", "⬅️ Back"],
        [
            ("Lookup", N["contacts_ask"]),
            ("Back", N["menu_l1"]),
        ],
        timeout_dest=N["timeout"],
        default_dest=N["contacts_menu"],
    ))

    nodes.append(_make_wait_input(
        N["contacts_ask"],
        "👤 Enter a phone number to look up (e.g. +50937145893):",
        "contact_phone",
        dest_uuid=N["contacts_lookup"],
        timeout_dest=N["timeout"],
    ))

    nodes.append(_make_webhook_split(
        N["contacts_lookup"],
        "GET",
        "http://localhost/api/v2/contacts.json?urn=tel:@results.contact_phone.value",
        "contact_result",
        ok_dest=N["contacts_show"],
        fail_dest=N["contacts_err"],
    ))

    nodes.append(_make_msg_node(N["contacts_show"],
        "📋 *Contact Found:*\n\n"
        "Name: @webhook.json.results.0.name\n"
        "UUID: @webhook.json.results.0.uuid\n"
        "Status: @webhook.json.results.0.status\n"
        "Created: @webhook.json.results.0.created_on",
        dest_uuid=N["contacts_menu"],
    ))

    nodes.append(_make_msg_node(N["contacts_err"],
        "⚠️ Lookup failed.\n@results.contact_result.value\n\n"
        "Check the phone format (include country code).",
        dest_uuid=N["contacts_menu"],
    ))

    # ══════════════════════════════════════════════════════════════════════
    # GROUPS SUB-MENU
    # ══════════════════════════════════════════════════════════════════════

    nodes.append(_make_wait_menu(
        N["groups_menu"],
        "📋 *Groups*\n\n📋 List — show all groups\n➕ Create — make a new group\n⬅️ Back",
        ["📋 List", "➕ Create", "⬅️ Back"],
        [
            ("List", N["groups_list"]),
            ("Create", N["groups_ask"]),
            ("Back", N["menu_l1"]),
        ],
        timeout_dest=N["timeout"],
        default_dest=N["groups_menu"],
    ))

    nodes.append(_make_webhook_split(
        N["groups_list"],
        "GET",
        "http://localhost/api/v2/groups.json",
        "groups_result",
        ok_dest=N["groups_show"],
        fail_dest=N["groups_err"],
    ))

    nodes.append(_make_msg_node(N["groups_show"],
        "📋 *Groups:*\n\n@webhook.json",
        dest_uuid=N["groups_menu"],
    ))

    nodes.append(_make_msg_node(N["groups_err"],
        "⚠️ Failed to list groups.\n@results.groups_result.value",
        dest_uuid=N["groups_menu"],
    ))

    nodes.append(_make_wait_input(
        N["groups_ask"],
        "➕ Enter a name for the new group:",
        "new_group_name",
        dest_uuid=N["groups_create"],
        timeout_dest=N["timeout"],
    ))

    nodes.append(_make_webhook_split(
        N["groups_create"],
        "POST",
        "http://localhost/api/v2/groups.json",
        "group_create_result",
        ok_dest=N["groups_ok"],
        fail_dest=N["groups_fail"],
        body='{"name": "@results.new_group_name.value"}',
    ))

    nodes.append(_make_msg_node(N["groups_ok"],
        "✅ Group *@results.new_group_name.value* created!\n\n"
        "UUID: @webhook.json.uuid",
        dest_uuid=N["groups_menu"],
    ))

    nodes.append(_make_msg_node(N["groups_fail"],
        "⚠️ Failed to create group.\n@results.group_create_result.value",
        dest_uuid=N["groups_menu"],
    ))

    # ══════════════════════════════════════════════════════════════════════
    # SYSTEM SUB-MENU
    # ══════════════════════════════════════════════════════════════════════

    nodes.append(_make_wait_menu(
        N["system_menu"],
        "⚙️ *System*\n\nℹ️ Org Info — workspace details\n📡 Channels — channel status\n⬅️ Back",
        ["ℹ️ Org Info", "📡 Channels", "⬅️ Back"],
        [
            ("Org", N["system_org"]),
            ("Channels", N["system_channels"]),
            ("Back", N["menu_l1"]),
        ],
        timeout_dest=N["timeout"],
        default_dest=N["system_menu"],
    ))

    nodes.append(_make_webhook_split(
        N["system_org"],
        "GET",
        "http://localhost/api/v2/org.json",
        "org_result",
        ok_dest=N["system_org_show"],
        fail_dest=N["system_org_err"],
    ))

    nodes.append(_make_msg_node(N["system_org_show"],
        "ℹ️ *Workspace Info:*\n\n@webhook.json",
        dest_uuid=N["system_menu"],
    ))

    nodes.append(_make_msg_node(N["system_org_err"],
        "⚠️ Failed to fetch org info.\n@results.org_result.value",
        dest_uuid=N["system_menu"],
    ))

    nodes.append(_make_webhook_split(
        N["system_channels"],
        "GET",
        "http://localhost/api/v2/channels.json",
        "channels_result",
        ok_dest=N["system_ch_show"],
        fail_dest=N["system_ch_err"],
    ))

    nodes.append(_make_msg_node(N["system_ch_show"],
        "📡 *Channels:*\n\n@webhook.json",
        dest_uuid=N["system_menu"],
    ))

    nodes.append(_make_msg_node(N["system_ch_err"],
        "⚠️ Failed to fetch channels.\n@results.channels_result.value",
        dest_uuid=N["system_menu"],
    ))

    # ══════════════════════════════════════════════════════════════════════
    # MESSAGES SUB-MENU
    # ══════════════════════════════════════════════════════════════════════

    nodes.append(_make_wait_menu(
        N["msg_menu"],
        "💬 *Messages*\n\n✉️ Send — send a message to a contact\n⬅️ Back",
        ["✉️ Send", "⬅️ Back"],
        [
            ("Send", N["msg_ask_urn"]),
            ("Back", N["menu_l1"]),
        ],
        timeout_dest=N["timeout"],
        default_dest=N["msg_menu"],
    ))

    nodes.append(_make_wait_input(
        N["msg_ask_urn"],
        "✉️ Enter the recipient phone number (e.g. +50937145893):",
        "msg_recipient",
        dest_uuid=N["msg_ask_text"],
        timeout_dest=N["timeout"],
    ))

    nodes.append(_make_wait_input(
        N["msg_ask_text"],
        "📝 Type the message text to send:",
        "msg_text",
        dest_uuid=N["msg_send"],
        timeout_dest=N["timeout"],
    ))

    nodes.append(_make_webhook_split(
        N["msg_send"],
        "POST",
        "http://localhost/api/v2/broadcasts.json",
        "msg_send_result",
        ok_dest=N["msg_ok"],
        fail_dest=N["msg_err"],
        body='{"urns": ["tel:@results.msg_recipient.value"], "text": "@results.msg_text.value"}',
    ))

    nodes.append(_make_msg_node(N["msg_ok"],
        "✅ Message sent to @results.msg_recipient.value",
        dest_uuid=N["msg_menu"],
    ))

    nodes.append(_make_msg_node(N["msg_err"],
        "⚠️ Failed to send message.\n@results.msg_send_result.value",
        dest_uuid=N["msg_menu"],
    ))

    # ── Build semantic UI layout ──
    # Layout: Auth spine at top, sub-menus fan out as 4 vertical branches
    #
    #         [auth]──────[denied]
    #           │
    #       [menu_l1]────[timeout]
    #        /    |    \      \
    # Contacts Groups  Msgs  System  (each branch stacks vertically)
    #

    X_CONTACTS = 0
    X_GROUPS   = 450
    X_MSGS     = 900
    X_SYSTEM   = 1350
    X_SPINE    = 600    # Auth + menu center
    ROW        = 220    # vertical spacing

    layout = {
        # ── Auth spine (centered) ──
        N["auth"]:            (X_SPINE, 0),
        N["denied"]:          (X_SPINE + 500, 0),
        N["menu_l1"]:         (X_SPINE, ROW),
        N["timeout"]:         (X_SPINE + 500, ROW),

        # ── Contacts branch (column 1) ──
        N["contacts_menu"]:   (X_CONTACTS, ROW * 3),
        N["contacts_ask"]:    (X_CONTACTS, ROW * 4),
        N["contacts_lookup"]: (X_CONTACTS, ROW * 5),
        N["contacts_show"]:   (X_CONTACTS, ROW * 6),
        N["contacts_err"]:    (X_CONTACTS + 250, ROW * 6),

        # ── Groups branch (column 2) ──
        N["groups_menu"]:     (X_GROUPS, ROW * 3),
        N["groups_list"]:     (X_GROUPS, ROW * 4),
        N["groups_show"]:     (X_GROUPS, ROW * 5),
        N["groups_err"]:      (X_GROUPS + 250, ROW * 5),
        N["groups_ask"]:      (X_GROUPS, ROW * 6),
        N["groups_create"]:   (X_GROUPS, ROW * 7),
        N["groups_ok"]:       (X_GROUPS, ROW * 8),
        N["groups_fail"]:     (X_GROUPS + 250, ROW * 8),

        # ── Messages branch (column 3) ──
        N["msg_menu"]:        (X_MSGS, ROW * 3),
        N["msg_ask_urn"]:     (X_MSGS, ROW * 4),
        N["msg_ask_text"]:    (X_MSGS, ROW * 5),
        N["msg_send"]:        (X_MSGS, ROW * 6),
        N["msg_ok"]:          (X_MSGS, ROW * 7),
        N["msg_err"]:         (X_MSGS + 250, ROW * 7),

        # ── System branch (column 4) ──
        N["system_menu"]:     (X_SYSTEM, ROW * 3),
        N["system_org"]:      (X_SYSTEM, ROW * 4),
        N["system_org_show"]: (X_SYSTEM, ROW * 5),
        N["system_org_err"]:  (X_SYSTEM + 250, ROW * 5),
        N["system_channels"]: (X_SYSTEM, ROW * 6),
        N["system_ch_show"]:  (X_SYSTEM, ROW * 7),
        N["system_ch_err"]:   (X_SYSTEM + 250, ROW * 7),
    }

    ui_nodes = {}
    for node in nodes:
        pos = layout.get(node["uuid"], (0, 0))
        ui_nodes[node["uuid"]] = {
            "position": {"left": pos[0], "top": pos[1]},
            "type": _infer_ui_type(node),
            "config": {},
        }

    flow = {
        "uuid": flow_uuid,
        "name": "CRM Operations",
        "spec_version": "14.4.0",
        "language": "eng",
        "type": "messaging",
        "revision": 1,
        "expire_after_minutes": 10,
        "localization": {},
        "nodes": nodes,
        "_ui": {"nodes": ui_nodes, "editor": "0.156.6"},
    }

    return flow_uuid, flow


def generate_exit_ops_flow():
    """Generate the Exit CRM Ops flow (single node: confirmation message)."""
    flow_uuid = u()

    nodes = [_make_msg_node(u(), "✅ CRM session ended.\n\nType *ops menu* to start again.")]

    flow = {
        "uuid": flow_uuid,
        "name": "Exit CRM Ops",
        "spec_version": "14.4.0",
        "language": "eng",
        "type": "messaging",
        "revision": 1,
        "expire_after_minutes": 5,
        "localization": {},
        "nodes": nodes,
        "_ui": _generate_ui(nodes),
    }

    return flow_uuid, flow


def generate_export(crm_flow, exit_flow):
    """Wrap flows in the RapidPro export format (version 13)."""
    return {
        "version": 13,
        "site": RAPIDPRO_HOST,
        "flows": [crm_flow, exit_flow],
        "campaigns": [],
        "triggers": [],
        "fields": [],
        "groups": [],
    }


# ── Step 4+5: Generate & Import Flows ────────────────────────────────────────

def create_and_import_flows(admins_group_uuid):
    """Generate flow JSON and import it into RapidPro via Django ORM."""
    print("\n── Step 4: Generate Flow JSON ──")

    # Check if CRM Operations flow already exists
    flows = api_get("flows.json", {"type": "message"})
    for f in flows.get("results", []):
        if f["name"] == "CRM Operations":
            print(f"   ✅ CRM Operations flow already exists: {f['uuid']}")
            return f["uuid"]

    crm_uuid, crm_flow = generate_crm_ops_flow(admins_group_uuid)
    exit_uuid, exit_flow = generate_exit_ops_flow()
    export = generate_export(crm_flow, exit_flow)

    # Save JSON for auditability
    json_path = Path(__file__).parent / "crm_ops_flows.json"
    with open(json_path, "w") as f:
        json.dump(export, f, indent=2)
    print(f"   ✅ Flow JSON saved to {json_path}")
    print(f"   📊 CRM Ops: {len(crm_flow['nodes'])} nodes")
    print(f"   📊 Exit Ops: {len(exit_flow['nodes'])} nodes")

    # Import via Django manage.py shell
    print("\n── Step 5: Import Flows into RapidPro ──")

    manage_py = "/opt/iiab/rapidpro/manage.py"
    if not Path(manage_py).exists():
        print(f"   ⚠️  {manage_py} not found. Import manually:")
        print(f"   Go to RapidPro → Settings → Import → upload {json_path}")
        return crm_uuid

    # Build a Python snippet for the Django shell
    import_script = f'''
import json
from temba.orgs.models import Org

org = Org.objects.filter(is_active=True).first()
if not org:
    print("ERROR: No active org found")
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

    venv_python = "/opt/iiab/rapidpro/.venv/bin/python"
    if not Path(venv_python).exists():
        venv_python = "python3"

    result = subprocess.run(
        [venv_python, manage_py, "shell", "-c", import_script],
        capture_output=True, text=True,
        cwd="/opt/iiab/rapidpro",
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "temba.settings"},
        timeout=60,
    )

    if result.returncode != 0 or "IMPORT_ERROR" in result.stdout:
        print(f"   ⚠️  Import failed!")
        print(f"   stdout: {result.stdout.strip()}")
        print(f"   stderr: {result.stderr.strip()[:500]}")
        print(f"\n   Manual fallback:")
        print(f"   Go to RapidPro → Settings → Import → upload {json_path}")
        return crm_uuid

    if "OK" in result.stdout:
        print(f"   ✅ Flows imported successfully!")
    else:
        print(f"   ⚠️  Unexpected output: {result.stdout.strip()[:200]}")
        return crm_uuid

    # Look up the actual UUID assigned by RapidPro (may differ from generated)
    flows = api_get("flows.json", {"type": "message"})
    for f in flows.get("results", []):
        if f["name"] == "CRM Operations":
            crm_uuid = f["uuid"]
            print(f"   📋 CRM Operations UUID: {crm_uuid}")
            break

    return crm_uuid


# ── Step 6: Create exit_ops Keyword Trigger ──────────────────────────────────

def create_exit_trigger():
    """Attempt to create the exit_ops keyword trigger."""
    print("\n── Step 6: exit_ops Keyword Trigger ──")

    # Check if Exit CRM Ops flow exists
    flows = api_get("flows.json", {"type": "message"})
    exit_flow_uuid = None
    for f in flows.get("results", []):
        if f["name"] == "Exit CRM Ops":
            exit_flow_uuid = f["uuid"]
            break

    if not exit_flow_uuid:
        print("   ⚠️  'Exit CRM Ops' flow not found. Trigger creation skipped.")
        return

    # Check if trigger already exists
    try:
        triggers = api_get("triggers.json")
        for t in triggers.get("results", []):
            if t.get("keyword") == "exit_ops":
                print(f"   ✅ exit_ops trigger already exists")
                return
    except Exception:
        pass

    # Try to create trigger
    try:
        api_post("triggers.json", {
            "flow": {"uuid": exit_flow_uuid, "name": "Exit CRM Ops"},
            "trigger_type": "keyword",
            "keyword": "exit_ops",
        })
        print("   ✅ Created exit_ops keyword trigger")
    except Exception as e:
        print(f"   ⚠️  Could not create trigger via API: {e}")
        print(f"   Create manually: RapidPro → Triggers → Keyword 'exit_ops' → 'Exit CRM Ops' flow")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    global API_TOKEN, HEADERS

    print("=" * 60)
    print("  ADR-010: CRM Operations — RapidPro Setup")
    print("=" * 60)

    if not API_TOKEN:
        print("❌ RAPIDPRO_API_TOKEN not set. Source .env first.")
        sys.exit(1)

    HEADERS = {"Authorization": f"Token {API_TOKEN}", "Content-Type": "application/json"}

    print(f"  Host:  {RAPIDPRO_HOST}")
    print(f"  Admin: whatsapp:{ADMIN_PHONE}")

    try:
        setup_api_token_global()
        admins_uuid = setup_admins_group()
        add_admin_to_group(admins_uuid)
        crm_flow_uuid = create_and_import_flows(admins_uuid)
        create_exit_trigger()
    except requests.HTTPError as e:
        print(f"\n❌ API Error: {e}")
        print(f"   Response: {e.response.text}")
        sys.exit(1)

    # Persist UUID
    if crm_flow_uuid:
        _persist_env("CRM_OPS_FLOW_UUID", crm_flow_uuid,
                     "CRM Ops — main flow UUID (auto-generated by setup_crm_ops.py)")

    print("\n" + "=" * 60)
    print("  Setup complete!")
    print()
    print("  NEXT STEPS:")
    print("  1. Run: source .env && bash scripts/scan_call_llm.sh")
    print("     (establishes baseline backup + governance check)")
    print("  2. Restart: sudo systemctl restart rapidpro-mailroom ai-gateway rivebot")
    print("  3. Send 'ops menu' via WhatsApp to test the CRM flow")
    print("=" * 60)


if __name__ == "__main__":
    main()
