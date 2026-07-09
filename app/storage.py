"""In-memory storage for handoff chains.

In-memory dict is a deliberate hackathon tradeoff: state is lost on process
restart (free-tier dynos sleep), mitigated operationally by a keepalive ping.
The public method signatures are storage-agnostic so a SQLite swap needs no
call-site changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models import PackageSnapshot


@dataclass(frozen=True)
class StoredHandoff:
    """One immutable hop in a handoff chain."""

    handoff_id: str
    parent_handoff_id: str | None
    root_handoff_id: str
    hop_index: int
    package: PackageSnapshot
    signature: bytes
    created_at: datetime


class HandoffStore:
    """Process-lifetime store of every hop, keyed by handoff_id.

    A class (not functions) because the dict is state that must persist
    across every request. Instantiated once in ``main.py`` and injected
    via FastAPI dependencies — never a bare module global.
    """

    def __init__(self) -> None:
        self._handoffs: dict[str, StoredHandoff] = {}

    def create_root(
        self, handoff_id: str, package: PackageSnapshot, signature: bytes
    ) -> StoredHandoff:
        """Store hop 0 of a new chain.

        Raises ``ValueError`` if the id already exists — silently overwriting
        a signed hop would defeat the whole tamper-evidence story.

        Example::

            stored = store.create_root("wb-1", snapshot, signature)
        """
        if handoff_id in self._handoffs:
            msg = f"handoff_id {handoff_id!r} already exists; refusing to overwrite a signed hop"
            raise ValueError(msg)
        stored = StoredHandoff(
            handoff_id=handoff_id,
            parent_handoff_id=None,
            root_handoff_id=handoff_id,
            hop_index=0,
            package=package,
            signature=signature,
            created_at=datetime.now(UTC),
        )
        self._handoffs[handoff_id] = stored
        return stored

    def get(self, handoff_id: str) -> StoredHandoff:
        """Fetch a hop by id.

        Raises ``KeyError`` naming the missing id — callers translate this
        to HTTP 404.

        Example::

            stored = store.get("wb-1")
        """
        stored = self._handoffs.get(handoff_id)
        if stored is None:
            msg = f"handoff_id {handoff_id!r} not found"
            raise KeyError(msg)
        return stored

    def append_hop(
        self,
        parent_handoff_id: str,
        handoff_id: str,
        package: PackageSnapshot,
        signature: bytes,
    ) -> StoredHandoff:
        """Store a new hop whose parent is ``parent_handoff_id``.

        Raises ``KeyError`` if the parent doesn't exist and ``ValueError``
        if the new id collides. Forward-carry validation (locked fields
        unchanged) is the route layer's job, before this is called.

        Example::

            stored = store.append_hop("wb-1", "wb-2", snapshot, signature)
        """
        parent = self.get(parent_handoff_id)
        if handoff_id in self._handoffs:
            msg = f"handoff_id {handoff_id!r} already exists; refusing to overwrite a signed hop"
            raise ValueError(msg)
        stored = StoredHandoff(
            handoff_id=handoff_id,
            parent_handoff_id=parent.handoff_id,
            root_handoff_id=parent.root_handoff_id,
            hop_index=parent.hop_index + 1,
            package=package,
            signature=signature,
            created_at=datetime.now(UTC),
        )
        self._handoffs[handoff_id] = stored
        return stored
