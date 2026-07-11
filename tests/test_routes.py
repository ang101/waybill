"""End-to-end route tests against the FastAPI app via TestClient."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import HandoffStore

_ROOT_BODY: dict[str, Any] = {
    "original_goal": "process the refund request backlog",
    "constraints": ["must log every refund decision", "never contact the customer directly"],
    "out_of_scope": ["issue partial refunds"],
    "completed": [],
    "remaining": ["triage backlog"],
}


@pytest.fixture()
def client() -> TestClient:
    # Fresh store per test so handoffs from one test never leak into another.
    app.state.store = HandoffStore()
    return TestClient(app)


def _create_root(client: TestClient) -> dict[str, Any]:
    response = client.post("/handoffs", json=_ROOT_BODY)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


class TestCreateHandoff:
    def test_post_handoffs_returns_id_and_signature(self, client: TestClient) -> None:
        body = _create_root(client)
        assert body["handoff_id"].startswith("wb-")
        assert body["hop_index"] == 0
        assert body["parent_handoff_id"] is None
        assert len(body["signature"]) == 128  # 64-byte Ed25519 signature, hex-encoded

    def test_post_handoffs_empty_goal_returns_422(self, client: TestClient) -> None:
        response = client.post("/handoffs", json={**_ROOT_BODY, "original_goal": ""})
        assert response.status_code == 422


class TestExtendHandoff:
    def test_extend_compliant_hop_increments_hop_index(self, client: TestClient) -> None:
        root = _create_root(client)
        response = client.post(
            f"/handoffs/{root['handoff_id']}/extend",
            json={**_ROOT_BODY, "completed": ["triage backlog"], "remaining": []},
        )
        assert response.status_code == 201, response.text
        assert response.json()["hop_index"] == 1
        assert response.json()["root_handoff_id"] == root["handoff_id"]

    def test_extend_unknown_id_returns_404(self, client: TestClient) -> None:
        response = client.post("/handoffs/wb-missing/extend", json=_ROOT_BODY)
        assert response.status_code == 404

    def test_extend_rewriting_goal_returns_400_with_root_values(self, client: TestClient) -> None:
        root = _create_root(client)
        response = client.post(
            f"/handoffs/{root['handoff_id']}/extend",
            json={**_ROOT_BODY, "original_goal": "upsell enterprise customers"},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "package_drift"
        assert body["root_original_goal"] == _ROOT_BODY["original_goal"]

    def test_extend_dropping_constraint_returns_400(self, client: TestClient) -> None:
        root = _create_root(client)
        response = client.post(
            f"/handoffs/{root['handoff_id']}/extend",
            json={**_ROOT_BODY, "constraints": ["must log every refund decision"]},
        )
        assert response.status_code == 400
        assert set(response.json()["root_constraints"]) == set(_ROOT_BODY["constraints"])


class TestValidatePlan:
    def test_validate_plan_compliant_plan_returns_aligned_true(self, client: TestClient) -> None:
        root = _create_root(client)
        response = client.post(
            f"/handoffs/{root['handoff_id']}/validate-plan",
            json={
                "proposed_plan": (
                    "Triage the refund backlog, log every refund decision "
                    "in the audit system, route approvals to finance."
                )
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["aligned"] is True
        assert body["signature_valid"] is True
        assert body["flags"] == []

    def test_validate_plan_dropped_obligation_returns_aligned_false(
        self, client: TestClient
    ) -> None:
        root = _create_root(client)
        response = client.post(
            f"/handoffs/{root['handoff_id']}/validate-plan",
            json={"proposed_plan": "Triage the backlog and route approvals to finance."},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["aligned"] is False
        assert any("obligation unmet" in flag for flag in body["flags"])

    def test_validate_plan_prohibited_action_returns_aligned_false(
        self, client: TestClient
    ) -> None:
        root = _create_root(client)
        response = client.post(
            f"/handoffs/{root['handoff_id']}/validate-plan",
            json={
                "proposed_plan": (
                    "Log every refund decision, then contact each customer directly to confirm."
                )
            },
        )
        assert response.status_code == 200
        assert response.json()["aligned"] is False

    def test_validate_plan_unknown_handoff_id_returns_404(self, client: TestClient) -> None:
        response = client.post("/handoffs/wb-missing/validate-plan", json={"proposed_plan": "x"})
        assert response.status_code == 404

    def test_validate_plan_empty_plan_returns_422(self, client: TestClient) -> None:
        root = _create_root(client)
        response = client.post(
            f"/handoffs/{root['handoff_id']}/validate-plan", json={"proposed_plan": "  "}
        )
        assert response.status_code == 422


class TestInspectionEndpoints:
    def test_get_handoff_returns_stored_hop(self, client: TestClient) -> None:
        root = _create_root(client)
        response = client.get(f"/handoffs/{root['handoff_id']}")
        assert response.status_code == 200
        assert response.json()["handoff_id"] == root["handoff_id"]

    def test_get_handoff_unknown_id_returns_404(self, client: TestClient) -> None:
        assert client.get("/handoffs/wb-missing").status_code == 404

    def test_get_skill_md_returns_markdown_content_type(self, client: TestClient) -> None:
        response = client.get("/skill.md")
        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]

    def test_get_health_returns_ok_with_operational_posture(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["signing"] in {"seeded", "ephemeral"}
        assert body["semantic_check"] in {"configured", "disabled"}

    def test_cors_header_present_on_response(self, client: TestClient) -> None:
        response = client.get("/health", headers={"Origin": "https://example.com"})
        assert response.headers["access-control-allow-origin"] == "*"
