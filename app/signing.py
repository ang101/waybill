"""Service-held Ed25519 signing for handoff packages.

Deliberate simplification for the hackathon: the *service* holds one keypair
and signs every package, giving tamper-evidence for stored/transported
content — not per-agent authentication (agents don't hold keys here; that's
AgentPass's territory and a documented future-work item).

The key must be derived from ``WAYBILL_SIGNING_KEY_SEED`` in production:
a fresh random key per process restart would invalidate every previously
issued signature the moment a free-tier dyno sleeps and wakes.
"""

from __future__ import annotations

import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SEED_LENGTH_BYTES = 32


class ServiceSigningKey:
    """Ed25519 keypair held for the service's lifetime.

    A class (not functions) because the private key is state that must
    persist across every request. Instantiated once in ``main.py`` and
    injected via FastAPI dependencies — never a bare module global.
    """

    def __init__(self, seed: bytes | None) -> None:
        """Derive the keypair from ``seed``, or generate ephemeral if ``None``.

        Any seed length is accepted: it is hashed to the exact
        ``SEED_LENGTH_BYTES`` Ed25519 requires, so operators can set a
        passphrase-style env var without worrying about byte counts.
        """
        self._seeded = seed is not None
        if seed is None:
            self._private_key = Ed25519PrivateKey.generate()
        else:
            digest = hashlib.sha256(seed).digest()[:SEED_LENGTH_BYTES]
            self._private_key = Ed25519PrivateKey.from_private_bytes(digest)

    @property
    def is_seeded(self) -> bool:
        """True when the key came from a seed and therefore survives restarts.

        Surfaced via ``/health`` so an ephemeral key on a deployed instance —
        which silently invalidates all prior signatures on restart — is
        detectable from outside, not discovered mid-demo.

        Example::

            assert ServiceSigningKey(b"seed").is_seeded
        """
        return self._seeded

    def sign(self, payload: bytes) -> bytes:
        """Sign payload bytes, returning the raw 64-byte Ed25519 signature.

        Example::

            signature = key.sign(canonicalize_package(snapshot))
        """
        return self._private_key.sign(payload)

    def verify(self, payload: bytes, signature: bytes) -> bool:
        """Return True iff ``signature`` is valid for ``payload`` under this key.

        Returns a bool rather than raising because "signature invalid" is an
        expected, reportable outcome (surfaced as ``signature_valid: false``
        in API responses), not an exceptional control-flow event.

        Example::

            assert key.verify(payload, signature)
        """
        try:
            self._private_key.public_key().verify(signature, payload)
        except InvalidSignature:
            return False
        return True
