#!/usr/bin/env python3
"""Seed realistic fake data into the Organized backend.

Populates CongBackupTable with properly-shaped data matching
the Organized app's Dexie schema. Replaces any existing test data.

Usage:
    /opt/iiab/organized-backend/.venv/bin/python \\
        /opt/iiab/ai-gateway/scripts/seed_organized_data.py
"""

import os, sys, json, django
from datetime import datetime, timedelta
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "organized_backend.settings")
# Load env
for line in open("/etc/iiab/organized.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v.strip("'\""))

sys.path.insert(0, "/opt/iiab/organized-backend")
django.setup()

from api.models import CongBackupTable, Congregation

u = lambda: str(uuid4())
now = datetime.now()

# Monday of this week
monday = now - timedelta(days=now.weekday())
def week_date(offset_weeks):
    d = monday + timedelta(weeks=offset_weeks)
    return d.strftime("%Y/%m/%d")

# ── Persons ──────────────────────────────────────────────────────────────────

PERSONS = [
    ("p-001", "Jean-Pierre", "Baptiste"),
    ("p-002", "Marie", "Desrosiers"),
    ("p-003", "Blondel", "Mondesir"),
    ("p-004", "Esther", "Joseph"),
    ("p-005", "Samuel", "Pierre-Louis"),
    ("p-006", "Ruth", "Toussaint"),
    ("p-007", "Daniel", "Étienne"),
    ("p-008", "Naomi", "Charles"),
    ("p-009", "Pierre", "Belizaire"),
    ("p-010", "Rachelle", "Préval"),
    ("p-011", "Jacques", "Lafontant"),
    ("p-012", "Miriam", "Saintil"),
]

def make_person(uid, first, last):
    return {
        "_deleted": {"value": False, "updatedAt": ""},
        "person_uid": uid,
        "person_data": {
            "person_firstname": {"value": first, "updatedAt": now.isoformat()},
            "person_lastname": {"value": last, "updatedAt": now.isoformat()},
            "person_display_name": {"value": f"{first} {last[0]}.", "updatedAt": now.isoformat()},
            "male": {"value": first in ("Jean-Pierre","Blondel","Samuel","Daniel","Pierre","Jacques"), "updatedAt": ""},
            "female": {"value": first in ("Marie","Esther","Ruth","Naomi","Rachelle","Miriam"), "updatedAt": ""},
            "birth_date": {"value": None, "updatedAt": ""},
            "phone": {"value": f"5093{700+int(uid.split('-')[1]):04d}", "updatedAt": now.isoformat()},
            "email": {"value": f"{first.lower()}@example.com", "updatedAt": ""},
            "archived": {"value": False, "updatedAt": ""},
            "disqualified": {"value": False, "updatedAt": ""},
            "assignments": [{"type": "main", "updatedAt": "", "values": []}],
            "privileges": [],
            "enrollments": [],
        },
    }

persons_data = [make_person(uid, f, l) for uid, f, l in PERSONS]

# ── Schedules ────────────────────────────────────────────────────────────────

def assign(person_uid):
    name = next((f"{f} {l[0]}." for u,f,l in PERSONS if u == person_uid), "")
    return [{"type": "main", "value": person_uid, "name": name, "updatedAt": now.isoformat()}]

def make_schedule(week_offset):
    return {
        "weekOf": week_date(week_offset),
        "midweek_meeting": {
            "chairman": {"main_hall": assign("p-001"), "aux_class_1": {"type":"main","value":"","name":"","updatedAt":""}},
            "opening_prayer": assign("p-005"),
            "tgw_talk": assign("p-007"),
            "tgw_gems": assign("p-009"),
            "tgw_bible_reading": {"main_hall": assign("p-003"), "aux_class_1": {"type":"main","value":"","name":"","updatedAt":""}, "aux_class_2": {"type":"main","value":"","name":"","updatedAt":""}},
            "ayf_part1": {"main_hall": {"student": assign("p-004"), "assistant": assign("p-006")}, "aux_class_1": {"student": {"type":"main","value":"","name":"","updatedAt":""}, "assistant": {"type":"main","value":"","name":"","updatedAt":""}}, "aux_class_2": {"student": {"type":"main","value":"","name":"","updatedAt":""}, "assistant": {"type":"main","value":"","name":"","updatedAt":""}}},
            "ayf_part2": {"main_hall": {"student": assign("p-008"), "assistant": assign("p-010")}, "aux_class_1": {"student": {"type":"main","value":"","name":"","updatedAt":""}, "assistant": {"type":"main","value":"","name":"","updatedAt":""}}, "aux_class_2": {"student": {"type":"main","value":"","name":"","updatedAt":""}, "assistant": {"type":"main","value":"","name":"","updatedAt":""}}},
            "ayf_part3": {"main_hall": {"student": assign("p-012"), "assistant": assign("p-002")}, "aux_class_1": {"student": {"type":"main","value":"","name":"","updatedAt":""}, "assistant": {"type":"main","value":"","name":"","updatedAt":""}}, "aux_class_2": {"student": {"type":"main","value":"","name":"","updatedAt":""}, "assistant": {"type":"main","value":"","name":"","updatedAt":""}}},
            "ayf_part4": {"main_hall": {"student": [], "assistant": []}, "aux_class_1": {"student": {"type":"main","value":"","name":"","updatedAt":""}, "assistant": {"type":"main","value":"","name":"","updatedAt":""}}, "aux_class_2": {"student": {"type":"main","value":"","name":"","updatedAt":""}, "assistant": {"type":"main","value":"","name":"","updatedAt":""}}},
            "lc_part1": assign("p-011"),
            "lc_part2": assign("p-009"),
            "lc_part3": [],
            "lc_cbs": {"conductor": assign("p-001"), "reader": assign("p-005")},
            "closing_prayer": assign("p-007"),
            "week_type": [{"type": "main", "value": 1, "updatedAt": ""}],
        },
        "weekend_meeting": {
            "chairman": assign("p-001"),
            "opening_prayer": assign("p-009"),
            "public_talk_type": [{"type": "main", "value": "localSpeaker", "updatedAt": ""}],
            "speaker": {"part_1": assign("p-011"), "part_2": [], "substitute": []},
            "wt_study": {"conductor": assign("p-007"), "reader": assign("p-003")},
            "closing_prayer": assign("p-005"),
            "week_type": [{"type": "main", "value": 1, "updatedAt": ""}],
            "outgoing_talks": [],
        },
    }

schedules_data = [make_schedule(i) for i in range(4)]

# ── Upcoming Events ──────────────────────────────────────────────────────────

events_data = [
    {
        "event_uid": u(),
        "event_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "start": (now + timedelta(days=10)).strftime("%Y-%m-%dT09:00:00"),
            "end": (now + timedelta(days=10)).strftime("%Y-%m-%dT12:00:00"),
            "type": "main", "category": 0,  # CircuitOverseerWeek
            "duration": 0, "description": "Circuit Overseer Visit",
        },
    },
    {
        "event_uid": u(),
        "event_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "start": (now + timedelta(days=30)).strftime("%Y-%m-%dT09:00:00"),
            "end": (now + timedelta(days=32)).strftime("%Y-%m-%dT17:00:00"),
            "type": "main", "category": 5,  # ConventionWeek
            "duration": 1, "description": "Regional Convention 2026",
        },
    },
    {
        "event_uid": u(),
        "event_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "start": (now + timedelta(days=60)).strftime("%Y-%m-%dT19:00:00"),
            "end": (now + timedelta(days=60)).strftime("%Y-%m-%dT21:00:00"),
            "type": "main", "category": 3,  # MemorialWeek
            "duration": 0, "description": "Memorial Observance",
        },
    },
    {
        "event_uid": u(),
        "event_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "start": (now + timedelta(days=14)).strftime("%Y-%m-%dT08:00:00"),
            "end": (now + timedelta(days=14)).strftime("%Y-%m-%dT12:00:00"),
            "type": "main", "category": 16,  # Custom
            "duration": 0, "description": "Kingdom Hall Cleaning Day",
            "custom": "Bring cleaning supplies",
        },
    },
]

