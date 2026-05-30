"""DiversityReranker — type quota + MMR deduplication.

Sits between the Reranker and final output. Ensures:
  - Type quota: at least 2 different types in top-K
  - MMR: penalize results too similar to already-selected ones
"""
from typing import List, Tuple, Set
from sisyphus.memory.store import Memory


class DiversityReranker:
    """Re-rank results for type diversity and novelty."""

    def __init__(self, min_types: int = 2, mmr_lambda: float = 0.7):
        self.min_types = min_types
        self.mmr_lambda = mmr_lambda  # 0=full diversity, 1=full relevance

    def rerank(self, candidates: List[Tuple[Memory, float]], top_k: int = 10) -> List[Tuple[Memory, float]]:
        """Apply diversity re-ranking with MMR."""
        if len(candidates) <= 2:
            return candidates[:top_k]

        ranked = list(candidates)
        selected: List[Tuple[Memory, float]] = []
        remaining = list(ranked)

        while remaining and len(selected) < top_k:
            # Score each remaining candidate
            best_idx, best_score = self._pick_best(remaining, selected)
            if best_idx is None:
                break
            selected.append(remaining.pop(best_idx))

        # Fallback: if not enough type diversity, inject from remaining
        selected = self._ensure_type_diversity(selected, ranked, top_k)
        return selected[:top_k]

    def _pick_best(self, remaining: list, selected: list) -> Tuple[int, float]:
        """MMR scoring: relevance - lambda * max_similarity_to_selected."""
        best_idx, best_score = None, -1.0
        for i, (mem, rel) in enumerate(remaining):
            mmr = self._mmr_score(mem, rel, selected)
            if mmr > best_score:
                best_score = mmr
                best_idx = i
        return best_idx, best_score

    def _mmr_score(self, mem: Memory, relevance: float, selected: list) -> float:
        if not selected:
            return relevance
        max_sim = max(self._similarity(mem, s[0]) for s in selected)
        return self.mmr_lambda * relevance - (1 - self.mmr_lambda) * max_sim

    @staticmethod
    def _similarity(a: Memory, b: Memory) -> float:
        """Keyword overlap similarity between two memories."""
        a_words = set((a.title + " " + a.content).lower().split())
        b_words = set((b.title + " " + b.content).lower().split())
        if not a_words or not b_words:
            return 0.0
        return len(a_words & b_words) / len(a_words | b_words)

    def _ensure_type_diversity(self, selected: list, all_candidates: list, top_k: int) -> list:
        """If selected has < min_types different types, inject from candidates."""
        seen_types = {m.types[0] if m.types else "" for m, _ in selected}
        if len(seen_types) >= self.min_types:
            return selected

        for mem, score in all_candidates:
            mem_type = mem.types[0] if mem.types else ""
            if mem_type not in seen_types and (mem, score) not in selected:
                if len(selected) >= top_k:
                    selected[-1] = (mem, score)
                else:
                    selected.append((mem, score))
                seen_types.add(mem_type)
                if len(seen_types) >= self.min_types:
                    break
        return selected
