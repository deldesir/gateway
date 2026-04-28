#!/usr/bin/env python3
"""
ADR-014: Social-Code L1 Drill Flow (Hermes-native)

Creates a RapidPro flow with WhatsApp List Messages and Quick Reply buttons
to navigate and run Social-Code drills via the Gateway's sim_* tools.

Flow structure:
  1. App Picker (List Message, 10 apps)
  2. Difficulty Picker (Quick Reply, 4 levels)
  3. Scenario (webhook → sim_get_scenario)
  4. Round Loop:
     a. Wait for user response
     b. Grade (webhook → sim_grade_response + sim_update_mood + sim_update_trust)
     c. Show scorecard
     d. Round Actions (Quick Reply: ▶️ Next / 🔄 Replay / 🏠 Menu)
  5. Final Summary

Usage:
    cd /opt/iiab/ai-gateway && source .env
    python scripts/setup_social_code_flow.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from flow_builders import (
    u, ROW, GATEWAY_WEBHOOK_URL,
    _make_msg_node, _make_noop_node, _make_wait_menu, _make_wait_input,
    _make_webhook_split, _make_action, _make_exit, _make_category,
    make_flow, make_export, import_flows, setup_keyword_trigger,
    ensure_gateway_key_global,
)

GW = GATEWAY_WEBHOOK_URL

# ── Social-Code apps and their display names ─────────────────────────────────
APPS = [
    ("small_talk",   "🗣️ Small Talk"),
    ("wit_gym",      "🧠 Wit Gym"),
    ("debate_club",  "⚔️ Debate Club"),
    ("deep_talk",    "🌊 Deep Talk"),
    ("empathy_lab",  "💚 Empathy Lab"),
    ("story_teller", "📖 Story Teller"),
    ("negotiator",   "🤝 Negotiator"),
    ("conductor",    "🎵 Conductor"),
    ("magnet",       "🧲 Magnet"),
    ("archive",      "📦 Archive"),
]

DIFFICULTIES = [
    (1, "🟢 Basic"),
    (2, "🟡 Intermediate"),
    (3, "🟠 Advanced"),
    (4, "🔴 Mastery"),
]

TOTAL_ROUNDS = 5


# ══════════════════════════════════════════════════════════════════════════════
#  Difficulty-to-int mapping helper (webhook body uses the label text)
# ══════════════════════════════════════════════════════════════════════════════

DIFFICULTY_MAP = {label: level for level, label in DIFFICULTIES}


# ══════════════════════════════════════════════════════════════════════════════
#  Flow generation
# ══════════════════════════════════════════════════════════════════════════════

def generate_drill_flow():
    flow_uuid = u()

    # ── UUIDs for all nodes ──
    N = {
        # Entry guard (absorbs keyword trigger double-fire)
        "entry_guard":    u(),

        # Menu phase
        "app_menu":       u(),
        "diff_menu":      u(),
        "timeout":        u(),
        "exit":           u(),

        # Language picker
        "lang_menu":      u(),
        "lang_wh":        u(),
        "lang_ok":        u(),
        "lang_err":       u(),

        # Free-text handler ("Other" input on menus)
        "freetext_wh":    u(),
        "freetext_ok":    u(),

        # Session summary
        "summary_wh":     u(),
        "summary_ok":     u(),

        # AI toggle
        "ai_toggle_wh":   u(),
        "ai_toggle_ok":   u(),
        "ai_toggle_err":  u(),

        # Scenario loading
        "scenario_wh":    u(),
        "scenario_ok":    u(),
        "scenario_err":   u(),

        # Round loop
        "round_prompt":   u(),
        "round_wait":     u(),
        "grade_wh":       u(),
        "grade_ok":       u(),
        "grade_err":      u(),

        # Round actions
        "round_action":   u(),

        # Round counter
        "inc_round":      u(),
        "check_done":     u(),

        # Completion
        "finished":       u(),
        "finish_action":  u(),
    }
    nodes = []

    # ════════════════════════════════════════════════════════════════════════
    #  Entry Guard — absorbs keyword trigger double-fire (silent)
    # ════════════════════════════════════════════════════════════════════════

    nodes.append(_make_noop_node(N["entry_guard"], N["app_menu"]))

    # ════════════════════════════════════════════════════════════════════════
    #  Phase 1: App Selection (WhatsApp List Message — 10+ items)
    # ════════════════════════════════════════════════════════════════════════

    nodes.append(_make_wait_menu(N["app_menu"],
        "🎯 *Social-Code Training*\n\n"
        "Choose a drill app to practice your social skills:",
        [(label, N["diff_menu"]) for _slug, label in APPS],
        timeout_dest=N["timeout"], default_dest=N["freetext_wh"],
    ))

    nodes.append(_make_msg_node(N["timeout"],
        "⏱️ Training session timed out.\n\nType *train* to start again."))

    nodes.append(_make_msg_node(N["exit"],
        "✅ Training session ended.\n\nType *train* anytime to practice again!"))

    # ════════════════════════════════════════════════════════════════════════
    #  Phase 2: Difficulty Selection (Quick Reply — 4 items + Back)
    # ════════════════════════════════════════════════════════════════════════

    nodes.append(_make_wait_menu(N["diff_menu"],
        "⚙️ *Select Difficulty*\n\n"
        "Choose your training level:",
        [(label, N["scenario_wh"]) for _level, label in DIFFICULTIES] +
        [
            ("🤖 AI Grading", N["ai_toggle_wh"]),
            ("🌐 Language", N["lang_menu"]),
            ("📊 Summary", N["summary_wh"]),
            ("⬅️ Back", N["app_menu"]),
            ("❌ Exit", N["exit"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["freetext_wh"],
    ))

    # ════════════════════════════════════════════════════════════════════════
    #  AI Grading Toggle
    # ════════════════════════════════════════════════════════════════════════

    nodes.append(_make_webhook_split(N["ai_toggle_wh"],
        "POST", f"{GW}/v1/tools/sim_toggle_ai",
        "ai_toggle_result", N["ai_toggle_ok"], N["ai_toggle_err"],
        body='{}',
        auth_type="gateway"))

    nodes.append(_make_msg_node(N["ai_toggle_ok"],
        "@webhook.json.result", dest_uuid=N["diff_menu"]))
    nodes.append(_make_msg_node(N["ai_toggle_err"],
        "⚠️ Could not toggle AI grading.", dest_uuid=N["diff_menu"]))

    # ════════════════════════════════════════════════════════════════════════
    #  Language Picker (Quick Reply — 4 languages)
    # ════════════════════════════════════════════════════════════════════════

    nodes.append(_make_wait_menu(N["lang_menu"],
        "🌐 *Select Language*\n\n"
        "Choose your preferred language for scenarios and feedback:",
        [
            ("English", N["lang_wh"]),
            ("Kreyol", N["lang_wh"]),
            ("Espanol", N["lang_wh"]),
            ("Francais", N["lang_wh"]),
            ("⬅️ Back", N["diff_menu"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["lang_menu"],
    ))

    lang_result_key = f"menu_{N['lang_menu'][:8]}"
    nodes.append(_make_webhook_split(N["lang_wh"],
        "POST", f"{GW}/v1/tools/sim_set_language",
        "lang_result", N["lang_ok"], N["lang_err"],
        body='{"language": "@results.' + lang_result_key + '.value"}',
        auth_type="gateway"))

    nodes.append(_make_msg_node(N["lang_ok"],
        "@webhook.json.result", dest_uuid=N["diff_menu"]))
    nodes.append(_make_msg_node(N["lang_err"],
        "⚠️ Could not change language.", dest_uuid=N["diff_menu"]))

    # ════════════════════════════════════════════════════════════════════════
    #  Free-Text Handler ("Other" input → RiveBot → Hermes)
    # ════════════════════════════════════════════════════════════════════════

    nodes.append(_make_webhook_split(N["freetext_wh"],
        "POST", f"{GW}/v1/tools/sim_freetext",
        "freetext", N["freetext_ok"], N["freetext_ok"],
        body='{"user_input": "@input.text"}',
        auth_type="gateway"))

    nodes.append(_make_msg_node(N["freetext_ok"],
        "@webhook.json.result", dest_uuid=N["app_menu"]))

    # ════════════════════════════════════════════════════════════════════════
    #  Session Summary (webhook → sim_session_summary)
    # ════════════════════════════════════════════════════════════════════════

    nodes.append(_make_webhook_split(N["summary_wh"],
        "GET", f"{GW}/v1/tools/sim_session_summary",
        "summary", N["summary_ok"], N["summary_ok"],
        auth_type="gateway"))

    nodes.append(_make_msg_node(N["summary_ok"],
        "@webhook.json.result", dest_uuid=N["diff_menu"]))

    # ════════════════════════════════════════════════════════════════════════
    #  Phase 3: Load Scenario (webhook → sim_get_scenario)
    # ════════════════════════════════════════════════════════════════════════

    # Map the selected difficulty label to a number via expression.
    # The webhook sends the difficulty level to sim_get_scenario.
    # We use the flow result variable to pass the difficulty.
    diff_result_key = f"menu_{N['diff_menu'][:8]}"
    app_result_key = f"menu_{N['app_menu'][:8]}"

    nodes.append(_make_webhook_split(N["scenario_wh"],
        "POST", f"{GW}/v1/tools/sim_get_scenario",
        "scenario", N["scenario_ok"], N["scenario_err"],
        body='{"difficulty": @(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE('
             f'@results.{diff_result_key}.value, '
             '"🟢 Basic", "1"), '
             '"🟡 Intermediate", "2"), '
             '"🟠 Advanced", "3"), '
             '"🔴 Mastery", "4"))}',
        auth_type="gateway"))

    nodes.append(_make_msg_node(N["scenario_ok"],
        "🎭 *@results." + app_result_key + ".value*\n\n"
        "@webhook.json.result\n\n"
        "Reply with your response — be natural!",
        dest_uuid=N["round_wait"]))

    nodes.append(_make_msg_node(N["scenario_err"],
        "⚠️ Could not load scenario. The golden set may not be available for this app.\n\n"
        "Tip: Small Talk, Empathy Lab, and Negotiator have the richest scenario banks.",
        dest_uuid=N["app_menu"]))

    # ════════════════════════════════════════════════════════════════════════
    #  Phase 4: Drill Round Loop
    # ════════════════════════════════════════════════════════════════════════

    # Wait for user's response (no extra prompt — scenario_ok already invites)
    _exit_resp = _make_exit(N["grade_wh"])
    _exit_timeout = _make_exit(N["timeout"])
    _cat_resp = _make_category("All Responses", _exit_resp["uuid"])
    _cat_timeout = _make_category("No Response", _exit_timeout["uuid"])
    nodes.append({
        "uuid": N["round_wait"],
        "actions": [],   # No send_msg — scenario display already has CTA
        "router": {
            "type": "switch", "operand": "@input.text",
            "wait": {"type": "msg", "timeout": {"seconds": 600,
                     "category_uuid": _cat_timeout["uuid"]}},
            "cases": [], "categories": [_cat_resp, _cat_timeout],
            "default_category_uuid": _cat_resp["uuid"],
            "result_name": "drill_response",
        },
        "exits": [_exit_resp, _exit_timeout],
    })

    # Grade the response — success goes directly to round_action
    # which shows feedback + action buttons in one message.
    nodes.append(_make_webhook_split(N["grade_wh"],
        "POST", f"{GW}/v1/tools/sim_drill_grade",
        "grade", N["round_action"], N["grade_err"],
        body='{"user_input": "@results.drill_response.value"}',
        auth_type="gateway"))

    nodes.append(_make_msg_node(N["grade_err"],
        "⚠️ Grading unavailable. Let's continue.",
        dest_uuid=N["round_action"]))

    # Feedback + round actions in one message (Quick Reply)
    nodes.append(_make_wait_menu(N["round_action"],
        "@webhook.json.result",
        [
            ("▶️ Next Round",   N["scenario_wh"]),
            ("🔄 Same Level",   N["scenario_wh"]),
            ("📊 Change Level", N["diff_menu"]),
            ("🏠 Back to Menu", N["app_menu"]),
            ("❌ Exit",         N["exit"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["freetext_wh"],
        timeout_seconds=600,
    ))

    # ════════════════════════════════════════════════════════════════════════
    #  Layout
    # ════════════════════════════════════════════════════════════════════════

    layout = {
        N["entry_guard"]:   (400, -ROW),
        N["app_menu"]:      (400, 0),
        N["timeout"]:       (800, 0),
        N["exit"]:          (800, ROW),
        N["freetext_wh"]:   (0, ROW),
        N["freetext_ok"]:   (0, ROW * 2),
        N["lang_menu"]:     (800, ROW * 2),
        N["lang_wh"]:       (800, ROW * 3),
        N["lang_ok"]:       (800, ROW * 4),
        N["lang_err"]:      (1050, ROW * 4),
        N["summary_wh"]:    (1050, ROW * 2),
        N["summary_ok"]:    (1050, ROW * 3),
        N["diff_menu"]:     (400, ROW * 3),
        N["scenario_wh"]:   (400, ROW * 4),
        N["scenario_ok"]:   (400, ROW * 5),
        N["scenario_err"]:  (700, ROW * 5),
        N["round_wait"]:    (400, ROW * 6),
        N["grade_wh"]:      (400, ROW * 7),
        N["grade_ok"]:      (400, ROW * 8),
        N["grade_err"]:     (700, ROW * 8),
        N["round_action"]:  (400, ROW * 9),
    }

    return flow_uuid, make_flow(flow_uuid, "Social-Code Training", nodes, layout, expire=60)


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  ADR-014: Social-Code L1 Flow Deployment (Hermes-native)")
    print("=" * 60)

    print("\n── Step 1: Gateway Key Global ──")
    ensure_gateway_key_global()

    print("\n── Step 2: Generate Flow ──")
    flow_uuid, flow = generate_drill_flow()
    print(f"   📊 {flow['name']:20s} — {len(flow['nodes']):2d} nodes")

    print("\n── Step 3: Import Flow ──")
    export = make_export(flow)
    json_path = Path(__file__).parent.parent / "exports" / "social_code_flow.json"
    if not import_flows(export, json_path):
        print("   ❌ Import failed.")
        sys.exit(1)

    print("\n── Step 4: Create 'train' Keyword Trigger ──")
    setup_keyword_trigger("train", "Social-Code Training")

    print("\n" + "=" * 60)
    print("  Social-Code L1 deployment complete!")
    print(f"  1 flow, {len(flow['nodes'])} nodes")
    print()
    print("  Flow structure:")
    print("    📱 App Picker (10 apps — WhatsApp List Message)")
    print("    ⚙️  Difficulty Picker (4 levels — Quick Reply)")
    print("    🎭 Scenario (webhook → sim_get_scenario)")
    print("    💬 User Response (free text input)")
    print("    📊 Grading (webhook → sim_grade_response)")
    print("    ▶️  Round Actions (Quick Reply: Next / Replay / Change / Menu)")
    print()
    print("  APPS: " + ", ".join(s for s, _ in APPS))
    print("  TRIGGER: Type 'train' via WhatsApp")
    print("  RESTART: sudo systemctl restart rapidpro-mailroom")
    print("=" * 60)


if __name__ == "__main__":
    main()
