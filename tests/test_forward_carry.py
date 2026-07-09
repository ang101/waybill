"""Forward-carry (locked-field) validation tests."""

from __future__ import annotations

import pytest

from app.forward_carry import PackageDriftError, validate_forward_carry
from app.models import ExtendHandoffRequest, PackageSnapshot

_GOAL = "process refunds"
_CONSTRAINTS = ["must log decisions", "never contact the customer"]
_OUT_OF_SCOPE = ["partial refunds"]


def _parent() -> PackageSnapshot:
    return PackageSnapshot(
        original_goal=_GOAL,
        constraints=list(_CONSTRAINTS),
        out_of_scope=list(_OUT_OF_SCOPE),
        completed=["triage"],
        remaining=["approve"],
    )


def _extend(**overrides: object) -> ExtendHandoffRequest:
    base: dict[str, object] = {
        "original_goal": _GOAL,
        "constraints": list(_CONSTRAINTS),
        "out_of_scope": list(_OUT_OF_SCOPE),
        "completed": ["triage", "approve"],
        "remaining": [],
    }
    base.update(overrides)
    return ExtendHandoffRequest.model_validate(base)


class TestForwardCarry:
    def test_unchanged_locked_fields_passes(self) -> None:
        validate_forward_carry(_parent(), _extend())  # does not raise

    def test_rewritten_goal_raises_package_drift_error(self) -> None:
        with pytest.raises(PackageDriftError) as exc:
            validate_forward_carry(_parent(), _extend(original_goal="upsell customers"))
        assert exc.value.root_original_goal == _GOAL

    def test_dropped_constraint_raises_package_drift_error(self) -> None:
        with pytest.raises(PackageDriftError):
            validate_forward_carry(_parent(), _extend(constraints=["must log decisions"]))

    def test_added_constraint_raises_package_drift_error(self) -> None:
        with pytest.raises(PackageDriftError):
            validate_forward_carry(
                _parent(), _extend(constraints=[*_CONSTRAINTS, "new invented rule"])
            )

    def test_rewritten_out_of_scope_raises_package_drift_error(self) -> None:
        with pytest.raises(PackageDriftError) as exc:
            validate_forward_carry(_parent(), _extend(out_of_scope=[]))
        assert exc.value.root_out_of_scope == _OUT_OF_SCOPE

    def test_reordered_but_same_constraints_passes(self) -> None:
        """Order is not meaning — reordering must not read as drift."""
        validate_forward_carry(_parent(), _extend(constraints=list(reversed(_CONSTRAINTS))))

    def test_extended_completed_list_passes(self) -> None:
        validate_forward_carry(_parent(), _extend(completed=["triage", "approve", "notify"]))

    def test_emptied_remaining_list_passes(self) -> None:
        validate_forward_carry(_parent(), _extend(remaining=[]))
