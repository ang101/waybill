"""Pydantic models for the Waybill API.

The package fields split into two groups with different mutability rules:

* **Locked after hop 0**: ``original_goal``, ``constraints``, ``out_of_scope``.
  These define the task's boundaries; a hop that rewrites any of them is
  rejected with HTTP 400 (see ``validate_forward_carry``).
* **Extendable**: ``completed``, ``remaining``. These track progress and may
  grow or shrink freely as work moves hop to hop.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PackageSnapshot(BaseModel):
    """The task-defining content that gets canonicalized and signed.

    Deliberately excludes ``handoff_id``/``hop_index``/timestamps so the
    signature covers only what the task *is*, not bookkeeping metadata.
    """

    original_goal: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)
    remaining: list[str] = Field(default_factory=list)


class CreateHandoffRequest(BaseModel):
    """Body for ``POST /handoffs`` — creates the root of a new handoff chain."""

    original_goal: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)
    remaining: list[str] = Field(default_factory=list)


class ExtendHandoffRequest(BaseModel):
    """Body for ``POST /handoffs/{id}/extend`` — appends a hop to an existing chain.

    ``original_goal``/``constraints``/``out_of_scope`` must match the root
    exactly; only ``completed``/``remaining`` may change.
    """

    original_goal: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)
    remaining: list[str] = Field(default_factory=list)


class HandoffResponse(BaseModel):
    """Response for create/extend/get: the stored hop plus its signature."""

    handoff_id: str
    parent_handoff_id: str | None
    root_handoff_id: str
    hop_index: int
    signature: str
    package: PackageSnapshot
    created_at: datetime


class ValidatePlanRequest(BaseModel):
    """Body for ``POST /handoffs/{id}/validate-plan``."""

    proposed_plan: str | list[str]


class ValidatePlanResponse(BaseModel):
    """Alignment verdict for a proposed plan against a stored handoff.

    ``goal_similarity`` is advisory only — it never gates ``aligned``
    (TF-IDF on short free text is too noisy to hard-fail on).
    ``check_mode`` reports which checks actually ran: keyword checks are the
    deterministic floor; the semantic (LLM) layer is additive and its
    unavailability is reported here, never hidden.
    """

    aligned: bool
    flags: list[str]
    signature_valid: bool
    goal_similarity: float
    check_mode: str


class DriftErrorResponse(BaseModel):
    """HTTP 400 body when a hop tries to rewrite locked fields.

    Carries the root's actual values so the caller can self-correct
    without a second round trip.
    """

    error: str
    detail: str
    root_original_goal: str
    root_constraints: list[str]
    root_out_of_scope: list[str]
