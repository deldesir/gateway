"""Reusable RapidPro flow building blocks.

Extracted from setup_crm_ops.py (ADR-010) for reuse across flow generators.
Each function returns a goflow-spec node dict ready for import via org.import_app.

Node types:
  - _make_msg_node:        send_msg → single exit
  - _make_webhook_split:   call_webhook → Success/Failed router
  - _make_wait_menu:       send_msg(quick_replies) → wait → switch on @input.text
  - _make_wait_input:      send_msg(prompt) → wait → catch-all category
  - _make_enter_flow_node: enter_flow (non-terminal) → exit when child completes
  - _make_confirm_guard:   typed CONFIRM gate for destructive operations

All UUIDs are generated fresh via uuid4().
"""

from uuid import uuid4


def u():
    """Generate a fresh UUID string."""
    return str(uuid4())


# ── Primitives ───────────────────────────────────────────────────────────────

def _make_action(type_, **fields):
    return {"uuid": u(), "type": type_, **fields}


def _make_exit(dest_uuid=None):
    return {"uuid": u(), "destination_uuid": dest_uuid}


def _make_category(name, exit_uuid):
    return {"uuid": u(), "name": name, "exit_uuid": exit_uuid}


# ── Composite Nodes ──────────────────────────────────────────────────────────

def make_msg_node(node_uuid, text, dest_uuid=None, quick_replies=None):
    """Simple send_msg node with one exit."""
    actions = [_make_action("send_msg", text=text,
                            **({} if not quick_replies else {"quick_replies": quick_replies}))]
    return {"uuid": node_uuid, "actions": actions, "exits": [_make_exit(dest_uuid)]}


def make_webhook_split(node_uuid, method, url, result_name, ok_dest, fail_dest,
                       body="", headers=None):
    """call_webhook → switch on @results.<result_name>.category (Success/Failed).

    Args:
        headers: dict of HTTP headers. Goflow expressions (@globals.xxx) are resolved.
    """
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    action = _make_action("call_webhook", method=method, url=url,
                          headers=hdrs, body=body, result_name=result_name)
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


def make_wait_menu(node_uuid, prompt, choices, timeout_dest,
                   default_dest=None, timeout_seconds=300):
    """Menu: send_msg(quick_replies) → wait → switch on @input.text.

    ADR-011 Finding 11: Courier auto-converts >3 quick_replies to WhatsApp
    List Messages (handler.go:474-628). ≤3 render as native buttons.
    Courier sends the Title field back as @input.text (handler.go:221-223).

    choices: list of (label, dest_uuid) pairs. Max 10 (goflow limit).
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


def make_wait_input(node_uuid, prompt, result_name, dest_uuid, timeout_dest,
                    timeout_seconds=300):
    """Prompt + wait for free-text input → single catch-all category."""
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


def make_enter_flow_node(node_uuid, flow_uuid, flow_name, return_dest):
    """enter_flow (non-terminal) → when child completes, go to return_dest."""
    action = _make_action("enter_flow",
                          flow={"uuid": flow_uuid, "name": flow_name},
                          terminal=False)
    return {"uuid": node_uuid, "actions": [action], "exits": [_make_exit(return_dest)]}


# ── UI & Flow Envelope ───────────────────────────────────────────────────────

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
        operand = router.get("operand", "")
        if "@contact.groups" in operand:
            return "split_by_groups"
        return "split_by_expression"
    return "execute_actions"


def build_ui(nodes, layout):
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
    """Build a complete goflow-spec flow dict."""
    return {
        "uuid": uuid, "name": name,
        "spec_version": "14.4.0", "language": "eng", "type": "messaging",
        "revision": 1, "expire_after_minutes": expire,
        "localization": {}, "nodes": nodes,
        "_ui": build_ui(nodes, layout),
    }


def make_export(*flows):
    """Wrap flows in a RapidPro export envelope."""
    return {
        "version": "13",
        "site": "http://localhost",
        "flows": list(flows),
        "campaigns": [], "triggers": [], "fields": [], "groups": [],
    }
