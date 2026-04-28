"""
Shared RapidPro flow-building primitives.

Extracted from setup_crm_ops.py (ADR-010) so all L1 flow scripts
use the same node/router/webhook helpers.
"""

import os
import sys
import json
import subprocess
from uuid import uuid4
from pathlib import Path


def u():
    return str(uuid4())


ROW = 220

# ── Webhook hosts ────────────────────────────────────────────────────────────
# Mailroom blocks localhost (SSRF protection), so webhooks must use a routable host.

WEBHOOK_HOST = os.getenv("RAPIDPRO_WEBHOOK_HOST", "https://garantie.boutique")
RAPIDPRO_API_URL = f"{WEBHOOK_HOST}/api/v2"

# Gateway tools are proxied via Nginx at /ai/ on the public host.
# If not proxied, set GATEWAY_WEBHOOK_URL to a routable address.
GATEWAY_WEBHOOK_URL = os.getenv("GATEWAY_WEBHOOK_URL", f"{WEBHOOK_HOST}/ai")


# ══════════════════════════════════════════════════════════════════════════════
#  Node builders
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


def _make_noop_node(node_uuid, dest_uuid):
    """Silent guard node — absorbs keyword trigger double-fires.

    Mailroom can fire a keyword-triggered flow's first node twice when the
    contact re-enters the flow (previous session expiry + new trigger).
    This node produces no visible output, so duplicates are harmless.
    """
    action = _make_action("set_run_result", name="entry_guard", value="1")
    return {"uuid": node_uuid, "actions": [action], "exits": [_make_exit(dest_uuid)]}


