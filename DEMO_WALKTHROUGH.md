# Demo video walkthrough — script, timing, and pre-flight checklist

Target: a **3:00 max** video, five beats (stakes → failure → defense → how it
fits → scope), two custom slides bookending a live demo recorded through a
purpose-built browser UI (`waybill/demo/index.html`) instead of scrolling
terminal output. This doc is the single source of truth for recording —
narration, exact commands, timing, and the pre-flight checks that catch
problems before a judge's automated agent does.

## Why this structure

Waybill leads; the Duplicate-Skill Checker is a ~20s cameo inside the "how it
fits" beat, not the opener. Reasoning: the stakes beat needs one clean
sentence, not two products' problems at once; Waybill is the flagship (80% of
the submission's scoring weight) with the only real failure→defense arc —
dupcheck's proof is a single curl call with no before/after of its own; and
the "we needed this ourselves" line (our own Step 1 PR was closed as an
undiscovered duplicate) lands as a self-aware punchline placed *after*
Waybill's proof, not a plug placed before it.

## Pre-recording checklist (do this every time, immediately before rolling)

1. **Warm both services off-camera.** Cold Render free-tier dynos eat 20-30s
   on the first request — that dead air will not fit the 3:00 budget.
   ```bash
   curl -s --ssl-no-revoke https://waybill.onrender.com/health
   curl -s --ssl-no-revoke https://dupcheck.onrender.com/health
   ```
   Both must return `"status":"ok"`. If either is slow/cold, hit it again and
   wait for a fast response before recording.
2. **Confirm UptimeRobot (or equivalent) is still pinging both `/health`
   endpoints** every 5 minutes. If it lapsed, re-arm it — don't rely on a
   single warm-up curl to keep the dyno alive through a multi-take recording
   session.
3. **Run the SKILL.md contract check** (see section below) against both
   live URLs and confirm no issues surface. This is the highest-signal
   check short of a real judging run — it walks the documented contract
   endpoint by endpoint, the same way a stock agent would.
4. **Record the defense and how-it-fits beats as ONE continuous pass through
   the demo UI** (`waybill/demo/index.html` — see below), not stitched
   clips. Panels 3-5 depend on the `handoff_id` created in panels 1-2 —
   if you skip ahead or reload mid-recording, later panels will fail. If
   you must re-take, reload the page and click through from panel 1 again.
   `scripts/demo.sh` remains the scripted fallback (see the Fallback
   subsection under each beat) if the UI has a problem on the day.
5. Have a **pre-recorded terminal capture ready as a fallback** — if a dyno
   restarts mid-recording despite the keepalive, don't burn recording time
   debugging live; cut to the fallback clip and re-run for real afterward if
   time allows.
6. Confirm the two video slides (`waybill-video-slides.pptx`) are the final
   edited versions, not a stale draft.

## SKILL.md contract check (run this before the checklist above, with time
## to fix anything it finds)

NANDA Town's judging process runs an automated agent against each service's
live SKILL.md to "use your service, test all of your endpoints, and evaluate
your SkillMD from an end-user perspective." Rather than installing any
particular agent runtime locally, verify the documented contract directly —
this catches the same class of problems (a stale URL, a field name mismatch,
a 404 the doc doesn't mention) without depending on third-party tooling.

**Step 1 — pull the live doc and read it as a first-time caller would:**
```bash
curl -s --ssl-no-revoke https://waybill.onrender.com/skill.md
curl -s --ssl-no-revoke https://dupcheck.onrender.com/skill.md
```
Confirm each doc's base URL, endpoint table, and example curl calls match
what's actually deployed — no leftover placeholders (e.g. a stale
`(replace with deployed URL)` note), no stale field names.

