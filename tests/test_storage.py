"""HandoffStore tests."""

from __future__ import annotations

import pytest

from app.models import PackageSnapshot
from app.storage import HandoffStore

_SIGNATURE = b"\x00" * 64


def _snapshot() -> PackageSnapshot:
    return PackageSnapshot(
        original_goal="process refunds",
        constraints=["must log decisions"],
        out_of_scope=[],
        completed=[],
        remaining=["triage backlog"],
    )


class TestCreateRoot:
    def test_create_root_then_get_returns_same_package(self) -> None:
        store = HandoffStore()
        created = store.create_root("wb-1", _snapshot(), _SIGNATURE)
        fetched = store.get("wb-1")
        assert fetched == created
        assert fetched.hop_index == 0
        assert fetched.parent_handoff_id is None
        assert fetched.root_handoff_id == "wb-1"

    def test_create_root_with_duplicate_id_raises_value_error(self) -> None:
        store = HandoffStore()
        store.create_root("wb-1", _snapshot(), _SIGNATURE)
        with pytest.raises(ValueError, match="already exists"):
            store.create_root("wb-1", _snapshot(), _SIGNATURE)


class TestGet:
    def test_get_missing_id_raises_key_error_naming_the_id(self) -> None:
        with pytest.raises(KeyError, match="wb-missing"):
            HandoffStore().get("wb-missing")


class TestAppendHop:
    def test_append_hop_increments_hop_index(self) -> None:
        store = HandoffStore()
        store.create_root("wb-1", _snapshot(), _SIGNATURE)
        second = store.append_hop("wb-1", "wb-2", _snapshot(), _SIGNATURE)
        third = store.append_hop("wb-2", "wb-3", _snapshot(), _SIGNATURE)
        assert second.hop_index == 1
        assert third.hop_index == 2

    def test_append_hop_preserves_root_id_across_hops(self) -> None:
        store = HandoffStore()
        store.create_root("wb-1", _snapshot(), _SIGNATURE)
        store.append_hop("wb-1", "wb-2", _snapshot(), _SIGNATURE)
        third = store.append_hop("wb-2", "wb-3", _snapshot(), _SIGNATURE)
        assert third.root_handoff_id == "wb-1"

    def test_extend_with_missing_parent_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="wb-missing"):
            HandoffStore().append_hop("wb-missing", "wb-2", _snapshot(), _SIGNATURE)

    def test_append_hop_with_duplicate_id_raises_value_error(self) -> None:
        store = HandoffStore()
        store.create_root("wb-1", _snapshot(), _SIGNATURE)
        with pytest.raises(ValueError, match="already exists"):
            store.append_hop("wb-1", "wb-1", _snapshot(), _SIGNATURE)