# ── Sources (meeting material) ───────────────────────────────────────────────

def make_source(week_offset):
    return {
        "weekOf": week_date(week_offset),
        "midweek_meeting": {
            "event_name": [{"type": "main", "value": "", "updatedAt": ""}],
            "weekly_bible_reading": {"src": f"Psalms {40+week_offset}-{42+week_offset}", "updatedAt": now.isoformat()},
            "song_first": {"src": str(45+week_offset), "updatedAt": ""},
            "tgw_talk": {"src": f"\"Trust in Jehovah\" (Ps {40+week_offset}:4)", "time": {"default": 10, "override": []}},
            "tgw_gems": {"title": {"src": f"Spiritual Gems from Psalms {40+week_offset}", "updatedAt": ""}, "time": {"default": 10, "override": []}},
            "tgw_bible_reading": {"src": f"Ps {40+week_offset}:1-11", "title": {"src": "Bible Reading", "updatedAt": ""}},
            "ayf_count": {"default": 3, "override": []},
            "ayf_part1": {"src": "Initial Call", "time": {"default": 4, "override": []}, "title": {"src": "Initial Call", "updatedAt": ""}, "type": {"default": 127, "override": []}},
            "ayf_part2": {"src": "Return Visit", "time": {"default": 5, "override": []}, "title": {"src": "Return Visit", "updatedAt": ""}, "type": {"default": 128, "override": []}},
            "ayf_part3": {"src": "Bible Study", "time": {"default": 5, "override": []}, "title": {"src": "Bible Study", "updatedAt": ""}, "type": {"default": 129, "override": []}},
            "song_middle": {"src": str(70+week_offset), "updatedAt": ""},
            "lc_count": {"default": 2, "override": []},
            "lc_part1": {"title": {"default": {"src": f"Be Faithful Under Trials", "updatedAt": ""}, "override": []}, "time": {"default": {"src": "15", "updatedAt": ""}, "override": []}, "desc": {"default": {"src": "", "updatedAt": ""}, "override": []}},
            "lc_part2": {"title": {"default": {"src": f"Congregation Bible Study", "updatedAt": ""}, "override": []}, "time": {"default": {"src": "30", "updatedAt": ""}, "override": []}, "desc": {"default": {"src": "", "updatedAt": ""}, "override": []}},
            "lc_cbs": {"src": f"\"Draw Close to God\" ch. {3+week_offset}", "time": {"default": 30, "override": []}, "title": {"default": {"src": "Congregation Bible Study", "updatedAt": ""}, "override": []}},
            "song_conclude": {"default": {"src": str(100+week_offset), "updatedAt": ""}, "override": []},
        },
        "weekend_meeting": {
            "event_name": [{"type": "main", "value": "", "updatedAt": ""}],
            "song_first": [{"type": "main", "value": str(20+week_offset), "updatedAt": ""}],
            "public_talk": [{"type": "main", "value": str(50+week_offset), "updatedAt": ""}],
            "song_middle": {"src": str(85+week_offset), "updatedAt": ""},
            "w_study": {"src": f"Watchtower Study: \"Walk by Faith\" (Part {week_offset+1})", "updatedAt": now.isoformat()},
            "song_conclude": {"default": {"src": str(110+week_offset), "updatedAt": ""}, "override": []},
        },
    }

