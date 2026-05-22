"""Tests for Path A/B retrieval and EmbeddingCache."""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.retrieval import ContextRetriever, EmbeddingCache


class TestChoosePath:
    def test_short_query_is_A(self):
        assert ContextRetriever._choose_path("hi") == "A"
        assert ContextRetriever._choose_path("hello world") == "A"

    def test_fuzzy_query_is_A(self):
        assert ContextRetriever._choose_path("关于记忆") == "A"
        assert ContextRetriever._choose_path("什么是记忆") == "A"
        assert ContextRetriever._choose_path("怎么用") == "A"

    def test_precise_query_is_B(self):
        assert ContextRetriever._choose_path("SubagentLauncher fixture_path parameter") == "B"
        assert ContextRetriever._choose_path("BM25 k1 b default values") == "B"

    def test_empty_query_is_A(self):
        assert ContextRetriever._choose_path("") == "A"

    def test_mixed_fuzzy_precise(self):
        assert ContextRetriever._choose_path("SubagentLauncher 是什么") == "A"


class TestEmbeddingCache:
    def test_get_put(self, tmp_path):
        db = str(tmp_path / "embeddings.db")
        cache = EmbeddingCache(db)
        cache.put("key1", [1.0, 2.0, 3.0])
        result = cache.get("key1")
        assert result == [1.0, 2.0, 3.0]

    def test_cache_miss(self, tmp_path):
        db = str(tmp_path / "embeddings.db")
        cache = EmbeddingCache(db)
        assert cache.get("nonexistent") is None

    def test_cache_overwrite(self, tmp_path):
        db = str(tmp_path / "embeddings.db")
        cache = EmbeddingCache(db)
        cache.put("k", [1.0])
        cache.put("k", [2.0])
        assert cache.get("k") == [2.0]

    def test_db_file_created(self, tmp_path):
        db = str(tmp_path / "embeddings.db")
        cache = EmbeddingCache(db)
        cache.put("x", [0.5])
        assert Path(db).exists()

    def test_cache_none_path_noop(self):
        cache = EmbeddingCache(None)
        cache.put("x", [1.0])  # should not crash
        assert cache.get("x") is None

    def test_cache_persists_across_instances(self, tmp_path):
        db = str(tmp_path / "embeddings.db")
        EmbeddingCache(db).put("k", [4.2])
        result = EmbeddingCache(db).get("k")
        assert result == [4.2]


class TestRetrievePathLogging:
    @pytest.fixture
    def retriever(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".omo" / "memory"
            store = MemoryStore(base)
            refined = RefinedStore(base)
            cache_path = str(base / "cache" / "embeddings.db")
            retriever = ContextRetriever(store, refined, subagent=None, cache_path=cache_path)
            # Add some test data
            store.create(title="Python typing", type="lesson", content="use Optional")
            store.create(title="Python list", type="lesson", content="use List")
            yield retriever

    def test_retrieve_returns_results(self, retriever):
        results = retriever.retrieve("Python", top_k=5)
        assert len(results) >= 1

    def test_retrieve_empty_query(self, retriever):
        results = retriever.retrieve("", top_k=5)
        assert len(results) >= 1

    def test_retrieve_with_cache_path(self, retriever):
        """Verify EmbeddingCache DB file is created after a put()."""
        cache = EmbeddingCache(retriever._cache._db_path)
        cache.put("test", [1.0])
        assert Path(retriever._cache._db_path).exists()


class TestDegradationChain:
    """Verify the system degrades gracefully when components are disabled."""

    @pytest.fixture
    def base_retriever(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".omo" / "memory"
            store = MemoryStore(base)
            refined = RefinedStore(base)
            for i in range(5):
                store.create(title=f"Memory {i}", type="lesson", content=f"content {i}")
            yield store, refined, base

    def test_no_reranker_still_works(self, base_retriever):
        """Path B without reranker falls back to BM25+Embedding."""
        store, refined, base = base_retriever
        retriever = ContextRetriever(store, refined, subagent=None,
                                      reranker=None, embedder=None)
        results = retriever.retrieve("Memory 1", top_k=3)
        assert len(results) >= 1

    def test_no_embedder_falls_to_tfidf(self, base_retriever):
        """Without embedder, TF-IDF fallback kicks in."""
        store, refined, base = base_retriever
        retriever = ContextRetriever(store, refined, subagent=None,
                                      reranker=None, embedder=None)
        results = retriever.retrieve("Memory", top_k=3)
        assert len(results) >= 1

    def test_no_subagent_still_works(self, base_retriever):
        """Without subagent, keyword fallback is used."""
        store, refined, base = base_retriever
        retriever = ContextRetriever(store, refined, subagent=None)
        results = retriever.retrieve("Memory", top_k=3)
        assert len(results) >= 1
