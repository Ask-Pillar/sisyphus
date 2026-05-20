"""Tests for CacheStore — rebuildable SQLite cache (v1.4)."""

import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.cache import CacheStore


@pytest.fixture
def store_and_cache():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo"
        store = MemoryStore(base / "memory")
        cache = CacheStore(base)
        yield store, cache


class TestCacheRebuild:
    def test_rebuild_empty(self, store_and_cache):
        store, cache = store_and_cache
        result = cache.rebuild(store)
        assert result["cached"] == 0

    def test_rebuild_after_create(self, store_and_cache):
        store, cache = store_and_cache
        store.create(title="T1", type="lesson", content="x")
        result = cache.rebuild(store)
        assert result["cached"] == 1

    def test_rebuild_twice_matches(self, store_and_cache):
        store, cache = store_and_cache
        store.create(title="T1", type="lesson", content="x")
        r1 = cache.rebuild(store)
        r2 = cache.rebuild(store)
        assert r1["cached"] == r2["cached"]


class TestCacheStatus:
    def test_status_empty(self, store_and_cache):
        _, cache = store_and_cache
        s = cache.status()
        assert s["total"] == 0

    def test_status_after_rebuild(self, store_and_cache):
        store, cache = store_and_cache
        store.create(title="T1", type="lesson", content="x")
        cache.rebuild(store)
        s = cache.status()
        assert s["total"] == 1
        assert "lesson" in s["by_type"]


class TestCacheSearch:
    def test_search_by_title(self, store_and_cache):
        store, cache = store_and_cache
        store.create(title="Python tips", type="lesson", content="details")
        store.create(title="JS notes", type="lesson", content="details")
        cache.rebuild(store)
        results = cache.search("Python")
        assert len(results) == 1

    def test_search_by_content(self, store_and_cache):
        store, cache = store_and_cache
        store.create(title="T1", type="lesson", content="unique content here")
        cache.rebuild(store)
        results = cache.search("unique")
        assert len(results) == 1

    def test_search_returns_all(self, store_and_cache):
        store, cache = store_and_cache
        store.create(title="A", type="lesson", content="a")
        store.create(title="B", type="lesson", content="b")
        cache.rebuild(store)
        results = cache.search("")
        assert len(results) == 2

    def test_search_empty_cache(self, store_and_cache):
        _, cache = store_and_cache
        assert cache.search("anything") == []