sources_data = [make_source(i) for i in range(4)]

# ── Field Service Groups ─────────────────────────────────────────────────────

groups_data = [
    {
        "group_id": u(),
        "group_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "sort_index": 0, "name": "Group 1 — Delmas",
            "members": [
                {"person_uid": "p-001", "sort_index": 0, "isOverseer": True, "isAssistant": False},
                {"person_uid": "p-002", "sort_index": 1, "isOverseer": False, "isAssistant": True},
                {"person_uid": "p-003", "sort_index": 2, "isOverseer": False, "isAssistant": False},
                {"person_uid": "p-004", "sort_index": 3, "isOverseer": False, "isAssistant": False},
            ],
        },
    },
    {
        "group_id": u(),
        "group_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "sort_index": 1, "name": "Group 2 — Pétion-Ville",
            "members": [
                {"person_uid": "p-005", "sort_index": 0, "isOverseer": True, "isAssistant": False},
                {"person_uid": "p-006", "sort_index": 1, "isOverseer": False, "isAssistant": True},
                {"person_uid": "p-007", "sort_index": 2, "isOverseer": False, "isAssistant": False},
                {"person_uid": "p-008", "sort_index": 3, "isOverseer": False, "isAssistant": False},
            ],
        },
    },
    {
        "group_id": u(),
        "group_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "sort_index": 2, "name": "Group 3 — Carrefour",
            "members": [
                {"person_uid": "p-009", "sort_index": 0, "isOverseer": True, "isAssistant": False},
                {"person_uid": "p-010", "sort_index": 1, "isOverseer": False, "isAssistant": True},
                {"person_uid": "p-011", "sort_index": 2, "isOverseer": False, "isAssistant": False},
                {"person_uid": "p-012", "sort_index": 3, "isOverseer": False, "isAssistant": False},
            ],
        },
    },
]

