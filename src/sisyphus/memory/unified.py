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
        diversified = self._diversify(all_results, top_k)
        gems = self._forgotten_gems(top_k)
        if gems and len(diversified) >= top_k:
            diversified[-1] = gems[0]
        opposing = self._opposing_views(diversified, query, top_k)
        if opposing:
            diversified.append(opposing[0])
        self._log_ab_test(diversified)

        from sisyphus.memory.diversity import DiversityReranker
        reranker = DiversityReranker(min_types=2, mmr_lambda=0.7)
        return reranker.rerank(diversified, top_k)

    def _diversify(self, results: list, top_k: int) -> list:
        if len(results) <= 2:
            return results[:top_k]
        top = list(results[:top_k])
        seen_pools = {r[2] for r in top}
        if len(seen_pools) < 2:
            remaining = [r for r in results[top_k:] if r[2] not in seen_pools]
            if remaining:
                top[-1] = remaining[0]
        return top

    def _opposing_views(self, top: list, query: str, top_k: int) -> list:
        """If top-3 all share same type, search for counterpoints."""
        if len(top) < 3:
            return []
        types = {m.types[0] if m.types else "" for m, _, _ in top[:3]}
        if len(types) > 1:
            return []
        excluded_type = list(types)[0]
        # Search personal pool for memories of different type
        store = self.registry.get_store("personal")
        candidates = []
        for mem in store.list():
            mem_type = mem.types[0] if mem.types else ""
            if mem_type and mem_type != excluded_type and not getattr(mem, "dismissed", False):
                score = self._score(mem, query)
                if score > 0:
                    candidates.append((mem, score, "personal"))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:1]

    def _log_ab_test(self, results: list):
        """Log retrieval results for A/B testing analysis."""
        import json
        from datetime import datetime
        log_path = self.registry.base_path / "ab_test.jsonl"
        record = {
            "ts": datetime.now().isoformat(),
            "count": len(results),
            "pools": list({r[2] for r in results}),
            "types": list({(r[0].types[0] if r[0].types else "") for r in results}),
            "top_score": results[0][1] if results else 0,
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _forgotten_gems(self, top_k: int) -> list:
        """10% chance to inject a high-importance forgotten memory."""
        import random
        if random.random() > 0.1:
            return []
        pool_stores = []
        for pool in self.registry.active_pools(["personal"]):
            pool_stores.append(self.registry.get_store(pool, ""))
        gems = []
        for store in pool_stores:
            for mem in store.list():
                if mem.importance >= 7 and mem.recall_count == 0 and not getattr(mem, "dismissed", False):
                    gems.append((mem, 0.5, "personal"))
        if gems:
            import random
            return random.sample(gems, min(1, len(gems)))
        return []

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
