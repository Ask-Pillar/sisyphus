"""Frozen memory snapshot for system prompt injection.

At session start, relevant memories are recalled and frozen into a
markdown block that gets injected into the system prompt. The snapshot
doesn't change mid-session, preserving the LLM's prefix cache.
"""

from typing import List, Optional

from sisyphus.memory.store import Memory

SNAPSHOT_HEADER = """<sisyphus_memory_snapshot>
These memories were captured at session start and are frozen.
They may be stale in a long session. Use the memory tool to refresh.
"""

SNAPSHOT_FOOTER = "</sisyphus_memory_snapshot>"

ENTRY_TEMPLATE = "- [{type}] {title} | {tags} | {date}\n  {content}\n"
EMPTY_SNAPSHOT = "<sisyphus_memory_snapshot>\nNo memories yet.\n</sisyphus_memory_snapshot>"


class FrozenSnapshot:
    """Builds and caches a frozen memory snapshot for system prompt injection.

    The snapshot is built once at session start and never changes.
    This preserves the LLM's prefix cache across turns within a session.
    """

    def __init__(
        self,
        recall,
        max_memories: int = 5,
        max_chars: int = 2000,
    ):
        self.recall = recall
        self.max_memories = max_memories
        self.max_chars = max_chars
        self._cached: Optional[str] = None

    def build(self, query: str = "") -> str:
        """Build (or return cached) frozen snapshot.

        Always returns the same result for a given session.
        """
        if self._cached is not None:
            return self._cached

        memories = self.recall.search(query=query, top_k=self.max_memories)
        self._cached = self._format(memories)
        return self._cached

    def reset(self):
        """Clear cache (for testing)."""
        self._cached = None

    def _format(self, memories: List[Memory]) -> str:
        if not memories:
            return EMPTY_SNAPSHOT

        lines = [SNAPSHOT_HEADER]
        char_count = len(SNAPSHOT_HEADER)

        for mem in memories:
            date = mem.created_at[:10] if mem.created_at else ""
            tags = ", ".join(mem.tags) if mem.tags else ""
            entry = ENTRY_TEMPLATE.format(
                type=mem.type,
                title=mem.title,
                tags=tags,
                date=date,
                content=mem.content[:200],
            )
            if char_count + len(entry) > self.max_chars:
                break
            lines.append(entry)
            char_count += len(entry)

        lines.append(SNAPSHOT_FOOTER)
        result = "".join(lines)
        if len(result) > self.max_chars:
            result = result[: self.max_chars]
        return result
