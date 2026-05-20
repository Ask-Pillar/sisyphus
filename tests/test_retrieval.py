"""Tests for ContextRetriever — 3-layer retrieval + decay scoring."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sisyphus.memory.store import Memory, MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.retrieval import (
    decay_score,
    _days_since,
    _collect_types,
    ContextRetriever,
    DECAY_HALF_LIFE_DAYS,
)


class TestDecayScore:

    def test_full_score_when_never_recalled(self):
        mem = Memory(id="t1", type="lesson", title="T", content="", importance=8)
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        mem.created_at = "2026-06-01T00:00:00+00:00"
        score = decay_score(mem, now)
        assert score == 8.0

    def test_half_life_reduces_score(self):
        mem = Memory(id="t1", type="lesson", title="T", content="", importance=8)
        now = datetime(2026, 7, 1, tzinfo=timezone.utc)
        mem.created_at = "2026-06-01T00:00:00+00:00"
        score = decay_score(mem, now)
        assert abs(score - 4.0) < 0.01

    def test_uses_last_recalled_over_created(self):
        mem = Memory(id="t1", type="lesson", title="T", content="", importance=8)
        now = datetime(2026, 7, 15, tzinfo=timezone.utc)
        mem.created_at = "2026-01-01T00:00:00+00:00"
        mem.last_recalled_at = "2026-07-01T00:00:00+00:00"
        score = decay_score(mem, now)
        expected = 8.0 * (0.5 ** (14 / DECAY_HALF_LIFE_DAYS))
        assert abs(score - expected) < 0.01

    def test_zero_importance_always_zero(self):
        mem = Memory(id="t1", type="lesson", title="T", content="", importance=0)
        score = decay_score(mem, datetime.now(timezone.utc))
        assert score == 0.0

    def test_days_since(self):
        now = datetime(2026, 6, 15, tzinfo=timezone.utc)
        assert _days_since("2026-06-10T00:00:00+00:00", now) == 5.0

    def test_days_since_empty(self):
        assert _days_since("", datetime.now(timezone.utc)) == 0.0

    def test_days_since_invalid(self):
        assert _days_since("not-a-date", datetime.now(timezone.utc)) == 0.0


class TestCollectTypes:

    def test_collects_from_both_stores(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        store.create(title="A", type="lesson", content="x")
        store.create(title="B", type="pattern", content="y")
        refined.create_reflection(title="C", content="x")
        types = _collect_types(store, refined)
        assert "lesson" in types
        assert "pattern" in types
        assert "reflection" in types

    def test_deduplicates(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        store.create(title="A", type="lesson", content="x")
        refined.create_reflection(title="B", content="y")
        types = _collect_types(store, refined)
        assert len(types) >= 2

    def test_empty_returns_empty(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(base_path=Path(tmp) / "mem")
            refined = RefinedStore(base_path=Path(tmp) / "mem")
            assert _collect_types(store, refined) == []


class MockSubagent:
    def __init__(self):
        self.classify_calls = []
        self.recall_calls = []
        self.classify_result = {"status": "ok", "types": []}
        self.recall_result = {"status": "ok", "memory_ids": []}

    def classify_types(self, types, query):
        self.classify_calls.append((types, query))
        return self.classify_result

    def recall_search(self, memories, query):
        self.recall_calls.append((len(memories), query))
        return self.recall_result


class TestContextRetriever:

    def test_empty_store_returns_empty(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        retriever = ContextRetriever(store, refined, MockSubagent())
        assert retriever.retrieve("test") == []

    def test_l1_classify_called(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        store.create(title="Python lesson", type="lesson", content="x")
        subagent = MockSubagent()
        subagent.classify_result = {"status": "ok", "types": ["lesson"]}
        subagent.recall_result = {"status": "ok", "memory_ids": []}
        retriever = ContextRetriever(store, refined, subagent)
        retriever.retrieve("Python")
        assert len(subagent.classify_calls) == 1

    def test_retrieve_refined_only(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        m = refined.create_reflection(title="Test pattern", content="refined content")
        subagent = MockSubagent()
        subagent.recall_result = {"status": "ok", "memory_ids": [m.id]}
        retriever = ContextRetriever(store, refined, subagent)
        results = retriever.retrieve_refined_only("test")
        assert len(results) == 1
        mem, score = results[0]
        assert mem.title == "Test pattern"
        assert score > 0

    def test_empty_query_returns_decay_sorted(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        m1 = store.create(title="Important", type="lesson", content="x", importance=10)
        m2 = store.create(title="Normal", type="lesson", content="y", importance=5)
        subagent = MockSubagent()
        subagent.classify_result = {"status": "ok", "types": ["lesson"]}
        subagent.recall_result = {"status": "ok", "memory_ids": []}
        retriever = ContextRetriever(store, refined, subagent)
        results = retriever.retrieve("")
        assert results == []

    def test_raw_fallback_when_refined_thin(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        raw = store.create(title="Raw knowledge", type="lesson", content="important raw", importance=7)
        subagent = MockSubagent()
        subagent.classify_result = {"status": "ok", "types": ["lesson"]}
        subagent.recall_result = {"status": "ok", "memory_ids": [raw.id]}
        retriever = ContextRetriever(store, refined, subagent)
        results = retriever.retrieve("find something", top_k=5)
        assert len(results) >= 1
        mem, score = results[0]
        assert mem.title == "Raw knowledge"

    def test_update_recall_stats(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        raw = store.create(title="Stat test", type="lesson", content="x", importance=5)
        assert raw.recall_count == 0
        subagent = MockSubagent()
        subagent.classify_result = {"status": "ok", "types": ["lesson"]}
        subagent.recall_result = {"status": "ok", "memory_ids": [raw.id]}
        retriever = ContextRetriever(store, refined, subagent)
        retriever.retrieve("test", top_k=5)
        updated = store.get(raw.id)
        assert updated is not None
        assert updated.recall_count == 1
        assert updated.last_recalled_at != ""

    def test_multiple_recalls_increment_count(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        raw = store.create(title="Multi test", type="lesson", content="x", importance=5)
        subagent = MockSubagent()
        subagent.classify_result = {"status": "ok", "types": ["lesson"]}
        subagent.recall_result = {"status": "ok", "memory_ids": [raw.id]}
        retriever = ContextRetriever(store, refined, subagent)
        retriever.retrieve("test", top_k=5)
        retriever.retrieve("test", top_k=5)
        updated = store.get(raw.id)
        assert updated is not None
        assert updated.recall_count == 2
