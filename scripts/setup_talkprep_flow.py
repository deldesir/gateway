#!/usr/bin/env python3
"""
ADR-013: TalkPrep L1 Menu Flow

Creates a RapidPro flow that provides a guided WhatsApp List Message
menu for the TalkPrep talk-preparation pipeline (6 stages, 14 tools).

Flow structure:
  Router → Main Menu (List Message, 8 items)
    📋 My Talks        → webhook → display → menu
    📚 Publications     → webhook → display → menu
    📑 Browse Topics    → ask pub → webhook → display → menu
    ➕ Import Talk      → ask name → webhook → display → menu
    🎯 Select Talk      → ask ID → webhook → display → menu
    ✏️ Work on Talk     → enter sub-flow (5 AI tools) → menu
    📚 Study Tools      → enter sub-flow (Anki + SiYuan) → menu
    💰 Cost Report      → webhook → display → menu
    ❌ Exit

The "Work on Talk" sub-flow:
    Create Revision → ask audience → webhook → display
    Develop Section → ask section → webhook → display
    Evaluate Talk   → webhook → display
    Rehearsal       → webhook → display
    Export          → webhook → display

Usage:
    cd /opt/iiab/ai-gateway && source .env
    python scripts/setup_talkprep_flow.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from flow_builders import (
    u, ROW, GATEWAY_WEBHOOK_URL,
    _make_msg_node, _make_noop_node, _make_wait_menu, _make_wait_input,
    _make_webhook_split, _make_enter_flow_node,
    make_flow, make_export, import_flows, setup_keyword_trigger,
    ensure_gateway_key_global,
)

GW = GATEWAY_WEBHOOK_URL


# ══════════════════════════════════════════════════════════════════════════════
#  Sub-flow: Work on Talk (AI tools)
# ══════════════════════════════════════════════════════════════════════════════

def generate_work_flow():
    flow_uuid = u()
    N = {
        "menu": u(), "timeout": u(), "back": u(),
        # Create Revision
        "rev_ask": u(), "rev_wh": u(), "rev_ok": u(), "rev_err": u(),
        # Develop Section
        "dev_ask": u(), "dev_wh": u(), "dev_ok": u(), "dev_err": u(),
        # Evaluate
        "eval_wh": u(), "eval_ok": u(), "eval_err": u(),
        # Rehearsal
        "reh_wh": u(), "reh_ok": u(), "reh_err": u(),
        # Export
        "exp_wh": u(), "exp_ok": u(), "exp_err": u(),
    }
    nodes = []

    nodes.append(_make_wait_menu(N["menu"],
        "✏️ *Work on Talk*\n\nSelect an operation:",
        [
            ("Create Revision", N["rev_ask"]),
            ("Develop Section", N["dev_ask"]),
            ("Evaluate Talk", N["eval_wh"]),
            ("Rehearsal", N["reh_wh"]),
            ("Export Manuscript", N["exp_wh"]),
            ("⬅️ Back", N["back"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))
    nodes.append(_make_msg_node(N["timeout"], "⏱️ Work session timed out."))
    nodes.append(_make_msg_node(N["back"], "⬅️ Returning to TalkPrep menu..."))

    # ── Create Revision ──
    nodes.append(_make_wait_input(N["rev_ask"],
        "📝 *Create Revision*\n\nEnter the audience and style:\n"
        "_Example: youth talk, encouraging tone_",
        "revision_spec", N["rev_wh"], N["timeout"]))
    nodes.append(_make_webhook_split(N["rev_wh"],
        "POST", f"{GW}/v1/tools/create_revision",
        "rev_result", N["rev_ok"], N["rev_err"],
        body='{"_args": ["@results.revision_spec.value"]}',
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["rev_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["rev_err"],
        "⚠️ Could not create revision. Make sure you have an active talk selected.",
        dest_uuid=N["menu"]))

    # ── Develop Section ──
    nodes.append(_make_wait_input(N["dev_ask"],
        "📖 *Develop Section*\n\nEnter the section name:\n"
        "_Example: Introduction_",
        "section_name", N["dev_wh"], N["timeout"]))
    nodes.append(_make_webhook_split(N["dev_wh"],
        "POST", f"{GW}/v1/tools/develop_section",
        "dev_result", N["dev_ok"], N["dev_err"],
        body='{"_args": ["@results.section_name.value"]}',
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["dev_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["dev_err"],
        "⚠️ Could not develop section. Create a revision first.",
        dest_uuid=N["menu"]))

    # ── Evaluate ──
    nodes.append(_make_webhook_split(N["eval_wh"],
        "GET", f"{GW}/v1/tools/evaluate_talk",
        "eval_result", N["eval_ok"], N["eval_err"],
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["eval_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["eval_err"],
        "⚠️ Could not evaluate. Make sure you have developed sections first.",
        dest_uuid=N["menu"]))

    # ── Rehearsal ──
    nodes.append(_make_webhook_split(N["reh_wh"],
        "GET", f"{GW}/v1/tools/rehearsal_cue",
        "reh_result", N["reh_ok"], N["reh_err"],
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["reh_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["reh_err"],
        "⚠️ Could not generate rehearsal tips.",
        dest_uuid=N["menu"]))

    # ── Export ──
    nodes.append(_make_webhook_split(N["exp_wh"],
        "GET", f"{GW}/v1/tools/export_talk_summary",
        "exp_result", N["exp_ok"], N["exp_err"],
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["exp_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["exp_err"],
        "⚠️ Could not export. Develop and evaluate first.",
        dest_uuid=N["menu"]))

    layout = {
        N["menu"]:     (300, 0),     N["timeout"]: (700, 0),     N["back"]: (700, ROW),
        N["rev_ask"]:  (0, ROW*2),   N["rev_wh"]:  (0, ROW*3),
        N["rev_ok"]:   (0, ROW*4),   N["rev_err"]: (300, ROW*4),
        N["dev_ask"]:  (500, ROW*2), N["dev_wh"]:  (500, ROW*3),
        N["dev_ok"]:   (500, ROW*4), N["dev_err"]: (800, ROW*4),
        N["eval_wh"]:  (0, ROW*5),   N["eval_ok"]: (0, ROW*6),   N["eval_err"]: (300, ROW*6),
        N["reh_wh"]:   (500, ROW*5), N["reh_ok"]:  (500, ROW*6), N["reh_err"]: (800, ROW*6),
        N["exp_wh"]:   (0, ROW*7),   N["exp_ok"]:  (0, ROW*8),   N["exp_err"]: (300, ROW*8),
    }
    return flow_uuid, make_flow(flow_uuid, "TalkPrep Work", nodes, layout)


# ══════════════════════════════════════════════════════════════════════════════
#  Sub-flow: Study Tools (Anki + SiYuan)
# ══════════════════════════════════════════════════════════════════════════════

def generate_study_flow():
    flow_uuid = u()
    N = {
        "menu": u(), "timeout": u(), "back": u(),
        "anki_wh": u(), "anki_ok": u(), "anki_err": u(),
        "siyuan_wh": u(), "siyuan_ok": u(), "siyuan_err": u(),
    }
    nodes = []

    nodes.append(_make_wait_menu(N["menu"],
        "📚 *Study Tools*\n\nSelect a tool:",
        [
            ("🃏 Anki Deck", N["anki_wh"]),
            ("📓 Push to SiYuan", N["siyuan_wh"]),
            ("⬅️ Back", N["back"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))
    nodes.append(_make_msg_node(N["timeout"], "⏱️ Study tools timed out."))
    nodes.append(_make_msg_node(N["back"], "⬅️ Returning to TalkPrep menu..."))

    # Anki
    nodes.append(_make_webhook_split(N["anki_wh"],
        "GET", f"{GW}/v1/tools/generate_anki_deck",
        "anki_result", N["anki_ok"], N["anki_err"],
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["anki_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["anki_err"],
        "⚠️ Could not generate Anki deck.", dest_uuid=N["menu"]))

    # SiYuan
    nodes.append(_make_webhook_split(N["siyuan_wh"],
        "GET", f"{GW}/v1/tools/push_to_siyuan",
        "siyuan_result", N["siyuan_ok"], N["siyuan_err"],
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["siyuan_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["siyuan_err"],
        "⚠️ Could not push to SiYuan.", dest_uuid=N["menu"]))

    layout = {
        N["menu"]: (300, 0), N["timeout"]: (700, 0), N["back"]: (700, ROW),
        N["anki_wh"]: (0, ROW*2), N["anki_ok"]: (0, ROW*3), N["anki_err"]: (300, ROW*3),
        N["siyuan_wh"]: (500, ROW*2), N["siyuan_ok"]: (500, ROW*3), N["siyuan_err"]: (800, ROW*3),
    }
    return flow_uuid, make_flow(flow_uuid, "TalkPrep Study", nodes, layout)


# ══════════════════════════════════════════════════════════════════════════════
#  Main Router Flow
# ══════════════════════════════════════════════════════════════════════════════

def generate_router_flow(work_uuid, study_uuid):
    flow_uuid = u()
    N = {
        "entry_guard": u(),
        "menu": u(), "timeout": u(), "exit": u(),
        # Single-shot webhooks
        "talks_wh": u(), "talks_ok": u(), "talks_err": u(),
        "pubs_wh": u(), "pubs_ok": u(), "pubs_err": u(),
        "cost_wh": u(), "cost_ok": u(), "cost_err": u(),
        # Parameterized
        "topics_ask": u(), "topics_wh": u(), "topics_ok": u(), "topics_err": u(),
        "import_ask": u(), "import_wh": u(), "import_ok": u(), "import_err": u(),
        "select_ask": u(), "select_wh": u(), "select_ok": u(), "select_err": u(),
        # Sub-flows
        "enter_work": u(), "enter_study": u(),
    }
    nodes = []

    # Entry guard — absorbs keyword trigger double-fire
    nodes.append(_make_noop_node(N["entry_guard"], N["menu"]))

    # Main menu — 9 items → WhatsApp List Message
    nodes.append(_make_wait_menu(N["menu"],
        "📚 *TalkPrep*\n\nSelect an option:",
        [
            ("📋 My Talks", N["talks_wh"]),
            ("📚 Publications", N["pubs_wh"]),
            ("📑 Browse Topics", N["topics_ask"]),
            ("➕ Import Talk", N["import_ask"]),
            ("🎯 Select Talk", N["select_ask"]),
            ("✏️ Work on Talk", N["enter_work"]),
            ("📚 Study Tools", N["enter_study"]),
            ("💰 Cost Report", N["cost_wh"]),
            ("❌ Exit", N["exit"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))
    nodes.append(_make_msg_node(N["timeout"],
        "⏱️ TalkPrep session timed out.\n\nType *prep* to start again."))
    nodes.append(_make_msg_node(N["exit"],
        "✅ TalkPrep session ended.\n\nType *prep* to start again."))

    # ── My Talks ──
    nodes.append(_make_webhook_split(N["talks_wh"],
        "GET", f"{GW}/v1/tools/talkmaster_status",
        "talks_result", N["talks_ok"], N["talks_err"],
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["talks_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["talks_err"],
        "⚠️ Could not fetch talks.", dest_uuid=N["menu"]))

    # ── Publications ──
    nodes.append(_make_webhook_split(N["pubs_wh"],
        "GET", f"{GW}/v1/tools/list_publications",
        "pubs_result", N["pubs_ok"], N["pubs_err"],
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["pubs_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["pubs_err"],
        "⚠️ Could not fetch publications.", dest_uuid=N["menu"]))

    # ── Cost Report ──
    nodes.append(_make_webhook_split(N["cost_wh"],
        "GET", f"{GW}/v1/tools/cost_report",
        "cost_result", N["cost_ok"], N["cost_err"],
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["cost_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["cost_err"],
        "⚠️ Could not fetch cost report.", dest_uuid=N["menu"]))

    # ── Browse Topics (parameterized) ──
    nodes.append(_make_wait_input(N["topics_ask"],
        "📑 *Browse Topics*\n\nEnter a publication name (or part of it):",
        "topic_pub", N["topics_wh"], N["timeout"]))
    nodes.append(_make_webhook_split(N["topics_wh"],
        "POST", f"{GW}/v1/tools/list_topics",
        "topics_result", N["topics_ok"], N["topics_err"],
        body='{"_args": ["@results.topic_pub.value"]}',
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["topics_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["topics_err"],
        "⚠️ No topics found for that publication.", dest_uuid=N["menu"]))

    # ── Import Talk ──
    nodes.append(_make_wait_input(N["import_ask"],
        "➕ *Import Talk*\n\nEnter the talk name or number:",
        "talk_name", N["import_wh"], N["timeout"]))
    nodes.append(_make_webhook_split(N["import_wh"],
        "POST", f"{GW}/v1/tools/import_talk",
        "import_result", N["import_ok"], N["import_err"],
        body='{"_args": ["@results.talk_name.value"]}',
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["import_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["import_err"],
        "⚠️ Could not import talk. Check the name/number.", dest_uuid=N["menu"]))

    # ── Select Talk ──
    nodes.append(_make_wait_input(N["select_ask"],
        "🎯 *Select Talk*\n\nEnter the talk ID number:",
        "talk_id", N["select_wh"], N["timeout"]))
    nodes.append(_make_webhook_split(N["select_wh"],
        "POST", f"{GW}/v1/tools/select_active_talk",
        "select_result", N["select_ok"], N["select_err"],
        body='{"_args": ["@results.talk_id.value"]}',
        auth_type="gateway"))
    nodes.append(_make_msg_node(N["select_ok"],
        "@webhook.json.result", dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["select_err"],
        "⚠️ Talk not found. Use *My Talks* to see available IDs.",
        dest_uuid=N["menu"]))

    # ── Sub-flow entries ──
    nodes.append(_make_enter_flow_node(N["enter_work"], work_uuid,
        "TalkPrep Work", return_dest=N["menu"]))
    nodes.append(_make_enter_flow_node(N["enter_study"], study_uuid,
        "TalkPrep Study", return_dest=N["menu"]))

    layout = {
        N["entry_guard"]: (400, -ROW),
        N["menu"]:       (400, 0),       N["timeout"]:    (800, 0),
        N["exit"]:       (800, ROW),
        N["talks_wh"]:   (0, ROW*2),     N["talks_ok"]:   (0, ROW*3),
        N["talks_err"]:  (250, ROW*3),
        N["pubs_wh"]:    (400, ROW*2),   N["pubs_ok"]:    (400, ROW*3),
        N["pubs_err"]:   (650, ROW*3),
        N["cost_wh"]:    (800, ROW*2),   N["cost_ok"]:    (800, ROW*3),
        N["cost_err"]:   (1050, ROW*3),
        N["topics_ask"]: (0, ROW*4),     N["topics_wh"]:  (0, ROW*5),
        N["topics_ok"]:  (0, ROW*6),     N["topics_err"]: (250, ROW*6),
        N["import_ask"]: (400, ROW*4),   N["import_wh"]:  (400, ROW*5),
        N["import_ok"]:  (400, ROW*6),   N["import_err"]: (650, ROW*6),
        N["select_ask"]: (800, ROW*4),   N["select_wh"]:  (800, ROW*5),
        N["select_ok"]:  (800, ROW*6),   N["select_err"]: (1050, ROW*6),
        N["enter_work"]: (200, ROW*7),   N["enter_study"]: (600, ROW*7),
    }
    return flow_uuid, make_flow(flow_uuid, "TalkPrep Menu", nodes, layout)


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  ADR-013: TalkPrep L1 Flow Deployment")
    print("=" * 60)

    # Step 1: Ensure gateway_key global
    print("\n── Step 1: Gateway Key Global ──")
    ensure_gateway_key_global()

    # Step 2: Generate flows
    print("\n── Step 2: Generate Flows ──")
    work_uuid, work_flow = generate_work_flow()
    study_uuid, study_flow = generate_study_flow()
    router_uuid, router_flow = generate_router_flow(work_uuid, study_uuid)

    all_flows = [router_flow, work_flow, study_flow]
    total_nodes = sum(len(f["nodes"]) for f in all_flows)
    for f in all_flows:
        print(f"   📊 {f['name']:20s} — {len(f['nodes']):2d} nodes")
    print(f"   {'─' * 30}")
    print(f"   📊 {'TOTAL':20s} — {total_nodes:2d} nodes across {len(all_flows)} flows")

    # Step 3: Import
    print("\n── Step 3: Import Flows ──")
    export = make_export(*all_flows)
    json_path = Path(__file__).parent / "talkprep_flows.json"
    if not import_flows(export, json_path):
        print("   ❌ Import failed.")
        sys.exit(1)

    # Step 4: Keyword trigger
    print("\n── Step 4: Create 'prep' Keyword Trigger ──")
    setup_keyword_trigger("prep", "TalkPrep Menu")

    print("\n" + "=" * 60)
    print("  TalkPrep L1 deployment complete!")
    print(f"  {len(all_flows)} flows, {total_nodes} nodes")
    print()
    print("  TRIGGER: Type 'prep' via WhatsApp")
    print("  RESTART: sudo systemctl restart rapidpro-mailroom")
    print("=" * 60)


if __name__ == "__main__":
    main()
