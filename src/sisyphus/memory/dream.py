"""Dream engine — LLM-driven reflection and insight generation.

Analyzes RAW memories to identify patterns, extract principles,
and generate structured insights (reflections) stored in the refined layer.
"""

import json
import logging
from typing import List, Optional

from sisyphus.memory.store import MemoryStore, Memory
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.log import LogStore, _now

logger = logging.getLogger(__name__)

DREAM_PROMPT = """You are a memory reflection system. Analyze the following memories and identify patterns, principles, and insights.

For each insight, return a JSON object with:
- "title": concise insight title (under 80 chars)
- "content": detailed explanation of the pattern/principle
- "importance": 1-10 score for how important this insight is
- "evidence": list of memory IDs that support this insight (can be empty if none match)

Return ONLY valid JSON with this structure:
{{"reflections": [{{"title": "...", "content": "...", "importance": 8, "evidence": ["mem_id1", "mem_id2"]}}]}}

Memories to analyze:
{memories}
"""


def _format_memories(memories: List[Memory]) -> str:
    lines = []
    for m in memories:
        tags = f" [{', '.join(m.tags)}]" if m.tags else ""
        lines.append(f"[{m.id}] ({m.type}) {m.title}{tags}")
        if m.content:
            lines.append(f"    {m.content[:200]}")
    return "\n".join(lines)


class DreamEngine:
    """Reflection engine: reads RAW memories, generates insights via LLM."""

    def __init__(self, store: MemoryStore, refined_store: RefinedStore, llm_client):
        self.store = store
        self.refined = refined_store
        self.llm = llm_client
        self.logger = LogStore(store.base_path.parent)
        self.last_log = None

    def dream(self) -> List[Memory]:
        """Run one reflection cycle.

        Returns list of newly created reflection Memory objects.
        """
        memories = self._gather_memories()
        if not memories:
            return []

        prompt = DREAM_PROMPT.format(memories=_format_memories(memories))
        raw_response = self.llm.ask(prompt)
        reflections = self._parse_response(raw_response)

        created = []
        for ref_data in reflections:
            ref = self.refined.create_reflection(
                title=ref_data.get("title", "Untitled"),
                content=ref_data.get("content", ""),
                evidence=ref_data.get("evidence", []),
                importance=ref_data.get("importance", 5),
                input_count=len(memories),
                llm_calls=1,
            )
            self._update_refined_by(ref.id, ref.evidence)
            created.append(ref)

        log_body = f"Generated {len(created)} reflections from {len(memories)} memories."
        self.last_log = self.logger.create_log("dream", body=log_body)
        return created

    def _gather_memories(self) -> List[Memory]:
        return self.store.list()

    def _parse_response(self, raw: str) -> List[dict]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Dream LLM returned invalid JSON: %s", raw[:200])
            return []
        return data.get("reflections", [])

    def _update_refined_by(self, ref_id: str, evidence_ids: List[str]):
        for mem_id in evidence_ids:
            mem = self.store.get(mem_id)
            if mem is None:
                continue
            if ref_id not in mem.refined_by:
                mem.refined_by = mem.refined_by + [ref_id]
                self.store.update(mem.id, status=mem.status)
                self.store._write_topic(mem)
