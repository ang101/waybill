"""Alignment logic tests.

The prohibition/obligation cases are the regression tests for the
constraint-typing bug found in design review: a prohibition ("never X") is
satisfied by absence, so flagging its absence — the pre-review behavior —
false-positives every compliant plan.
"""

from __future__ import annotations

import pytest

from app.alignment import (
    evaluate_alignment,
    goal_similarity_score,
    keyword_overlap_ratio,
    normalize_proposed_plan,
    split_constraints,
)

_GOAL = "process the refund request backlog for enterprise customers"
_PROHIBITION = "never contact the customer directly"
_OBLIGATION = "must log every refund decision"

_COMPLIANT_PLAN = (
    "Fetch the refund backlog, evaluate each request against policy, "
    "log every refund decision in the audit system, and route approvals to finance."
)
_VIOLATING_PLAN = (
    "Fetch the refund backlog, then contact each customer directly by phone "
    "to confirm their request before processing."
)
_OBLIVIOUS_PLAN = "Fetch the refund backlog and route approvals to finance."


class TestConstraintSplitting:
    def test_split_constraints_classifies_prefixes_correctly(self) -> None:
        prohibitions, obligations = split_constraints([_PROHIBITION, _OBLIGATION])
        assert prohibitions == [_PROHIBITION]
        assert obligations == [_OBLIGATION]

    def test_split_constraints_empty_input_returns_two_empty_lists(self) -> None:
        assert split_constraints([]) == ([], [])


class TestProhibitions:
    def test_prohibition_absent_from_plan_is_not_flagged(self) -> None:
        """A compliant plan never mentions the prohibited action — no flag."""
        result = evaluate_alignment(_GOAL, [_PROHIBITION, _OBLIGATION], [], _COMPLIANT_PLAN)
        assert result.aligned, result.flags

    def test_prohibition_violated_by_plan_is_flagged(self) -> None:
        result = evaluate_alignment(_GOAL, [_PROHIBITION], [], _VIOLATING_PLAN)
        assert not result.aligned
        assert any("prohibition violated" in flag for flag in result.flags)


class TestObligations:
    def test_obligation_absent_from_plan_is_flagged(self) -> None:
        result = evaluate_alignment(_GOAL, [_OBLIGATION], [], _OBLIVIOUS_PLAN)
        assert not result.aligned
        assert any("obligation unmet" in flag for flag in result.flags)

    def test_obligation_addressed_by_plan_is_not_flagged(self) -> None:
        result = evaluate_alignment(_GOAL, [_OBLIGATION], [], _COMPLIANT_PLAN)
        assert result.aligned, result.flags


class TestOutOfScope:
    def test_out_of_scope_phrase_present_flags_violation(self) -> None:
        result = evaluate_alignment(
            _GOAL, [], ["issue partial refunds"], "Issue partial refunds for stale requests."
        )
        assert not result.aligned
        assert any("out-of-scope" in flag for flag in result.flags)

    def test_out_of_scope_phrase_absent_is_not_flagged(self) -> None:
        result = evaluate_alignment(_GOAL, [], ["issue partial refunds"], _COMPLIANT_PLAN)
        assert result.aligned, result.flags


class TestVerdictComposition:
    def test_empty_constraints_and_out_of_scope_returns_aligned_true(self) -> None:
        """Nothing to violate is a legitimate green, not an error."""
        result = evaluate_alignment(_GOAL, [], [], _COMPLIANT_PLAN)
        assert result.aligned
        assert result.flags == []

    def test_goal_similarity_reported_but_never_gates_aligned(self) -> None:
        """A plan with zero lexical overlap with the goal still passes if no
        constraint is violated — similarity is advisory only."""
        unrelated_plan = "Assemble widgets and paint them blue."
        result = evaluate_alignment(_GOAL, [], [], unrelated_plan)
        assert result.aligned
        assert result.goal_similarity < 0.1


class TestInputValidation:
    def test_empty_plan_text_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            normalize_proposed_plan("   ")

    def test_empty_plan_list_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            normalize_proposed_plan([])

    def test_plan_list_is_joined_into_text(self) -> None:
        assert "fetch" in normalize_proposed_plan(["fetch records", "log decisions"])

    def test_phrase_with_only_stopwords_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="no content tokens"):
            keyword_overlap_ratio("the and of", _COMPLIANT_PLAN)


class TestGoalSimilarity:
    def test_identical_texts_score_near_one(self) -> None:
        assert goal_similarity_score(_GOAL, _GOAL) > 0.99

    def test_unrelated_texts_score_near_zero(self) -> None:
        assert goal_similarity_score("assemble blue widgets", _GOAL) < 0.1
