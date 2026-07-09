"""Optional LLM semantic alignment check — additive over the keyword base.

The keyword checks in ``alignment.py`` are the deterministic floor: they run
always, need no network, and cannot be rate-limited. This module adds recall
for what keywords structurally miss — *paraphrased* violations ("reach out
to the client by phone" against "never contact the customer directly").

Degradation is visible, never silent: every outcome carries an ``available``
flag and a ``reason``, surfaced to callers as the response's ``check_mode``
field. A missing key, a 429, or malformed model output downgrades the check
to keyword-only *and says so* — it never breaks the endpoint and never
pretends the semantic pass ran.

Provider-agnostic: any OpenAI-compatible chat-completions API works (Groq,
xAI Grok, OpenRouter, ...) — the base URL and model are env-configured.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import cast

import httpx

LLM_API_KEY_ENV_VAR = "WAYBILL_LLM_API_KEY"
LLM_BASE_URL_ENV_VAR = "WAYBILL_LLM_BASE_URL"
LLM_MODEL_ENV_VAR = "WAYBILL_LLM_MODEL"
DEFAULT_LLM_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TIMEOUT_SECONDS = 8.0
SEMANTIC_FLAG_PREFIX = "semantic:"

_VERDICT_PROMPT = """You audit whether a proposed plan stays within its assigned task contract.

TASK GOAL:
{goal}

CONSTRAINTS (obligations the plan must fulfil, prohibitions it must not do):
{constraints}

OUT OF SCOPE (the plan must not do these):
{out_of_scope}

PROPOSED PLAN:
{plan}

Identify every way the plan violates a prohibition, does something out of scope, \
or ignores an obligation — including paraphrased violations that use different \
wording. Judge meaning, not word overlap.

Respond with ONLY a JSON object, no other text:
{{"violations": ["<short description citing the violated constraint>", ...]}}

If the plan is fully compliant, respond: {{"violations": []}}"""


@dataclass(frozen=True)
class LlmConfig:
    """Connection settings for an OpenAI-compatible chat-completions API."""

    api_key: str
    base_url: str
    model: str


@dataclass(frozen=True)
class SemanticOutcome:
    """Result of one semantic check attempt.

    ``available=False`` means the check did not run (no config) or failed
    (network/parse); ``reason`` says why so callers can surface it.
    """

    flags: list[str]
    available: bool
    reason: str


def load_llm_config_from_env() -> LlmConfig | None:
    """Build an :class:`LlmConfig` from environment variables, or None if unset.

    Example::

        config = load_llm_config_from_env()
        if config is None:
            print("semantic check disabled; keyword mode only")
    """
    api_key = os.environ.get(LLM_API_KEY_ENV_VAR, "").strip()
    if not api_key:
        return None
    return LlmConfig(
        api_key=api_key,
        base_url=os.environ.get(LLM_BASE_URL_ENV_VAR, DEFAULT_LLM_BASE_URL).rstrip("/"),
        model=os.environ.get(LLM_MODEL_ENV_VAR, DEFAULT_LLM_MODEL),
    )


def semantic_alignment_check(
    config: LlmConfig,
    original_goal: str,
    constraints: list[str],
    out_of_scope: list[str],
    plan_text: str,
) -> SemanticOutcome:
    """Ask the configured LLM for paraphrase-aware violations of the contract.

    Never raises: every failure mode (HTTP error, non-200, malformed output)
    returns ``available=False`` with a specific ``reason`` — the caller
    surfaces it as a visible downgrade, per the no-silent-failure rule.

    Example::

        outcome = semantic_alignment_check(config, goal, constraints, oos, plan)
        if outcome.available:
            flags.extend(outcome.flags)
    """
    prompt = _VERDICT_PROMPT.format(
        goal=original_goal,
        constraints="\n".join(f"- {c}" for c in constraints) or "(none)",
        out_of_scope="\n".join(f"- {o}" for o in out_of_scope) or "(none)",
        plan=plan_text,
    )
    try:
        with httpx.Client(timeout=LLM_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{config.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {config.api_key}"},
                json={
                    "model": config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
    except httpx.HTTPError as exc:
        return SemanticOutcome(flags=[], available=False, reason=f"request failed: {exc}")

    if response.status_code != 200:
        return SemanticOutcome(
            flags=[], available=False, reason=f"provider returned HTTP {response.status_code}"
        )

    try:
        content = response.json()["choices"][0]["message"]["content"]
        verdict = json.loads(str(content).strip())
        raw_violations = verdict["violations"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        return SemanticOutcome(
            flags=[], available=False, reason=f"malformed model output: {type(exc).__name__}"
        )
    if not isinstance(raw_violations, list):
        return SemanticOutcome(
            flags=[], available=False, reason="malformed model output: violations not a list"
        )
    violations = cast("list[object]", raw_violations)

    flags = [f"{SEMANTIC_FLAG_PREFIX} {str(v).strip()}" for v in violations if str(v).strip()]
    return SemanticOutcome(flags=flags, available=True, reason="")
