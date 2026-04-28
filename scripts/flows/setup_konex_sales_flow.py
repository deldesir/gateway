#!/usr/bin/env python3
"""
ADR-013: Konex Sales L1 Flow

Creates a RapidPro flow for the Konex Sales persona with:
  - Plan browser (List Message with plan details)
  - Upgrade wizard (pick plan → confirm → process)
  - Promo check
  - Account info

Trigger: "sales" keyword

Usage:
    cd /opt/iiab/ai-gateway && source .env
    python scripts/setup_konex_sales_flow.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from flow_builders import (
    u, ROW,
    _make_action, _make_exit, _make_category,
    _make_msg_node, _make_noop_node, _make_wait_menu, _make_wait_input,
    make_flow, make_export, import_flows, setup_keyword_trigger,
)


def generate_sales_flow():
    flow_uuid = u()
    N = {
        "entry_guard": u(),
        "menu": u(), "timeout": u(), "exit": u(),
        # Plans
        "plans": u(),
        # Upgrade wizard
        "upgrade_pick": u(), "upgrade_confirm": u(), "upgrade_ok": u(), "upgrade_cancel": u(),
        # Promo
        "promo": u(),
        # Account
        "account": u(),
    }
    nodes = []

    # Entry guard — absorbs keyword trigger double-fire
    nodes.append(_make_noop_node(N["entry_guard"], N["menu"]))

    # ── Main Menu ──
    nodes.append(_make_wait_menu(N["menu"],
        "👋 *Konex Sales*\n\nHow can I help you today?",
        [
            ("📱 View Plans", N["plans"]),
            ("🚀 Upgrade", N["upgrade_pick"]),
            ("🎉 Promotions", N["promo"]),
            ("📋 My Account", N["account"]),
            ("❌ Exit", N["exit"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))
    nodes.append(_make_msg_node(N["timeout"],
        "⏱️ Sales session timed out.\n\nType *sales* to start again."))
    nodes.append(_make_msg_node(N["exit"],
        "✅ Thanks for visiting Konex Sales!\n\nType *sales* anytime."))

    # ── Plans ──
    nodes.append(_make_msg_node(N["plans"],
        "📱 *Konex Plans*\n\n"
        "• *Basic* — 250 HTG/mwa (1GB, 50 min)\n"
        "• *Standard* — 500 HTG/mwa (5GB, unlimited min)\n"
        "• *Premium* — 1000 HTG/mwa (unlimited data + min)\n\n"
        "Tap *Upgrade* to change your plan!",
        dest_uuid=N["menu"]))

    # ── Upgrade: pick plan ──
    nodes.append(_make_wait_menu(N["upgrade_pick"],
        "🚀 *Upgrade Plan*\n\nWhich plan would you like?",
        [
            ("Basic — 250 HTG", N["upgrade_confirm"]),
            ("Standard — 500 HTG", N["upgrade_confirm"]),
            ("Premium — 1000 HTG", N["upgrade_confirm"]),
            ("⬅️ Back", N["menu"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["upgrade_pick"],
    ))

    # ── Upgrade: confirm ──
    result_key = f"menu_{N['upgrade_pick'][:8]}"
    nodes.append(_make_wait_menu(N["upgrade_confirm"],
        "⚠️ *Confirm Upgrade*\n\n"
        f"You selected: *@results.{result_key}.value*\n\n"
        "Proceed with the upgrade?",
        [
            ("✅ Confirm", N["upgrade_ok"]),
            ("❌ Cancel", N["upgrade_cancel"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))

    nodes.append(_make_msg_node(N["upgrade_ok"],
        f"✅ *Upgrade request submitted!*\n\n"
        f"Plan: @results.{result_key}.value\n"
        "A representative will confirm your upgrade shortly.\n\n"
        "Questions? Type *talk to support*.",
        dest_uuid=N["menu"]))
    nodes.append(_make_msg_node(N["upgrade_cancel"],
        "❌ Upgrade cancelled.\n\nNo changes made to your plan.",
        dest_uuid=N["menu"]))

    # ── Promotions ──
    nodes.append(_make_msg_node(N["promo"],
        "🎉 *Current Promotions*\n\n"
        "• 🆕 *New Customer* — First month free on Standard+\n"
        "• 📞 *Referral Bonus* — Get 100 HTG credit per referral\n"
        "• 📱 *Weekend Double* — 2x data on weekends (Premium)\n\n"
        "Type *upgrade* to take advantage of these offers!",
        dest_uuid=N["menu"]))

    # ── Account ──
    nodes.append(_make_msg_node(N["account"],
        "📋 *Your Account*\n\n"
        "Name: @contact.name\n"
        "Number: @contact.urns.0\n"
        "Plan: —\n\n"
        "For detailed account info, type *talk to support*.",
        dest_uuid=N["menu"]))

    layout = {
        N["entry_guard"]:     (300, -ROW),
        N["menu"]:            (300, 0),
        N["timeout"]:         (700, 0),
        N["exit"]:            (700, ROW),
        N["plans"]:           (0, ROW*2),
        N["upgrade_pick"]:    (400, ROW*2),
        N["upgrade_confirm"]: (400, ROW*3),
        N["upgrade_ok"]:      (300, ROW*4),
        N["upgrade_cancel"]:  (600, ROW*4),
        N["promo"]:           (800, ROW*2),
        N["account"]:         (0, ROW*3),
    }
    return flow_uuid, make_flow(flow_uuid, "Konex Sales Menu", nodes, layout)


def main():
    print("=" * 60)
    print("  ADR-013: Konex Sales L1 Flow Deployment")
    print("=" * 60)

    print("\n── Step 1: Generate Flow ──")
    flow_uuid, flow = generate_sales_flow()
    print(f"   📊 {flow['name']:20s} — {len(flow['nodes']):2d} nodes")

    print("\n── Step 2: Import Flow ──")
    export = make_export(flow)
    json_path = Path(__file__).parent.parent / "exports" / "konex_sales_flow.json"
    if not import_flows(export, json_path):
        print("   ❌ Import failed.")
        sys.exit(1)

    print("\n── Step 3: Create 'sales' Keyword Trigger ──")
    setup_keyword_trigger("sales", "Konex Sales Menu")

    print("\n" + "=" * 60)
    print("  Konex Sales L1 deployment complete!")
    print(f"  1 flow, {len(flow['nodes'])} nodes")
    print("  TRIGGER: Type 'sales' via WhatsApp")
    print("  RESTART: sudo systemctl restart rapidpro-mailroom")
    print("=" * 60)


if __name__ == "__main__":
    main()
