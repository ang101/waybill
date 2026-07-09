"""Semantic-check tests — all LLM calls mocked, no network in CI.

The invariant under test is visible degradation: every failure mode
(no key, HTTP error, non-200, malformed output) must downgrade to
keyword-only mode *with a stated reason*, never silently and never
breaking the endpoint.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.semantic import (
    LlmConfig,
    SemanticOutcome,
    load_llm_config_from_env,
    semantic_alignment_check,
)
from app.storage import HandoffStore

_CONFIG = LlmConfig(api_key="test-key", base_url="https://llm.example", model="test-model")
_GOAL = "process the refund request backlog"
_CONSTRAINTS = ["never contact the customer directly"]
_PARAPHRASED_VIOLATION_PLAN = "Reach out to each client by phone to confirm their request."


def _llm_response(payload: dict[str, Any], status_code: int = 200) -> httpx.Response:
    content = json.dumps(payload)
    return httpx.Response(
        status_code=status_code,
        json={"choices": [{"message": {"content": content}}]},
    )


class TestConfigLoading:
    def test_no_api_key_env_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("WAYBILL_LLM_API_KEY", raising=False)
        assert load_llm_config_from_env() is None

    def test_key_set_returns_config_with_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WAYBILL_LLM_API_KEY", "k")
        monkeypatch.delenv("WAYBILL_LLM_BASE_URL", raising=False)
        monkeypatch.delenv("WAYBILL_LLM_MODEL", raising=False)
        config = load_llm_config_from_env()
        assert config is not None
        assert "groq.com" in config.base_url

    def test_custom_base_url_and_model_override_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAYBILL_LLM_API_KEY", "k")
        monkeypatch.setenv("WAYBILL_LLM_BASE_URL", "https://api.x.ai/v1/")
        monkeypatch.setenv("WAYBILL_LLM_MODEL", "grok-3-mini")
        config = load_llm_config_from_env()
        assert config is not None
        assert config.base_url == "https://api.x.ai/v1"
        assert config.model == "grok-3-mini"


class TestSemanticCheck:
    def test_paraphrased_violation_caught_when_semantic_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        verdict = {"violations": ["plan contacts the customer, violating the prohibition"]}
        monkeypatch.setattr(httpx.Client, "post", lambda self, *a, **kw: _llm_response(verdict))
        outcome = semantic_alignment_check(
            _CONFIG, _GOAL, _CONSTRAINTS, [], _PARAPHRASED_VIOLATION_PLAN
        )
        assert outcome.available
        assert len(outcome.flags) == 1
        assert outcome.flags[0].startswith("semantic:")

    def test_compliant_plan_returns_no_semantic_flags(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            httpx.Client, "post", lambda self, *a, **kw: _llm_response({"violations": []})
        )
        outcome = semantic_alignment_check(_CONFIG, _GOAL, _CONSTRAINTS, [], "Triage refunds.")
        assert outcome.available
        assert outcome.flags == []

    def test_llm_http_error_downgrades_visibly_not_silently(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(self: httpx.Client, *a: object, **kw: object) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx.Client, "post", _raise)
        outcome = semantic_alignment_check(_CONFIG, _GOAL, _CONSTRAINTS, [], "plan")
        assert not outcome.available
        assert "request failed" in outcome.reason

    def test_llm_rate_limit_status_downgrades_with_status_in_reason(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            httpx.Client,
            "post",
            lambda self, *a, **kw: httpx.Response(status_code=429, json={}),
        )
        outcome = semantic_alignment_check(_CONFIG, _GOAL, _CONSTRAINTS, [], "plan")
        assert not outcome.available
        assert "429" in outcome.reason

    def test_llm_malformed_json_downgrades_visibly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            httpx.Client,
            "post",
            lambda self, *a, **kw: httpx.Response(
                status_code=200,
                json={"choices": [{"message": {"content": "not json at all"}}]},
            ),
        )
        outcome = semantic_alignment_check(_CONFIG, _GOAL, _CONSTRAINTS, [], "plan")
        assert not outcome.available
        assert "malformed model output" in outcome.reason

    def test_llm_violations_not_a_list_downgrades_visibly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            httpx.Client,
            "post",
            lambda self, *a, **kw: _llm_response({"violations": "should be a list"}),
        )
        outcome = semantic_alignment_check(_CONFIG, _GOAL, _CONSTRAINTS, [], "plan")
        assert not outcome.available
        assert "not a list" in outcome.reason


class TestRouteIntegration:
    """check_mode and aligned-gate behavior through the real endpoint."""

    def _client(self, llm_config: LlmConfig | None) -> TestClient:
        app.state.store = HandoffStore()
        app.state.llm_config = llm_config
        return TestClient(app)

    def _create_root(self, client: TestClient) -> str:
        response = client.post(
            "/handoffs",
            json={
                "original_goal": _GOAL,
                "constraints": _CONSTRAINTS,
                "out_of_scope": [],
                "completed": [],
                "remaining": [],
            },
        )
        assert response.status_code == 201
        handoff_id: str = response.json()["handoff_id"]
        return handoff_id

    def test_no_api_key_falls_back_to_keyword_mode(self) -> None:
        client = self._client(llm_config=None)
        handoff_id = self._create_root(client)
        response = client.post(
            f"/handoffs/{handoff_id}/validate-plan", json={"proposed_plan": "Triage refunds."}
        )
        assert response.status_code == 200
        assert response.json()["check_mode"] == "keyword"

    def test_semantic_flags_merge_into_aligned_verdict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Patch at the route's import site, not httpx.Client — TestClient is
        # itself an httpx.Client, so a global httpx patch would hijack the
        # test's own requests.
        monkeypatch.setattr(
            "app.main.semantic_alignment_check",
            lambda *a, **kw: SemanticOutcome(
                flags=["semantic: plan contacts the customer by phone"],
                available=True,
                reason="",
            ),
        )
        client = self._client(llm_config=_CONFIG)
        handoff_id = self._create_root(client)
        response = client.post(
            f"/handoffs/{handoff_id}/validate-plan",
            json={"proposed_plan": _PARAPHRASED_VIOLATION_PLAN},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["check_mode"] == "keyword+semantic"
        assert body["aligned"] is False
        assert any(flag.startswith("semantic:") for flag in body["flags"])

    def test_llm_failure_reports_downgraded_mode_and_keeps_keyword_verdict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.main.semantic_alignment_check",
            lambda *a, **kw: SemanticOutcome(
                flags=[], available=False, reason="provider returned HTTP 429"
            ),
        )
        client = self._client(llm_config=_CONFIG)
        handoff_id = self._create_root(client)
        response = client.post(
            f"/handoffs/{handoff_id}/validate-plan", json={"proposed_plan": "Triage refunds."}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["check_mode"].startswith("keyword (semantic unavailable")
        assert body["aligned"] is True  # keyword verdict stands

    def test_oversized_plan_returns_422(self) -> None:
        client = self._client(llm_config=None)
        handoff_id = self._create_root(client)
        response = client.post(
            f"/handoffs/{handoff_id}/validate-plan", json={"proposed_plan": "x" * 20_001}
        )
        assert response.status_code == 422
        assert "max is" in response.json()["detail"]

    def test_health_reports_signing_and_semantic_posture(self) -> None:
        client = self._client(llm_config=None)
        body = client.get("/health").json()
        assert body["signing"] in {"seeded", "ephemeral"}
        assert body["semantic_check"] == "disabled"