# ── Meeting Attendance ───────────────────────────────────────────────────────

import random
random.seed(42)

def make_attendance(month_offset):
    month = now.replace(day=1) - timedelta(days=30*month_offset)
    def week_att():
        return {
            "midweek": [{"type": "main", "online": random.randint(3,8), "present": random.randint(35,55), "updatedAt": now.isoformat()}],
            "weekend": [{"type": "main", "online": random.randint(2,6), "present": random.randint(40,65), "updatedAt": now.isoformat()}],
        }
    return {
        "_deleted": {"value": False, "updatedAt": ""},
        "month_date": month.strftime("%Y/%m"),
        "week_1": week_att(), "week_2": week_att(),
        "week_3": week_att(), "week_4": week_att(),
        "week_5": week_att(),
    }

attendance_data = [make_attendance(i) for i in range(3)]

# ── Field Service Reports ────────────────────────────────────────────────────

def make_report(person_uid, month_offset):
    month = now.replace(day=1) - timedelta(days=30*month_offset)
    return {
        "report_id": u(),
        "report_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "report_date": month.strftime("%Y/%m"),
            "person_uid": person_uid,
            "shared_ministry": True,
            "hours": {
                "field_service": random.randint(5, 25),
                "credit": {"value": 0, "approved": 0},
            },
            "bible_studies": random.randint(0, 3),
            "comments": "",
            "late": {"value": False, "submitted": ""},
            "status": "confirmed",
        },
    }

reports_data = []
for pid in [f"p-{i:03d}" for i in range(1, 13)]:
    for m in range(2):
        reports_data.append(make_report(pid, m))

# ── Visiting Speakers ────────────────────────────────────────────────────────

