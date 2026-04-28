"""ADR-012 Phase 3: Organized Menu flow generator.

Generates a RapidPro flow for the Organized scheduling persona with
sub-menu architecture:

  Organized Menu (main)
  ├─ 📅 Meetings → This Week · Next Week · Material · Attendance · ⬅️ Back
  ├─ 👤 Personal → My Schedule · My Group · My Report · ⬅️ Back
  ├─ 🔍 Search   → ask name → webhook: search_persons → display
  ├─ 📆 Events   → webhook: get_events → display
  └─ ❌ Exit

All data operations use call_webhook to the organized backend's /query
endpoint, authenticated via @globals.organized_webhook_secret.
"""

from .builders import (
    u, make_msg_node, make_webhook_split, make_wait_menu,
    make_wait_input, make_flow,
)

ROW = 220


def _wh_headers():
    return {
        "Content-Type": "application/json",
        "X-Webhook-Secret": "@globals.organized_webhook_secret",
    }


def generate_organized_menu(webhook_base_url: str):
    """Generate the Organized Menu flow with sub-menus.

    Returns:
        (flow_uuid, flow_dict)
    """
    WH = f"{webhook_base_url}/v3/webhooks/query"
    flow_uuid = u()

    # ── Node UUIDs ────────────────────────────────────────────────────────
    N = {
        # Main menu
        "main_menu": u(), "timeout": u(), "exit": u(),
        # Meetings sub-menu
        "meetings_menu": u(),
        "tw_wh": u(), "tw_ok": u(), "tw_err": u(),
        "nw_wh": u(), "nw_ok": u(), "nw_err": u(),
        "mat_wh": u(), "mat_ok": u(), "mat_err": u(),
        "att_wh": u(), "att_ok": u(), "att_err": u(),
        # Personal sub-menu
        "personal_menu": u(),
        "my_wh": u(), "my_ok": u(), "my_err": u(),
        "grp_wh": u(), "grp_ok": u(), "grp_err": u(),
        "rpt_wh": u(), "rpt_ok": u(), "rpt_err": u(),
        # Search (top-level)
        "search_ask": u(), "search_wh": u(), "search_ok": u(), "search_err": u(),
        # Events (top-level)
        "events_wh": u(), "events_ok": u(), "events_err": u(),
    }

    nodes = []

    # ═══════════════════════════════════════════════════════════════════════
    #  MAIN MENU
    # ═══════════════════════════════════════════════════════════════════════

    nodes.append(make_wait_menu(
        N["main_menu"],
        "📋 *Organized*\n\nSelect a category:",
        [
            ("📅 Meetings", N["meetings_menu"]),
            ("👤 Personal", N["personal_menu"]),
            ("🔍 Search", N["search_ask"]),
            ("📆 Events", N["events_wh"]),
            ("❌ Exit", N["exit"]),
        ],
        timeout_dest=N["timeout"],
        default_dest=N["main_menu"],
    ))

    nodes.append(make_msg_node(N["timeout"],
        "⏱️ Session timed out. Type *menu* to start again."))
    nodes.append(make_msg_node(N["exit"],
        "✅ Session ended. Type *menu* to start again."))

    # ═══════════════════════════════════════════════════════════════════════
    #  MEETINGS SUB-MENU
    # ═══════════════════════════════════════════════════════════════════════

    nodes.append(make_wait_menu(
        N["meetings_menu"],
        "📅 *Meetings*\n\nSelect an option:",
        [
            ("This Week", N["tw_wh"]),
            ("Next Week", N["nw_wh"]),
            ("📖 Material", N["mat_wh"]),
            ("📊 Attendance", N["att_wh"]),
            ("⬅️ Back", N["main_menu"]),
        ],
        timeout_dest=N["timeout"],
        default_dest=N["meetings_menu"],
    ))

    # This Week
    _S = "@webhook.json.schedules"
    nodes.append(make_webhook_split(
        N["tw_wh"], "POST", WH, "this_week",
        N["tw_ok"], N["tw_err"],
        body='{"action": "get_schedule"}',
        headers=_wh_headers(),
    ))
    nodes.append(make_msg_node(N["tw_ok"],
        "📅 *This Week's Schedule*\n\n"
        f"📆 Week of {_S}.0.weekOf\n\n"
        f"📖 *Midweek:*\n"
        f"• Chairman: {_S}.0.midweek_meeting.chairman.main_hall.0.name\n"
        f"• Prayer: {_S}.0.midweek_meeting.opening_prayer.0.name\n"
        f"• TGW Talk: {_S}.0.midweek_meeting.tgw_talk.0.name\n"
        f"• Bible Reading: {_S}.0.midweek_meeting.tgw_bible_reading.main_hall.0.name\n"
        f"• CBS Conductor: {_S}.0.midweek_meeting.lc_cbs.conductor.0.name\n\n"
        f"☀️ *Weekend:*\n"
        f"• Chairman: {_S}.0.weekend_meeting.chairman.0.name\n"
        f"• Speaker: {_S}.0.weekend_meeting.speaker.part_1.0.name\n"
        f"• WT Conductor: {_S}.0.weekend_meeting.wt_study.conductor.0.name\n"
        f"• WT Reader: {_S}.0.weekend_meeting.wt_study.reader.0.name",
        dest_uuid=N["meetings_menu"]))
    nodes.append(make_msg_node(N["tw_err"],
        "⚠️ Could not fetch this week's schedule.",
        dest_uuid=N["meetings_menu"]))

    # Next Week
    nodes.append(make_webhook_split(
        N["nw_wh"], "POST", WH, "next_week",
        N["nw_ok"], N["nw_err"],
        body='{"action": "get_schedule", '
             '"week_of": "@(format_date(datetime_add(now(), 7, \\"D\\"), \\"2006/01/02\\"))"}',
        headers=_wh_headers(),
    ))
    nodes.append(make_msg_node(N["nw_ok"],
        "📅 *Next Week's Schedule*\n\n"
        f"📆 Week of {_S}.0.weekOf\n\n"
        f"📖 *Midweek:*\n"
        f"• Chairman: {_S}.0.midweek_meeting.chairman.main_hall.0.name\n"
        f"• Prayer: {_S}.0.midweek_meeting.opening_prayer.0.name\n\n"
        f"☀️ *Weekend:*\n"
        f"• Chairman: {_S}.0.weekend_meeting.chairman.0.name\n"
        f"• Speaker: {_S}.0.weekend_meeting.speaker.part_1.0.name",
        dest_uuid=N["meetings_menu"]))
    nodes.append(make_msg_node(N["nw_err"],
        "⚠️ No schedule found for next week.",
        dest_uuid=N["meetings_menu"]))

    # Material
    _M = "@webhook.json.sources"
    nodes.append(make_webhook_split(
        N["mat_wh"], "POST", WH, "material",
        N["mat_ok"], N["mat_err"],
        body='{"action": "get_sources"}',
        headers=_wh_headers(),
    ))
    nodes.append(make_msg_node(N["mat_ok"],
        f"📖 *Meeting Material — {_M}.0.weekOf*\n\n"
        f"📕 Bible Reading: {_M}.0.bible_reading\n"
        f"💎 TGW Talk: {_M}.0.tgw_talk\n"
        f"📗 CBS: {_M}.0.cbs\n"
        f"📙 WT Study: {_M}.0.wt_study",
        dest_uuid=N["meetings_menu"]))
    nodes.append(make_msg_node(N["mat_err"],
        "⚠️ Could not fetch meeting material.",
        dest_uuid=N["meetings_menu"]))

    # Attendance
    _AT = "@webhook.json.attendance"
    nodes.append(make_webhook_split(
        N["att_wh"], "POST", WH, "attendance",
        N["att_ok"], N["att_err"],
        body='{"action": "get_attendance"}',
        headers=_wh_headers(),
    ))
    nodes.append(make_msg_node(N["att_ok"],
        f"📊 *Meeting Attendance*\n\n"
        f"📅 *{_AT}.0.month*\n"
        f"  📖 Midweek avg: {_AT}.0.avg_midweek\n"
        f"  ☀️ Weekend avg: {_AT}.0.avg_weekend\n\n"
        f"📅 *{_AT}.1.month*\n"
        f"  📖 Midweek avg: {_AT}.1.avg_midweek\n"
        f"  ☀️ Weekend avg: {_AT}.1.avg_weekend",
        dest_uuid=N["meetings_menu"]))
    nodes.append(make_msg_node(N["att_err"],
        "⚠️ Could not fetch attendance data.",
        dest_uuid=N["meetings_menu"]))

    # ═══════════════════════════════════════════════════════════════════════
    #  PERSONAL SUB-MENU
    # ═══════════════════════════════════════════════════════════════════════

    nodes.append(make_wait_menu(
        N["personal_menu"],
        "👤 *Personal*\n\nSelect an option:",
        [
            ("My Schedule", N["my_wh"]),
            ("👥 My Group", N["grp_wh"]),
            ("📋 My Report", N["rpt_wh"]),
            ("⬅️ Back", N["main_menu"]),
        ],
        timeout_dest=N["timeout"],
        default_dest=N["personal_menu"],
    ))

    # My Schedule
    _A = "@webhook.json.assignments"
    nodes.append(make_webhook_split(
        N["my_wh"], "POST", WH, "my_assignments",
        N["my_ok"], N["my_err"],
        body='{"action": "get_person_assignments", '
             '"person_name": "@contact.name"}',
        headers=_wh_headers(),
    ))
    nodes.append(make_msg_node(N["my_ok"],
        "👤 *Your Assignments (@contact.name):*\n\n"
        f"• {_A}.0.week_of — {_A}.0.type\n"
        f"• {_A}.1.week_of — {_A}.1.type\n"
        f"• {_A}.2.week_of — {_A}.2.type\n"
        f"• {_A}.3.week_of — {_A}.3.type\n"
        f"• {_A}.4.week_of — {_A}.4.type",
        dest_uuid=N["personal_menu"]))
    nodes.append(make_msg_node(N["my_err"],
        "⚠️ Could not fetch your assignments.\n\n"
        "Make sure your contact name matches the Organized app.",
        dest_uuid=N["personal_menu"]))

    # My Group
    _G = "@webhook.json.groups"
    nodes.append(make_webhook_split(
        N["grp_wh"], "POST", WH, "my_group",
        N["grp_ok"], N["grp_err"],
        body='{"action": "get_field_groups", '
             '"person_name": "@contact.name"}',
        headers=_wh_headers(),
    ))
    nodes.append(make_msg_node(N["grp_ok"],
        f"👥 *{_G}.0.name*\n\n"
        f"• {_G}.0.members.0.name {_G}.0.members.0.role\n"
        f"• {_G}.0.members.1.name {_G}.0.members.1.role\n"
        f"• {_G}.0.members.2.name {_G}.0.members.2.role\n"
        f"• {_G}.0.members.3.name {_G}.0.members.3.role",
        dest_uuid=N["personal_menu"]))
    nodes.append(make_msg_node(N["grp_err"],
        "⚠️ Could not find your field service group.",
        dest_uuid=N["personal_menu"]))

    # My Report
    _R = "@webhook.json.reports"
    nodes.append(make_webhook_split(
        N["rpt_wh"], "POST", WH, "my_report",
        N["rpt_ok"], N["rpt_err"],
        body='{"action": "get_field_report", '
             '"person_name": "@contact.name"}',
        headers=_wh_headers(),
    ))
    nodes.append(make_msg_node(N["rpt_ok"],
        f"📋 *Field Service Report (@contact.name):*\n\n"
        f"✅ *{_R}.0.month* — {_R}.0.hours h · {_R}.0.bible_studies studies\n"
        f"✅ *{_R}.1.month* — {_R}.1.hours h · {_R}.1.bible_studies studies",
        dest_uuid=N["personal_menu"]))
    nodes.append(make_msg_node(N["rpt_err"],
        "⚠️ Could not fetch your field service report.",
        dest_uuid=N["personal_menu"]))

    # ═══════════════════════════════════════════════════════════════════════
    #  SEARCH (top-level)
    # ═══════════════════════════════════════════════════════════════════════

    nodes.append(make_wait_input(
        N["search_ask"],
        "🔍 Enter the person's name to search:",
        "search_name", N["search_wh"], N["timeout"],
    ))

    _P = "@webhook.json.persons"
    nodes.append(make_webhook_split(
        N["search_wh"], "POST", WH, "person_search",
        N["search_ok"], N["search_err"],
        body='{"action": "search_persons", '
             '"query": "@results.search_name.value"}',
        headers=_wh_headers(),
    ))
    nodes.append(make_msg_node(N["search_ok"],
        "🔍 *Results for \"@results.search_name.value\":*\n\n"
        f"• {_P}.0.display_name\n"
        f"• {_P}.1.display_name\n"
        f"• {_P}.2.display_name",
        dest_uuid=N["main_menu"]))
    nodes.append(make_msg_node(N["search_err"],
        "⚠️ Search failed. Try again.",
        dest_uuid=N["main_menu"]))

    # ═══════════════════════════════════════════════════════════════════════
    #  EVENTS (top-level)
    # ═══════════════════════════════════════════════════════════════════════

    _E = "@webhook.json.events"
    nodes.append(make_webhook_split(
        N["events_wh"], "POST", WH, "events",
        N["events_ok"], N["events_err"],
        body='{"action": "get_events"}',
        headers=_wh_headers(),
    ))
    nodes.append(make_msg_node(N["events_ok"],
        f"📆 *Upcoming Events*\n\n"
        f"📌 {_E}.0.description — {_E}.0.start\n"
        f"📌 {_E}.1.description — {_E}.1.start\n"
        f"📌 {_E}.2.description — {_E}.2.start\n"
        f"📌 {_E}.3.description — {_E}.3.start",
        dest_uuid=N["main_menu"]))
    nodes.append(make_msg_node(N["events_err"],
        "⚠️ Could not fetch events.",
        dest_uuid=N["main_menu"]))

    # ═══════════════════════════════════════════════════════════════════════
    #  LAYOUT
    # ═══════════════════════════════════════════════════════════════════════

    layout = {
        # Main menu
        N["main_menu"]:      (400, 0),
        N["timeout"]:        (850, 0),
        N["exit"]:           (850, ROW),
        # Meetings sub-menu
        N["meetings_menu"]:  (0, ROW * 2),
        N["tw_wh"]:          (0, ROW * 3),
        N["tw_ok"]:          (0, ROW * 4),
        N["tw_err"]:         (200, ROW * 4),
        N["nw_wh"]:          (350, ROW * 3),
        N["nw_ok"]:          (350, ROW * 4),
        N["nw_err"]:         (550, ROW * 4),
        N["mat_wh"]:         (700, ROW * 3),
        N["mat_ok"]:         (700, ROW * 4),
        N["mat_err"]:        (900, ROW * 4),
        N["att_wh"]:         (1050, ROW * 3),
        N["att_ok"]:         (1050, ROW * 4),
        N["att_err"]:        (1250, ROW * 4),
        # Personal sub-menu
        N["personal_menu"]:  (0, ROW * 6),
        N["my_wh"]:          (0, ROW * 7),
        N["my_ok"]:          (0, ROW * 8),
        N["my_err"]:         (200, ROW * 8),
        N["grp_wh"]:         (350, ROW * 7),
        N["grp_ok"]:         (350, ROW * 8),
        N["grp_err"]:        (550, ROW * 8),
        N["rpt_wh"]:         (700, ROW * 7),
        N["rpt_ok"]:         (700, ROW * 8),
        N["rpt_err"]:        (900, ROW * 8),
        # Search
        N["search_ask"]:     (0, ROW * 10),
        N["search_wh"]:      (0, ROW * 11),
        N["search_ok"]:      (0, ROW * 12),
        N["search_err"]:     (250, ROW * 12),
        # Events
        N["events_wh"]:      (500, ROW * 10),
        N["events_ok"]:      (500, ROW * 11),
        N["events_err"]:     (750, ROW * 11),
    }

    return flow_uuid, make_flow(flow_uuid, "Organized Menu", nodes, layout, expire=10)
