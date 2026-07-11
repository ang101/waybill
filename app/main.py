"""Waybill — Task Handoff Integrity service.

Routes are HTTP plumbing only: request parsing, dependency wiring, and
error-to-status translation. All real logic lives in the pure modules
(``alignment``, ``canonical``, ``forward_carry``) and the two stateful
components (``ServiceSigningKey``, ``HandoffStore``).
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.alignment import evaluate_alignment, normalize_proposed_plan
from app.canonical import canonicalize_package
from app.forward_carry import PackageDriftError, validate_forward_carry
from app.models import (
    CreateHandoffRequest,
    DriftErrorResponse,
    ExtendHandoffRequest,
    HandoffResponse,
    PackageSnapshot,
    ValidatePlanRequest,
    ValidatePlanResponse,
)
from app.semantic import LlmConfig, load_llm_config_from_env, semantic_alignment_check
from app.signing import ServiceSigningKey
from app.storage import HandoffStore, StoredHandoff

SKILL_MD_PATH = Path(__file__).resolve().parent.parent / "SKILL.md"
DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"
SIGNING_SEED_ENV_VAR = "WAYBILL_SIGNING_KEY_SEED"
MAX_PLAN_LENGTH_CHARS = 20_000
"""Upper bound on plan text — keeps a public endpoint from being abused to
burn the free-tier LLM quota with giant payloads."""

logger = logging.getLogger("waybill")


def _load_dotenv_if_present() -> None:
    """Load KEY=VALUE lines from a local ``.env`` into the environment.

    Local-dev convenience only — Render supplies real env vars via its
    dashboard. Deliberately minimal (no quoting/expansion) rather than a
    python-dotenv dependency; already-set variables always win so a real
    environment can never be overridden by a stale file.
    """
    if not DOTENV_PATH.exists():
        return
    for line in DOTENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        os.environ.setdefault(name.strip(), value.strip())


_load_dotenv_if_present()

app = FastAPI(
    title="Waybill — Task Handoff Integrity",
    description=(
        "Validate task handoffs between agents. Prevents goal drift, dropped "
        "constraints, and scope creep when work passes through multiple agents."
    ),
    version="0.1.0",
)

# All endpoints are already public and unauthenticated (see SKILL.md); this
# only lets browser-based callers (e.g. the demo UI) receive responses they
# could already fetch with curl — it grants no new access.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _build_signing_key() -> ServiceSigningKey:
    """Build the service key from the env seed, or ephemeral for local dev.

    Without the seed, every restart mints a new key and invalidates all prior
    signatures — acceptable locally, never in the deployed judging window,
    hence the loud warning (also externally visible via /health).
    """
    seed = os.environ.get(SIGNING_SEED_ENV_VAR)
    if not seed:
        logger.warning(
            "%s is not set — signing key is EPHEMERAL and every restart will "
            "invalidate all previously issued signatures. Set it before judging.",
            SIGNING_SEED_ENV_VAR,
        )
    return ServiceSigningKey(seed.encode("utf-8") if seed else None)


app.state.store = HandoffStore()
app.state.signing_key = _build_signing_key()
app.state.llm_config = load_llm_config_from_env()


def get_store(request: Request) -> HandoffStore:
    """Dependency: the process-lifetime handoff store."""
    store: HandoffStore = request.app.state.store
    return store


def get_signing_key(request: Request) -> ServiceSigningKey:
    """Dependency: the process-lifetime signing key."""
    key: ServiceSigningKey = request.app.state.signing_key
    return key


def get_llm_config(request: Request) -> LlmConfig | None:
    """Dependency: the optional LLM config (None = keyword-only mode)."""
    config: LlmConfig | None = request.app.state.llm_config
    return config


def _to_response(stored: StoredHandoff) -> HandoffResponse:
    """Map a stored hop to its API shape (signature hex-encoded)."""
    return HandoffResponse(
        handoff_id=stored.handoff_id,
        parent_handoff_id=stored.parent_handoff_id,
        root_handoff_id=stored.root_handoff_id,
        hop_index=stored.hop_index,
        signature=stored.signature.hex(),
        package=stored.package,
        created_at=stored.created_at,
    )


@app.post("/handoffs", response_model=HandoffResponse, status_code=201)
def create_handoff(
    body: CreateHandoffRequest,
    store: Annotated[HandoffStore, Depends(get_store)],
    key: Annotated[ServiceSigningKey, Depends(get_signing_key)],
) -> HandoffResponse:
    """Create the signed root (hop 0) of a new handoff chain."""
    package = PackageSnapshot(**body.model_dump())
    signature = key.sign(canonicalize_package(package))
    stored = store.create_root(f"wb-{uuid.uuid4()}", package, signature)
    return _to_response(stored)


@app.post("/handoffs/{handoff_id}/extend", response_model=HandoffResponse, status_code=201)
def extend_handoff(
    handoff_id: str,
    body: ExtendHandoffRequest,
    store: Annotated[HandoffStore, Depends(get_store)],
    key: Annotated[ServiceSigningKey, Depends(get_signing_key)],
) -> HandoffResponse | JSONResponse:
    """Append a hop; locked fields must match the parent exactly."""
    try:
        parent = store.get(handoff_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        validate_forward_carry(parent.package, body)
    except PackageDriftError as exc:
        return JSONResponse(
            status_code=400,
            content=DriftErrorResponse(
                error="package_drift",
                detail=exc.detail,
                root_original_goal=exc.root_original_goal,
                root_constraints=exc.root_constraints,
                root_out_of_scope=exc.root_out_of_scope,
            ).model_dump(),
        )

    package = PackageSnapshot(**body.model_dump())
    signature = key.sign(canonicalize_package(package))
    stored = store.append_hop(parent.handoff_id, f"wb-{uuid.uuid4()}", package, signature)
    return _to_response(stored)


@app.post("/handoffs/{handoff_id}/validate-plan", response_model=ValidatePlanResponse)
def validate_plan(
    handoff_id: str,
    body: ValidatePlanRequest,
    store: Annotated[HandoffStore, Depends(get_store)],
    key: Annotated[ServiceSigningKey, Depends(get_signing_key)],
    llm_config: Annotated[LlmConfig | None, Depends(get_llm_config)],
) -> ValidatePlanResponse:
    """Check a proposed plan against a stored handoff's goal and constraints.

    Keyword checks always run (deterministic floor); the LLM semantic layer
    runs when configured and its unavailability is reported in ``check_mode``,
    never hidden.
    """
    try:
        stored = store.get(handoff_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        plan_text = normalize_proposed_plan(body.proposed_plan)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(plan_text) > MAX_PLAN_LENGTH_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"proposed_plan is {len(plan_text)} chars; max is {MAX_PLAN_LENGTH_CHARS}",
        )

    signature_valid = key.verify(canonicalize_package(stored.package), stored.signature)
    result = evaluate_alignment(
        stored.package.original_goal,
        stored.package.constraints,
        stored.package.out_of_scope,
        plan_text,
    )

    flags = list(result.flags)
    if llm_config is None:
        check_mode = "keyword"
    else:
        outcome = semantic_alignment_check(
            llm_config,
            stored.package.original_goal,
            stored.package.constraints,
            stored.package.out_of_scope,
            plan_text,
        )
        if outcome.available:
            check_mode = "keyword+semantic"
            flags.extend(outcome.flags)
        else:
            check_mode = f"keyword (semantic unavailable: {outcome.reason})"

    return ValidatePlanResponse(
        aligned=not flags and signature_valid,
        flags=flags,
        signature_valid=signature_valid,
        goal_similarity=result.goal_similarity,
        check_mode=check_mode,
    )


@app.get("/handoffs/{handoff_id}", response_model=HandoffResponse)
def get_handoff(
    handoff_id: str,
    store: Annotated[HandoffStore, Depends(get_store)],
) -> HandoffResponse:
    """Inspect a stored hop (debugging / demo convenience)."""
    try:
        stored = store.get(handoff_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(stored)


@app.get("/skill.md", response_class=PlainTextResponse)
def get_skill_md() -> PlainTextResponse:
    """Serve SKILL.md from disk per-request so edits appear without redeploy."""
    if not SKILL_MD_PATH.exists():
        raise HTTPException(status_code=404, detail="SKILL.md not found on server")
    return PlainTextResponse(SKILL_MD_PATH.read_text(encoding="utf-8"), media_type="text/markdown")


@app.get("/health")
def health(
    key: Annotated[ServiceSigningKey, Depends(get_signing_key)],
    llm_config: Annotated[LlmConfig | None, Depends(get_llm_config)],
) -> dict[str, str]:
    """Liveness endpoint for the keepalive pinger.

    Also reports operational posture so misconfiguration is externally
    detectable: an ``ephemeral`` signing key on a deployed instance means
    every restart silently invalidates all prior signatures.
    """
    return {
        "status": "ok",
        "signing": "seeded" if key.is_seeded else "ephemeral",
        "semantic_check": "configured" if llm_config is not None else "disabled",
    }
