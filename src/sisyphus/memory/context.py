"""MemoryContext — automatic context builder for per-turn memory injection.

Called before each conversation turn to retrieve relevant memories
and format them as a Markdown block for system prompt injection.

Replaces the one-shot FrozenSnapshot model with dynamic, layered retrieval.
"""

import logging
from typing import List, Tuple

from sisyphus.memory.store import Memory, MemoryStore

logger = logging.getLogger(__name__)

CONTEXT_HEADER = "<sisyphus_context>\n"
CONTEXT_FOOTER = "</sisyphus_context>"
ENTRY_TEMPLATE = "- [{type}] {title} | importance={score:.0f}\n  {content}\n"


def _format_entry(memory: Memory, score: float) -> str:
    tags = ", ".join(memory.tags) if memory.tags else ""
    title = memory.title
    content = memory.content[:200] if memory.content else ""
    return ENTRY_TEMPLATE.format(
        type=memory.type,
        title=title,
        score=score,
        content=content,
    )


def _format_context(memories: List[Tuple[Memory, float]], max_chars: int) -> str:
    lines = [CONTEXT_HEADER]
    char_count = len(CONTEXT_HEADER)

    for mem, score in memories:
        entry = _format_entry(mem, score)
        if char_count + len(entry) > max_chars - len(CONTEXT_FOOTER):
            break
        lines.append(entry)
        char_count += len(entry)

    lines.append(CONTEXT_FOOTER)
    return "".join(lines)


class MemoryContext:
    """Per-turn memory context builder.

    Usage (called before each agent turn)::

        ctx = MemoryContext(retriever, store, refresh_interval=5)
        context_block = ctx.build("current query", turn_count=12)
        # inject context_block into system prompt
    """

    def __init__(self, retriever, store: MemoryStore, refresh_interval: int = 5):
        self.retriever = retriever
        self.store = store
        self.refresh_interval = refresh_interval
        self._last_full_turn = 0
        self._cached = ""

    def build(
        self,
        query: str = "",
        turn_count: int = 0,
        max_chars: int = 4000,
    ) -> str:
        """Build context block for this turn.

        Full refresh (3-layer) every ``refresh_interval`` turns.
        In-between turns do a lightweight refined-only retrieval.
        """
        if turn_count == 0 or turn_count - self._last_full_turn >= self.refresh_interval:
            memories = self.retriever.retrieve(query=query, top_k=10)
            self._last_full_turn = turn_count
        else:
            memories = self.retriever.retrieve_refined_only(query=query, top_k=5)

        self._cached = _format_context(memories, max_chars)
        return self._cached
