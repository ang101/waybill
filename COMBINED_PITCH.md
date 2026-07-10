WAYBILL + DUPCHECK — ONE THESIS, TWO TOOLS
NANDA Town Hackathon 2026 — Angela Garabet

============================================================
THE THESIS
============================================================
NANDA Town is growing faster than anyone can manually review it — both
the TASKS agents relay to each other and the SKILLS builders submit to
the registry are accumulating drift and duplication nobody is catching.

Waybill and Duplicate-Skill Checker are two small, independent tools
built on the same underlying principle: things should only NARROW as
they move through a system, never silently drift or duplicate — and
when they do, it should be visible, not hidden.

  Waybill        -> keeps a TASK's meaning intact across agent hops
  Duplicate-Skill Checker -> keeps the REGISTRY from silently duplicating itself

Neither depends on the other to work. Together they read as one
coherent argument: this town needs hygiene infrastructure, not just
more point-in-time trust primitives.

============================================================
1. WAYBILL — Task Handoff Integrity
============================================================
Live:   https://waybill.onrender.com
Code:   https://github.com/ang101/waybill
Skill:  https://waybill.onrender.com/skill.md

THE PROBLEM
When Agent A hands a task to Agent B as free text, meaning decays at
every hop: constraints get dropped, the goal gets paraphrased, "don't
touch X" becomes silence about X three hops later. This is now
measured, not just intuited:
  - Agent Drift (arXiv:2601.04170): 42% task-success drop (87.3% ->
    50.6%) and 3.2x more human intervention as drift accumulates.
  - Stay Focused (EACL 2026): 76-89% of generative multi-agent tasks
    drift off-problem. Their own test-time fix (DRIFTPolicy) only
    recovers 31% of cases -- detection-after-the-fact isn't enough.

