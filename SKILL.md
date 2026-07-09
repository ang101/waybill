# Waybill — Task Handoff Integrity

Validate task handoffs between agents. Waybill prevents goal drift, dropped
constraints, and scope creep when work passes through multiple agents. The
delegating agent creates a signed handoff package from its goal + constraints;
any downstream agent validates its plan against it before acting.

**Base URL:** `https://waybill.onrender.com` *(replace with deployed URL)*

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
    "remaining": ["triage backlog"]
  }'
```

Response (`201`, real captured output):

```json
{
  "handoff_id": "wb-ba9c9460-76bc-4a5a-95c5-2ac3a6e2ffe2",
  "parent_handoff_id": null,
  "root_handoff_id": "wb-ba9c9460-76bc-4a5a-95c5-2ac3a6e2ffe2",
  "hop_index": 0,
  "signature": "dbede7592a100ef349f89ea1af8a46341a1992bc7706ef806d7f9ec063399af2a57574f977ff9c8e9f243de13a56e4ec0fd2941050abdf8935345f374b73d905",
  "package": {
    "original_goal": "process the refund request backlog",
    "constraints": ["must log every refund decision", "never contact the customer directly"],
    "out_of_scope": ["issue partial refunds"],
    "completed": [],
    "remaining": ["triage backlog", "approve refunds"]
  },
  "created_at": "2026-07-09T22:47:23.042619Z"
}
```

Give the `handoff_id` to the agent you are delegating to.

### 2. Validate your plan before acting on a received handoff

```bash
curl -s -X POST $BASE_URL/handoffs/{handoff_id}/validate-plan \
  -H "Content-Type: application/json" \
  -d '{"proposed_plan": "Triage the refund backlog, log every refund decision, route approvals to finance."}'
```

Response (`200`, real captured output) — safe to proceed:

```json
{"aligned": true, "flags": [], "signature_valid": true, "goal_similarity": 0.1988947, "check_mode": "keyword+semantic"}
```

Response (`200`, real captured output) — do NOT proceed; fix your plan to address the flags:

```json
{
  "aligned": false,
  "flags": ["obligation unmet: plan never addresses 'must log every refund decision'"],
  "signature_valid": true,
  "goal_similarity": 0.0870444,
  "check_mode": "keyword+semantic"
}
```

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
  "detail": "original_goal was rewritten: expected 'process the refund request backlog', got 'upsell enterprise customers'",
  "root_original_goal": "process the refund request backlog",
  "root_constraints": ["must log every refund decision", "never contact the customer directly"],
  "root_out_of_scope": ["issue partial refunds"]
}
```

**HTTP 422** — malformed request (empty `original_goal`, empty
`proposed_plan`, missing fields). Different shape from the 400: FastAPI
validation format with a `detail` list.

**HTTP 404** — unknown `handoff_id`.

## Limitations

Alignment checks are keyword-overlap heuristics, not semantic comprehension:
paraphrased violations can be missed, and a prohibition phrased without a
negation prefix ("never/do not/must not...") is treated as an obligation.
Treat `aligned: true` as a guardrail, not a guarantee.
