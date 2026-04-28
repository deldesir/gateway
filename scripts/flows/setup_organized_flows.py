#!/usr/bin/env python3
"""ADR-012 Phase 3: Organized Menu Flow Setup

Creates the RapidPro infrastructure for the Organized scheduling menu:
  1. organized_webhook_secret global (for flow → backend auth)
  2. Organized Menu flow (18 nodes, 6 operations)
  3. Import via Django ORM (org.import_app)
  4. Persist flow UUID to .env
  5. Sync UUID with DB (import_app may remap)
  6. Verify end-to-end webhook connectivity

Usage:
    cd /opt/iiab/ai-gateway
    source .env
    python scripts/setup_organized_flows.py

Prerequisites:
    - RAPIDPRO_API_TOKEN set in environment
    - ORGANIZED_WEBHOOK_SECRET set in /etc/iiab/organized.env
    - nginx proxy: /organized/api/ → 127.0.0.1:8088/api/
    - garantie.boutique in organized DJANGO_ALLOWED_HOSTS
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import requests

# ── Configuration ────────────────────────────────────────────────────────────

RAPIDPRO_HOST = os.getenv("RAPIDPRO_HOST", "http://localhost:8080")
API_TOKEN = os.getenv("RAPIDPRO_API_TOKEN")
WEBHOOK_HOST = os.getenv("RAPIDPRO_WEBHOOK_HOST", "https://garantie.boutique")
ORGANIZED_WEBHOOK_SECRET = os.getenv("ORGANIZED_WEBHOOK_SECRET", "")

API_URL = f"{RAPIDPRO_HOST}/api/v2"
WEBHOOK_BASE = f"{WEBHOOK_HOST}/organized/api"

HEADERS = {}


def api_get(endpoint, params=None):
    r = requests.get(f"{API_URL}/{endpoint}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()


def api_post(endpoint, data):
    r = requests.post(f"{API_URL}/{endpoint}", headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()


def _persist_env(key: str, value: str, comment: str = ""):
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    content = env_path.read_text()
    if key in content:
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                break
        env_path.write_text("\n".join(lines) + "\n")
        print(f"   ✅ Updated {key} in .env")
        return
    with open(env_path, "a") as f:
        if comment:
            f.write(f"\n# {comment}\n")
        f.write(f"{key}={value}\n")
    print(f"   ✅ Persisted {key} to .env")


# ── Step 1: Create organized_webhook_secret Global ──────────────────────────

def setup_webhook_secret_global():
    print("\n── Step 1: organized_webhook_secret Global ──")
    if not ORGANIZED_WEBHOOK_SECRET:
        print("   ⚠️  ORGANIZED_WEBHOOK_SECRET not set — reading from /etc/iiab/organized.env")
        env_path = Path("/etc/iiab/organized.env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("ORGANIZED_WEBHOOK_SECRET="):
                    secret = line.split("=", 1)[1].strip().strip("'\"")
                    if secret:
                        os.environ["ORGANIZED_WEBHOOK_SECRET"] = secret
                        return _create_global(secret)
        print("   ❌ No secret found. Set ORGANIZED_WEBHOOK_SECRET.")
        sys.exit(1)
    return _create_global(ORGANIZED_WEBHOOK_SECRET)


def _create_global(secret):
    globals_data = api_get("globals.json")
    for g in globals_data.get("results", []):
        if g["key"] == "organized_webhook_secret":
            # Update if changed
            if g["value"] != secret:
                api_post(f"globals.json?key=organized_webhook_secret",
                         {"value": secret})
                print("   ✅ Updated organized_webhook_secret global")
            else:
                print("   ✅ organized_webhook_secret global already exists")
            return
    api_post("globals.json", {
        "name": "Organized Webhook Secret",
        "key": "organized_webhook_secret",
        "value": secret,
    })
    print("   ✅ Created organized_webhook_secret global")


# ── Step 2: Verify Webhook Connectivity ─────────────────────────────────────

def verify_webhook_connectivity():
    print("\n── Step 2: Verify Webhook Connectivity ──")
    print(f"   Testing: {WEBHOOK_BASE}/v3/webhooks/query")

    secret = os.environ.get("ORGANIZED_WEBHOOK_SECRET", ORGANIZED_WEBHOOK_SECRET)
    try:
        r = requests.post(
            f"{WEBHOOK_BASE}/v3/webhooks/query",
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": secret,
            },
            json={"action": "get_schedule"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            print(f"   ✅ Webhook reachable — {len(data.get('schedules', []))} schedules")
            return True
        elif r.status_code == 404:
            print("   ⚠️  Got 404 — endpoint may still be /webhooks/hermes")
            print("   Trying legacy endpoint...")
            r2 = requests.post(
                f"{WEBHOOK_BASE}/v3/webhooks/hermes",
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Secret": secret,
                },
                json={"action": "get_schedule"},
                timeout=10,
            )
            if r2.status_code == 200:
                print(f"   ✅ Legacy /hermes endpoint works — "
                      f"rename to /query recommended")
                return "legacy"
            print(f"   ❌ Both endpoints failed: {r2.status_code}")
            return False
        else:
            print(f"   ❌ Webhook returned {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False


# ── Step 3: Generate & Import Flow ──────────────────────────────────────────

def generate_and_import(webhook_endpoint_path):
    print("\n── Step 3: Generate Organized Menu Flow ──")

    from organized_flows.flows import generate_organized_menu
    from organized_flows.builders import make_export

    wh_base = WEBHOOK_BASE
    flow_uuid, flow = generate_organized_menu(wh_base)

    # If using legacy /hermes endpoint, patch the flow's webhook URLs
    if webhook_endpoint_path == "hermes":
        print("   ⚠️  Patching flow to use /webhooks/hermes (legacy)")
        flow_json = json.dumps(flow)
        flow_json = flow_json.replace("/webhooks/query", "/webhooks/hermes")
        flow = json.loads(flow_json)

    print(f"   📊 Organized Menu — {len(flow['nodes'])} nodes")

    export = make_export(flow)

    # Save to disk
    json_path = Path(__file__).parent.parent / "exports" / "organized_menu_flow.json"
    with open(json_path, "w") as f:
        json.dump(export, f, indent=2)
    print(f"   📁 Saved to {json_path}")

    # Import via Django ORM
    print("\n── Step 4: Import Flow into RapidPro ──")
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
        [venv_python, "/opt/iiab/rapidpro/manage.py", "shell", "-c", import_script],
        capture_output=True, text=True,
        cwd="/opt/iiab/rapidpro",
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "temba.settings"},
        timeout=60,
    )
    stdout = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    if "OK" in stdout:
        print(f"   ✅ Flow imported successfully!")
        return flow_uuid
    else:
        print(f"   ❌ Import failed: {stdout}")
        if result.stderr.strip():
            print(f"   stderr: {result.stderr.strip()[:300]}")
        sys.exit(1)


# ── Step 5: Persist & Sync UUIDs ────────────────────────────────────────────

def sync_flow_uuid(generated_uuid):
    print("\n── Step 5: Persist & Sync Flow UUID ──")
    _persist_env("ORGANIZED_MENU_FLOW_UUID", generated_uuid,
                 "ADR-012 — Organized Menu flow")

    # Sync with DB (import_app may remap UUIDs)
    db_flows = api_get("flows.json")
    for f in db_flows.get("results", []):
        if f["name"] == "Organized Menu":
            db_uuid = f["uuid"]
            if db_uuid != generated_uuid:
                print(f"   ⚠️  UUID remapped: {generated_uuid[:8]}… → {db_uuid[:8]}…")
                _persist_env("ORGANIZED_MENU_FLOW_UUID", db_uuid)
            else:
                print(f"   ✅ UUID matches DB: {db_uuid[:8]}…")
            return db_uuid
    print("   ⚠️  Flow not found in DB after import")
    return generated_uuid


# ── Step 6: Create 'menu' keyword trigger ───────────────────────────────────

def setup_menu_trigger():
    print("\n── Step 6: Create 'menu' Keyword Trigger ──")
    venv_python = "/opt/iiab/rapidpro/.venv/bin/python"
    if not Path(venv_python).exists():
        venv_python = "python3"

    script = '''
from temba.triggers.models import Trigger
from temba.flows.models import Flow
from temba.orgs.models import Org
from django.db.models import Max

org = Org.objects.filter(is_active=True).first()
user = org.get_owner()
flow = Flow.objects.filter(name="Organized Menu", is_active=True).first()
if not flow:
    print("SKIP: Organized Menu flow not found")
else:
    existing = Trigger.objects.filter(
        org=org, trigger_type="K", is_active=True, is_archived=False,
        keywords__contains=["organized"]
    )
    if existing.exists():
        t = existing.first()
        if t.flow_id != flow.id:
            t.flow = flow
            t.save(update_fields=["flow"])
            print(f"UPDATED: id={t.id}")
        else:
            print(f"EXISTS: id={t.id}")
    else:
        max_p = Trigger.objects.filter(org=org).aggregate(
            Max("priority"))["priority__max"] or 0
        t = Trigger.objects.create(
            org=org, trigger_type="K", keywords=["organized"],
            match_type="F", flow=flow,
            created_by=user, modified_by=user, priority=max_p + 1,
        )
        print(f"CREATED: id={t.id}")
'''
    result = subprocess.run(
        [venv_python, "/opt/iiab/rapidpro/manage.py", "shell", "-c", script],
        capture_output=True, text=True,
        cwd="/opt/iiab/rapidpro",
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "temba.settings"},
        timeout=30,
    )
    stdout = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    if "CREATED" in stdout:
        print("   ✅ Created 'organized' keyword trigger → Organized Menu")
    elif "EXISTS" in stdout or "UPDATED" in stdout:
        print("   ✅ 'organized' keyword trigger already configured")
    elif "SKIP" in stdout:
        print("   ⚠️  Flow not found — trigger not created")
    else:
        print(f"   ⚠️  Trigger result: {stdout}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    global HEADERS

    if not API_TOKEN:
        print("❌ RAPIDPRO_API_TOKEN not set. Add to .env and source it.")
        sys.exit(1)

    HEADERS = {
        "Authorization": f"Token {API_TOKEN}",
        "Content-Type": "application/json",
    }

    print("=" * 60)
    print("  ADR-012 Phase 3: Organized Menu Flow Setup")
    print("=" * 60)
    print(f"  RapidPro: {RAPIDPRO_HOST}")
    print(f"  Webhook:  {WEBHOOK_BASE}")

    # Step 1
    setup_webhook_secret_global()

    # Step 2
    connectivity = verify_webhook_connectivity()
    if not connectivity:
        print("\n❌ Cannot reach organized backend. Check:")
        print("   1. nginx: /organized/api/ → 127.0.0.1:8088/api/")
        print("   2. DJANGO_ALLOWED_HOSTS includes garantie.boutique")
        print("   3. organized service is running")
        sys.exit(1)

    endpoint_path = "hermes" if connectivity == "legacy" else "query"

    # Step 3-4
    generated_uuid = generate_and_import(endpoint_path)

    # Step 5
    final_uuid = sync_flow_uuid(generated_uuid)

    # Step 6
    setup_menu_trigger()

    # Summary
    print("\n" + "=" * 60)
    print("  Organized Menu deployment complete!")
    print()
    print(f"  FLOW:     Organized Menu ({final_uuid[:8]}…)")
    print(f"  NODES:    18 nodes, 6 operations")
    print(f"  WEBHOOK:  {WEBHOOK_BASE}/v3/webhooks/{endpoint_path}")
    print(f"  TRIGGER:  'organized' keyword")
    print()
    print("  NEXT STEPS:")
    print("  1. sudo systemctl restart rapidpro-mailroom ai-gateway rivebot")
    print("  2. Send 'organized' via WhatsApp to test the menu flow")
    print("  3. Or type 'this week' / 'search [name]' for direct commands")
    print("=" * 60)


if __name__ == "__main__":
    main()