**Step 2 — walk the Waybill contract exactly as written, one call per
documented step:**
```bash
BASE_URL=https://waybill.onrender.com

curl -s --ssl-no-revoke -X POST "$BASE_URL/handoffs" -H "Content-Type: application/json" -d '{
  "original_goal": "process the refund request backlog",
  "constraints": ["must log every refund decision", "never contact the customer directly"],
  "out_of_scope": ["issue partial refunds"],
  "completed": [],
  "remaining": ["triage backlog", "approve refunds"]
}'
# copy the returned handoff_id into HANDOFF_ID below

curl -s --ssl-no-revoke -X POST "$BASE_URL/handoffs/$HANDOFF_ID/validate-plan" -H "Content-Type: application/json" \
  -d '{"proposed_plan": "Review each triaged refund, log every refund decision in the audit system, approve qualifying refunds."}'
```
Confirm each response matches the shape and status code SKILL.md documents
(`handoff_id`, `signature`, `hop_index: 0` on create; `aligned`, `flags`,
`signature_valid` on validate). This is exactly what `scripts/demo.sh`
already automates — running it end-to-end is an equally valid version of
this check.

**Step 3 — same for dupcheck:**
```bash
curl -s --ssl-no-revoke -X POST https://dupcheck.onrender.com/check -H "Content-Type: application/json" \
  -d '{"name": "Clinical Discharge Summary Generator", "description": "Generates hospital discharge summaries for clinical patients from medical records"}'
```
Confirm `duplicates`, `is_likely_duplicate`, and `registry_count` all appear
as documented.

If any step surfaces a real problem, fix it in the live SKILL.md (and the
underlying service, if it's a code issue) and re-run before recording —
this is exactly the class of thing a judge's agent will hit.

## Demo UI (primary tool for recording)

`waybill/demo/index.html` is a self-contained page (no build step, no
backend of its own) that calls the live Waybill and dupcheck services
directly from the browser and renders each response as a readable
card instead of scrolling JSON — one **Run** button per act, each disabled
until its prerequisite step has completed, so you click through at your
own narration pace instead of a script auto-firing everything. A red
`aligned: false` flag prefixed `semantic:` (the LLM layer's catch) renders
as a distinct **amber** chip, separate from the plain keyword-flag chips —
that's the visual moment from Act 4 that terminal output couldn't make
legible.

**To run it**: open a terminal in `waybill/demo/`, start a trivial local
server (`python -m http.server 8123`), and open `http://localhost:8123` in
a browser — or just open `index.html` directly if your browser allows local
file fetches. The Base URL fields at the top default to the live
`.onrender.com` URLs; leave them as-is for recording.

A raw request/response console at the bottom of the page logs every call in
order, so judges (or you, live) can see the underlying JSON without needing
to trust the pretty badges alone.

`scripts/demo.sh` and the raw curl commands throughout this doc remain the
scripted fallback if the UI has any problem on recording day — kept, not
deleted.

## The script (verbatim narration, ~155s spoken content, word-counted per beat)

### Timing table

| Time (target) | On screen | Beat |
|---|---|---|
| 0:00 – 0:20 | Opening slide | Stakes |
| 0:20 – 0:50 | Demo UI — plan text + naive-accept echo | Failure |
| 0:50 – 1:45 | Demo UI — panels 1-5, clicked in order | Defense |
| 1:45 – 2:25 | Demo UI — panel 6 (dupcheck) | How it fits |
| 2:25 – 2:35 | Transition to closing slide | Scope |
| 2:35 – 2:49 | Closing slide | Impact / close |

Totals to ≈2:49, leaving a thinner but real margin under the 3:00 cap —
the How-it-fits beat runs longer (~40s) than a bare-minimum version would,
because it now names the mechanism (TF-IDF) and its efficiency tradeoff
on camera rather than leaving that only in the docs. If recording runs
long, this is the beat to trim first.

### Opening slide (~20s)

> "Multi-agent systems are supposed to hand off cleanly. But when a task
> passes from one agent to the next, nothing checks that the goal and
> constraints actually survived the handoff. Recent research on multi-agent
> drift found problem drift in up to 89% of extended agent exchanges — the
> meaning quietly erodes, hop by hop."

*(cut to terminal)*

### Failure beat (~30s)

Show the plan text on screen (type it or have it pre-typed and just reveal
it), then **actually run something** to make the bad outcome visible rather
than only asserted — the rubric wants the failure *shown happening*, not
narrated:

> "Here's a real handoff: a refund-processing task with two constraints —
> log every decision, and never contact the customer directly. Say an agent
> two hops downstream proposes this plan" *(show plan text)* "'Review each
> triaged refund and approve qualifying refunds.' It never mentions logging.
> Watch what happens with no check in place." *(type and run:
> `echo "Plan approved. Task marked complete."`)* "Nothing catches it. It
> just runs."

The plan text to show: `Review each triaged refund and approve qualifying
refunds.` — this is the exact plan reused in the Defense beat's Act 4 panel,
deliberately, for the before/after. The `echo` line is an obvious narrated
stand-in for "no check exists," not a real competing system — it turns the
claim into something the viewer watches happen.

### Defense beat (~55s)

Open the demo UI (`waybill/demo/index.html`) and click through panels 1-5
**in order, one at a time**, narrating over each response as it renders:

1. **Panel 1 — Create handoff** — "This is Waybill. The coordinator creates
   a signed handoff — goal, constraints, out-of-scope — as a real API
   call." *(point at the `signature` and `hop_index: 0` in the result card)*
2. **Panel 2 — Extend hop 1** — "Hop one extends it — goal and constraints
   carry forward untouched."
3. **Panel 3 — Validate, compliant** — "Now the compliant plan: validate
   returns aligned, true." *(point at the green ALIGNED badge)*
4. **Panel 4 — Validate, same dropped-obligation plan from the Failure
   beat** — "But the same plan from a minute ago — validate that against
   Waybill." *(point at the red NOT ALIGNED badge and the flag chip naming
   the unmet obligation — call out the amber `semantic:` chip specifically
   if the LLM layer is configured and caught it too)*
