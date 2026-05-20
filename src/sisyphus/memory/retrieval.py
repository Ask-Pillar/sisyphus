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

from sisyphus.memory.moc import MocGenerator
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


def _moc_types(base_path: Path) -> dict:
    """Read INDEX.md MOC and return {type_name: [title, ...]}.

    Supports two formats:
      - MocGenerator: '## type_name' with '- [[id|title]]' wikilinks
      - MemoryStore: '- [id] type | title' flat entries
    Returns empty dict if INDEX.md doesn't exist or has no content.
    """
    index_path = base_path / "INDEX.md"
    if not index_path.exists():
        return {}

    text = index_path.read_text()
    result: dict = {}
    current_type: Optional[str] = None

    for line in text.splitlines():
        line = line.strip()
        # MocGenerator format: ## type_name
        if line.startswith("## "):
            current_type = line[3:].strip()
            if current_type not in result:
                result[current_type] = []
        # MocGenerator wikilink: - [[id|title]]
        elif line.startswith("- [[") and "|" in line and current_type:
            title = line.split("|", 1)[1].rstrip("]]")
            result[current_type].append(title.strip())
        # Flat format: - [id] type | title (fallback when no headings)
        elif line.startswith("- [") and "|" in line and not result:
            parts = line.split("|", 1)
            if len(parts) == 2:
                title = parts[1].strip()
                type_part = parts[0].split("]", 1)[-1].strip()
                result.setdefault(type_part, []).append(title)

    return result


def _moc_match_types(query: str, base_path: Path) -> List[str]:
    """Match query against MOC type sections by keyword overlap.

    Scores each type by how many distinct query words appear in its
    type name or entry titles. Returns types sorted by relevance.
    """
    index = _moc_types(base_path)
    if not index:
        return []

    query_words = {w.lower() for w in query.split() if len(w) > 1}
    if not query_words:
        return list(index.keys())

    scored = []
    for type_name, titles in index.items():
        candidates = [type_name.lower()] + [t.lower() for t in titles]
        hits = sum(1 for w in query_words if any(w in cand for cand in candidates))
        if hits > 0:
            scored.append((type_name, hits))

    scored.sort(key=lambda x: (-x[1], x[0]))
    return [t for t, _ in scored]


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
            if self.subagent:
                ref_result = self.subagent.recall_search(refined_mems, query)
                ref_ids = set(ref_result.get("memory_ids", []))
            else:
                ref_ids = {m.id for m in refined_mems}
            for m in refined_mems:
                if m.id in ref_ids:
                    candidates.append(m)

        if len(candidates) < top_k and query.strip():
            raw_mems = [m for m in self.store.list() if m.type in types]
            if raw_mems:
                if self.subagent:
                    raw_result = self.subagent.recall_search(raw_mems, query)
                    raw_ids = set(raw_result.get("memory_ids", []))
                else:
                    raw_ids = {m.id for m in raw_mems}
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
        matched = _moc_match_types(query, self.store.base_path)
        if matched:
            return matched
        all_types = _collect_types(self.store, self.refined)
        return all_types
