#!/usr/bin/env python3
"""
ADR-013: Konex Support L1 Flow

Creates a RapidPro flow for the Konex Support persona with:
  - Ticket wizard (describe issue → categorize → confirm → submit)
  - FAQ browser
  - Account/profile info

Trigger: "support" keyword

Usage:
    cd /opt/iiab/ai-gateway && source .env
    python scripts/setup_konex_support_flow.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from flow_builders import (
    u, ROW,
    _make_msg_node, _make_noop_node, _make_wait_menu, _make_wait_input,
    make_flow, make_export, import_flows, setup_keyword_trigger,
)


def generate_support_flow():
    flow_uuid = u()
    N = {
        "entry_guard": u(),
        "menu": u(), "timeout": u(), "exit": u(),
        # Ticket wizard
        "ticket_describe": u(), "ticket_category": u(),
        "ticket_confirm": u(), "ticket_ok": u(), "ticket_cancel": u(),
        # FAQ
        "faq_menu": u(), "faq_billing": u(), "faq_speed": u(), "faq_reset": u(),
        # Profile
        "profile": u(),
    }
    nodes = []

    # Entry guard — absorbs keyword trigger double-fire
    nodes.append(_make_noop_node(N["entry_guard"], N["menu"]))

    # ── Main Menu ──
    nodes.append(_make_wait_menu(N["menu"],
        "🔧 *Konex Support*\n\nHow can I help?",
        [
            ("🎫 Open Ticket", N["ticket_describe"]),
            ("❓ FAQ", N["faq_menu"]),
            ("📋 My Profile", N["profile"]),
            ("❌ Exit", N["exit"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))
    nodes.append(_make_msg_node(N["timeout"],
        "⏱️ Support session timed out.\n\nType *support* to start again."))
    nodes.append(_make_msg_node(N["exit"],
        "✅ Support session ended.\n\nType *support* anytime you need help."))

    # ══════════════════════════════════════════════════════════════
    #  Ticket Wizard
    # ══════════════════════════════════════════════════════════════

    # Step 1: Describe issue
    nodes.append(_make_wait_input(N["ticket_describe"],
        "🎫 *Open Support Ticket*\n\n"
        "Describe your issue in a few words:",
        "ticket_description", N["ticket_category"], N["timeout"],
        timeout_seconds=600))

    # Step 2: Categorize
    nodes.append(_make_wait_menu(N["ticket_category"],
        "📂 *Category*\n\n"
        "What type of issue is this?",
        [
            ("📶 Connectivity", N["ticket_confirm"]),
            ("💰 Billing", N["ticket_confirm"]),
            ("📱 Device", N["ticket_confirm"]),
            ("📦 Service", N["ticket_confirm"]),
            ("❓ Other", N["ticket_confirm"]),
            ("⬅️ Cancel", N["menu"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["ticket_category"],
    ))

    # Step 3: Confirm
    cat_key = f"menu_{N['ticket_category'][:8]}"
    nodes.append(_make_wait_menu(N["ticket_confirm"],
        "📝 *Review Ticket*\n\n"
        "Issue: @results.ticket_description.value\n"
        f"Category: @results.{cat_key}.value\n"
        "Contact: @contact.name (@contact.urns.0)\n\n"
        "Submit this ticket?",
        [
            ("✅ Submit", N["ticket_ok"]),
            ("❌ Cancel", N["ticket_cancel"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["menu"],
    ))

    nodes.append(_make_msg_node(N["ticket_ok"],
        "✅ *Ticket Submitted!*\n\n"
        "Issue: @results.ticket_description.value\n"
        f"Category: @results.{cat_key}.value\n"
        "Status: 🟡 Open\n\n"
        "A support agent will contact you shortly.\n"
        "Reference: @contact.uuid",
        dest_uuid=N["menu"]))

    nodes.append(_make_msg_node(N["ticket_cancel"],
        "❌ Ticket cancelled. No issue was submitted.",
        dest_uuid=N["menu"]))

    # ══════════════════════════════════════════════════════════════
    #  FAQ
    # ══════════════════════════════════════════════════════════════

    nodes.append(_make_wait_menu(N["faq_menu"],
        "❓ *Frequently Asked Questions*\n\n"
        "Select a topic:",
        [
            ("💰 Billing & Payments", N["faq_billing"]),
            ("📶 Slow Internet", N["faq_speed"]),
            ("🔄 Reset Account", N["faq_reset"]),
            ("⬅️ Back", N["menu"]),
        ],
        timeout_dest=N["timeout"], default_dest=N["faq_menu"],
    ))

    nodes.append(_make_msg_node(N["faq_billing"],
        "💰 *Billing & Payments*\n\n"
        "• Payments are due on the 1st of each month\n"
        "• Accepted: MonCash, NatCash, bank transfer\n"
        "• Late payment: service suspended after 5 days\n"
        "• Refunds: contact support within 48h\n\n"
        "Need more help? Open a ticket.",
        dest_uuid=N["faq_menu"]))

    nodes.append(_make_msg_node(N["faq_speed"],
        "📶 *Slow Internet*\n\n"
        "Try these steps:\n"
        "1. Restart your router\n"
        "2. Check if other devices have the same issue\n"
        "3. Run a speed test (fast.com)\n"
        "4. Check for outages in your area\n\n"
        "Still slow? Open a ticket with your speed test results.",
        dest_uuid=N["faq_menu"]))

    nodes.append(_make_msg_node(N["faq_reset"],
        "🔄 *Reset Account*\n\n"
        "To reset your account password:\n"
        "1. Go to konex.ht/reset\n"
        "2. Enter your phone number\n"
        "3. Follow the SMS instructions\n\n"
        "If you can't reset, open a ticket.",
        dest_uuid=N["faq_menu"]))

    # ── Profile ──
    nodes.append(_make_msg_node(N["profile"],
        "📋 *Your Profile*\n\n"
        "Name: @contact.name\n"
        "Number: @contact.urns.0\n"
        "Plan: —\n"
        "Status: Active\n\n"
        "To update your info, open a ticket.",
        dest_uuid=N["menu"]))

    layout = {
        N["entry_guard"]:      (300, -ROW),
        N["menu"]:             (300, 0),
        N["timeout"]:          (700, 0),
        N["exit"]:             (700, ROW),
        N["ticket_describe"]:  (0, ROW*2),
        N["ticket_category"]:  (0, ROW*3),
        N["ticket_confirm"]:   (0, ROW*4),
        N["ticket_ok"]:        (0, ROW*5),
        N["ticket_cancel"]:    (300, ROW*5),
        N["faq_menu"]:         (500, ROW*2),
        N["faq_billing"]:      (500, ROW*3),
        N["faq_speed"]:        (800, ROW*3),
        N["faq_reset"]:        (500, ROW*4),
        N["profile"]:          (800, ROW*2),
    }
    return flow_uuid, make_flow(flow_uuid, "Konex Support Menu", nodes, layout)


def main():
    print("=" * 60)
    print("  ADR-013: Konex Support L1 Flow Deployment")
    print("=" * 60)

    print("\n── Step 1: Generate Flow ──")
    flow_uuid, flow = generate_support_flow()
    print(f"   📊 {flow['name']:20s} — {len(flow['nodes']):2d} nodes")

    print("\n── Step 2: Import Flow ──")
    export = make_export(flow)
    json_path = Path(__file__).parent.parent / "exports" / "konex_support_flow.json"
    if not import_flows(export, json_path):
        print("   ❌ Import failed.")
        sys.exit(1)

    print("\n── Step 3: Create 'support' Keyword Trigger ──")
    setup_keyword_trigger("support", "Konex Support Menu")

    print("\n" + "=" * 60)
    print("  Konex Support L1 deployment complete!")
    print(f"  1 flow, {len(flow['nodes'])} nodes")
    print("  TRIGGER: Type 'support' via WhatsApp")
    print("  RESTART: sudo systemctl restart rapidpro-mailroom")
    print("=" * 60)


if __name__ == "__main__":
    main()
