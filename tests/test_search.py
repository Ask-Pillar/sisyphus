"""Tests for semantic search — lightweight vector search (v0.6)."""

import pytest
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.search import SemanticSearcher


def _seed(store):
    store.create(title="Python type hints", type="lesson", content="Use Optional not pipe syntax")
    store.create(title="沟通语言", type="preference", content="Prompt用中文，代码用英文")
    store.create(title="Docker compose", type="pattern", content="Use docker-compose.yml for services")
    store.create(title="测试驱动开发", type="lesson", content="TDD: Red-Green-Refactor")


class TestEmbedding:

    def test_search_returns_relevant_results(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "s1")
        _seed(store)
        searcher = SemanticSearcher(store=store)
        results = searcher.search("Python coding")
        assert len(results) > 0
        assert any("Python" in r.title for r in results)

    def test_search_ranks_relevant_higher(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "s2")
        _seed(store)
        searcher = SemanticSearcher(store=store)
        results = searcher.search("Docker service")
        assert len(results) > 0
        assert results[0].title == "Docker compose"

    def test_top_k_parameter(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "s3")
        _seed(store)
        searcher = SemanticSearcher(store=store)
        results = searcher.search("test", top_k=2)
        assert len(results) == 2

    def test_empty_query_returns_recent(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "s4")
        _seed(store)
        searcher = SemanticSearcher(store=store)
        results = searcher.search("")
        assert len(results) > 0

    def test_empty_store_returns_empty(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "s5")
        searcher = SemanticSearcher(store=store)
        assert searcher.search("anything") == []

    def test_vector_cache(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "s6")
        _seed(store)
        searcher = SemanticSearcher(store=store)
        searcher.search("test")
        first_ids = set(searcher._vectors.keys())
        searcher.search("other")
        assert set(searcher._vectors.keys()) == first_ids