visiting_speakers_data = [
    {
        "_deleted": {"value": False, "updatedAt": ""},
        "person_uid": u(),
        "speaker_data": {
            "cong_id": "neighbor-001",
            "person_display_name": {"value": "Frère Antoine Michel", "updatedAt": now.isoformat()},
            "person_firstname": {"value": "Antoine", "updatedAt": ""},
            "person_lastname": {"value": "Michel", "updatedAt": ""},
            "person_notes": {"value": "Excellent speaker on prophecy", "updatedAt": ""},
            "elder": {"value": True, "updatedAt": ""},
            "ministerial_servant": {"value": False, "updatedAt": ""},
            "person_email": {"value": "antoine@example.com", "updatedAt": ""},
            "person_phone": {"value": "50938001234", "updatedAt": ""},
            "local": {"value": False, "updatedAt": ""},
            "talks": [
                {"_deleted": False, "updatedAt": now.isoformat(), "talk_number": 12, "talk_title": "Is This Life All There Is?"},
                {"_deleted": False, "updatedAt": now.isoformat(), "talk_number": 52, "talk_title": "What Is True Love?"},
            ],
        },
    },
    {
        "_deleted": {"value": False, "updatedAt": ""},
        "person_uid": u(),
        "speaker_data": {
            "cong_id": "neighbor-002",
            "person_display_name": {"value": "Frère Gérard Paul", "updatedAt": now.isoformat()},
            "person_firstname": {"value": "Gérard", "updatedAt": ""},
            "person_lastname": {"value": "Paul", "updatedAt": ""},
            "person_notes": {"value": "", "updatedAt": ""},
            "elder": {"value": True, "updatedAt": ""},
            "ministerial_servant": {"value": False, "updatedAt": ""},
            "person_email": {"value": "", "updatedAt": ""},
            "person_phone": {"value": "50938005678", "updatedAt": ""},
            "local": {"value": False, "updatedAt": ""},
            "talks": [
                {"_deleted": False, "updatedAt": now.isoformat(), "talk_number": 35, "talk_title": "Winning the Battle for Your Mind"},
            ],
        },
    },
    {
        "_deleted": {"value": False, "updatedAt": ""},
        "person_uid": u(),
        "speaker_data": {
            "cong_id": "neighbor-001",
            "person_display_name": {"value": "Frère Louis Jean-Baptiste", "updatedAt": now.isoformat()},
            "person_firstname": {"value": "Louis", "updatedAt": ""},
            "person_lastname": {"value": "Jean-Baptiste", "updatedAt": ""},
            "person_notes": {"value": "Available weekends only", "updatedAt": ""},
            "elder": {"value": False, "updatedAt": ""},
            "ministerial_servant": {"value": True, "updatedAt": ""},
            "person_email": {"value": "", "updatedAt": ""},
            "person_phone": {"value": "50938009999", "updatedAt": ""},
            "local": {"value": False, "updatedAt": ""},
            "talks": [
                {"_deleted": False, "updatedAt": now.isoformat(), "talk_number": 72, "talk_title": "Making Wise Decisions"},
            ],
        },
    },
]

# ── Speakers Congregations ───────────────────────────────────────────────────

speakers_congregations_data = [
    {
        "_deleted": {"value": False, "updatedAt": ""},
        "cong_data": {
            "cong_id": "neighbor-001",
            "cong_number": {"value": "HT-10042", "updatedAt": ""},
            "cong_name": {"value": "Pétion-Ville Central", "updatedAt": now.isoformat()},
            "cong_circuit": {"value": "HT-3A", "updatedAt": ""},
            "cong_location": {"address": {"value": "Rue Panamericaine, Pétion-Ville", "updatedAt": ""}, "lat": 18.5125, "lng": -72.2854},
            "midweek_meeting": {"weekday": {"value": 3, "updatedAt": ""}, "time": {"value": "19:00", "updatedAt": ""}},
            "weekend_meeting": {"weekday": {"value": 0, "updatedAt": ""}, "time": {"value": "09:30", "updatedAt": ""}},
            "public_talk_coordinator": {"name": {"value": "Fr. Antoine Michel", "updatedAt": ""}, "email": {"value": "antoine@example.com", "updatedAt": ""}, "phone": {"value": "50938001234", "updatedAt": ""}},
            "coordinator": {"name": {"value": "Fr. Jean Ducasse", "updatedAt": ""}, "email": {"value": "", "updatedAt": ""}, "phone": {"value": "50938002222", "updatedAt": ""}},
            "request_status": "approved", "request_id": u(),
        },
    },
    {
        "_deleted": {"value": False, "updatedAt": ""},
        "cong_data": {
            "cong_id": "neighbor-002",
            "cong_number": {"value": "HT-10078", "updatedAt": ""},
            "cong_name": {"value": "Delmas 33 Sud", "updatedAt": now.isoformat()},
            "cong_circuit": {"value": "HT-3A", "updatedAt": ""},
            "cong_location": {"address": {"value": "Delmas 33, Port-au-Prince", "updatedAt": ""}, "lat": 18.5412, "lng": -72.3087},
            "midweek_meeting": {"weekday": {"value": 2, "updatedAt": ""}, "time": {"value": "19:00", "updatedAt": ""}},
            "weekend_meeting": {"weekday": {"value": 6, "updatedAt": ""}, "time": {"value": "10:00", "updatedAt": ""}},
            "public_talk_coordinator": {"name": {"value": "Fr. Gérard Paul", "updatedAt": ""}, "email": {"value": "", "updatedAt": ""}, "phone": {"value": "50938005678", "updatedAt": ""}},
            "coordinator": {"name": {"value": "Fr. Max Pierre", "updatedAt": ""}, "email": {"value": "", "updatedAt": ""}, "phone": {"value": "50938003333", "updatedAt": ""}},
            "request_status": "approved", "request_id": u(),
        },
    },
]

