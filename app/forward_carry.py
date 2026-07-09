"""Forward-carry validation: locked fields must survive every hop unchanged.

``original_goal``, ``constraints``, and ``out_of_scope`` define the task's
boundaries and are immutable after hop 0. ``completed``/``remaining`` track
progress and may change freely. Constraint *order* is not meaningful, so
reordering is not drift — comparison is set-based.
"""

from __future__ import annotations

from app.models import ExtendHandoffRequest, PackageSnapshot


class PackageDriftError(ValueError):
    """Raised when an extend request rewrites a locked field.

    Carries the root's actual values so the HTTP layer can return them in
    the 400 body, letting the caller self-correct without a second round trip.
    """

    def __init__(
        self,
        detail: str,
        root_original_goal: str,
        root_constraints: list[str],
        root_out_of_scope: list[str],
    ) -> None:
        self.detail = detail
        self.root_original_goal = root_original_goal
        self.root_constraints = root_constraints
        self.root_out_of_scope = root_out_of_scope
        super().__init__(detail)


def validate_forward_carry(parent: PackageSnapshot, incoming: ExtendHandoffRequest) -> None:
    """Reject an extend request that rewrites any locked field.

    Raises ``PackageDriftError`` naming exactly which field drifted.
    ``completed``/``remaining`` are not checked — they may extend freely.

    Example::

        validate_forward_carry(parent.package, request)  # raises on drift
    """
    if incoming.original_goal != parent.original_goal:
        raise PackageDriftError(
            f"original_goal was rewritten: expected {parent.original_goal!r}, "
            f"got {incoming.original_goal!r}",
            parent.original_goal,
            parent.constraints,
            parent.out_of_scope,
        )
    if set(incoming.constraints) != set(parent.constraints):
        raise PackageDriftError(
            "constraints were modified: expected exactly "
            f"{sorted(parent.constraints)}, got {sorted(incoming.constraints)}",
            parent.original_goal,
            parent.constraints,
            parent.out_of_scope,
        )
    if set(incoming.out_of_scope) != set(parent.out_of_scope):
        raise PackageDriftError(
            "out_of_scope was modified: expected exactly "
            f"{sorted(parent.out_of_scope)}, got {sorted(incoming.out_of_scope)}",
            parent.original_goal,
            parent.constraints,
            parent.out_of_scope,
        )
