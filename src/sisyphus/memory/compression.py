"""Memory compression — anneal old memories into one summary."""

import json
from sisyphus.memory.store import Memory


COMPRESSION_PROMPT = """Compress the following memories into ONE concise summary.
Keep all unique facts, decisions, and patterns. Remove redundancy.

Output valid JSON only: {{"title": "...", "content": "..."}}

Memories to compress:
{text}"""


class Compressor:
    """Annealing-style compression. Merges all old memories into one summary."""

    def __init__(self, store, llm_client, threshold=20, keep_recent=5):
        self.store = store
        self.llm = llm_client
        self.threshold = threshold
        self.keep_recent = keep_recent

    def run(self):
        """Compress old memories into one summary. Returns count of deleted."""
        all_memories = self.store.list()
        if len(all_memories) <= self.threshold:
            return 0

        sorted_mems = sorted(all_memories, key=lambda m: m.created_at or "")
        old_mems = sorted_mems[:-self.keep_recent]
        if not old_mems:
            return 0

        summary = self._merge(old_mems)
        if summary is None:
            return 0

        self.store.create(
            title="[compressed] " + summary["title"],
            type="compressed",
            content=summary["content"],
        )
        count = len(old_mems)
        for m in old_mems:
            self.store.delete(m.id)
        return count

    def _merge(self, memories):
        lines = []
        for m in memories:
            lines.append(f"[{m.created_at[:10]}] ({m.type}) {m.title}")
            lines.append(m.content[:500])
            lines.append("---")
        text = "\n".join(lines)

        try:
            response = self.llm.chat(messages=[
                {"role": "system", "content": "You are a memory summarizer."},
                {"role": "user", "content": COMPRESSION_PROMPT.format(text=text)},
            ])
            data = json.loads(response)
            return data
        except Exception:
            return None
