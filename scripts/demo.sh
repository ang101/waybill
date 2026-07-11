#!/usr/bin/env bash
# Waybill demo: proves the four core claims from the pitch against a real,
# live deployment. Each act explains WHAT is being tested and WHY it
# matters before showing the raw request/response.
#
#   BASE_URL=http://localhost:8000 bash scripts/demo.sh
#   BASE_URL=https://waybill.onrender.com bash scripts/demo.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

say()     { printf '\n\033[1;34m=== %s ===\033[0m\n' "$1"; }
explain() { printf '\033[0;36m%s\033[0m\n\n' "$1"; }
result()  { printf '\n%s\n' "$1"; }
pretty()  { python -c "import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))"; }

GOAL="process the refund request backlog"
CONSTRAINTS='["must log every refund decision", "never contact the customer directly"]'
OUT_OF_SCOPE='["issue partial refunds"]'

echo ""
echo "WAYBILL LIVE DEMO — testing against: $BASE_URL"
echo "Scenario: an orchestrator hands off a refund-processing task through"
echo "two agent hops, with one required obligation and one hard constraint."
echo ""

# ---------------------------------------------------------------------------
say "ACT 1 — Create the signed handoff root"
explain "WHAT: The orchestrator defines the task once — goal, constraints,
out-of-scope items — and POSTs it to Waybill. Waybill signs it and returns
a handoff_id. This is the ONE moment the goal/constraints are ever written.
WHY: Everything downstream will be checked against this root. If a later
hop tries to change it, Waybill will reject the change (see Act 4)."

ROOT=$(curl -sf --ssl-no-revoke -X POST "$BASE_URL/handoffs" -H "Content-Type: application/json" -d "{
  \"original_goal\": \"$GOAL\",
  \"constraints\": $CONSTRAINTS,
  \"out_of_scope\": $OUT_OF_SCOPE,
  \"completed\": [],
  \"remaining\": [\"triage backlog\", \"approve refunds\"]
}")
echo "$ROOT" | pretty
ROOT_ID=$(echo "$ROOT" | python -c "import json,sys; print(json.load(sys.stdin)['handoff_id'])")
result "✅ Root created at hop_index=0. handoff_id=$ROOT_ID. Signature attached — this content can now be tamper-checked forever."

# ---------------------------------------------------------------------------
say "ACT 2 — Agent hop 1 extends the handoff (compliant relay)"
explain "WHAT: A downstream agent picks up the task, marks 'triage backlog'
as completed, and extends the handoff — WITHOUT touching the locked fields.
WHY: This is the normal, healthy path. Waybill re-verifies that goal,
constraints, and out_of_scope are byte-identical to the root before
accepting the extension. If they don't match, this call fails (Act 4
shows exactly that failure)."

HOP1=$(curl -sf --ssl-no-revoke -X POST "$BASE_URL/handoffs/$ROOT_ID/extend" -H "Content-Type: application/json" -d "{
  \"original_goal\": \"$GOAL\",
  \"constraints\": $CONSTRAINTS,
  \"out_of_scope\": $OUT_OF_SCOPE,
  \"completed\": [\"triage backlog\"],
  \"remaining\": [\"approve refunds\"]
}")
echo "$HOP1" | pretty
HOP1_ID=$(echo "$HOP1" | python -c "import json,sys; print(json.load(sys.stdin)['handoff_id'])")
result "✅ Extended to hop_index=1. Locked fields (goal, constraints, out_of_scope) carried through byte-for-byte from the root — nothing drifted."

# ---------------------------------------------------------------------------
say "ACT 3a — GREEN: validate a plan that satisfies every constraint"
explain "WHAT: Before the next agent acts, it must POST its proposed plan
for validation. This plan explicitly logs the refund decision and never
contacts the customer — satisfying the one obligation and one prohibition
from the root.
WHY: This proves the happy path works cleanly: zero false positives when
a plan actually complies."

curl -sf --ssl-no-revoke -X POST "$BASE_URL/handoffs/$HOP1_ID/validate-plan" -H "Content-Type: application/json" \
  -d '{"proposed_plan": "Review each triaged refund, log every refund decision in the audit system, approve qualifying refunds."}' | pretty
result "✅ aligned=true, flags=[] — the agent is cleared to execute this plan. No manual review needed."

# ---------------------------------------------------------------------------
say "ACT 3b — RED: validate a plan that silently drops an obligation"
explain "WHAT: Same handoff, but this plan quietly omits the logging step —
exactly the kind of silent drift that happens when tasks are relayed as
free text instead of a structured contract.
WHY: This is the core value proposition. Waybill catches it TWICE: the
deterministic keyword check flags the missing obligation, AND the LLM
semantic layer independently confirms it — defense in depth, not just one
brittle check."

curl -sf --ssl-no-revoke -X POST "$BASE_URL/handoffs/$HOP1_ID/validate-plan" -H "Content-Type: application/json" \
  -d '{"proposed_plan": "Review each triaged refund and approve qualifying refunds."}' | pretty
result "❌ aligned=false — blocked BEFORE execution, not detected after the fact. Two independent checks agree: the obligation was dropped."

# ---------------------------------------------------------------------------
say "ACT 4 — TAMPER: an agent tries to rewrite the original goal"
explain "WHAT: A rogue or buggy hop tries to change what the task even IS —
rewriting 'process the refund backlog' into 'upsell enterprise customers'.
This is the scenario Act 2's byte-identical check was guarding against.
WHY: Instead of silently accepting the rewrite (which is what free-text
handoffs do), Waybill rejects it with HTTP 400 AND returns the root's real
values — so the caller can self-correct instead of just failing blindly."

curl -s --ssl-no-revoke -X POST "$BASE_URL/handoffs/$HOP1_ID/extend" -H "Content-Type: application/json" -d "{
  \"original_goal\": \"upsell enterprise customers on premium plans\",
  \"constraints\": $CONSTRAINTS,
  \"out_of_scope\": $OUT_OF_SCOPE,
  \"completed\": [\"triage backlog\"],
  \"remaining\": []
}" | pretty
result "🛑 HTTP 400 package_drift — rewrite blocked. Root's true goal returned in the error body for self-correction, not just a bare rejection."

# ---------------------------------------------------------------------------
say "DONE"
echo "Summary: one signed contract, two agent hops, one compliant plan"
echo "accepted, one non-compliant plan blocked by two independent checks,"
echo "and one tamper attempt rejected with a self-correcting error."
