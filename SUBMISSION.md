# How to submit Waybill to NANDA Town

Step-by-step guide for the skills-page submission, with every field
pre-filled and copy-paste ready. Form fields confirmed against the live
skills page on 2026-07-10.

## Before you submit — 2-minute pre-flight

Run these and confirm both return healthy output (endpoints are
live-checked by the registry at submission time):

```bash
curl https://waybill.onrender.com/health
# expect: {"status":"ok","signing":"seeded","semantic_check":"configured"}

curl https://waybill.onrender.com/skill.md
# expect: the full SKILL.md markdown
```

If `signing` says `"ephemeral"` — STOP: the `WAYBILL_SIGNING_KEY_SEED`
env var got lost on Render; fix it in the dashboard before submitting.

## The form

Go to **https://nandatown.projectnanda.org/skills** and find the submit
form. Fill in:

| Field | Value (copy-paste) |
|---|---|
| **Skill name** | `Waybill — Task Handoff Integrity` |
| **Your name or team** | Angela Garabet |
| **Email** | agarabet@gmail.com *(private, only visible to the NANDA team)* |
| **GitHub username** | `ang101` |
| **One-line description** | `Validate task handoffs between agents — prevents goal drift, dropped constraints, and scope creep when work passes through multiple agents or ephemeral subagents.` |
| **Submission method** | Choose **Hosted link to .md file** |
| **SKILL.md hosted link** | `https://waybill.onrender.com/skill.md` |
| **Endpoint URLs** (one per line) | see below |
| **Tags** | `handoff, delegation, task-integrity, drift, validation, multi-agent, coordination, orchestration, subtask, safety` |

**Endpoint URLs — paste exactly this, one per line:**

```
https://waybill.onrender.com/handoffs
https://waybill.onrender.com/skill.md
https://waybill.onrender.com/health
```

*(The parameterized endpoints — `/handoffs/{id}/extend`,
`/handoffs/{id}/validate-plan`, `/handoffs/{id}` — are documented in
SKILL.md; the registry's reachability checker needs concrete URLs, and a
templated path would fail its live check.)*

## After submitting

1. Search the skills page for "handoff" or "waybill" and confirm the
   entry appears and shows as reachable.
2. Optionally run the Duplicate-Skill Checker against your own entry to
   confirm it now shows up as prior art for handoff-related proposals.

## Remaining deadlines (ET)

- **Sat Jul 11, 2:00 PM** — edit window closes; **demo video due**.
  Record `scripts/demo.sh` running against the live URL (all 4 acts),
  plus a short segment of an agent using the service from SKILL.md alone.
- **Sun Jul 12, 2:00 PM** — final Google form due (link on the hackathon
  page). Have ready: the skills-page entry, this repo's URL, the video.

## Demo video crib sheet (4 acts, ~3 minutes)

```bash
BASE_URL=https://waybill.onrender.com bash scripts/demo.sh
```

1. **Act 1–2**: coordinator creates the signed root; hop 1 extends it
   compliantly — point out `hop_index`, the signature, and that
   goal/constraints carried verbatim.
2. **Act 3 GREEN**: compliant plan → `aligned: true`, empty flags,
   `check_mode: "keyword+semantic"`.
3. **Act 3 RED**: plan that silently drops the logging obligation →
   `aligned: false` with the deterministic `obligation unmet` flag plus
   the LLM's `semantic:` flags.
4. **Act 4 TAMPER**: a hop tries to rewrite the goal → HTTP 400 with the
   root's actual values returned so the caller can self-correct.

Talking points if asked:
- "Signatures prove content integrity, not authorship — per-agent keys
  are the roadmap item" (don't oversell the crypto).
- "Keyword checks are the deterministic floor; the LLM layer adds
  paraphrase recall and degrades *visibly* via check_mode."
- "The killer use case is ephemeral subagents — born from a lossy
  distilled prompt, dead after one step; Waybill is the task contract
  that outlives them."
