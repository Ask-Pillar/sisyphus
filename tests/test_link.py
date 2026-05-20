"""Tests for LinkCleaner — link validation and cleanup (v1.1 step3)."""

import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.link import LinkCleaner


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo" / "memory"
        yield MemoryStore(base_path=base)


@pytest.fixture
def cleaner(store):
    return LinkCleaner(store)


class TestLinkCleaner:
    def test_empty_store_returns_zero(self, cleaner):
        result = cleaner.clean()
        assert result["total_cleaned"] == 0

    def test_removes_dead_link(self, cleaner):
        m = cleaner.store.create(
            title="Test", type="lesson", content="Content.",
            links=["nonexistent_id"],
        )
        result = cleaner.clean()
        assert result["total_cleaned"] == 1
        updated = cleaner.store.get(m.id)
        assert "nonexistent_id" not in updated.links

    def test_removes_self_reference(self, cleaner):
        m = cleaner.store.create(
            title="Test", type="lesson", content="Content.",
        )
        cleaner.store.update(m.id, links=[m.id])
        result = cleaner.clean()
        updated = cleaner.store.get(m.id)
        assert m.id not in updated.links

    def test_deduplicates_links(self, cleaner):
        m1 = cleaner.store.create(title="A", type="lesson", content="A")
        m2 = cleaner.store.create(title="B", type="lesson", content="B")
        cleaner.store.update(m1.id, links=[m2.id, m2.id, m2.id])
        result = cleaner.clean()
        updated = cleaner.store.get(m1.id)
        assert updated.links == [m2.id]

    def test_preserves_valid_links(self, cleaner):
        m1 = cleaner.store.create(title="A", type="lesson", content="A")
        m2 = cleaner.store.create(title="B", type="lesson", content="B")
        cleaner.store.update(m1.id, links=[m2.id])
        result = cleaner.clean()
        assert result["total_cleaned"] == 0
        updated = cleaner.store.get(m1.id)
        assert m2.id in updated.links

    def test_mixed_links_cleaned_correctly(self, cleaner):
        m1 = cleaner.store.create(title="A", type="lesson", content="A")
        m2 = cleaner.store.create(title="B", type="lesson", content="B")
        cleaner.store.update(m1.id, links=[m2.id, "dead1", m2.id, m1.id, "dead2"])
        result = cleaner.clean()
        updated = cleaner.store.get(m1.id)
        assert updated.links == [m2.id]
        assert result["total_cleaned"] == 1
        assert result["removed_dead"] == 2
