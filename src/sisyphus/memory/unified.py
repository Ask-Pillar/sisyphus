"""UnifiedRetriever — cross-pool retrieval with weighted scoring.

Uses PoolRegistry for multi-pool access and ContextRetriever per pool.
Merges results with pool-specific weights for rank fusion.
"""

from pathlib import Path
from typing import Optional, List, Tuple

from sisyphus.memory.store import Memory
from sisyphus.memory.pools import PoolRegistry


class UnifiedRetriever:
    """Cross-pool memory retrieval with weighted fusion.

    Usage:
        retriever = UnifiedRetriever()
        results = retriever.retrieve("database config", top_k=10)
    """

    def __init__(self, base_path: Optional[Path] = None, project_hash: str = ""):
        self.registry = PoolRegistry(base_path)
        self.registry.init_structure()
        self._project_hash = project_hash

    def retrieve(self, query: str, scope: Optional[List[str]] = None,
                 top_k: int = 10) -> List[Tuple[Memory, float, str]]:
        """Retrieve memories across pools with weighted scoring.

        Returns list of (memory, score, pool_name) sorted by weighted score.
        """
        pools = self.registry.active_pools(scope)
        if not pools:
            return []

        all_results = []
        for pool in pools:
            weight = self.registry.config.get("pools", {}).get(pool, {}).get("weight", 0.3)
            sub = self._project_hash if pool == "project" else ""
            store = self.registry.get_store(pool, sub)
            candidates = self._recall(store, query, top_k)
            for mem, score in candidates:
                weighted = score * weight
                all_results.append((mem, weighted, pool))

        all_results.sort(key=lambda x: x[1], reverse=True)
        return all_results[:top_k]

    def _recall(self, store, query: str, top_k: int) -> List[Tuple[Memory, float]]:
        """Pool-level recall using FTS5 + keyword scoring."""
        results = []
        for mem in store.list():
            score = self._score(mem, query)
            if score > 0:
                results.append((mem, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @staticmethod
    def _score(mem: Memory, query: str) -> float:
        """Score a single memory against a query (keyword + importance)."""
        q = query.lower()
        if not q:
            return 0
        title = (mem.title or "").lower()
        content = (mem.content or "").lower()
        tags = " ".join(mem.tags or []).lower()

        title_hits = title.count(q) * 10 if q in title else 0
        content_hits = content.count(q) * 2
        tag_hits = 3 if q in tags else 0

        base = title_hits + content_hits + tag_hits
        if base == 0:
            return 0
        return base * (mem.importance or 5) / 5.0
