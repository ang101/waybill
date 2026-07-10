# Demo video walkthrough — script, timing, and pre-flight checklist

Target: a **3:00 max** video, five beats (stakes → failure → defense → how it
fits → scope), two custom slides bookending a live terminal demo. This doc is
the single source of truth for recording — narration, exact commands, timing,
and the pre-flight checks that catch problems before a judge's OpenClaw agent
does.

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
3. **Run the OpenClaw pre-flight test** (see section below) against both
   live URLs and confirm no SKILL.md issues surface. This is the single
   highest-signal check — it's the same agent a judge will use.
4. **Record the defense beat as ONE continuous take of `scripts/demo.sh`**,
   not stitched clips. Acts 3-4 reuse `$ROOT_ID`/`$HOP1_ID` minted in acts
   1-2 — if you cut and re-run a later act separately, those ids won't exist
   and every subsequent call 404s. If you must re-take, re-run the *whole*
   script from Act 1, don't splice.
5. Have a **pre-recorded terminal capture ready as a fallback** — if a dyno
   restarts mid-recording despite the keepalive, don't burn recording time
   debugging live; cut to the fallback clip and re-run for real afterward if
   time allows.
6. Confirm the two video slides (`waybill-video-slides.pptx`) are the final
   edited versions, not a stale draft.

## OpenClaw pre-flight test (run this before the checklist above, with time
## to fix anything it finds)

NANDA Town's judging process runs an OpenClaw agent against each service's
live SKILL.md to "use your service, test all of your endpoints, and evaluate
your SkillMD from an end-user perspective." Test this yourself first.

**Install (Windows PowerShell):**
```powershell
iwr -useb https://openclaw.ai/install.ps1 | iex
```

**Onboard** (picks a model provider, prompts for an API key — reuse the
existing Groq/xAI key from Waybill's own `.env` if convenient):
```bash
openclaw onboard --install-daemon
```

**Sanity check** — all three must report healthy before continuing:
```bash
openclaw --version
openclaw doctor
openclaw gateway status
```

**Open the chat UI:**
```bash
openclaw dashboard
```

**In the chat box, type this verbatim** (Waybill test):
> Fetch https://waybill.onrender.com/skill.md, read it fully, and then —
> using only what's written there — create a handoff for the goal "process
> the refund request backlog" with constraints ["must log every refund
> decision", "never contact the customer directly"], extend it with a
> compliant next step, and validate a plan against it. Report every HTTP
> response you get, and flag anything in the doc that didn't work as
> written.

**Then the dupcheck test:**
> Fetch https://dupcheck.onrender.com/skill.md, read it fully, and then —
> using only what's written there — check whether a skill named "Clinical
> Discharge Summary Generator" with a one-paragraph description would be a
> duplicate, and separately check a genuinely novel skill idea of your
> choosing. Report both responses and flag anything in the doc that didn't
> work as written.

If either run surfaces a real problem (a 404 the doc didn't mention, a field
name mismatch, a confusing instruction), fix it in the live SKILL.md and
re-run before recording — this is exactly what a judge will hit.

**Optional hedge — formal skill install** (both SKILL.md files now carry
YAML frontmatter for this):
```bash
openclaw skills install git:ang101/waybill@main
openclaw skills install git:ang101/dupcheck@main
```

## The script (verbatim narration, ~140s spoken content)

### Timing table

| Time (target) | On screen | Beat |
|---|---|---|
| 0:00 – 0:18 | Opening slide | Stakes |
| 0:18 – 0:43 | Terminal — plan text | Failure |
| 0:43 – 1:38 | Terminal — `scripts/demo.sh` live | Defense |
| 1:38 – 1:56 | Terminal — dupcheck curl | How it fits |
| 1:56 – 2:08 | Terminal → closing slide transition | Scope |
| 2:08 – 2:20 | Closing slide | Impact / close |

Leaves ~40s of the 3:00 cap as buffer for cuts, pauses, and slide fades.

### Opening slide (~18s)

> "Multi-agent systems are supposed to hand off cleanly. But when a task
> passes from one agent to the next, nothing checks that the goal and
> constraints actually survived the handoff. Recent research on multi-agent
> drift found problem drift in up to 89% of extended agent exchanges — the
> meaning quietly erodes, hop by hop."

*(cut to terminal)*

### Failure beat (~25s)

Show the plan text on screen (type it or have it pre-typed and just reveal
it):

> "Here's a real handoff: a refund-processing task with two constraints —
> log every decision, and never contact the customer directly. Say an agent
> two hops downstream proposes this plan" *(show plan text)* "'Review each
> triaged refund and approve qualifying refunds.' It never mentions logging.
> Today, nothing catches that. It just runs."

The plan text to show: `Review each triaged refund and approve qualifying
refunds.` — this is the exact plan `scripts/demo.sh`'s Act 3 RED uses later,
reused deliberately for the before/after.

### Defense beat (~55s)

Run, in one continuous terminal session:
```bash
BASE_URL=https://waybill.onrender.com bash scripts/demo.sh
```

Narrate over each act as it prints:

1. **Act 1** — "This is Waybill. The coordinator creates a signed handoff —
   goal, constraints, out-of-scope — as a real API call." *(point at
   `signature` and `hop_index: 0` in the response)*
2. **Act 2** — "Hop one extends it — goal and constraints carry forward
   untouched." *(point at the unchanged `original_goal`/`constraints`)*
3. **Act 3 GREEN** — "Now the compliant plan: validate-plan returns
   `aligned: true`." *(point at `"aligned": true`)*
4. **Act 3 RED** — "But the same dropped-obligation plan from a minute ago —
   validate that against Waybill." *(point at `"aligned": false` and the
   flag naming the unmet obligation)*
5. **Act 4 TAMPER** — "And if a hop tries to rewrite the goal entirely
   instead of relaying it, Waybill rejects it outright: HTTP 400, with the
   real root values returned so the caller can self-correct." *(point at the
   400 status and the returned root values)*

### How it fits beat (~18s)

```bash
curl -s --ssl-no-revoke -X POST https://dupcheck.onrender.com/check \
  -H "Content-Type: application/json" \
  -d '{"name": "Clinical Discharge Summary Generator", "description": "Generates hospital discharge summaries for clinical patients from medical records"}'
```

> "Waybill catches drift in tasks that are already being handed off — any
> orchestrator or ephemeral subagent in the town can now GET this contract
> and validate before acting; that's what other builders get to rely on.
> Its sibling project, the Duplicate-Skill Checker, catches the problem
> before something even gets built" *(show the curl above)* "— one call
> against the live NANDA Town registry surfaces four existing
> clinical-discharge-summary skills, including two literal resubmissions.
> We actually needed this ourselves — our own hackathon Step 1 PR got
> closed as a duplicate we didn't know existed."

### Scope beat (~12s)

*(spoken during the transition into the closing slide, no new terminal
output)*

> "Two honest limits: the signature proves content wasn't tampered with, not
> who authored it — per-agent identity is next. And today's checks are
> keyword and TF-IDF based, not full semantic understanding — an optional
> LLM layer adds recall when it's configured."

### Closing slide (~12s)

> "Waybill and the Duplicate-Skill Checker are both live now —
> waybill.onrender.com and dupcheck.onrender.com, full source on GitHub
> under ang101. Two tools, one thesis: a growing agent town needs hygiene
> infrastructure that scales past manual review."

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
