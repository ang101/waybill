#!/usr/bin/env bash
# Waybill demo: green path (compliant 3-hop relay), red path (dropped
# obligation), and tamper path (rewritten goal -> 400). Run against a local
# or deployed instance:
#
#   BASE_URL=http://localhost:8000 bash scripts/demo.sh
#   BASE_URL=https://waybill.onrender.com bash scripts/demo.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

say() { printf '\n=== %s ===\n' "$1"; }

GOAL="process the refund request backlog"
CONSTRAINTS='["must log every refund decision", "never contact the customer directly"]'
OUT_OF_SCOPE='["issue partial refunds"]'

say "Act 1: coordinator creates the signed handoff root"
ROOT=$(curl -sf --ssl-no-revoke -X POST "$BASE_URL/handoffs" -H "Content-Type: application/json" -d "{
  \"original_goal\": \"$GOAL\",
  \"constraints\": $CONSTRAINTS,
  \"out_of_scope\": $OUT_OF_SCOPE,
  \"completed\": [],
  \"remaining\": [\"triage backlog\", \"approve refunds\"]
}")
echo "$ROOT"
ROOT_ID=$(echo "$ROOT" | python -c "import json,sys; print(json.load(sys.stdin)['handoff_id'])")

say "Act 2: hop 1 relays onward compliantly (extend)"
HOP1=$(curl -sf --ssl-no-revoke -X POST "$BASE_URL/handoffs/$ROOT_ID/extend" -H "Content-Type: application/json" -d "{
  \"original_goal\": \"$GOAL\",
  \"constraints\": $CONSTRAINTS,
  \"out_of_scope\": $OUT_OF_SCOPE,
  \"completed\": [\"triage backlog\"],
  \"remaining\": [\"approve refunds\"]
}")
echo "$HOP1"
HOP1_ID=$(echo "$HOP1" | python -c "import json,sys; print(json.load(sys.stdin)['handoff_id'])")

say "Act 3 GREEN: hop 2's compliant plan validates -> aligned: true"
curl -sf --ssl-no-revoke -X POST "$BASE_URL/handoffs/$HOP1_ID/validate-plan" -H "Content-Type: application/json" \
  -d '{"proposed_plan": "Review each triaged refund, log every refund decision in the audit system, approve qualifying refunds."}'
echo

say "Act 3 RED: hop 2's plan silently drops the logging obligation -> aligned: false"
curl -sf --ssl-no-revoke -X POST "$BASE_URL/handoffs/$HOP1_ID/validate-plan" -H "Content-Type: application/json" \
  -d '{"proposed_plan": "Review each triaged refund and approve qualifying refunds."}'
echo

say "Act 4 TAMPER: a hop tries to rewrite the goal -> HTTP 400 with root values"
curl -s --ssl-no-revoke -X POST "$BASE_URL/handoffs/$HOP1_ID/extend" -H "Content-Type: application/json" -d "{
  \"original_goal\": \"upsell enterprise customers on premium plans\",
  \"constraints\": $CONSTRAINTS,
  \"out_of_scope\": $OUT_OF_SCOPE,
  \"completed\": [\"triage backlog\"],
  \"remaining\": []
}"
echo

say "Done"
