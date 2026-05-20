"""ContextRetriever — three-layer memory retrieval with decay scoring.

Layers:
    L1: MOC type classification — LLM filters memory types by query relevance
    L2: Refined recall — search reflections/summaries within relevant types
    L3: RAW recall — supplement with raw memories if refined results are thin

Output is scored by exponential decay (half-life: 30 days) and capped at top_k.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from sisyphus.memory.store import Memory, MemoryStore
from sisyphus.memory.refined import RefinedStore

logger = logging.getLogger(__name__)

DECAY_HALF_LIFE_DAYS = 30.0


def _days_since(timestamp_iso: str, now: datetime) -> float:
    if not timestamp_iso:
        return 0.0
    try:
        dt = datetime.fromisoformat(timestamp_iso)
        delta = now - dt
        return max(0.0, delta.total_seconds() / 86400.0)
    except (ValueError, TypeError):
        return 0.0


def decay_score(memory: Memory, now: Optional[datetime] = None) -> float:
    """Compute decay-adjusted relevance score for a memory.

    Uses last_recalled_at if set, otherwise falls back to created_at.
    Half-life: 30 days. Never recalled = uses creation time.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    ref_time = memory.last_recalled_at or memory.created_at
    days = _days_since(ref_time, now)
    decay = 0.5 ** (days / DECAY_HALF_LIFE_DAYS)
    return memory.importance * decay


def _collect_types(store: MemoryStore, refined: RefinedStore) -> List[str]:
    """Collect unique memory types from both RAW and refined stores."""
    types: set = set()
    for m in store.list():
        if m.type:
            types.add(m.type)
    for m in refined.list_refined():
        if m.type:
            types.add(m.type)
    return sorted(types)


def _update_recall_count(store: MemoryStore, memory: Memory, now: datetime):
    """Increment recall count and update timestamp, then persist."""
    memory.recall_count += 1
    memory.last_recalled_at = now.isoformat()
    store.update(
        memory.id,
        recall_count=memory.recall_count,
        last_recalled_at=memory.last_recalled_at,
    )


class ContextRetriever:
    """Three-layer memory retriever with decay scoring.

    Usage::

        retriever = ContextRetriever(store, refined, subagent)
        results = retriever.retrieve("Python typing conventions", top_k=5)
        for mem, score in results:
            print(mem.title, score)
    """

    def __init__(self, store: MemoryStore, refined: RefinedStore, subagent):
        self.store = store
        self.refined = refined
        self.subagent = subagent

    def retrieve(self, query: str = "", top_k: int = 8) -> List[Tuple[Memory, float]]:
        """Three-layer retrieve, scored and sorted by decay.

        Returns list of (Memory, decay_score) tuples, highest score first.
        """
        now = datetime.now(timezone.utc)

        if query.strip():
            types = self._classify_types(query)
        else:
            types = _collect_types(self.store, self.refined)

        candidates: List[Memory] = []
        refined_mems = [m for m in self.refined.list_refined() if m.type in types]
        if refined_mems:
            ref_result = self.subagent.recall_search(refined_mems, query)
            ref_ids = set(ref_result.get("memory_ids", []))
            for m in refined_mems:
                if m.id in ref_ids:
                    candidates.append(m)

        if len(candidates) < top_k and query.strip():
            raw_mems = [m for m in self.store.list() if m.type in types]
            if raw_mems:
                raw_result = self.subagent.recall_search(raw_mems, query)
                raw_ids = set(raw_result.get("memory_ids", []))
                for m in raw_mems:
                    if m.id in raw_ids:
                        candidates.append(m)

        if not candidates:
            return []

        scored = [(m, decay_score(m, now)) for m in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        for mem, _ in top:
            try:
                _update_recall_count(self.store, mem, now)
            except Exception as exc:
                logger.warning("Failed to update recall stats for %s: %s", mem.id, exc)

        return top

    def retrieve_refined_only(self, query: str = "", top_k: int = 5) -> List[Tuple[Memory, float]]:
        """Lightweight retrieval: skip L1/L3, only search refined memories.

        Doesn't update recall stats (use full retrieve() for that).
        """
        now = datetime.now(timezone.utc)

        refined_mems = self.refined.list_refined()
        if not refined_mems:
            return []

        if query.strip():
            result = self.subagent.recall_search(refined_mems, query)
            ids = set(result.get("memory_ids", []))
            candidates = [m for m in refined_mems if m.id in ids]
        else:
            candidates = refined_mems

        scored = [(m, decay_score(m, now)) for m in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _classify_types(self, query: str) -> List[str]:
        """L1: ask subagent which types are relevant."""
        all_types = _collect_types(self.store, self.refined)
        if not all_types:
            return []

        result = self.subagent.classify_types(all_types, query)
        selected = result.get("types", [])
        return selected or all_types
