"""Tests for UnifiedRetriever."""
import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.pools import PoolRegistry
from sisyphus.memory.unified import UnifiedRetriever


@pytest.fixture
def retriever(tmp_path):
    base = tmp_path / ".omo"
    reg = PoolRegistry(base)
    reg.init_structure()

    s_personal = reg.get_store("personal")
    s_project = reg.get_store("projects", "abc123")
    s_shared = reg.get_store("shared")

    s_personal.create(title="personal note", type="note", content="user preference for dark theme")
    s_personal.create(title="personal lesson", type="lesson", content="always backup before migration")
    s_project.create(title="project config", type="decision", content="database host is localhost:5432")
    s_project.create(title="project API", type="lesson", content="use JWT for authentication")
    s_shared.create(title="shared tip", type="pattern", content="use git hooks for linting")

    return UnifiedRetriever(base, project_hash="abc123")


class TestUnifiedRetriever:
    def test_retrieve_returns_results(self, retriever):
        results = retriever.retrieve("database", top_k=5)
        assert len(results) >= 1
        assert results[0][2] in ("personal", "project", "shared")

    def test_retrieve_pool_label(self, retriever):
        results = retriever.retrieve("JWT", top_k=5)
        pools = {r[2] for r in results}
        assert "project" in pools

    def test_retrieve_top_k(self, retriever):
        results = retriever.retrieve("backup", top_k=2)
        assert len(results) <= 2

    def test_empty_query(self, retriever):
        results = retriever.retrieve("", top_k=5)
        assert results == []

    def test_scope_limits_pools(self, retriever):
        results = retriever.retrieve("note", scope=["personal"], top_k=5)
        pools = {r[2] for r in results}
        assert all(p == "personal" for p in pools)

    def test_weighted_results(self, retriever):
        results = retriever.retrieve("theme OR JWT OR linting", top_k=10)
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)
