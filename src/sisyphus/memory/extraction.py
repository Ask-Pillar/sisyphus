"""Background memory extraction.

After significant work, an extraction agent analyzes the session content
and saves important information that the main agent might have missed.
"""

import json
import logging
from typing import List, Optional

from sisyphus.memory.store import Memory, MemoryStore

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """You are a memory extraction system. Given a conversation turn, extract important information that should be remembered for future sessions.

Focus on:
- Decisions made ("chose X over Y because...")
- Patterns discovered ("this codebase uses X convention")
- Lessons learned ("X approach caused Y bug")
- User preferences ("prefers Z pattern")
- Configuration/setup details ("need to set X env var")

Return ONLY a JSON object with this exact structure:
{{"memories": [{{"type": "lesson", "title": "...", "content": "...", "tags": ["tag1", "tag2"]}}]}}

Memory types: lesson, decision, pattern, user_preference, skill, project_context
Keep titles concise (under 80 chars). Content should be detailed but under 500 chars.
Omit memories that are trivial, obvious, or unlikely to be needed again.

Conversation turn:
{turn}
"""


def _fingerprint(mem: Memory) -> str:
    """Create a stable fingerprint for dedup."""
    return f"{mem.types[0] if mem.types else ''}:::{mem.title}:::{mem.content[:100]}"


class Extractor:
    """Background memory extractor.

    Analyzes conversation turns and saves important information
    to the memory store. Deduplicates against existing memories.
    """

    def __init__(self, store: MemoryStore, llm_client):
        self.store = store
        self.llm = llm_client

    def extract(self, turn: str) -> List[Memory]:
        """Analyze a conversation turn and save extracted memories.

        Returns the list of newly saved Memory objects.
        """
        if not turn.strip():
            return []

        prompt = EXTRACT_PROMPT.format(turn=turn)

        try:
            response = self.llm.chat([
                {"role": "system", "content": "You are a precise memory extraction system. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ])
            candidates = self._parse_response(response)
            return self._save_new(candidates)
        except Exception as e:
            logger.warning(f"Memory extraction failed: {e}")
            return []

    def _parse_response(self, response: str) -> List[Memory]:
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])
        data = json.loads(response)
        raw_memories = data.get("memories", [])
        result = []
        for raw in raw_memories:
            mem_type = raw.get("type", "lesson")
            title = raw.get("title", "").strip()
            content = raw.get("content", "").strip()
            tags = raw.get("tags", [])
            if title and content:
                result.append(Memory(
                    id="",
                    types=[mem_type],
                    title=title,
                    content=content,
                    tags=tags,
                ))
        return result

    def _save_new(self, candidates: List[Memory]) -> List[Memory]:
        if not candidates:
            return []

        existing = self.store.list()
        existing_fps = {_fingerprint(m) for m in existing}

        saved = []
        for mem in candidates:
            fp = _fingerprint(mem)
            if fp in existing_fps:
                continue
            saved_mem = self.store.create(
                title=mem.title,
                type=mem.types[0] if mem.types else "",
                content=mem.content,
                tags=mem.tags,
            )
            saved.append(saved_mem)
            existing_fps.add(fp)

        return saved
