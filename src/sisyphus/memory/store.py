"""File-based memory store for Sisyphus.

Each memory is stored as a Markdown topic file.
INDEX.md serves as the always-loaded table of contents.
"""

import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List


@dataclass
class Memory:
    """A single memory entry."""
    id: str
    type: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return "mem_" + uuid.uuid4().hex[:12]


INDEX_HEADER = "# Sisyphus Memory Index\n\n"
INDEX_ENTRY = "- [{id}] {type} | {title} | {created_at}\n"


class MemoryStore:
    """Manages memories as Markdown files on disk.

    Layout:
      <base_path>/
        INDEX.md          ← Always-loaded table of contents
        <id>.md           ← Topic files (on-demand)
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._ensure_index()

    # ── Public API ──────────────────────────────────────────────

    def create(
        self,
        title: str,
        type: str,
        content: str = "",
        tags: Optional[List[str]] = None,
    ) -> Memory:
        mem = Memory(
            id=_new_id(),
            type=type,
            title=title,
            content=content,
            tags=tags or [],
            created_at=_now(),
            updated_at=_now(),
        )
        self._write_topic(mem)
        self._rebuild_index()
        return mem

    def get(self, mem_id: str) -> Optional[Memory]:
        topic_file = self.base_path / f"{mem_id}.md"
        if not topic_file.exists():
            return None
        return self._parse_topic(topic_file)

    def list(self, type_filter: Optional[str] = None) -> List[Memory]:
        memories = []
        for f in sorted(self.base_path.glob("*.md")):
            if f.name == "INDEX.md":
                continue
            mem = self._parse_topic(f)
            if type_filter is None or mem.type == type_filter:
                memories.append(mem)
        return memories

    def update(
        self,
        mem_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Memory]:
        mem = self.get(mem_id)
        if mem is None:
            return None
        if title is not None:
            mem.title = title
        if content is not None:
            mem.content = content
        if tags is not None:
            mem.tags = tags
        mem.updated_at = _now()
        self._write_topic(mem)
        self._rebuild_index()
        return mem

    def delete(self, mem_id: str) -> None:
        topic_file = self.base_path / f"{mem_id}.md"
        if topic_file.exists():
            topic_file.unlink()
            self._rebuild_index()

    # ── Internal ────────────────────────────────────────────────

    def _ensure_index(self):
        index = self.base_path / "INDEX.md"
        if not index.exists():
            index.write_text(INDEX_HEADER)

    def _write_topic(self, mem: Memory):
        lines = [
            f"# {mem.title}\n",
            f"\n",
            f"- **ID**: {mem.id}\n",
            f"- **Type**: {mem.type}\n",
            f"- **Created**: {mem.created_at}\n",
            f"- **Updated**: {mem.updated_at}\n",
            f"- **Tags**: {', '.join(mem.tags)}\n",
            f"\n",
        ]
        if mem.content:
            lines.append(mem.content)
            if not mem.content.endswith("\n"):
                lines.append("\n")
        topic_file = self.base_path / f"{mem.id}.md"
        topic_file.write_text("".join(lines))

    def _parse_topic(self, path: Path) -> Memory:
        text = path.read_text()
        mem_id = _extract_field(text, "ID", path.stem)
        mem_type = _extract_field(text, "Type", "lesson")
        created = _extract_field(text, "Created", "")
        updated = _extract_field(text, "Updated", "")
        tags_raw = _extract_field(text, "Tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        title = _extract_title(text)
        content = _extract_content(text)
        return Memory(
            id=mem_id,
            type=mem_type,
            title=title,
            content=content,
            tags=tags,
            created_at=created,
            updated_at=updated,
        )

    def _rebuild_index(self):
        memories = []
        for f in sorted(self.base_path.glob("*.md")):
            if f.name == "INDEX.md":
                continue
            mem = self._parse_topic(f)
            memories.append(mem)

        lines = [INDEX_HEADER]
        for m in memories:
            created = m.created_at[:19].replace("T", " ") if m.created_at else ""
            lines.append(INDEX_ENTRY.format(id=m.id, type=m.type, title=m.title, created_at=created))
        (self.base_path / "INDEX.md").write_text("".join(lines))


# ── Parsing helpers ─────────────────────────────────────────────

def _extract_field(text: str, field: str, default: str) -> str:
    """Extract a metadata field like '- **ID**: abc123' from Markdown."""
    m = re.search(rf"^[-*] \*\*{field}\*\*:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else default


def _extract_title(text: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _extract_content(text: str) -> str:
    """Extract content after the metadata block.

    Topic file format:
      # Title\n
      \n
      - **ID**: ...\n
      - **Type**: ...\n
      ...\n
      - **Tags**: ...\n
      \n
      <actual content>\n
    """
    parts = re.split(r"^- \*\*Tags\*\*:.*$(?:\n\s*)?", text, flags=re.MULTILINE)
    if len(parts) > 1:
        return parts[1].strip()
    return ""