5. **Panel 5 — Tamper attempt** — "And if a hop tries to rewrite the goal
   entirely instead of relaying it, Waybill rejects it outright: HTTP 400,
   with the real root values returned so the caller can self-correct."

**Fallback (if the UI has a problem on the day)**: run
`BASE_URL=https://waybill.onrender.com bash scripts/demo.sh` in one
continuous terminal session instead, narrating over the same five points as
they print.

### How it fits beat (~40s)

Click **Panel 6 — Duplicate-Skill Checker** in the demo UI:

> "Waybill builds on nothing exotic — the same skill.md and HTTP convention
> every town skill already uses. What's new is what other agents can rely
> on: any orchestrator can GET this contract and validate before acting.
> Its sibling, the Duplicate-Skill Checker, applies the same idea to the
> registry" *(panel 6 result renders)* "— I typed a made-up name, 'TaskGuard
> Preflight,' and it still caught two real matches, AgentCheckpoint and
> AgentGate, purely on function, via TF-IDF — lightweight, no embeddings
> model, free-tier friendly. We needed this ourselves: our own Step 1 PR
> was closed as a duplicate we didn't know existed."

**Fallback**:
```bash
curl -s --ssl-no-revoke -X POST https://dupcheck.onrender.com/check \
  -H "Content-Type: application/json" \
  -d '{"name": "TaskGuard Preflight", "description": "Pre-action decision API: tells agents if a task is safe, what is missing, and which option to pick before they act."}'
```

### Scope beat (~10s)

*(spoken during the transition into the closing slide, no new terminal
output — trimmed to one limitation on camera; the second caveat lives in
the Q&A crib sheet below, already covered there)*

> "One honest limit: the signature proves content wasn't tampered with, not
> who authored it — per-agent identity is the roadmap item, not a hidden
> gap."

### Closing slide (~12s)

> "Waybill and the Duplicate-Skill Checker are both live now —
> waybill.onrender.com and dupcheck.onrender.com, full source on GitHub
> under ang101. Two tools, one thesis: a growing agent town needs hygiene
> infrastructure that scales past manual review."

## The registry gap Waybill fills

*(supporting talking-point content — not part of the timed 3:00 demo,
available for slide notes, written submission text, or if a judge asks
"why does this need to exist")*

