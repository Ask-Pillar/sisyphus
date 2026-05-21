"""Tests for MemoryContext — per-turn context builder."""

import pytest
from pathlib import Path
from sisyphus.memory.store import Memory, MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.context import (
    MemoryContext, AgentMemory, _format_context,
    CONTEXT_HEADER, CONTEXT_FOOTER,
)


class MockRetriever:
    def __init__(self):
        self.retrieve_calls = []
        self.refined_calls = []
        self.results = []
        self.refined_results = []

    def retrieve(self, query="", top_k=8):
        self.retrieve_calls.append((query, top_k))
        return self.results

    def retrieve_refined_only(self, query="", top_k=5):
        self.refined_calls.append((query, top_k))
        return self.refined_results


class TestFormatContext:

    def test_empty_returns_header_footer(self):
        result = _format_context([], max_chars=4000)
        assert result == CONTEXT_HEADER + CONTEXT_FOOTER

    def test_includes_memories(self):
        mem = Memory(id="t1", type="lesson", title="Test", content="Content text", importance=8)
        result = _format_context([(mem, 8.0)], max_chars=4000)
        assert "Test" in result
        assert "Content text" in result
        assert "lesson" in result
        assert "importance=8" in result

    def test_respects_max_chars(self):
        mem = Memory(id="t1", type="lesson", title="Long " * 100, content="X" * 1000, importance=5)
        result = _format_context([(mem, 5.0)], max_chars=200)
        assert len(result) <= 200

    def test_multiple_memories(self):
        m1 = Memory(id="t1", type="lesson", title="First", content="A", importance=8)
        m2 = Memory(id="t2", type="pattern", title="Second", content="B", importance=5)
        result = _format_context([(m1, 8.0), (m2, 5.0)], max_chars=4000)
        assert "First" in result
        assert "Second" in result


class TestMemoryContext:

    def test_empty_retriever_returns_header_footer(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        retriever = MockRetriever()
        ctx = MemoryContext(retriever, store)
        result = ctx.build("test", turn_count=0)
        assert CONTEXT_HEADER in result
        assert CONTEXT_FOOTER in result

    def test_turn_zero_always_full_retrieve(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        retriever = MockRetriever()
        ctx = MemoryContext(retriever, store)
        ctx.build("q", turn_count=0)
        assert len(retriever.retrieve_calls) == 1

    def test_full_retrieve_when_turn_reaches_interval(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        retriever = MockRetriever()
        mem = Memory(id="t1", type="lesson", title="Python", content="Type hints", importance=7)
        retriever.results = [(mem, 7.0)]
        ctx = MemoryContext(retriever, store, refresh_interval=5)
        result = ctx.build("Python typing", turn_count=5)
        assert "Python" in result
        assert len(retriever.retrieve_calls) == 1
        assert retriever.retrieve_calls[0] == ("Python typing", 10)

    def test_incremental_uses_refined_only(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        retriever = MockRetriever()
        mem = Memory(id="t1", type="lesson", title="Ref", content="x", importance=5)
        retriever.refined_results = [(mem, 5.0)]
        ctx = MemoryContext(retriever, store, refresh_interval=5)
        ctx.build("query", turn_count=1)
        ctx.build("query", turn_count=2)
        assert len(retriever.retrieve_calls) == 0
        assert len(retriever.refined_calls) == 2

    def test_refined_results_appear_in_output(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        retriever = MockRetriever()
        mem = Memory(id="t1", type="lesson", title="Refined result", content="detail", importance=6)
        retriever.refined_results = [(mem, 6.0)]
        ctx = MemoryContext(retriever, store, refresh_interval=5)
        result = ctx.build("query", turn_count=1)
        assert "Refined result" in result

    def test_full_retrieve_after_interval(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        retriever = MockRetriever()
        retriever.results = []
        mem = Memory(id="t1", type="lesson", title="R", content="x", importance=5)
        retriever.refined_results = [(mem, 5.0)]
        ctx = MemoryContext(retriever, store, refresh_interval=3)
        ctx.build("q", turn_count=1)
        ctx.build("q", turn_count=4)
        assert len(retriever.retrieve_calls) == 1
        assert len(retriever.refined_calls) == 1

    def test_caches_result(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        retriever = MockRetriever()
        mem = Memory(id="t1", type="lesson", title="Cached", content="x", importance=5)
        retriever.results = [(mem, 5.0)]
        ctx = MemoryContext(retriever, store)
        r1 = ctx.build("q", turn_count=5)
        assert "Cached" in r1
        assert ctx._cached == r1

    def test_dirty_triggers_full_refresh(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        retriever = MockRetriever()
        retriever.results = []
        m = Memory(id="t1", type="x", title="D", content="y", importance=5)
        retriever.refined_results = [(m, 5.0)]
        ctx = MemoryContext(retriever, store, refresh_interval=10)
        ctx.build("q", turn_count=1)
        assert len(retriever.retrieve_calls) == 0
        assert len(retriever.refined_calls) == 1
        store.mark_dirty()
        ctx.build("q", turn_count=2)
        assert len(retriever.retrieve_calls) == 1
        assert store.is_dirty is False

    def test_store_write_auto_marks_dirty(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        assert store.is_dirty is False
        store.create(title="New", type="lesson", content="x")
        assert store.is_dirty is True

    def test_clear_dirty_resets(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        store.create(title="New", type="lesson", content="x")
        assert store.is_dirty is True
        store.clear_dirty()
        assert store.is_dirty is False


class TestAgentMemory:

    def test_before_turn_returns_context_block(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        store.create(title="Python hints", type="lesson", content="Use Optional", importance=8)
        agent = AgentMemory(store, refined)
        result = agent.before_turn("Python")
        assert "<sisyphus_context>" in result
        assert "</sisyphus_context>" in result

    def test_record_writes_and_marks_dirty(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        agent = AgentMemory(store, refined)
        mem = agent.record(title="test", type="note", content="hello")
        assert mem.id is not None
        assert store.is_dirty is True

    def test_turn_increments(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        agent = AgentMemory(store, refined)
        agent.before_turn("q")
        agent.before_turn("q")
        assert agent._turn == 2
