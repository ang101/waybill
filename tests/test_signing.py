"""Signing and canonicalization tests."""

from __future__ import annotations

from app.canonical import canonicalize_package
from app.models import PackageSnapshot
from app.signing import ServiceSigningKey

_SEED = b"test-seed"


def _snapshot(**overrides: object) -> PackageSnapshot:
    base: dict[str, object] = {
        "original_goal": "process refunds",
        "constraints": ["must log decisions"],
        "out_of_scope": ["partial refunds"],
        "completed": [],
        "remaining": ["triage backlog"],
    }
    base.update(overrides)
    return PackageSnapshot.model_validate(base)


class TestSigning:
    def test_sign_then_verify_returns_true(self) -> None:
        key = ServiceSigningKey(_SEED)
        payload = canonicalize_package(_snapshot())
        assert key.verify(payload, key.sign(payload))

    def test_verify_fails_after_payload_tampered(self) -> None:
        key = ServiceSigningKey(_SEED)
        signature = key.sign(canonicalize_package(_snapshot()))
        tampered = canonicalize_package(_snapshot(original_goal="upsell customers"))
        assert not key.verify(tampered, signature)

    def test_verify_fails_after_signature_tampered(self) -> None:
        key = ServiceSigningKey(_SEED)
        payload = canonicalize_package(_snapshot())
        signature = bytearray(key.sign(payload))
        signature[0] ^= 0xFF
        assert not key.verify(payload, bytes(signature))

    def test_seeded_key_produces_identical_signatures_across_instances(self) -> None:
        """The restart-survival property: same seed, same key, same signatures."""
        payload = canonicalize_package(_snapshot())
        first = ServiceSigningKey(_SEED).sign(payload)
        second = ServiceSigningKey(_SEED).sign(payload)
        assert first == second

    def test_different_seeds_cannot_verify_each_others_signatures(self) -> None:
        payload = canonicalize_package(_snapshot())
        signature = ServiceSigningKey(b"seed-a").sign(payload)
        assert not ServiceSigningKey(b"seed-b").verify(payload, signature)

    def test_ephemeral_key_still_signs_and_verifies(self) -> None:
        key = ServiceSigningKey(None)
        payload = canonicalize_package(_snapshot())
        assert key.verify(payload, key.sign(payload))


class TestCanonicalization:
    def test_canonicalize_is_field_order_independent(self) -> None:
        """Same content must produce byte-identical encodings regardless of
        construction order, or signatures would break randomly."""
        a = PackageSnapshot(
            original_goal="g", constraints=["c"], out_of_scope=[], completed=[], remaining=[]
        )
        b = PackageSnapshot(
            remaining=[], completed=[], out_of_scope=[], constraints=["c"], original_goal="g"
        )
        assert canonicalize_package(a) == canonicalize_package(b)

    def test_different_content_produces_different_bytes(self) -> None:
        assert canonicalize_package(_snapshot()) != canonicalize_package(
            _snapshot(original_goal="different goal")
        )
