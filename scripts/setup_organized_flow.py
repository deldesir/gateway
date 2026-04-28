#!/usr/bin/env python3
"""
ADR-012 Phase 3: Organized Menu Flow

Creates a RapidPro flow named "organized_menu".
This flow simply sends a list message with the menu options and immediately exits.
When the user clicks an option, the flow has already ended, so Mailroom routes
the response text directly to RiveBot (Layer 2), where the macros execute.
"""

import os
import sys
import json
import subprocess
from uuid import uuid4
from pathlib import Path

def u(): return str(uuid4())

def generate_export():
    flow_uuid = u()
    guard_uuid = u()
    node_uuid = u()
    
    # Menu options — 4 items will render as a List Message in WuzAPI
    choices = ["My Schedule", "This Week", "Next Week", "Search"]
    
    # Guard node — absorbs keyword trigger double-fire (silent)
    guard_node = {
        "uuid": guard_uuid,
        "actions": [{"uuid": u(), "type": "set_run_result", "name": "entry_guard", "value": "1"}],
        "exits": [{"uuid": u(), "destination_uuid": node_uuid}]
    }
    
    # Node: Send message and exit
    actions = [{
        "uuid": u(), 
        "type": "send_msg", 
        "text": "📋 *Organized Menu*\n\nSelect an option to manage your congregation schedule:",
        "quick_replies": choices
    }]
    
    nodes = [
        guard_node,
        {
            "uuid": node_uuid,
            "actions": actions,
            "exits": [{"uuid": u(), "destination_uuid": None}]
        }
    ]
    
    layout = {guard_uuid: (300, -200), node_uuid: (300, 0)}
    
    flow = {
        "uuid": flow_uuid,
        "name": "organized_menu",
        "spec_version": "14.4.0",
        "language": "eng",
        "type": "messaging",
        "revision": 1,
        "expire_after_minutes": 5,
        "localization": {},
        "nodes": nodes,
        "_ui": {"nodes": {nid: {"position": {"left": pos[0], "top": pos[1]}, "type": "execute_actions", "config": {}} for nid, pos in layout.items()}, "editor": "0.156.6"},
    }

    return {
        "version": "13",
        "site": "http://localhost",
        "flows": [flow],
        "campaigns": [], "triggers": [], "fields": [], "groups": [],
    }


def import_flows(export_json):
    json_path = Path(__file__).parent / "organized_menu_flow.json"
    with open(json_path, "w") as f:
        json.dump(export_json, f, indent=2)
    print(f"   📁 Saved export to {json_path}")

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
        print(f"   ✅ Flow 'organized_menu' imported successfully!")
        return True
    else:
        print(f"   ⚠️  Import: {stdout}")
        if result.stderr.strip():
            print(f"   stderr: {result.stderr.strip()[:300]}")
        return False


if __name__ == "__main__":
    export = generate_export()
    if import_flows(export):
        print("\n  Deployment complete! You can now use the `menu` trigger in RiveBot.")
