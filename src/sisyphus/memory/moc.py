"""MOC (Map of Content) generation.

Generates type-grouped index pages with Obsidian-compatible wikilinks.
Writes to MOC.md (topic-grouped index) to avoid overwriting INDEX.md (flat index).
"""

from pathlib import Path
from typing import Optional

from sisyphus.memory.utils import atomic_write

from .store import MemoryStore
from .refined import RefinedStore

MOC_HEADER = "# Sisyphus Memory Index\n\n"


class MocGenerator:
    """Generates MOC.md (topic-grouped) and dimension-specific MOC files."""

    def __init__(self, store: MemoryStore, refined_store: Optional[RefinedStore] = None):
        self.store = store
        self.refined_store = refined_store

    def generate(self):
        memories = self.store.list()
        if self.refined_store:
            memories.extend(self.refined_store.list_refined())
        self._write_index(memories)

    def generate_dimension(self, dimension: str, tag: str):
        memories = [m for m in self.store.list() if tag in m.tags]
        if self.refined_store:
            memories.extend(
                m for m in self.refined_store.list_refined() if tag in m.tags
            )
        self._write_dimension(dimension, memories)

    def _write_index(self, memories):
        sections = self._group_by_type(memories)
        lines = [MOC_HEADER]
        for mem_type in sorted(sections, key=_type_sort_key):
            lines.append(f"## {mem_type}\n")
            for m in sections[mem_type]:
                lines.append(f"- [[{m.id}|{m.title}]]\n")
            lines.append("\n")
        while lines and lines[-1] == "\n":
            lines.pop()
        lines.append("\n")
        atomic_write(self.store.base_path / "MOC.md", "".join(lines))

    def _write_dimension(self, dimension: str, memories):
        sections = self._group_by_type(memories)
        lines = [f"# {dimension}维度 — {dimension}\n\n"]
        for mem_type in sorted(sections, key=_type_sort_key):
            lines.append(f"## {mem_type}\n")
            for m in sections[mem_type]:
                lines.append(f"- [[{m.id}|{m.title}]]\n")
            lines.append("\n")
        atomic_write(self.store.base_path / f"MOC-{dimension}.md", "".join(lines))

    def _group_by_type(self, memories):
        sections = {}
        for m in memories:
            for t in (m.types or [""]):
                sections.setdefault(t, []).append(m)
        return sections


def _type_sort_key(t: str) -> str:
    """Sort refined types after raw types."""
    priority = {"reflection": "z_reflection", "summary": "z_summary", "loop_record": "z_loop"}
    return priority.get(t, t)