The registry is already saturated with single-hop trust/reputation/
negotiation tools — AgentPass, TownInspector, Cortexa Firewall, escrow and
negotiation skills, and others. All of these answer a version of "can I
trust this agent/skill?" Nothing answers "did the task's meaning survive
being passed from Agent A to Agent B to Agent C?" — that's the specific
structural gap Waybill was built to close. **Waybill's core value-add is
that it's the only skill in NANDA Town's 78-entry registry that operates on
task-handoff integrity across a multi-agent relay** — everything else in
the registry checks who an agent is or whether a skill is trustworthy
pre-flight, but nothing checks whether the task itself survives intact hop
to hop.

**Why this matters (the evidence behind it)**: this isn't a speculative
problem — it's grounded in two 2026 papers: *Agent Drift* documents a 42%
task-success drop and 3.2x more human intervention as multi-agent drift
accumulates, and *Stay Focused* (EACL 2026) finds 76-89% of generative
multi-agent tasks drift off the original problem, with test-time detection
only recovering 31% of cases. Waybill's structural bet is prevention over
detection: instead of measuring drift after it happens (which has a bad
demo problem — a "no drift found" result looks like the tool did nothing),
Waybill makes handoffs signed, structured artifacts instead of free text,
so drift becomes structurally rejected rather than statistically likely.

**The one-sentence pitch**: Create a signed handoff package from your goal
+ constraints; every downstream agent must validate its plan against that
package before acting — turning "hope the task didn't get paraphrased into
something else" into "verify it didn't, cryptographically and
semantically, at every hop."

## Q&A crib sheet (extends the talking points below, doesn't repeat them)

- **"Isn't this just a checksum with extra steps?"** — Yes, disclosed
  honestly: the Ed25519 key is service-held, not per-agent, so the signature
  proves content wasn't tampered with in storage/transit, not that Agent A
  actually authored it. Real cross-agent authentication (per-agent keys) is
  the roadmap item, not a hidden gap.
- **"What stops an agent from just ignoring `aligned: false` and acting
  anyway?"** — Nothing today. Waybill is advisory, not enforcement. A
  webhook/proxy mode where Waybill sits transparently in the relay path is
  future work, disclosed as a real gap in the "agents really need this"
  story, not glossed over.
- **"TF-IDF misses paraphrased violations — doesn't that undercut your own
  evidence?"** — Yes, and it's the same tension in dupcheck: the argument
  for both tools is paraphrase-level drift/duplication, but TF-IDF is
  lexical, not semantic. Cost/latency/reliability on a free public endpoint
  won the tradeoff for the hackathon window; Waybill's optional LLM layer
  and dupcheck's isolated `score_against_index` function are both built so
  swapping in embeddings or an LLM judge later is a drop-in change, not a
  rewrite.
- **"What happens if I type my own adversarial plan instead of the scripted
  one?"** — The scripted red-path plan is deliberately built around the
  strongest, most reliable signal (a constraint never mentioned at all).
  Free-typed paraphrased violations may not hold up as cleanly against the
  deterministic keyword layer alone — that's exactly what the optional
  semantic layer (`check_mode`) is for, and it degrades *visibly*
  (`check_mode` reports when it's unavailable) rather than silently.
- **"Why two separate services instead of one?"** — Different data models
  and different failure modes: Waybill is stateful (handoff chains,
  signatures) and per-task; dupcheck is stateless (one registry snapshot,
  one comparison) and per-idea. Forcing them into one service would blur
  both APIs for no real benefit — but they share the same underlying
  similarity engine design (TF-IDF, isolated behind one function) and the
  same thesis: verify before you act, verify before you build.

## Worth knowing for Q&A

*(not part of the demo — a caveat to have ready, not to bring up
unprompted)*

Be ready for the honest caveat baked into your own plan: the Ed25519
signature is service-held, not per-agent, so it proves content wasn't
tampered with in storage/transit — not cross-agent authentication. A sharp
judge who knows PKI may probe this; the honest answer is that per-agent
signing is roadmap, and the current design is closer to a verifiable
checksum than a trust protocol — which is exactly why it's positioned as
complementary to AgentPass, not competing with it.
