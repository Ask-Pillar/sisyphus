"""Tests for frozen memory snapshot."""

import pytest
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.snapshot import FrozenSnapshot


class MockRecall:
    def __init__(self, memories=None):
        self.memories = memories or []
        self.last_query = None

    def search(self, query, top_k=5):
        self.last_query = query
        return self.memories[:top_k]


@pytest.fixture
def store(tmp_path):
    return MemoryStore(base_path=tmp_path / ".omo" / "memory")


def _seed(store):
    store.create(title="Python 3.9 conventions", type="project_context",
                 content="Use Optional[X] not X | None. List not list.",
                 tags=["python"])
    store.create(title="沟通用中文", type="user_preference",
                 content="Prompt/指令用中文，代码/路径用英文",
                 tags=["language"])
    store.create(title="DeepSeek cache 91.5%", type="lesson",
                 content="磁盘缓存 + append-only",
                 tags=["deepseek"])
    return store


class TestFrozenSnapshot:

    def test_empty_store_returns_empty_snapshot(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / ".omo" / "memory")
        recall = MockRecall()
        snap = FrozenSnapshot(recall=recall)
        result = snap.build(query="test")
        assert "No memories yet" in result
        assert "<sisyphus_memory_snapshot>" in result.lower()
        assert "</sisyphus_memory_snapshot>" in result.lower()

    def test_snapshot_includes_memories(self, store):
        _seed(store)
        recall = MockRecall(memories=store.list())
        snap = FrozenSnapshot(recall=recall)
        result = snap.build(query="test")
        assert "Python 3.9" in result
        assert "沟通用中文" in result
        assert "DeepSeek" in result

    def test_snapshot_is_deterministic(self, store):
        _seed(store)
        recall = MockRecall(memories=store.list())
        snap = FrozenSnapshot(recall=recall)
        r1 = snap.build(query="test")
        r2 = snap.build(query="test")
        assert r1 == r2

    def test_snapshot_passes_query_to_recall(self, store):
        _seed(store)
        recall = MockRecall(memories=store.list())
        snap = FrozenSnapshot(recall=recall)
        snap.build(query="帮我看看 Python 项目结构")
        assert "Python" in recall.last_query

    def test_snapshot_respects_max_memories(self, store):
        _seed(store)
        all_mems = store.list()
        recall = MockRecall(memories=all_mems)
        snap = FrozenSnapshot(recall=recall, max_memories=2)
        result = snap.build(query="test")
        lines = result.strip().split("\n")
        memory_lines = [l for l in lines if l.startswith("- [")]
        assert len(memory_lines) == 2

    def test_snapshot_respects_max_chars(self, store):
        _seed(store)
        recall = MockRecall(memories=store.list())
        snap = FrozenSnapshot(recall=recall, max_chars=100)
        result = snap.build(query="test")
        assert len(result) <= 100

    def test_snapshot_format_is_parseable(self, store):
        _seed(store)
        recall = MockRecall(memories=store.list())
        snap = FrozenSnapshot(recall=recall)
        result = snap.build(query="test")
        assert "<sisyphus_memory_snapshot>" in result.lower()
        assert "</sisyphus_memory_snapshot>" in result.lower()

    def test_multiple_builds_same_result(self, store):
        _seed(store)
        recall = MockRecall(memories=store.list())
        snap = FrozenSnapshot(recall=recall)
        r1 = snap.build(query="hello")
        r2 = snap.build(query="world")
        assert r1 == r2
