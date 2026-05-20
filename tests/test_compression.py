"""Tests for memory compression — subagent-based annealing (v0.5)."""

import pytest
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.compression import Compressor


class MockSubagent:
    def __init__(self, deleted_count=0):
        self.deleted_count = deleted_count
        self.last_call = None

    def compress(self, **kwargs):
        self.last_call = kwargs
        return {"status": "ok", "deleted_count": self.deleted_count}


def _seed(store, count, mem_type="lesson", prefix="M"):
    for i in range(count):
        store.create(title=f"{prefix}{i}", type=mem_type, content=f"content {i}")


class TestThreshold:

    def test_below_threshold_does_nothing(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_below")
        _seed(store, 5)
        subagent = MockSubagent(deleted_count=0)
        c = Compressor(store=store, subagent=subagent, threshold=10)
        assert c.run() == 0
        assert len(store.list()) == 5

    def test_above_threshold_delegates_to_subagent(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_above")
        _seed(store, 25)
        subagent = MockSubagent(deleted_count=20)
        c = Compressor(store=store, subagent=subagent, threshold=20)
        assert c.run() == 20
        assert subagent.last_call is not None

    def test_empty_store_zero(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_empty")
        subagent = MockSubagent()
        assert Compressor(store=store, subagent=subagent).run() == 0

    def test_passes_threshold_and_keep_recent(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_params")
        _seed(store, 25)
        subagent = MockSubagent(deleted_count=20)
        Compressor(store=store, subagent=subagent, threshold=15, keep_recent=3).run()
        assert subagent.last_call["threshold"] == 15
        assert subagent.last_call["keep_recent"] == 3

    def test_threshold_not_met_does_not_call_subagent(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_no_call")
        _seed(store, 5)
        subagent = MockSubagent(deleted_count=0)
        Compressor(store=store, subagent=subagent, threshold=10).run()
        assert subagent.last_call is None

    def test_subagent_error_returns_zero(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "tc_err")
        _seed(store, 25)
        class ErrorSubagent:
            def compress(self, **kwargs):
                return {"status": "error", "message": "LLM failed"}
        c = Compressor(store=store, subagent=ErrorSubagent(), threshold=20)
        assert c.run() == 0
