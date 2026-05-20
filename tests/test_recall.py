"""Tests for LLM-powered recall via subagent."""

import pytest
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.recall import Recall


class MockSubagent:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.default = {"status": "ok", "memory_ids": []}
        self.calls = []

    def recall_search(self, memories, query):
        self.calls.append(("recall_search", memories, query))
        for key, resp in self.responses.items():
            if key in query:
                return resp
        return self.default

    def recall_relevant(self, memory, query):
        return {"status": "ok", "relevance": 0.5}


@pytest.fixture
def store(tmp_path):
    return MemoryStore(base_path=tmp_path / ".omo" / "memory")


@pytest.fixture
def subagent():
    return MockSubagent()


@pytest.fixture
def populated_store(store):
    store.create(title="Python 3.9", type="project_context",
                 content="Python 3.9, pytest",
                 tags=["python"])
    store.create(title="DeepSeek cache 91.5%", type="lesson",
                 content="Disk cache + append-only",
                 tags=["deepseek", "cache"])
    store.create(title="Use Chinese", type="user_preference",
                 content="日常沟通用中文",
                 tags=["convention"])
    store.create(title="Check lsp_diagnostics first", type="skill",
                 content="运行 lsp_diagnostics 验证",
                 tags=["workflow"])
    return store


class TestRecallSearch:

    def test_search_relevant(self, populated_store):
        lesson_id = populated_store.list(type_filter="lesson")[0].id
        subagent = MockSubagent(responses={
            "cache": {"status": "ok", "memory_ids": [lesson_id]},
        })
        recall = Recall(store=populated_store, subagent=subagent)
        results = recall.search("DeepSeek cache")
        assert len(results) == 1
        assert "DeepSeek" in results[0].title

    def test_search_top_k_limit(self, populated_store):
        all_ids = [m.id for m in populated_store.list()]
        subagent = MockSubagent(responses={
            "": {"status": "ok", "memory_ids": all_ids},
        })
        recall = Recall(store=populated_store, subagent=subagent)
        results = recall.search("anything", top_k=2)
        assert len(results) <= 2

    def test_search_empty_query_returns_recent(self, populated_store):
        recall = Recall(store=populated_store, subagent=MockSubagent())
        results = recall.search("", top_k=3)
        assert len(results) == 3

    def test_search_empty_store_returns_empty(self, store):
        recall = Recall(store=store, subagent=MockSubagent())
        results = recall.search("anything")
        assert results == []

    def test_subagent_receives_memories_in_call(self, populated_store):
        subagent = MockSubagent()
        recall = Recall(store=populated_store, subagent=subagent)
        recall.search("test query")
        assert len(subagent.calls) > 0
        _, mems, query = subagent.calls[0]
        assert len(mems) == 4
        assert query == "test query"

    def test_subagent_returns_nonexistent_ids(self, populated_store):
        subagent = MockSubagent(responses={
            "": {"status": "ok", "memory_ids": ["mem_nonexistent"]},
        })
        recall = Recall(store=populated_store, subagent=subagent)
        results = recall.search("anything")
        assert results == []

    def test_subagent_error_returns_empty(self, populated_store):
        class ErrorSubagent:
            def recall_search(self, memories, query):
                return {"status": "error", "message": "LLM failed"}
            def recall_relevant(self, memory, query):
                return {"status": "error", "message": "LLM failed"}

        recall = Recall(store=populated_store, subagent=ErrorSubagent())
        results = recall.search("anything")
        assert len(results) == 0


class TestRecallEdgeCases:

    def test_llm_returns_empty_ids(self, populated_store):
        subagent = MockSubagent(responses={
            "": {"status": "ok", "memory_ids": []},
        })
        recall = Recall(store=populated_store, subagent=subagent)
        results = recall.search("anything")
        assert results == []


class TestRecallIntegration:

    def test_recall_then_show_full_memory(self, populated_store):
        pref_id = populated_store.list(type_filter="user_preference")[0].id
        subagent = MockSubagent(responses={
            "语言": {"status": "ok", "memory_ids": [pref_id]},
        })
        recall = Recall(store=populated_store, subagent=subagent)
        results = recall.search("我应该用什么语言沟通")
        assert len(results) == 1
        mem = results[0]
        assert mem.type == "user_preference"
        assert "中文" in mem.content

    def test_is_relevant_delegates_to_subagent(self, populated_store):
        subagent = MockSubagent()
        recall = Recall(store=populated_store, subagent=subagent)
        mem = populated_store.list()[0]
        score = recall.is_relevant("test", mem)
        assert score == 0.5
