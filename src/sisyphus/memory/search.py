"""Lightweight vector search for memory using character n-grams.

Zero external dependencies beyond Python stdlib. Uses character-level
n-grams (n=2,3,4) for vectorization and cosine similarity for ranking.
"""

from collections import Counter
from sisyphus.memory.store import Memory


def _ngrams(text, n=3):
    """Extract character n-grams from text."""
    return [text[i:i+n] for i in range(len(text) - n + 1)]


def _vectorize(text):
    """Build a character n-gram frequency vector (n=2,3,4)."""
    text = text.lower()
    vec = Counter()
    for n in [2, 3, 4]:
        for gram in _ngrams(text, n):
            vec[gram] += 1
    return vec


def _cosine(a, b):
    """Cosine similarity between two Counter vectors."""
    dot = sum(a[k] * b.get(k, 0) for k in a)
    na = sum(v * v for v in a.values()) ** 0.5
    nb = sum(v * v for v in b.values()) ** 0.5
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


class SemanticSearcher:
    """Zero-dependency semantic search via character n-gram vectors."""

    def __init__(self, store):
        self.store = store
        self._vectors = {}

    def search(self, query, top_k=5):
        """Search memories by semantic similarity. Uses cached vectors."""
        memories = self.store.list()
        if not memories:
            return []
        if not query.strip():
            return sorted(memories, key=lambda m: m.created_at or "", reverse=True)[:top_k]

        for m in memories:
            if m.id not in self._vectors:
                self._vectors[m.id] = _vectorize(f"{m.title} {m.content}")

        qvec = _vectorize(query)
        scored = [(_cosine(qvec, self._vectors[m.id]), m) for m in memories]
        scored.sort(key=lambda x: -x[0])
        return [m for _, m in scored[:top_k]]
