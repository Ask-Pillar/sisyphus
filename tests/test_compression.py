"""Tests for memory compression — annealing style (v0.5)."""

import pytest
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.compression import Compressor


class MockLLM:
    def chat(self, messages):
        return '{"title": "historical context", "content": "Compressed summary."}'


class TrackingLLM:
    def __init__(self):
        self.calls = []
    def chat(self, messages):
        self.calls.append(messages[-1]["content"])
        return '{"title": "x", "content": "y"}'


def _seed(store, count, mem_type="lesson", prefix="M"):
    for i in range(count):
        store.create(title=f"{prefix}{i}", type=mem_type, content=f"content {i}")


class TestThreshold:

    def test_below_threshold_does_nothing(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_below")
        _seed(store, 5)
        c = Compressor(store=store, llm_client=MockLLM(), threshold=10)
        assert c.run() == 0
        assert len(store.list()) == 5

    def test_above_threshold_compresses(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_above")
        _seed(store, 25)
        c = Compressor(store=store, llm_client=MockLLM(), threshold=20)
        assert c.run() >= 15

    def test_empty_store_zero(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_empty")
        assert Compressor(store=store, llm_client=MockLLM()).run() == 0


class TestAnnealing:

    def test_merges_old_into_one_summary(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_one_summary")
        _seed(store, 30)
        Compressor(store=store, llm_client=MockLLM(), threshold=20, keep_recent=5).run()
        remaining = store.list()
        summaries = [m for m in remaining if "[compressed]" in m.title]
        assert len(summaries) == 1

    def test_keeps_recent_memories(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_keep")
        _seed(store, 30)
        recent = sorted(store.list(), key=lambda m: m.created_at, reverse=True)[:5]
        Compressor(store=store, llm_client=MockLLM(), threshold=20, keep_recent=5).run()
        recent_ids = {m.id for m in store.list()}
        for m in recent:
            assert m.id in recent_ids

    def test_summary_from_llm(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_llm_out")
        _seed(store, 25)
        Compressor(store=store, llm_client=MockLLM(), threshold=20).run()
        remaining = store.list()
        summary = [m for m in remaining if "[compressed]" in m.title]
        assert len(summary) == 1
        assert "Compressed summary" in summary[0].content

    def test_originals_deleted_replaced_by_summary(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_delete")
        _seed(store, 25)
        before = len(store.list())
        Compressor(store=store, llm_client=MockLLM(), threshold=15, keep_recent=5).run()
        remaining = store.list()
        assert len(remaining) < before
        assert len(remaining) == 6

    def test_no_type_grouping(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_no_group")
        _seed(store, 10, mem_type="lesson")
        _seed(store, 10, mem_type="pattern")
        _seed(store, 10, mem_type="preference")
        Compressor(store=store, llm_client=MockLLM(), threshold=20, keep_recent=5).run()
        remaining = store.list()
        summaries = [m for m in remaining if "[compressed]" in m.title]
        assert len(summaries) == 1

    def test_llm_receives_all_old_memories(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_llm_in")
        _seed(store, 25)
        tracker = TrackingLLM()
        Compressor(store=store, llm_client=tracker, threshold=20, keep_recent=3).run()
        assert len(tracker.calls) > 0
        assert "M0" in tracker.calls[0]
