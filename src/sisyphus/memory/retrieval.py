"""ContextRetriever — three-layer memory retrieval with decay scoring.

Layers:
    L1: MOC type classification — keyword-match memory types by query relevance
    L2: Refined recall — search reflections/summaries within relevant types
    L3: RAW recall — supplement with raw memories if refined results are thin

Output is scored by exponential decay (half-life: 30 days) and capped at top_k.

Optional reranker: Qwen3-Reranker-0.6B (CausalLM + yes/no logit scoring).
Path A/B routing: short/fuzzy queries use BM25+Embedding;
                 precise queries add Reranker re-ranking.
"""

import json
import logging
import os
import sqlite3
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


class TFIDFEmbedder:
    """Pure Python TF-IDF text embedder — zero dependencies.

    Tokenizes with CJK bigrams + EN words, builds vocabulary from
    a corpus of memories, and computes cosine similarity for ranking.
    """

    def __init__(self, memories: List[Memory]):
        self.vocab = []
        self.vocab_idx = {}
        self.vectors = []  # list of {idx: tfidf}

        if not memories:
            return

        # Tokenize and count
        docs = []
        df = {}
        import math

        for m in memories:
            text = f"{m.title} {m.content} {' '.join(m.tags)}"
            tokens = _tokenize(text)
            docs.append(tokens)
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1

        N = len(memories)
        self.vocab = sorted(df.keys())
        self.vocab_idx = {t: i for i, t in enumerate(self.vocab)}

        for tokens in docs:
            vec = {}
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            max_tf = max(tf.values()) if tf else 1
            for t, count in tf.items():
                idf = math.log((N - df[t] + 0.5) / (df[t] + 0.5) + 1.0)
                vec[self.vocab_idx[t]] = (count / max_tf) * idf
            self.vectors.append(vec)

    def query_vector(self, query: str) -> dict:
        tokens = _tokenize(query)
        if not tokens:
            return {}
        vec = {}
        max_tf = max(tokens.count(t) for t in set(tokens))
        import math
        for t in set(tokens):
            if t in self.vocab_idx:
                tf = tokens.count(t) / max_tf
                n = sum(1 for v in self.vectors if self.vocab_idx[t] in v)
                idf = math.log((len(self.vectors) - n + 0.5) / (n + 0.5) + 1.0) if n > 0 else 0.0
                if tf * idf > 0:
                    vec[self.vocab_idx[t]] = tf * idf
        return vec

    @staticmethod
    def _cosine(a: dict, b: dict) -> float:
        import math
        if not a or not b:
            return 0.0
        dot = sum(a[k] * b.get(k, 0) for k in a)
        norm_a = math.sqrt(sum(v ** 2 for v in a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def similarity(self, query: str, doc_idx: int) -> float:
        q_vec = self.query_vector(query)
        return self._cosine(q_vec, self.vectors[doc_idx]) if 0 <= doc_idx < len(self.vectors) else 0.0


_Q3_EMBED_PATH = os.path.expanduser(
    "~/.cache/sisyphus/models/models--Qwen--Qwen3-Embedding-0.6B"
)
_Q3_RERANK_PATH = os.path.expanduser(
    "~/.cache/sisyphus/models/models--Qwen--Qwen3-Reranker-0.6B"
)


class Qwen3Embedder:
    """Qwen3-Embedding-0.6B via sentence-transformers.

    Provides dense-vector cosine similarity ranking.
    Falls back gracefully if model unavailable.
    """

    def __init__(self, model_path: str = _Q3_EMBED_PATH, device: str = "cpu"):
        self._model_path = model_path
        self._device = device
        self._model = None

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        if not os.path.isdir(self._model_path):
            logger.warning("Qwen3-Embedding model not found at %s", self._model_path)
            return False
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self._model_path, trust_remote_code=True, device=self._device
            )
            logger.info("Qwen3-Embedding loaded (%s)", self._device)
            return True
        except Exception as exc:
            logger.warning("Failed to load Qwen3-Embedding: %s", exc)
            return False

    def encode(self, texts):
        if not self._ensure_loaded():
            return None
        return self._model.encode(texts, show_progress_bar=False, batch_size=8)

    def encode_query(self, query: str):
        if not self._ensure_loaded():
            return None
        return self._model.encode(query, show_progress_bar=False)

    def close(self):
        self._model = None


class Qwen3Reranker:
    """Qwen3-Reranker-0.6B via CausalLM + yes/no logit scoring.

    Uses auto-regressive LM last-token logits for "yes"/"no" tokens to score
    query-document relevance.  Falls back gracefully if model unavailable.
    """

    TRUE_TOKEN_ID = 9693   # "yes"
    FALSE_TOKEN_ID = 2152  # "no"

    def __init__(self, model_path: str = _Q3_RERANK_PATH):
        self._model_path = model_path
        self._model = None
        self._tokenizer = None
        self._device = "cpu"

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        if not os.path.isdir(self._model_path):
            logger.warning("Qwen3-Reranker model not found at %s", self._model_path)
            return False
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_path, padding_side="left"
            )
            self._tokenizer.pad_token = "<|endoftext|>"
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_path, dtype=torch.float16
            )
            self._model.eval()
            self._model.to(self._device)
            logger.info("Qwen3-Reranker loaded successfully")
            return True
        except Exception as exc:
            logger.warning("Failed to load Qwen3-Reranker: %s", exc)
            return False

    @staticmethod
    def _format_pair(query: str, doc: str, instruction: Optional[str] = None) -> str:
        if instruction is None:
            instruction = (
                "Given a web search query, retrieve relevant passages "
                "that answer the query"
            )
        return (
            "<|im_start|>system\nJudge whether the Document meets the requirements "
            "based on the Query and the Instruct provided. Note that the answer can "
            'only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
            f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: "
            f"{doc}<|im_end|>\n<|im_start|>assistant\n"
        )

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        instruction: Optional[str] = None,
    ) -> List[Tuple[int, float]]:
        """Score documents by relevance to query.

        Returns list of (doc_index, score) sorted descending.
        Score is probability of "yes" in [0, 1].
        """
        if not self._ensure_loaded():
            return [(i, 0.0) for i in range(len(documents))]

        import torch
        from torch import no_grad

        texts = [self._format_pair(query, d, instruction) for d in documents]
        enc = self._tokenizer(
            texts, padding=True, truncation=True,
            max_length=512, return_tensors="pt",
        )
        enc = {k: v.to(self._device) for k, v in enc.items()}
        with no_grad():
            logits = self._model(**enc).logits
        last_logits = logits[:, -1, :]
        true_scores = last_logits[:, self.TRUE_TOKEN_ID]
        false_scores = last_logits[:, self.FALSE_TOKEN_ID]
        stacked = torch.stack([false_scores, true_scores], dim=1)
        probs = torch.nn.functional.log_softmax(stacked, dim=1)
        scores = probs[:, 1].exp().tolist()

        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        if top_k is not None:
            indexed = indexed[:top_k]
        return indexed

    def close(self):
        self._model = None
        self._tokenizer = None


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


