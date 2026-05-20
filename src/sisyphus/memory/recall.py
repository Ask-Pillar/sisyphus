"""LLM-powered memory recall.

Uses a side-query to an LLM to determine which memories are relevant to the
current context. Inspired by Claude Code's approach: instead of keyword matching
or vector search, we ask the LLM to reason about relevance.
"""

import json
import logging
from typing import List, Optional

from sisyphus.memory.store import Memory, MemoryStore

logger = logging.getLogger(__name__)

RECALL_PROMPT = """You are a memory retrieval system. Given a user query and a list of available memories, select the memories that are relevant to the query.

Return ONLY a JSON object with this exact structure:
{{"memory_ids": ["mem_id1", "mem_id2", ...]}}

If no memories are relevant, return {{"memory_ids": []}}

Available memories:
{index}

User query: {query}
"""


class Recall:
    """LLM-powered memory recall.

    Queries an LLM to find relevant memories instead of keyword matching.
    Handles semantic understanding, negation, and context-aware selection.
    """

    def __init__(self, store: MemoryStore, llm_client):
        self.store = store
        self.llm = llm_client

    def search(self, query: str, top_k: int = 5) -> List[Memory]:
        """Find memories relevant to the query using LLM reasoning."""
        all_memories = self.store.list()
        if not all_memories:
            return []
        if not query.strip():
            return self._recent(top_k)

        index_text = self._build_index_text(all_memories)
        prompt = RECALL_PROMPT.format(index=index_text, query=query)

        try:
            response = self.llm.chat([
                {"role": "system", "content": "You are a precise memory retrieval system. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ])
            memory_ids = self._parse_response(response)
            results = [m for m in all_memories if m.id in memory_ids]
            return results[:top_k]
        except Exception as e:
            logger.warning(f"LLM recall failed: {e}")
            return []

    def is_relevant(self, query: str, memory: Memory) -> float:
        """Score relevance of a single memory to a query (0.0 to 1.0)."""
        prompt = f"""Rate the relevance of this memory to the query from 0.0 to 1.0.
Return ONLY a JSON object: {{"relevance": 0.0}}

Memory ({memory.type}): {memory.title}
Content: {memory.content[:200]}

Query: {query}
Relevance:"""
        try:
            response = self.llm.chat([
                {"role": "user", "content": prompt},
            ])
            data = json.loads(response.strip())
            return float(data.get("relevance", 0.0))
        except Exception:
            return 0.0

    def _build_index_text(self, memories: List[Memory]) -> str:
        lines = []
        for m in memories:
            created = m.created_at[:10] if m.created_at else ""
            tags = f" [{', '.join(m.tags)}]" if m.tags else ""
            lines.append(f"- {m.id} | type={m.type} | {m.title}{tags} | {created}")
        return "\n".join(lines)

    def _parse_response(self, response: str) -> List[str]:
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[-1]
            response = response.rsplit("\n", 1)[0] if "```" in response else response
        data = json.loads(response)
        return data.get("memory_ids", [])

    def _recent(self, top_k: int) -> List[Memory]:
        memories = self.store.list()
        memories.sort(key=lambda m: m.created_at, reverse=True)
        return memories[:top_k]