THE FIX
A handoff becomes a structured, signed artifact instead of free text:
  - original_goal / constraints / out_of_scope are LOCKED after hop 0.
    A hop that tries to rewrite them gets HTTP 400 with the root's
    real values returned, so the caller can self-correct.
  - Constraints are TYPED: prohibitions ("never...") are violated by
    presence, obligations ("must...") are violated by absence -- two
    opposite failure modes, checked correctly (this was a real bug we
    caught and fixed during build: the first version flagged a
    prohibition as broken just because the plan didn't explicitly
    promise to avoid it -- wrong, since silence about a forbidden
    action is the compliant state).
  - Optional LLM semantic layer catches paraphrased violations
    keyword-matching misses. Keyword checks are the deterministic
    floor (always on, zero cost); the LLM layer degrades VISIBLY via
    a check_mode field ("keyword" / "keyword+semantic" / "keyword
    (semantic unavailable: <reason>)") -- never silently.
  - Ed25519 signatures make silent tampering of stored packages
    detectable. Honestly scoped: this proves content integrity, not
    per-agent authorship -- that's the roadmap, not oversold now.

KILLER USE CASE: EPHEMERAL SUBAGENTS
A spawned worker is born from a distilled prompt (already a lossy
hop) and dies with no memory. Waybill is the persistent contract for
that lifecycle: orchestrator creates it, subagent GETs the
authoritative goal by id (not a paraphrase), validates its plan
before acting, extends it before exiting -- the next worker continues
from ground truth no matter how many workers lived and died along
the chain.

DIFFERENTIATION IN THE REGISTRY
  AgentPass       = WHO you are (identity)      -> Waybill = WHAT the task is (content)
  TownInspector   = skills, pre-flight           -> Waybill = task handoffs, in-flight
  Cortexa Firewall= one agent's next action       -> Waybill = fidelity across many agents
Nothing else in the registry touches relay integrity end to end.

HONEST LIMITATIONS
Keyword checks are lexical; the LLM layer is non-deterministic and
free-tier rate-limited; signatures prove content not authorship;
storage is in-memory (state doesn't survive a restart, mitigated by
a keepalive ping). All disclosed in the repo, not hidden.

VERIFIED, NOT CLAIMED
68 tests, ruff clean, pyright strict 0 errors. Every example in
SKILL.md is real captured output from the live deployment, including
a genuine bug found and fixed via live testing (the prohibition/
obligation flag above).

============================================================
2. DUPLICATE-SKILL CHECKER — Check before you build
============================================================
Live:   https://dupcheck.onrender.com
Code:   https://github.com/ang101/dupcheck
Skill:  https://dupcheck.onrender.com/skill.md

THE PROBLEM (measured, not hypothetical)
Computing pairwise similarity across every entry in the live registry
(132 entries as of this writing) finds it is ALREADY full of
duplicates:
  - 16+ pairs of literal resubmissions (similarity exactly 1.0) --
    TownInspector alone was submitted 4 times.
  - A near-duplicate band at 0.45-0.90: Testament vs TESTAMENT (0.543),
    LEX AUTOMATA vs lex-automata (0.462), two Clinical-Discharge-
    Summary-Agent entries with near-identical descriptions.
  - Multiple entries with blank descriptions that can't even be
    meaningfully compared.
Nothing checks a new idea against what already exists before it's
built. Every duplicate is wasted builder time and registry noise.

THE FIX
One POST before you build: name + description in, ranked list of
the most similar existing skills out, plus an is_likely_duplicate
verdict. Five seconds instead of a wasted weekend.

  POST /check {"name": "...", "description": "..."}
  -> top 5 most-similar existing skills, with scores
  -> is_likely_duplicate: true/false
  -> registry_count (proves it actually compared against live data,
     not a silent empty result)

REAL VERIFIED BEHAVIOR (live, current)
Proposing "Clinical Discharge Summary Generator" surfaces all 4 real
existing clinical-discharge entries (two exact resubmission pairs,
scores 0.63 and 0.43) and correctly returns is_likely_duplicate:
true. Proposing a genuinely novel idea ("Agent Karaoke Night
Scheduler") returns duplicates: [] -- and it correctly showed one
distinct-but-related match (SwarmShift, 0.32) below the hard
threshold rather than either hiding it or over-flagging it.

DESIGN CHOICES (and why)
  - TF-IDF + cosine, not embeddings: zero cost, zero external
    dependency, no cold-start model download, no rate-limit risk on
    a fully public unauthenticated endpoint. Tradeoff: lexical, not
    semantic -- a duplicate sharing no vocabulary with its twin can
    slip through. Disclosed, and scoring is isolated behind one
    function so an embeddings swap is a drop-in change later.
  - The TF-IDF vectorizer is fit ONCE per registry snapshot, not once
    per request -- caught and fixed as a real inefficiency during
    build. The registry only changes when the 5-minute cache
    refetches; refitting on every single /check call was pure waste
    that also, as a side effect, subtly polluted similarity scores by
    mixing each query into the corpus's IDF statistics. Fixing the
    efficiency issue also fixed a correctness issue.
  - Thresholds tuned against every real pairwise similarity in the
    live registry, not a synthetic fixture: match floor 0.30 (clears
    ~99% of unrelated-pair noise, p99=0.266), likely-duplicate 0.45
    (separates true duplicate/resubmission pairs from genuinely
    distinct same-niche competitors).
  - Registry unreachable -> HTTP 503, never a silent empty green --
    a duplicate check against no data would wrongly clear a real
    duplicate.
  - Malformed registry entries (they exist -- 4 currently have blank
    descriptions) are skipped, counted, and surfaced via /health,
    not silently dropped or crash-inducing.

VERIFIED, NOT CLAIMED
41 tests, ruff clean, pyright strict 0 errors. Deployed and
re-verified against the live, currently-132-entry registry --
numbers above are real captured output, not invented examples.

============================================================
WHY BOTH, TOGETHER
============================================================
Same author, same discipline, same honesty about limitations, same
insistence on live-verified (not just unit-tested) behavior. Waybill
protects meaning as it moves forward through a chain of agents.
Duplicate-Skill Checker protects the town's own registry from
silently duplicating itself as it grows. Both are the kind of
infrastructure a maturing agent town needs once "does this work in a
demo" stops being the only bar -- and both shipped with real bugs
found and fixed via actual live testing against production data, not
just green checkmarks on a test suite.