# ── Congregation Field Service Reports (aggregate per month) ─────────────────

def make_cong_report(month_offset):
    month = now.replace(day=1) - timedelta(days=30*month_offset)
    return {
        "report_id": u(),
        "report_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "report_date": month.strftime("%Y/%m"),
            "person_uid": "",  # aggregate
            "shared_ministry": False,
            "hours": {"field_service": random.randint(120, 280), "credit": {"value": 0, "approved": 0}},
            "bible_studies": random.randint(15, 35),
            "comments": f"Congregation total for {month.strftime('%B %Y')}",
            "late": {"value": False, "submitted": ""},
            "status": "confirmed",
        },
    }

cong_reports_data = [make_cong_report(i) for i in range(3)]

# ── Branch Field Service Reports ─────────────────────────────────────────────

def make_branch_report(month_offset):
    month = now.replace(day=1) - timedelta(days=30*month_offset)
    return {
        "report_date": month.strftime("%Y/%m"),
        "report_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "submitted": month_offset > 0,
            "publishers_active": random.randint(45, 55),
            "weekend_meeting_average": random.randint(48, 62),
            "publishers": {"report_count": random.randint(38, 50), "bible_studies": random.randint(15, 30)},
            "APs": {"report_count": random.randint(2, 5), "bible_studies": random.randint(3, 8), "hours": random.randint(100, 250)},
            "FRs": {"report_count": random.randint(0, 2), "bible_studies": random.randint(0, 3), "hours": random.randint(0, 120)},
        },
    }

branch_reports_data = [make_branch_report(i) for i in range(3)]

# ── Delegated Field Service Reports ──────────────────────────────────────────

delegated_reports_data = [
    {
        "report_id": u(),
        "report_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "shared_ministry": True,
            "hours": {"field_service": {"daily": "", "monthly": "6"}, "credit": {"daily": "", "monthly": ""}},
            "bible_studies": {"daily": 0, "monthly": 1, "records": []},
            "comments": "Submitted on behalf — elderly publisher",
            "status": "confirmed",
            "person_uid": "p-010",  # Rachelle Préval
            "report_date": (now.replace(day=1) - timedelta(days=30)).strftime("%Y/%m"),
        },
    },
    {
        "report_id": u(),
        "report_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "shared_ministry": True,
            "hours": {"field_service": {"daily": "", "monthly": "4"}, "credit": {"daily": "", "monthly": ""}},
            "bible_studies": {"daily": 0, "monthly": 0, "records": []},
            "comments": "Submitted on behalf — traveling",
            "status": "pending",
            "person_uid": "p-012",  # Miriam Saintil
            "report_date": now.replace(day=1).strftime("%Y/%m"),
        },
    },
]

