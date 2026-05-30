"""Tests for DiversityReranker."""
import pytest
from sisyphus.memory.store import Memory
from sisyphus.memory.diversity import DiversityReranker


def make_mem(title, content, types):
    return Memory(id=title, types=types, title=title, content=content)


class TestDiversityReranker:
    @pytest.fixture
    def candidates(self):
        return [
            (make_mem("a", "database postgres config", ["decision"]), 0.9),
            (make_mem("b", "database mysql backup", ["decision"]), 0.85),
            (make_mem("c", "api auth jwt token", ["lesson"]), 0.8),
            (make_mem("d", "api endpoint rate limit", ["lesson"]), 0.75),
            (make_mem("e", "redis cache pattern", ["pattern"]), 0.7),
        ]

    def test_rerank_returns_top_k(self, candidates):
        reranker = DiversityReranker(min_types=2)
        result = reranker.rerank(candidates, top_k=3)
        assert len(result) == 3

    def test_type_diversity(self, candidates):
        reranker = DiversityReranker(min_types=2)
        result = reranker.rerank(candidates, top_k=3)
        types = {m.types[0] for m, _ in result}
        assert len(types) >= 2

    def test_empty_candidates(self):
        reranker = DiversityReranker()
        assert reranker.rerank([], top_k=5) == []

    def test_single_candidate(self):
        mem = make_mem("x", "test", ["note"])
        reranker = DiversityReranker()
        result = reranker.rerank([(mem, 0.5)], top_k=5)
        assert len(result) == 1

    def test_mmr_reduces_similar(self):
        mem1 = make_mem("db config", "database postgres config host port", ["decision"])
        mem2 = make_mem("db backup", "database postgres backup script schedule", ["decision"])
        mem3 = make_mem("api design", "REST API endpoint versioning strategy", ["pattern"])
        candidates = [(mem1, 0.9), (mem2, 0.88), (mem3, 0.7)]
        reranker = DiversityReranker(min_types=1, mmr_lambda=0.5)
        result = reranker.rerank(candidates, top_k=3)
        types = [m.types[0] for m, _ in result]
        assert "pattern" in types
