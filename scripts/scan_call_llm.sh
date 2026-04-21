#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  ADR-010: Governance Scanner — Verify no call_llm in CRM Ops Flow
#
#  Exports the CRM Operations flow definition and scans for any
#  call_llm nodes that would violate the "LLM is not involved"
#  guarantee (Finding 9).
#
#  Usage:
#    cd /opt/iiab/ai-gateway && source .env
#    bash scripts/scan_call_llm.sh
#
#  Exit codes:
#    0 — Clean (no call_llm nodes found)
#    1 — VIOLATION (call_llm node found in CRM ops flow)
#    2 — Configuration error
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

RAPIDPRO_HOST="${RAPIDPRO_HOST:-http://localhost:8080}"
API_TOKEN="${RAPIDPRO_API_TOKEN:-}"
FLOW_UUID="${CRM_OPS_FLOW_UUID:-}"

if [ -z "$API_TOKEN" ]; then
    echo "❌ RAPIDPRO_API_TOKEN not set. Source .env first."
    exit 2
fi

if [ -z "$FLOW_UUID" ]; then
    echo "❌ CRM_OPS_FLOW_UUID not set. Run setup_crm_ops.py first."
    exit 2
fi

echo "🔍 Scanning CRM Operations flow for call_llm contamination..."
echo "   Flow UUID: $FLOW_UUID"
echo "   Host:      $RAPIDPRO_HOST"
echo ""

# ── Q6: Backup before scan (flow versioning) ───────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/../backups/flows"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/crm_ops_$(date +%Y%m%d_%H%M%S).json"

echo "📦 Backing up flow definition..."
curl -s -H "Authorization: Token $API_TOKEN" \
  "$RAPIDPRO_HOST/api/v2/definitions.json?flow=$FLOW_UUID" \
  -o "$BACKUP_FILE"
BACKUP_SIZE=$(wc -c < "$BACKUP_FILE" | tr -d ' ')
if [ "$BACKUP_SIZE" -lt 100 ]; then
    echo "   ⚠️  Backup suspiciously small ($BACKUP_SIZE bytes) — check UUID and host."
else
    echo "   ✅ Saved $BACKUP_SIZE bytes → $BACKUP_FILE"
fi
echo ""

curl -s -H "Authorization: Token $API_TOKEN" \
  "$RAPIDPRO_HOST/api/v2/definitions.json?flow=$FLOW_UUID" | \
python3 -c "
import json, sys

try:
    d = json.load(sys.stdin)
except json.JSONDecodeError:
    print('❌ Failed to parse flow JSON. Check UUID and host.')
    sys.exit(2)

violations = []
for flow in d.get('flows', []):
    for node in flow.get('nodes', []):
        for action in node.get('actions', []):
            if action.get('type') == 'call_llm':
                violations.append({
                    'flow': flow.get('name', 'unknown'),
                    'node': node.get('uuid', 'unknown')[:8],
                    'instructions': action.get('instructions', '')[:50],
                })

if violations:
    print('🔴 VIOLATION: call_llm nodes found in CRM ops flow!')
    for v in violations:
        print(f'   Flow: {v[\"flow\"]} | Node: {v[\"node\"]} | Instructions: {v[\"instructions\"]}...')
    sys.exit(1)
else:
    node_count = sum(len(f.get('nodes', [])) for f in d.get('flows', []))
    action_count = sum(
        len(a.get('actions', []))
        for f in d.get('flows', [])
        for a in f.get('nodes', [])
    )
    print(f'✅ Clean — no call_llm nodes found.')
    print(f'   Scanned {len(d.get(\"flows\", []))} flow(s), {node_count} nodes, {action_count} actions.')
"