class EmbeddingCache:
    """SQLite cache for embedding vectors to avoid redundant model inference."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path

    def _db(self):
        if self._db_path is None:
            return None
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA wal_autocheckpoint=1000")
        conn.execute("""CREATE TABLE IF NOT EXISTS embeddings (
            key TEXT PRIMARY KEY,
            vector BLOB,
            created_at TEXT
        )""")
        return conn

    def get(self, key: str) -> Optional[object]:
        conn = self._db()
        if conn is None:
            return None
        row = conn.execute("SELECT vector FROM embeddings WHERE key=?", (key,)).fetchone()
        conn.close()
        if row is None:
            return None
        import pickle
        return pickle.loads(row[0])

    def put(self, key: str, vector: object):
        conn = self._db()
        if conn is None:
            return
        import pickle
        conn.execute(
            "INSERT OR REPLACE INTO embeddings (key, vector, created_at) VALUES (?, ?, ?)",
            (key, sqlite3.Binary(pickle.dumps(vector)),
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()


class ContextRetriever:
    """Three-layer memory retriever with decay scoring and Path A/B routing.

    Usage::

        retriever = ContextRetriever(store, refined, subagent)
        results = retriever.retrieve("Python typing conventions", top_k=5)
        for mem, score in results:
            print(mem.title, score)
    """

    def __init__(self, store: MemoryStore, refined: RefinedStore, subagent,
                 reranker: Optional[Qwen3Reranker] = None,
                 embedder: Optional[Qwen3Embedder] = None,
                 cache_path: Optional[str] = None):
        self.store = store
        self.refined = refined
        self.subagent = subagent
        self.reranker = reranker
        self.embedder = embedder
        self._cache = EmbeddingCache(cache_path) if cache_path else None

    @staticmethod
    def _choose_path(query: str) -> str:
        """Classify query as Path A (short/fuzzy) or Path B (precise).

        Path A: BM25 + Embedding (faster, good for vague queries)
        Path B: BM25 + Embedding + Reranker (slower, better for specific queries)
        """
        if not query.strip():
            return "A"
        words = query.split()
        if len(words) < 3:
            return "A"
        fuzzy = {"关于", "什么", "怎么", "如何", "为什么", "介绍",
                 "说明", "哪些", "哪个", "有没有", "是不是", "能否"}
        if any(w in fuzzy for w in words):
            return "A"
        return "B"

    def retrieve(self, query: str = "", top_k: int = 8) -> List[Tuple[Memory, float]]:
        """Three-layer retrieve with Path A/B routing.

        Architecture:
            L1: Type classification — MOC keyword match or full fallback
            Stage 1: BM25 coarse filter — top_k × 3 broad recall
            Stage 2: Embedding fine re-rank — cosine + 5% decay modifier
            Fallback: TF-IDF when embedder unavailable
            Path B: Optional Qwen3-Reranker for precise queries

        Returns list of (Memory, score) tuples, highest score first.
        """
        now = datetime.now(timezone.utc)
        path = self._choose_path(query)
        logger.info("path=%s query=%r", path, query)

        if query.strip():
            types = self._classify_types(query)
        else:
            types = _collect_types(self.store, self.refined)

        all_raw = self.store.list()
        all_refined = self.refined.list_refined()
        if types:
            refined_mems = [m for m in all_refined if m.type in types]
            raw_mems = [m for m in all_raw if m.type in types]
        else:
            refined_mems = all_refined
            raw_mems = all_raw
        candidates = list({m.id: m for m in refined_mems + raw_mems}.values())

        if len(candidates) < top_k and query.strip():
            all_mems = list({m.id: m for m in all_raw + all_refined}.values())
            bm25_all = BM25Ranker(all_mems)
            supplement = [m for m, _ in bm25_all.search(query, top_k=top_k * 2)]
            existing_ids = {m.id for m in candidates}
            for m in supplement:
                if m.id not in existing_ids:
                    candidates.append(m)
                    existing_ids.add(m.id)

        if not candidates:
            return []

        PRE_FILTER_N = top_k * 3
        bm25 = BM25Ranker(candidates)
        bm25_pre = bm25.search(query, top_k=PRE_FILTER_N)
        pre_candidates = [m for m, _ in bm25_pre] if bm25_pre else candidates

        scored = []
        if self.embedder is not None and query.strip():
            try:
                docs = [
                    f"{m.title} {m.content} {' '.join(m.tags)}"
                    for m in pre_candidates
                ]
                cache_key = f"q:{query}" if self._cache else None
                q_vec = self._cache.get(cache_key) if cache_key else None
                if q_vec is None:
                    q_vec = self.embedder.encode_query(query)
                    if cache_key and q_vec is not None:
                        self._cache.put(cache_key, q_vec)
                d_vecs = self.embedder.encode(docs)
                if q_vec is not None and d_vecs is not None:
                    import numpy as np
                    q_np = np.array(q_vec)
                    q_norm = np.linalg.norm(q_np) + 1e-10
                    for i, m in enumerate(pre_candidates):
                        d_np = np.array(d_vecs[i])
                        cos_sim = float(np.dot(q_np, d_np) / (
                            q_norm * (np.linalg.norm(d_np) + 1e-10)
                        ))
                        score = cos_sim * (1.0 + 0.05 * decay_score(m, now))
                        scored.append((m, score))
                else:
                    raise RuntimeError("Embedder returned None")
            except Exception as exc:
                logger.warning("Qwen3Embedder failed, TF-IDF fallback: %s", exc)
                scored = []

        if not scored:
            candidate_idx = {id(m): i for i, m in enumerate(candidates)}
            tfidf = TFIDFEmbedder(candidates)
            for m in pre_candidates:
                idx = candidate_idx.get(id(m), -1)
                if idx < 0:
                    continue
                tf_s = tfidf.similarity(query, idx)
                score = tf_s * (1.0 + 0.05 * decay_score(m, now))
                if tf_s > 0 or not query.strip():
                    scored.append((m, score))
            if not scored:
                for m in candidates:
                    scored.append((m, decay_score(m, now)))

        scored.sort(key=lambda x: -x[1])

        if self.reranker is not None and query.strip() and path == "B":
            logger.info("reranker=on path=B")
            try:
                top_n = scored[:top_k * 2]
                docs = [m.content or m.title or "" for m, _ in top_n]
                reranked = self.reranker.rerank(query, docs, top_k=top_k)
                top = [top_n[i] for i, _ in reranked]
            except Exception as exc:
                logger.warning("Reranker failed, falling back to BM25: %s", exc)
                top = scored[:top_k]
        else:
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
