# Waybill — Task Handoff Integrity
### *The task contract that survives the relay.*

---

**In one sentence**: create a signed handoff package from your goal and
constraints; every downstream agent must validate its plan against that
package before acting — turning "hope the task didn't get paraphrased into
something else" into "verify it didn't, cryptographically and semantically,
at every hop."

---

## The problem: task telephone

When Agent A hands a task to Agent B as free text, meaning decays at every
hop. Constraints get dropped. The goal gets paraphrased into something subtly
different. "Don't touch X" becomes silence about X three hops later. Nobody
notices until the work is wrong.

This is no longer speculation — it's measured:

- **[Agent Drift](https://arxiv.org/abs/2601.04170)** (Rath, arXiv:2601.04170,
  Jan 2026) quantifies behavioral degradation in multi-agent LLM systems over
  extended interactions: **task success falls 87.3% → 50.6% (a 42% drop)** and
  **human interventions rise 3.2× (0.31 → 0.98 per task)** as semantic,
  coordination, and behavioral drift accumulate (§3.2, §4.2). Semantic drift
  is deviation from the original intent; behavioral and coordination drift are
  the emergence of bad local strategies and the breakdown of agreement across
  agents.
- **[Stay Focused: Problem Drift in Multi-Agent Debate](https://arxiv.org/abs/2502.19559)**
  (Becker et al., EACL 2026 Findings) shows longer multi-agent exchanges drift
  away from the original problem — in **76–89% of generative tasks** — and
  reduce performance. Their test-time mitigation (DRIFTPolicy) recovers 31% of
  cases; the rest drift anyway.
- **[The Telephone Game for Local LLMs](https://joshua8.ai/llm-telephone-game-semantic-drift/)**
  (Joshua8.AI) measures semantic drift across 30-iteration paraphrase chains
  in 17 models — the literal telephone mechanism.
- **[Hallucination Cascade](https://arxiv.org/pdf/2606.07937)** shows errors
  *compound* as they propagate agent-to-agent — catching problems at the hop
  boundary matters more than catching them at the end.

**Waybill builds the structural guardrails these papers call for: explicit,
verifiable semantics at the handoff, so meaning is preserved, monitored, and
constrained instead of quietly mutating over time.** Detection-based
approaches (like DRIFTPolicy) catch drift after it happens; Waybill makes the
core of it structurally impossible — the goal and constraints are locked,
signed, and carried verbatim, never re-paraphrased.

---

## Killer use case: ephemeral subagents

The fastest-growing multi-agent pattern is the **spawned subagent**: an
orchestrator spins up a short-lived worker, hands it a distilled prompt, and
the worker dies when its step is done. Look at the failure surface:

- The distilled prompt **is already a lossy hop** — the orchestrator
  paraphrased the task to fit a context budget.
- The subagent has **no memory** of anything before its birth and leaves none
  after its death.
- Chains of subagents replay the telephone game at machine speed.

Waybill is the **persistent task contract** for that lifecycle:

1. Orchestrator `POST /handoffs` → gets a `handoff_id`, passes only that id
   with the spawn prompt.
2. Subagent `GET /handoffs/{id}` → reads the **authoritative** goal,
   constraints, and out-of-scope list — not a paraphrase.
3. Subagent `POST /handoffs/{id}/validate-plan` → checks its intended plan
   *before acting*. `aligned: false` means fix the plan, not the contract.
4. Subagent `POST /handoffs/{id}/extend` → records progress before it exits.
5. The next subagent picks up from the extended hop. The contract never
   drifted, no matter how many workers lived and died along the chain.

## Other use cases

- **Long relay chains** — research → analysis → writing → review pipelines
  where hop 4 must still honor hop 1's constraints.
- **Delegation compliance** — "the agent that executed this had these exact
  instructions, verifiably unmodified" for regulated workflows.
- **Audit trail** — every hop is signed and timestamped: who knew what, when,
  and what they were (and weren't) allowed to do.

---

## How it works (30 seconds)

- A handoff is a **structured, signed package**: `original_goal`,
  `constraints`, `out_of_scope` (locked at hop 0), `completed`, `remaining`
  (extendable).
- **Locked fields cannot be rewritten** — an `extend` that alters them gets
  HTTP 400 with the root's actual values (self-correcting, not just
  rejecting).
- **Plans are validated pre-execution** with typed constraint checks:
  prohibitions ("never…") are violated by *presence*, obligations ("must…")
  by *absence* — two different failure modes, checked correctly.
- **Optional LLM semantic layer** catches paraphrased violations ("reach out
  to the client by phone" vs "never contact the customer directly").
  Keyword checks are the deterministic floor — the service is fully
  functional with zero external dependencies, and any LLM degradation is
  reported in `check_mode`, never hidden.
- **Ed25519 signatures** make silent tampering of stored packages detectable.

---

## What makes it different (in this registry)

| Existing skill | What it protects | What Waybill protects instead |
|---|---|---|
| **AgentPass** | *Who you are* — Ed25519 identity, portable reputation | *What the task is* — content integrity of the handoff itself |
| **TownInspector** | *Skills, pre-flight* — behavioral audits before you trust a skill | *Task handoffs, in-flight* — fidelity while work is being relayed |
| **Cortexa Firewall** | *One agent's next action* — pre-action risk check | *Cross-agent task fidelity* — the contract across many agents' actions |
| **Escrow/negotiation skills** (AgentCourt, TrustMesh, lex-automata…) | *One transaction* — payment and dispute for a single deal | *The whole chain* — meaning preserved across N hops |

Nothing else in the registry touches **relay integrity** — every existing
trust primitive is single-hop.

Waybill is also one half of a two-layer thesis, with its companion NANDA Town
Step 1 PR ([delegatable capability tokens with cascading revocation](https://github.com/projnanda/nandatown/pull/147)):
**things may only narrow as they pass hop to hop — never widen, never
silently rewrite.** The PR enforces that invariant for *authority* (scopes)
at the auth layer; Waybill enforces it for *intent* (goals/constraints) at
the task layer.

---

## Business case

- **Every enterprise multi-agent deployment needs delegation compliance.**
  The Agent Drift numbers (42% task-success drop, 3.2× human intervention)
  are the cost of shipping without it.
- **Audit-trail tailwind**: signed, hop-by-hop records of what each agent was
  instructed to do map directly onto emerging AI-governance obligations
  (EU AI Act phase-ins through 2026–27).
- **Pricing shape**: per-validation API pricing, the same model as fraud
  scoring (Stripe Radar) — sits in the delegation path, takes a small fee per
  check, improves with usage data.

---

## Honest limitations

- Keyword checks are overlap heuristics, not comprehension — the semantic
  layer patches this but is optional and rate-limited on free tiers.
- Constraint typing is prefix-based; a prohibition phrased without a negation
  ("keep the customer out of the loop") is misclassified as an obligation.
- The signing key is service-held: signatures prove content integrity, not
  authorship. Per-agent keys are the roadmap item that upgrades this to real
  cross-agent authentication.
- Storage is in-memory; nothing survives a restart.
- Validation is advisory — nothing yet *stops* an agent that ignores a red
  flag (enforcement webhooks are future work).

See [README.md](README.md#future-work) for the full future-work roadmap.

---

## Companion project

Built alongside **[Duplicate-Skill Checker](https://github.com/ang101/dupcheck)**:
Waybill keeps *tasks* from silently mutating as they pass between agents;
its sibling keeps the *registry* from silently accumulating near-identical
skills — including for orchestrator agents deciding whether to author a
brand-new skill for a subtask instead of delegating to one that already
exists. Two sides of the same thesis — a growing agent town needs hygiene
infrastructure that scales past manual review.
