"""Tests for SQLiteMemoryStore."""
import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.sqlite_store import SQLiteMemoryStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "store"
        yield SQLiteMemoryStore(base_path=base)


class TestSQLiteStoreCRUD:
    def test_create(self, store):
        mem = store.create(title="test", type="lesson", content="hello")
        assert mem.id.startswith("mem_")
        assert mem.title == "test"
        assert "lesson" in mem.types

    def test_get(self, store):
        mem = store.create(title="find me", type="note", content="xyz")
        found = store.get(mem.id)
        assert found is not None
        assert found.title == "find me"

    def test_get_nonexistent(self, store):
        assert store.get("nonexistent") is None

    def test_list(self, store):
        store.create(title="a", type="lesson", content="1")
        store.create(title="b", type="decision", content="2")
        assert len(store.list()) == 2

    def test_list_type_filter(self, store):
        store.create(title="a", type="lesson", content="1")
        store.create(title="b", type="decision", content="2")
        store.create(title="c", type="lesson", content="3")
        assert len(store.list(type_filter="lesson")) == 2

    def test_soft_delete(self, store):
        mem = store.create(title="delete me", type="note", content="x")
        assert store.delete(mem.id)
        assert len(store.list()) == 0
        assert len(store.list(include_deleted=True)) == 1

    def test_restore(self, store):
        mem = store.create(title="restore me", type="note", content="x")
        store.delete(mem.id)
        assert store.restore(mem.id)
        assert len(store.list()) == 1

    def test_rate(self, store):
        mem = store.create(title="rate me", type="lesson", content="x")
        assert store.rate(mem.id, 4)
        fetched = store.get(mem.id)
        assert fetched.feedback_score == 4

    def test_dismiss(self, store):
        mem = store.create(title="dismiss me", type="lesson", content="x")
        assert store.dismiss(mem.id)
        assert len(store.list()) == 0

    def test_dismiss_nonexistent(self, store):
        assert not store.dismiss("nonexistent")

    def test_search(self, store):
        store.create(title="database config", type="decision", content="postgres host localhost")
        store.create(title="api docs", type="note", content="swagger setup")
        results = store.search("database")
        assert len(results) >= 1


class TestSQLiteStoreMigration:
    def test_migrates_from_files(self, tmp_path):
        from sisyphus.memory.store import MemoryStore
        base = tmp_path / "mem"
        old = MemoryStore(base)
        old.create(title="old memory", type="lesson", content="migrated content")

        new = SQLiteMemoryStore(base_path=base)
        assert len(new.list()) == 1
        assert new.list()[0].title == "old memory"
