"""MemoryContext — automatic context builder for per-turn memory injection.

Called before each conversation turn to retrieve relevant memories
and format them as a Markdown block for system prompt injection.

Replaces the one-shot FrozenSnapshot model with dynamic, layered retrieval.
"""

import logging
from typing import List, Optional, Tuple

from sisyphus.memory.store import Memory, MemoryStore
from sisyphus.memory.refined import RefinedStore

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

        Full refresh (3-layer) triggers when:
          - turn_count is 0 (first turn)
          - store has new writes since last refresh (dirty)
          - refresh_interval turns have passed since last full refresh
        In-between turns do a lightweight refined-only retrieval.
        """
        store_dirty = self.store.is_dirty
        needs_full = (
            turn_count == 0
            or store_dirty
            or turn_count - self._last_full_turn >= self.refresh_interval
        )
        if needs_full:
            memories = self.retriever.retrieve(query=query, top_k=10)
            self._last_full_turn = turn_count
            self.store.clear_dirty()
        else:
            memories = self.retriever.retrieve_refined_only(query=query, top_k=5)
            if not memories:
                memories = self.retriever.retrieve(query=query, top_k=10)

        self._cached = _format_context(memories, max_chars)
        return self._cached


class AgentMemory:
    """Auto-inject integration entry point.

    Wraps MemoryStore + ContextRetriever + MemoryContext into one
    ``before_turn(query)`` call that returns a context block ready
    for system prompt injection each turn.

    Usage::

        memory = AgentMemory(base_path=Path.home() / ".omo" / "memory")
        context = memory.before_turn("current user query")
        # → inject context into system prompt
        # → agent responds
        memory.after_turn(...)  # optionally record new memories
    """

    def __init__(
        self,
        store: MemoryStore,
        refined: Optional[RefinedStore] = None,
        subagent=None,
        refresh_interval: int = 5,
        reranker: Optional[object] = None,
    ):
        from sisyphus.memory.retrieval import ContextRetriever

        self.store = store
        self.subagent = subagent
        self.refined = refined or RefinedStore(base_path=store.base_path)
        cache_path = str(store.base_path / "cache" / "embeddings.db")
        self.retriever = ContextRetriever(self.store, self.refined, subagent,
                                          reranker=reranker, cache_path=cache_path)
        self.context = MemoryContext(self.retriever, self.store, refresh_interval)
        self._turn = 0

    def before_turn(self, query: str = "", max_chars: int = 4000) -> str:
        """Call before each agent response.

        Returns a formatted ``<sisyphus_context>`` block with relevant
        memories, automatically handling full vs incremental refresh
        and responding to new memory writes (dirty detection).
        """
        self._turn += 1
        return self.context.build(query=query, turn_count=self._turn, max_chars=max_chars)

    def record(
        self,
        title: str,
        type: str = "note",
        content: str = "",
        tags: Optional[List[str]] = None,
        importance: int = 5,
    ) -> Memory:
        """Record a new memory and auto-refresh context next turn."""
        return self.store.create(
            title=title, type=type, content=content,
            tags=tags, importance=importance,
        )
