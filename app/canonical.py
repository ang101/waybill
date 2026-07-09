"""Deterministic byte encoding of a package for signing and verification.

Sign-time and verify-time must produce identical bytes for the same content,
so the encoding pins key order and separators — field insertion order or
whitespace differences must never break a signature.
"""

from __future__ import annotations

import json

from app.models import PackageSnapshot


def canonicalize_package(package: PackageSnapshot) -> bytes:
    """Encode a package as deterministic JSON bytes.

    Example::

        payload = canonicalize_package(snapshot)
        signature = signing_key.sign(payload)
    """
    return json.dumps(package.model_dump(), sort_keys=True, separators=(",", ":")).encode("utf-8")
