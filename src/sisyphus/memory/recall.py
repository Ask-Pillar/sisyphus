"""LLM-powered memory recall via subagent subprocess.

Uses a side-query to an LLM (run in child process) to determine which
memories are relevant to the current context. Inspired by Claude Code's
approach: instead of keyword matching or vector search, we ask the LLM
to reason about relevance.
"""

import logging
from typing import List, Optional

from sisyphus.memory.store import Memory, MemoryStore

logger = logging.getLogger(__name__)


class Recall:
    """LLM-powered memory recall via subagent.

    Dispatches LLM work to a subprocess so the main agent's context
    window stays clean.
    """

    def __init__(self, store: MemoryStore, subagent):
        self.store = store
        self.subagent = subagent

    def search(self, query: str, top_k: int = 5) -> List[Memory]:
        """Find memories relevant to the query via subagent LLM."""
        all_memories = self.store.list()
        if not all_memories:
            return []
        if not query.strip():
            return self._recent(top_k)

        result = self.subagent.recall_search(all_memories, query)
        memory_ids = result.get("memory_ids", [])
        results = [m for m in all_memories if m.id in memory_ids]
        return results[:top_k]

    def is_relevant(self, query: str, memory: Memory) -> float:
        """Score relevance of a single memory to a query (0.0 to 1.0)."""
        if not query.strip():
            return 0.0

        result = self.subagent.recall_relevant(memory, query)
        return result.get("relevance", 0.0)

    def _recent(self, top_k: int) -> List[Memory]:
        memories = self.store.list()
        memories.sort(key=lambda m: m.created_at, reverse=True)
        return memories[:top_k]