# ── Branch Congregation Analysis ─────────────────────────────────────────────

def make_analysis(month_offset):
    month = now.replace(day=1) - timedelta(days=30*month_offset)
    return {
        "report_date": month.strftime("%Y/%m"),
        "report_data": {
            "_deleted": False, "updatedAt": now.isoformat(),
            "submitted": month_offset > 0,
            "meeting_average": {"midweek": random.randint(42, 52), "weekend": random.randint(48, 62)},
            "publishers": {"active": random.randint(45, 55), "inactive": random.randint(2, 5), "reactivated": random.randint(0, 2)},
            "territories": {"total": 8, "uncovered": random.randint(0, 3)},
        },
    }

analysis_data = [make_analysis(i) for i in range(3)]

# ── User Bible Studies ───────────────────────────────────────────────────────

bible_studies_data = [
    {"person_uid": "bs-001", "person_data": {"_deleted": False, "person_name": "Wilner François", "updatedAt": now.isoformat()}},
    {"person_uid": "bs-002", "person_data": {"_deleted": False, "person_name": "Claudette Romain", "updatedAt": now.isoformat()}},
    {"person_uid": "bs-003", "person_data": {"_deleted": False, "person_name": "Ti-Jean Alcius", "updatedAt": now.isoformat()}},
]

# ── Notifications ────────────────────────────────────────────────────────────

notifications_data = [
    {
        "id": u(), "type": "assignment",
        "title": "New Assignment",
        "body": f"You have been assigned as Chairman for the midweek meeting, week of {week_date(1)}.",
        "created": (now - timedelta(hours=6)).isoformat(),
        "read": False, "person_uid": "p-001",
    },
    {
        "id": u(), "type": "assignment",
        "title": "New Assignment",
        "body": f"You have been assigned as Bible Reading for the midweek meeting, week of {week_date(1)}.",
        "created": (now - timedelta(hours=6)).isoformat(),
        "read": False, "person_uid": "p-003",
    },
    {
        "id": u(), "type": "reminder",
        "title": "Meeting Reminder",
        "body": "Midweek meeting tonight at 7:00 PM.",
        "created": (now - timedelta(hours=2)).isoformat(),
        "read": True, "person_uid": "",  # broadcast
    },
    {
        "id": u(), "type": "event",
        "title": "Upcoming Event",
        "body": "Circuit Overseer visit in 10 days. Prepare your field service report.",
        "created": (now - timedelta(days=1)).isoformat(),
        "read": False, "person_uid": "",  # broadcast
    },
]

# ══════════════════════════════════════════════════════════════════════════════
#  PERSIST
# ══════════════════════════════════════════════════════════════════════════════

def main():
    cong = Congregation.objects.first()
    if not cong:
        print("❌ No congregation found")
        sys.exit(1)

    tables = {
        "persons": persons_data,
        "schedules": schedules_data,
        "upcoming_events": events_data,
        "sources": sources_data,
        "field_service_groups": groups_data,
        "meeting_attendance": attendance_data,
        "field_service_reports": reports_data,
        "visiting_speakers": visiting_speakers_data,
        "speakers_congregations": speakers_congregations_data,
        "cong_field_service_reports": cong_reports_data,
        "branch_field_service_reports": branch_reports_data,
        "delegated_field_service_reports": delegated_reports_data,
        "branch_cong_analysis": analysis_data,
        "user_bible_studies": bible_studies_data,
        "notifications": notifications_data,
    }

    print(f"Seeding {len(tables)} tables for {cong}...\n")

    for table_name, data in tables.items():
        obj, created = CongBackupTable.objects.update_or_create(
            congregation=cong, table_name=table_name,
            defaults={"data": data},
        )
        action = "Created" if created else "Updated"
        print(f"  ✅ {action} {table_name}: {len(data)} entries")

    print(f"\n✅ Done — {sum(len(d) for d in tables.values())} total entries across {len(tables)} tables")


if __name__ == "__main__":
    main()

