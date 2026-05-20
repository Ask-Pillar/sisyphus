"""Tests for LLM-powered recall."""

import pytest
import json
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.recall import Recall
from sisyphus.memory.llm import LLMClient


class MockLLM:
    """Simulates an LLM that returns controlled responses."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.default_response = '{"memory_ids": []}'
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        prompt = messages[-1]["content"] if messages else ""
        for key, resp in self.responses.items():
            if key in prompt:
                return resp
        return self.default_response


@pytest.fixture
def store(tmp_path):
    return MemoryStore(base_path=tmp_path / ".omo" / "memory")


@pytest.fixture
def mock_llm():
    return MockLLM()


@pytest.fixture
def populated_store(store):
    store.create(title="项目使用 Python 3.9", type="project_context",
                 content="Python 3.9, pytest, 无第三方依赖",
                 tags=["python", "setup"])
    store.create(title="DeepSeek 缓存命中率 91.5%", type="lesson",
                 content="磁盘缓存 + append-only 即可享受高命中率",
                 tags=["deepseek", "cache"])
    store.create(title="沟通用中文", type="user_preference",
                 content="日常沟通用中文，代码/术语用英文",
                 tags=["convention", "language"])
    store.create(title="推送前先检查 lsp_diagnostics", type="skill",
                 content="修改文件后运行 lsp_diagnostics 验证",
                 tags=["workflow", "quality"])
    return store


class TestRecallSearch:

    def test_search_returns_relevant_memories(self, populated_store):
        llm = MockLLM(responses={
            "缓存": json.dumps({"memory_ids": [populated_store.list(type_filter="lesson")[0].id]}),
        })
        recall = Recall(store=populated_store, llm_client=llm)
        results = recall.search("DeepSeek cache")
        assert len(results) == 1
        assert "DeepSeek" in results[0].title

    def test_search_top_k_limit(self, populated_store):
        llm = MockLLM(responses={
            "memory_ids": json.dumps({
                "memory_ids": [m.id for m in populated_store.list()][:3]
            }),
        })
        recall = Recall(store=populated_store, llm_client=llm)
        results = recall.search("anything", top_k=2)
        assert len(results) <= 2

    def test_search_empty_query_returns_recent(self, populated_store):
        recall = Recall(store=populated_store, llm_client=MockLLM())
        results = recall.search("", top_k=3)
        assert len(results) == 3

    def test_search_empty_store_returns_empty(self, store):
        recall = Recall(store=store, llm_client=MockLLM())
        results = recall.search("anything")
        assert results == []

    def test_llm_receives_index_in_prompt(self, populated_store):
        llm = MockLLM()
        recall = Recall(store=populated_store, llm_client=llm)
        recall.search("test query")
        assert len(llm.calls) > 0
        prompt = llm.calls[0][-1]["content"]
        assert "Python 3.9" in prompt or "DeepSeek" in prompt
        assert "memory_ids" in prompt


class TestRecallEdgeCases:

    def test_llm_returns_invalid_json(self, populated_store):
        llm = MockLLM(responses={"": "not valid json"})
        recall = Recall(store=populated_store, llm_client=llm)
        results = recall.search("anything")
        assert results == []

    def test_llm_returns_nonexistent_ids(self, populated_store):
        llm = MockLLM(responses={
            "": json.dumps({"memory_ids": ["mem_nonexistent"]}),
        })
        recall = Recall(store=populated_store, llm_client=llm)
        results = recall.search("anything")
        assert results == []

    def test_llm_timeout_fallback(self, populated_store):
        class SlowLLM:
            def chat(self, messages):
                raise TimeoutError("LLM timeout")

        recall = Recall(store=populated_store, llm_client=SlowLLM())
        results = recall.search("anything")
        assert len(results) == 0


class TestRecallIntegration:
    """End-to-end with real prompt structure."""

    def test_recall_then_show_full_memory(self, populated_store):
        llm = MockLLM(responses={
            "沟通": json.dumps({
                "memory_ids": [populated_store.list(type_filter="user_preference")[0].id]
            }),
        })
        recall = Recall(store=populated_store, llm_client=llm)
        results = recall.search("我应该用什么语言沟通")
        assert len(results) == 1
        mem = results[0]
        assert mem.type == "user_preference"
        assert "中文" in mem.content
