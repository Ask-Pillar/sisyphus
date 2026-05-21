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


def _keyword_score(memory: Memory, query: str) -> float:
    """Keyword overlap score — character-level for CJK, word-level for EN."""
    if not query.strip():
        return 1.0
    text = f"{memory.title} {memory.content} {' '.join(memory.tags)}".lower()
    q = query.lower()
    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in q)
    if has_cjk:
        bigrams = {q[i:i+2] for i in range(len(q)-1)}
        bigrams.discard(' ')
        hits = sum(1 for bg in bigrams if bg in text)
        return hits / max(len(bigrams), 1)
    else:
        q_words = set(q.split())
        hits = sum(1 for w in q_words if w in text)
        return hits / max(len(q_words), 1)


def _tokenize(text: str) -> List[str]:
    """Tokenize: CJK → overlapping bigrams, EN → word split."""
    tokens = []
    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in text)
    if has_cjk:
        tokens = [text[i:i+2] for i in range(len(text)-1) if text[i:i+2].strip()]
    en_words = [w for w in text.lower().split() if len(w) > 1]
    return tokens + en_words


class BM25Ranker:
    """Pure Python BM25 text ranker — no external dependencies."""

    def __init__(self, memories: List[Memory], k1: float = 1.2, b: float = 0.75):
        self.memories = memories
        self.k1 = k1
        self.b = b
        self.docs = []
        self.avgdl = 0.0
        self.df = {}
        self.N = 0
        if memories:
            self._index()

    def _index(self):
        self.N = len(self.memories)
        total_len = 0
        for m in self.memories:
            text = f"{m.title} {m.content} {' '.join(m.tags)}"
            tokens = _tokenize(text)
            self.docs.append(tokens)
            total_len += len(tokens)
            seen = set(tokens)
            for t in seen:
                self.df[t] = self.df.get(t, 0) + 1
        self.avgdl = total_len / max(self.N, 1)

    def _idf(self, token: str) -> float:
        n = self.df.get(token, 0)
        if n == 0:
            return 0.0
        import math
        return math.log((self.N - n + 0.5) / (n + 0.5) + 1.0)

    def _score(self, query: str, doc_tokens: List[str], doc_len: int) -> float:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return 0.0
        score = 0.0
        for t in q_tokens:
            idf = self._idf(t)
            if idf == 0:
                continue
            tf = doc_tokens.count(t)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1))
            score += idf * numerator / denominator
        return score

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Memory, float]]:
        scored = []
        for i, (mem, tokens) in enumerate(zip(self.memories, self.docs)):
            s = self._score(query, tokens, len(tokens))
            if s > 0:
                scored.append((mem, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


def _filter_by_keyword(memories: List[Memory], query: str, min_score: float = 0.1) -> List[Memory]:
    """Keep memories with keyword overlap above threshold."""
    if not query.strip():
        return memories
    return [m for m in memories if _keyword_score(m, query) >= min_score]


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
            use_fallback = True
            if self.subagent:
                ref_result = self.subagent.recall_search(refined_mems, query)
                if ref_result.get("status") in ("ok",):
                    ref_ids = set(ref_result.get("memory_ids", []))
                    use_fallback = False
            if use_fallback:
                ref_ids = {m.id for m in _filter_by_keyword(refined_mems, query)}
            for m in refined_mems:
                if m.id in ref_ids:
                    candidates.append(m)

        if len(candidates) < top_k and query.strip():
            raw_mems = [m for m in self.store.list() if m.type in types]
            if raw_mems:
                use_fallback = True
                if self.subagent:
                    raw_result = self.subagent.recall_search(raw_mems, query)
                    if raw_result.get("status") in ("ok",):
                        raw_ids = set(raw_result.get("memory_ids", []))
                        use_fallback = False
                if use_fallback:
                    raw_ids = {m.id for m in _filter_by_keyword(raw_mems, query)}
                for m in raw_mems:
                    if m.id in raw_ids:
                        candidates.append(m)

        if not candidates:
            return []

        # BM25 re-rank for better relevance
        bm25 = BM25Ranker(candidates)
        bm25_scored = bm25.search(query, top_k=len(candidates))
        if bm25_scored:
            scored = [(m, decay_score(m, now) * (1.0 + bm_s * 0.5)) for m, bm_s in bm25_scored]
        else:
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
            use_fallback = True
            if self.subagent:
                result = self.subagent.recall_search(refined_mems, query)
                if result.get("status") in ("ok",):
                    ids = set(result.get("memory_ids", []))
                    use_fallback = False
            if use_fallback:
                ids = {m.id for m in _filter_by_keyword(refined_mems, query)}
            candidates = [m for m in refined_mems if m.id in ids]
        else:
            candidates = refined_mems

        bm25 = BM25Ranker(candidates)
        bm25_scored = bm25.search(query, top_k=len(candidates))
        if bm25_scored:
            scored = [(m, decay_score(m, now) * (1.0 + bm_s * 0.5)) for m, bm_s in bm25_scored]
        else:
            scored = [(m, decay_score(m, now)) for m in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _classify_types(self, query: str) -> List[str]:
        matched = _moc_match_types(query, self.store.base_path)
        if matched:
            return matched
        all_types = _collect_types(self.store, self.refined)
        return all_types
