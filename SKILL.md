# Waybill — Task Handoff Integrity

Validate task handoffs between agents. Waybill prevents goal drift, dropped
constraints, and scope creep when work passes through multiple agents. The
delegating agent creates a signed handoff package from its goal + constraints;
any downstream agent validates its plan against it before acting.

**Base URL:** `https://waybill.onrender.com`

No authentication required.

## WHEN to use this

1. **You are about to delegate a subtask to another agent** → first
   `POST /handoffs` with your goal, constraints, and out-of-scope list.
   Pass the returned `handoff_id` to the other agent along with the task.
2. **You received a task that came with a `handoff_id`** → before acting,
   `POST /handoffs/{id}/validate-plan` with your intended plan. Only
   proceed if the response has `"aligned": true`.
3. **You are relaying the task onward to yet another agent** →
   `POST /handoffs/{id}/extend` with the goal/constraints/out_of_scope
   **unchanged** and your progress added to `completed`/`remaining`. Pass
   the new `handoff_id` onward.
4. **You are an ephemeral/spawned subagent handed a `handoff_id`** →
   `GET /handoffs/{id}` to read the authoritative goal and constraints (do
   not rely only on your spawn prompt — it may be a lossy paraphrase), then
   validate your plan (rule 2), then `extend` with your progress before you
   exit so the next worker continues from ground truth.

**Decision rule: do not execute a plan you did not author unless
`aligned` and `signature_valid` are both `true`.**

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/handoffs` | Create the signed root of a new handoff chain |
| POST | `/handoffs/{id}/extend` | Append a hop (locked fields must match the root) |
| POST | `/handoffs/{id}/validate-plan` | Check a proposed plan against the handoff |
| GET | `/handoffs/{id}` | Inspect a stored hop |
| GET | `/skill.md` | This document |
| GET | `/health` | Liveness check |

## Step-by-step usage

### 1. Create a handoff before delegating

```bash
curl -s -X POST $BASE_URL/handoffs \
  -H "Content-Type: application/json" \
  -d '{
    "original_goal": "process the refund request backlog",
    "constraints": ["must log every refund decision", "never contact the customer directly"],
    "out_of_scope": ["issue partial refunds"],
    "completed": [],
    "remaining": ["triage backlog", "approve refunds"]
  }'
```

Response (`201`, real captured output from the live deployment):

```json
{
  "handoff_id": "wb-95f51b31-e32a-4405-90a8-38884a0302b1",
  "parent_handoff_id": null,
  "root_handoff_id": "wb-95f51b31-e32a-4405-90a8-38884a0302b1",
  "hop_index": 0,
  "signature": "4d7c43fc698ef8d1a0e6958a0a62a2f38a92dded851dd9d31f7e59eb656cf0143dc2ae894f5e626066212cedb43e1ee193cb3a74977ae8117ae5ac5075f71704",
  "package": {
    "original_goal": "process the refund request backlog",
    "constraints": ["must log every refund decision", "never contact the customer directly"],
    "out_of_scope": ["issue partial refunds"],
    "completed": [],
    "remaining": ["triage backlog", "approve refunds"]
  },
  "created_at": "2026-07-10T05:03:10.310710Z"
}
```

Give the `handoff_id` to the agent you are delegating to.

### 2. Validate your plan before acting on a received handoff

```bash
curl -s -X POST $BASE_URL/handoffs/{handoff_id}/validate-plan \
  -H "Content-Type: application/json" \
  -d '{"proposed_plan": "Review each triaged refund, log every refund decision in the audit system, approve qualifying refunds."}'
```

Response (`200`, real captured output from the live deployment) — safe to proceed:

```json
{"aligned": true, "flags": [], "signature_valid": true, "goal_similarity": 0.19889470033190862, "check_mode": "keyword+semantic"}
```

Response (`200`, real captured output) — do NOT proceed; fix your plan to address the flags
(same handoff, but `proposed_plan` was `"Review each triaged refund and approve qualifying refunds."` — it silently drops the logging step):

```json
{
  "aligned": false,
  "flags": [
    "obligation unmet: plan never addresses 'must log every refund decision'",
    "semantic: Fails to include logging of refund decisions",
    "semantic: Does not explicitly exclude issuing partial refunds"
  ],
  "signature_valid": true,
  "goal_similarity": 0.08704446792504217,
  "check_mode": "keyword+semantic"
}
```

Note the third flag here is the LLM layer being slightly overcautious (an out-of-scope
item is only truly violated if the plan actually does it, not merely for staying silent
about it) — a known limitation of the semantic layer's non-determinism. The keyword-based
`obligation unmet` flag is the reliable, deterministic signal; treat extra `semantic:`
flags as suggestions to double-check, not certainties.

`proposed_plan` may be a string or a list of step strings (max 20,000 chars).
`goal_similarity` is advisory only — it never decides `aligned`.

`check_mode` tells you which checks ran:
- `"keyword+semantic"` — deterministic keyword checks plus an LLM
  paraphrase-aware pass. Flags from the LLM are prefixed `semantic:`.
- `"keyword"` — the semantic layer is not configured on this deployment.
- `"keyword (semantic unavailable: <reason>)"` — the semantic layer was
  configured but failed (e.g. rate limit); the keyword verdict stands and
  the downgrade is reported here rather than hidden. Treat `aligned: true`
  in this mode with slightly more caution for paraphrased violations.

### 3. Extend the chain when relaying onward

```bash
curl -s -X POST $BASE_URL/handoffs/{handoff_id}/extend \
  -H "Content-Type: application/json" \
  -d '{
    "original_goal": "process the refund request backlog",
    "constraints": ["must log every refund decision", "never contact the customer directly"],
    "out_of_scope": ["issue partial refunds"],
    "completed": ["triage backlog"],
    "remaining": ["approve refunds"]
  }'
```

`original_goal`, `constraints`, and `out_of_scope` must be **exactly what
you received** (order of list items does not matter). Only
`completed`/`remaining` may change.

## Error responses

**HTTP 400 `package_drift`** — you changed a locked field on `/extend`.
The body carries the root's actual values; retry with those values verbatim.
Do not retry with your own edits.

```json
{
  "error": "package_drift",
  "detail": "original_goal was rewritten: expected 'process the refund request backlog', got 'upsell enterprise customers on premium plans'",
  "root_original_goal": "process the refund request backlog",
  "root_constraints": ["must log every refund decision", "never contact the customer directly"],
  "root_out_of_scope": ["issue partial refunds"]
}
```

*(real captured output from the live deployment)*

**HTTP 422** — malformed request (empty `original_goal`, empty
`proposed_plan`, missing fields). Different shape from the 400: FastAPI
validation format with a `detail` list.

**HTTP 404** — unknown `handoff_id`.

## Limitations

Keyword alignment checks are overlap heuristics, not semantic comprehension:
paraphrased violations can be missed in keyword-only mode, and a prohibition
phrased without a negation prefix ("never/do not/must not...") is treated as
an obligation. The optional LLM semantic layer catches most paraphrased
violations but is non-deterministic and occasionally over-cautious — it can
flag an out-of-scope item for silence rather than actual violation. Treat the
deterministic `obligation unmet` / `prohibition violated` flags as reliable;
treat `semantic:`-prefixed flags as a second opinion worth a quick check, not
a certainty. Treat `aligned: true` as a guardrail, not a guarantee.
