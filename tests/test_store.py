"""Tests for memory store."""

import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.store import MemoryStore, Memory


@pytest.fixture
def store():
    """Create a MemoryStore in a temp directory."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo" / "memory"
        yield MemoryStore(base_path=base)


class TestMemoryStoreInit:
    """Initialization."""

    def test_init_creates_directory(self, store):
        assert store.base_path.exists()
        assert store.base_path.is_dir()

    def test_init_creates_index(self, store):
        index_file = store.base_path / "INDEX.md"
        assert index_file.exists()
        content = index_file.read_text()
        assert "# Sisyphus Memory Index" in content


class TestMemoryCRUD:
    """Create, Read, Update, Delete."""

    def test_create_memory(self, store):
        mem = store.create(
            title="Test memory",
            type="lesson",
            content="This is a test memory.",
            tags=["test", "pytest"],
        )
        assert mem.id is not None
        assert mem.title == "Test memory"
        assert mem.type == "lesson"
        assert mem.content == "This is a test memory."
        assert mem.tags == ["test", "pytest"]
        assert mem.created_at is not None

    def test_create_adds_to_index(self, store):
        mem = store.create(title="Indexed", type="decision", content="In index.")
        index = (store.base_path / "INDEX.md").read_text()
        assert mem.id in index
        assert "Indexed" in index
        assert "decision" in index

    def test_create_writes_topic_file(self, store):
        mem = store.create(title="File test", type="lesson", content="In file.")
        topic_file = store.base_path / f"{mem.id}.md"
        assert topic_file.exists()
        content = topic_file.read_text()
        assert "# File test" in content
        assert "In file." in content
        assert "lesson" in content.lower()

    def test_get_memory(self, store):
        created = store.create(title="Get me", type="pattern", content="To be retrieved.")
        retrieved = store.get(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == "Get me"

    def test_get_nonexistent_returns_none(self, store):
        assert store.get("nonexistent") is None

    def test_list_memories(self, store):
        store.create(title="First", type="lesson", content="First content.")
        store.create(title="Second", type="decision", content="Second content.")
        all_mems = store.list()
        assert len(all_mems) == 2

    def test_list_filter_by_type(self, store):
        store.create(title="Lesson A", type="lesson", content="A")
        store.create(title="Decision B", type="decision", content="B")
        store.create(title="Lesson C", type="lesson", content="C")
        lessons = store.list(type_filter="lesson")
        assert len(lessons) == 2
        decisions = store.list(type_filter="decision")
        assert len(decisions) == 1

    def test_update_memory(self, store):
        mem = store.create(title="Original", type="lesson", content="Original content.")
        updated = store.update(mem.id, title="Updated", content="Updated content.")
        assert updated.title == "Updated"
        assert updated.content == "Updated content."
        # Topic file should reflect updates
        topic = (store.base_path / f"{mem.id}.md").read_text()
        assert "Updated" in topic
        assert "Updated content" in topic
        # Index should also reflect
        index = (store.base_path / "INDEX.md").read_text()
        assert "Updated" in index

    def test_delete_memory(self, store):
        mem = store.create(title="Delete me", type="lesson", content="Going away.")
        store.delete(mem.id)
        assert store.get(mem.id) is None
        # Topic file should be removed
        topic_file = store.base_path / f"{mem.id}.md"
        assert not topic_file.exists()
        # Index should no longer list it
        index = (store.base_path / "INDEX.md").read_text()
        assert mem.id not in index

    def test_delete_nonexistent_does_not_raise(self, store):
        store.delete("nonexistent")  # should not raise


class TestMemoryPersistence:
    """Memories survive store re-initialization."""

    def test_memories_persist_across_reinit(self, tmp_path):
        base = tmp_path / ".omo" / "memory"
        s1 = MemoryStore(base_path=base)
        s1.create(title="Persistent", type="lesson", content="I survive.")
        s2 = MemoryStore(base_path=base)
        all_mems = s2.list()
        assert len(all_mems) == 1
        assert all_mems[0].title == "Persistent"


class TestINDEXFormat:
    """INDEX.md format is consistent."""

    def test_index_format(self, store):
        m1 = store.create(title="Alpha", type="lesson", content="First.")
        m2 = store.create(title="Beta", type="decision", content="Second.")
        index = (store.base_path / "INDEX.md").read_text()
        # Has header
        assert index.startswith("# Sisyphus Memory Index")
        # Both entries listed
        assert m1.id in index
        assert m2.id in index
        # Format: id, type, title, created_at
        for line in index.split("\n"):
            if line.startswith("- ["):
                assert m1.id in line or m2.id in line
