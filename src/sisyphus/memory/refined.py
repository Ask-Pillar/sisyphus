"""Refined memory store — processed memories in refined/ subdirectory.

Types: reflection, summary, loop_record.
Same frontmatter format as RAW, stored under base_path/refined/.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from .store import Memory, MemoryStore, _now


def _refined_id(prefix: str) -> str:
    return f"{prefix}_" + uuid.uuid4().hex[:12]


class RefinedStore:
    """Store for refined (processed) memories.

    Wraps MemoryStore at base_path/refined/ with type-specific
    creation methods for reflections, summaries, and loop records.
    """

    def __init__(self, base_path: Path):
        refined_path = Path(base_path) / "refined"
        self.store = MemoryStore(refined_path)

    @property
    def base_path(self) -> Path:
        return self.store.base_path

    def create_reflection(
        self,
        title: str,
        content: str = "",
        evidence: Optional[List[str]] = None,
        importance: int = 5,
        tags: Optional[List[str]] = None,
        trigger: str = "",
        input_count: int = 0,
        llm_calls: int = 0,
        duration_ms: int = 0,
    ) -> Memory:
        mem = Memory(
            id=_refined_id("ref"),
            types=["reflection"],
            title=title,
            content=content,
            evidence=evidence or [],
            importance=importance,
            tags=tags or [],
            trigger=trigger,
            input_count=input_count,
            llm_calls=llm_calls,
            duration_ms=duration_ms,
        )
        self.store._write_topic(mem)
        self.store._rebuild_index()
        return mem

    def create_summary(
        self,
        title: str,
        content: str = "",
        compressed_from: Optional[List[str]] = None,
        importance: int = 5,
        tags: Optional[List[str]] = None,
    ) -> Memory:
        mem = Memory(
            id=_refined_id("sum"),
            types=["summary"],
            title=title,
            content=content,
            compressed_from=compressed_from or [],
            importance=importance,
            tags=tags or [],
        )
        self.store._write_topic(mem)
        self.store._rebuild_index()
        return mem

    def create_loop_record(
        self,
        title: str,
        content: str = "",
        repeat_count: int = 0,
        repeat_pattern: str = "",
        resolved: bool = False,
        importance: int = 8,
        tags: Optional[List[str]] = None,
    ) -> Memory:
        mem = Memory(
            id=_refined_id("loop"),
            types=["loop_record"],
            title=title,
            content=content,
            repeat_count=repeat_count,
            repeat_pattern=repeat_pattern,
            resolved=resolved,
            importance=importance,
            tags=tags or [],
            detected_at=_now(),
        )
        self.store._write_topic(mem)
        self.store._rebuild_index()
        return mem

    def list_refined(self, type_filter: Optional[str] = None) -> List[Memory]:
        return self.store.list(type_filter=type_filter)

    def get_refined(self, mem_id: str) -> Optional[Memory]:
        return self.store.get(mem_id)

    def delete_refined(self, mem_id: str) -> None:
        self.store.delete(mem_id)