def _make_webhook_split(node_uuid, method, url, result_name, ok_dest, fail_dest,
                        body="", extra_headers=None, auth_type="rapidpro"):
    """Build a webhook node that splits on Success/Failed.

    auth_type:
        "rapidpro" — uses Token @globals.api_token (default)
        "gateway"  — uses X-API-Key @globals.gateway_key + X-User-Id
        "none"     — no auth headers
    """
    headers = {"Accept": "application/json"}
    if auth_type == "rapidpro":
        headers["Authorization"] = "Token @globals.api_token"
    elif auth_type == "gateway":
        headers["X-API-Key"] = "@globals.gateway_key"
        headers["X-User-Id"] = "@contact.urns.0"
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

    >3 items auto-convert to WhatsApp List Message via Courier.
    choices: list of (label, dest_uuid) pairs.
    """
    quick_replies = [text for text, _dest in choices]
    actions = [_make_action("send_msg", text=prompt.rstrip(),
                            quick_replies=quick_replies)]
    exits, categories, cases = [], [], []
    for text, dest in choices:
        ex = _make_exit(dest)
        cat = _make_category(text, ex["uuid"])
        case = {"uuid": u(), "type": "has_only_phrase",
                "arguments": [text], "category_uuid": cat["uuid"]}
        exits.append(ex); categories.append(cat); cases.append(case)
    ex_timeout = _make_exit(timeout_dest)
    cat_timeout = _make_category("No Response", ex_timeout["uuid"])
    exits.append(ex_timeout); categories.append(cat_timeout)
    ex_other = _make_exit(default_dest or exits[0]["destination_uuid"])
    cat_other = _make_category("Other", ex_other["uuid"])
    exits.append(ex_other); categories.append(cat_other)
    router = {
        "type": "switch", "operand": "@input.text",
        "wait": {"type": "msg", "timeout": {"seconds": timeout_seconds,
                 "category_uuid": cat_timeout["uuid"]}},
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
        "wait": {"type": "msg", "timeout": {"seconds": timeout_seconds,
                 "category_uuid": cat_timeout["uuid"]}},
        "cases": [], "categories": [cat_resp, cat_timeout],
        "default_category_uuid": cat_resp["uuid"],
        "result_name": result_name,
    }
    return {"uuid": node_uuid, "actions": actions, "router": router,
            "exits": [exit_resp, exit_timeout]}


def _make_enter_flow_node(node_uuid, flow_uuid, flow_name, return_dest):
    action = _make_action("enter_flow",
                          flow={"uuid": flow_uuid, "name": flow_name},
                          terminal=False)
    return {"uuid": node_uuid, "actions": [action], "exits": [_make_exit(return_dest)]}


# ══════════════════════════════════════════════════════════════════════════════
#  Flow / Export builders
# ══════════════════════════════════════════════════════════════════════════════

def _infer_ui_type(node):
    actions = [a["type"] for a in node.get("actions", [])]
    router = node.get("router", {})
    if "wait" in router:
        return "wait_for_response"
    if "enter_flow" in actions:
        return "split_by_subflow"
    if "call_webhook" in actions:
        return "split_by_webhook"
    if router.get("type") == "switch":
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


def make_flow(uuid, name, nodes, layout, expire=30):
    return {
        "uuid": uuid, "name": name,
        "spec_version": "14.4.0", "language": "eng", "type": "messaging",
        "revision": 1, "expire_after_minutes": expire,
        "localization": {}, "nodes": nodes,
        "_ui": _build_ui(nodes, layout),
    }


def make_export(*flows):
    return {
        "version": "13", "site": "http://localhost",
        "flows": list(flows),
        "campaigns": [], "triggers": [], "fields": [], "groups": [],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Import helpers
# ══════════════════════════════════════════════════════════════════════════════

MANAGE_PY = "/opt/iiab/rapidpro/manage.py"
VENV_PYTHON = "/opt/iiab/rapidpro/.venv/bin/python"


def import_flows(export_json, json_path):
    """Import flows into RapidPro via Django ORM."""
    with open(json_path, "w") as f:
        json.dump(export_json, f, indent=2)
    print(f"   📁 Saved export to {json_path}")

    venv = VENV_PYTHON if Path(VENV_PYTHON).exists() else "python3"
    script = f'''
import json
from temba.orgs.models import Org
org = Org.objects.filter(is_active=True).first()
if not org:
    print("ERROR: No active org"); exit(1)
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
        [venv, MANAGE_PY, "shell", "-c", script],
        capture_output=True, text=True,
        cwd="/opt/iiab/rapidpro",
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "temba.settings"},
        timeout=60,
    )
    stdout = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    if "OK" in stdout:
        print("   ✅ Flows imported successfully!")
        return True
    print(f"   ⚠️  Import: {stdout}")
    if result.stderr.strip():
        print(f"   stderr: {result.stderr.strip()[:300]}")
    return False


def setup_keyword_trigger(keyword, flow_name):
    """Create a keyword trigger via Django ORM."""
    venv = VENV_PYTHON if Path(VENV_PYTHON).exists() else "python3"
    script = f'''
from temba.triggers.models import Trigger
from temba.flows.models import Flow
from temba.orgs.models import Org
from django.db.models import Max
org = Org.objects.filter(is_active=True).first()
user = org.get_owner()
flow = Flow.objects.filter(name="{flow_name}", is_active=True).first()
if not flow:
    print("SKIP: {flow_name} flow not found")
else:
    existing = Trigger.objects.filter(
        org=org, trigger_type="K", is_active=True, is_archived=False,
        keywords__contains=["{keyword}"]
    )
    if existing.exists():
        print(f"EXISTS: id={{existing.first().id}}")
    else:
        max_p = Trigger.objects.filter(org=org).aggregate(Max("priority"))["priority__max"] or 0
        t = Trigger.objects.create(
            org=org, trigger_type="K", keywords=["{keyword}"], match_type="F",
            flow=flow, created_by=user, modified_by=user, priority=max_p + 1,
        )
        print(f"CREATED: id={{t.id}}")
'''
    result = subprocess.run(
        [venv, MANAGE_PY, "shell", "-c", script],
        capture_output=True, text=True,
        cwd="/opt/iiab/rapidpro",
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "temba.settings"},
        timeout=30,
    )
    stdout = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    if "CREATED" in stdout:
        print(f"   ✅ Created '{keyword}' keyword trigger → {flow_name}")
    elif "EXISTS" in stdout:
        print(f"   ✅ '{keyword}' trigger already exists")
    else:
        print(f"   ⚠️  Trigger: {stdout}")


def ensure_gateway_key_global():
    """Create the gateway_key RapidPro global for webhook auth."""
    import requests
    api_token = os.getenv("RAPIDPRO_API_TOKEN", "")
    gateway_key = os.getenv("GATEWAY_INTERNAL_KEY", "")
    if not api_token or not gateway_key:
        print("   ⚠️  RAPIDPRO_API_TOKEN or GATEWAY_INTERNAL_KEY not set")
        return

    headers = {"Authorization": f"Token {api_token}"}
    resp = requests.get(f"{RAPIDPRO_API_URL}/globals.json", headers=headers)
    for g in resp.json().get("results", []):
        if g["key"] == "gateway_key":
            print("   ✅ gateway_key global already exists")
            return
    requests.post(f"{RAPIDPRO_API_URL}/globals.json", headers=headers,
                  json={"name": "Gateway Key", "key": "gateway_key", "value": gateway_key})
    print("   ✅ Created gateway_key global")
