"""File-based memory store for Sisyphus.

Each memory is stored as a Markdown file with YAML frontmatter.
INDEX.md serves as the always-loaded table of contents.
"""

import re
import json
import uuid
import hashlib
import yaml
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from sisyphus.memory.utils import atomic_write


@dataclass
class Memory:
    id: str
    types: list[str] = field(default_factory=list)
    title: str = ""
    content: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    importance: int = 5
    links: list[str] = field(default_factory=list)
    deleted: bool = False
    status: str = "active"
    source: str = ""
    session_id: str = ""
    refined_by: list[str] = field(default_factory=list)
    # Refined-layer fields
    evidence: list[str] = field(default_factory=list)
    compressed_from: list[str] = field(default_factory=list)
    trigger: str = ""
    input_count: int = 0
    llm_calls: int = 0
    duration_ms: int = 0
    detected_at: str = ""
    repeat_count: int = 0
    repeat_pattern: str = ""
    resolved: bool = False
    # Retrieval-layer fields
    recall_count: int = 0
    last_recalled_at: str = ""
    # Feedback-layer fields
    feedback_score: int = 0
    feedback_at: str = ""
    dismissed: bool = False


def _now() -> str:
    """Return current time as ISO 8601 string in the system's local timezone."""
    return datetime.now().astimezone().isoformat()


def _new_id() -> str:
    return "mem_" + uuid.uuid4().hex[:12]


INDEX_HEADER = "# Sisyphus Memory Index\n\n"
INDEX_ENTRY = "- [{id}] {type} | {title} | {created_at}\n"


class MemoryStore:
    def __init__(self, base_path: Path, max_raw: int = 0):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._ensure_index()
        self._dirty = False
        self.max_raw = max_raw  # 0 = unlimited

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self):
        self._dirty = True

    def clear_dirty(self):
        self._dirty = False

    def create(
        self,
        title: str,
        type: str = "",
        content: str = "",
        tags: Optional[List[str]] = None,
        importance: int = 5,
        links: Optional[List[str]] = None,
        status: str = "active",
        source: str = "",
        session_id: str = "",
        types: Optional[List[str]] = None,
    ) -> Memory:
        _types = types or ([type] if type else [])
        mem = Memory(
            id=_new_id(),
            types=_types,
            title=title,
            content=content,
            tags=tags or [],
            created_at=_now(),
            updated_at=_now(),
            importance=importance,
            links=links or [],
            status=status,
            source=source,
            session_id=session_id,
        )
        self._write_topic(mem)
        self._rebuild_index()
        self._dirty = True
        self._log_operation("create", mem)
        return mem

    def find_similar(self, title: str, types: Optional[List[str]] = None, type: str = "") -> Optional[Memory]:
        """Find existing memory with same (types, title). Returns None if not found."""
        _types = types or ([type] if type else [])
        fp = hashlib.sha256(f"{':'.join(sorted(_types))}:{title}".encode()).hexdigest()[:12]
        for existing in self.list():
            if hashlib.sha256(f"{':'.join(sorted(existing.types))}:{existing.title}".encode()).hexdigest()[:12] == fp:
                return existing
        return None

    def create_if_new(self, **kwargs) -> Memory:
        """Create memory only if no similar one exists. Returns existing if found."""
        title = kwargs.get("title", "")
        types = kwargs.get("types") or ([kwargs.get("type", "")] if kwargs.get("type") else [])
        existing = self.find_similar(title=title, types=types)
        if existing:
            return existing
        return self.create(**kwargs)

    def get(self, mem_id: str) -> Optional[Memory]:
        topic_file = self.base_path / f"{mem_id}.md"
        if not topic_file.exists():
            return None
        return self._parse_topic(topic_file)

    def list(self, type_filter: Optional[str] = None, include_deleted: bool = False) -> List[Memory]:
        memories = []
        for f in sorted(self.base_path.glob("*.md")):
            if f.name == "INDEX.md":
                continue
            mem = self._parse_topic(f)
            if not include_deleted and mem.deleted:
                continue
            if mem.dismissed:
                continue
            if type_filter is None or type_filter in mem.types:
                memories.append(mem)
        return memories

    def update(
        self,
        mem_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance: Optional[int] = None,
        links: Optional[List[str]] = None,
        status: Optional[str] = None,
        detected_at: Optional[str] = None,
        repeat_count: Optional[int] = None,
        repeat_pattern: Optional[str] = None,
        recall_count: Optional[int] = None,
        last_recalled_at: Optional[str] = None,
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
        if importance is not None:
            mem.importance = importance
        if links is not None:
            mem.links = links
        if status is not None:
            mem.status = status
        if detected_at is not None:
            mem.detected_at = detected_at
        if repeat_count is not None:
            mem.repeat_count = repeat_count
        if repeat_pattern is not None:
            mem.repeat_pattern = repeat_pattern
        if recall_count is not None:
            mem.recall_count = recall_count
        if last_recalled_at is not None:
            mem.last_recalled_at = last_recalled_at
        mem.updated_at = _now()
        self._write_topic(mem)
        self._rebuild_index()
        self._dirty = True
        self._log_operation("update", mem)
        return mem

    def delete(self, mem_id: str) -> bool:
        """Soft delete: mark as deleted without removing the file."""
        mem = self.get(mem_id)
        if mem is None:
            return False
        mem.deleted = True
        mem.updated_at = _now()
        self._write_topic(mem)
        self._rebuild_index()
        self._dirty = True
        self._log_operation("delete", mem)
        return True

    def restore(self, mem_id: str) -> bool:
        """Restore a soft-deleted memory."""
        mem = self.get(mem_id)
        if mem is None or not mem.deleted:
            return False
        mem.deleted = False
        mem.updated_at = _now()
        self._write_topic(mem)
        self._rebuild_index()
        self._dirty = True
        self._log_operation("restore", mem)
        return True

    def rate(self, mem_id: str, score: int) -> bool:
        """Rate a memory (1-5). Negative feedback scores bias retrieval."""
        mem = self.get(mem_id)
        if mem is None:
            return False
        mem.feedback_score = max(1, min(5, score))
        mem.feedback_at = _now()
        mem.updated_at = _now()
        self._write_topic(mem)
        self._dirty = True
        self._log_operation("rate", mem)
        return True

    def dismiss(self, mem_id: str) -> bool:
        """Dismiss a memory. It will be excluded from future retrieval."""
        mem = self.get(mem_id)
        if mem is None:
            return False
        mem.dismissed = True
        mem.updated_at = _now()
        self._write_topic(mem)
        self._dirty = True
        self._log_operation("dismiss", mem)
        return True

    def _ensure_index(self):
        index = self.base_path / "INDEX.md"
        if not index.exists():
            atomic_write(index, INDEX_HEADER)

    def _write_topic(self, mem: Memory):
        fm = {
            "id": mem.id,
            "types": mem.types,
            "title": mem.title,
            "tags": mem.tags,
            "importance": mem.importance,
            "links": mem.links,
            "deleted": mem.deleted,
            "status": mem.status,
            "source": mem.source,
            "session_id": mem.session_id,
            "created": mem.created_at,
            "updated": mem.updated_at,
        }
        if mem.refined_by:
            fm["refined_by"] = mem.refined_by
        if mem.evidence:
            fm["evidence"] = mem.evidence
        if mem.compressed_from:
            fm["compressed_from"] = mem.compressed_from
        if mem.trigger:
            fm["trigger"] = mem.trigger
        if mem.input_count:
            fm["input_count"] = mem.input_count
        if mem.llm_calls:
            fm["llm_calls"] = mem.llm_calls
        if mem.duration_ms:
            fm["duration_ms"] = mem.duration_ms
        if mem.detected_at:
            fm["detected_at"] = mem.detected_at
        if mem.repeat_count:
            fm["repeat_count"] = mem.repeat_count
        if mem.repeat_pattern:
            fm["repeat_pattern"] = mem.repeat_pattern
        if mem.resolved:
            fm["resolved"] = mem.resolved
        if mem.recall_count:
            fm["recall_count"] = mem.recall_count
        if mem.last_recalled_at:
            fm["last_recalled_at"] = mem.last_recalled_at
        if mem.feedback_score:
            fm["feedback_score"] = mem.feedback_score
        if mem.feedback_at:
            fm["feedback_at"] = mem.feedback_at
        if mem.dismissed:
            fm["dismissed"] = True
        fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
        lines = [f"---\n{fm_yaml}\n---\n"]
        if mem.content:
            lines.append(mem.content)
            if not mem.content.endswith("\n"):
                lines.append("\n")
        topic_file = self.base_path / f"{mem.id}.md"
        atomic_write(topic_file, "".join(lines))

    def _parse_topic(self, path: Path) -> Memory:
        text = path.read_text()
        fm = self._parse_frontmatter(text)
        if fm is not None:
            content = self._extract_content_after_fm(text)
            return Memory(
                id=fm.get("id", path.stem),
                types=fm.get("types", fm.get("type") and [fm.get("type")] or []),
                title=fm.get("title", ""),
                content=content,
                tags=fm.get("tags", []),
                created_at=fm.get("created", ""),
                updated_at=fm.get("updated", ""),
                importance=fm.get("importance", 5),
                links=fm.get("links", []),
                deleted=fm.get("deleted", False),
                status=fm.get("status", "active"),
                source=fm.get("source", ""),
                session_id=fm.get("session_id", ""),
                refined_by=fm.get("refined_by", []),
                evidence=fm.get("evidence", []),
                compressed_from=fm.get("compressed_from", []),
                trigger=fm.get("trigger", ""),
                input_count=fm.get("input_count", 0),
                llm_calls=fm.get("llm_calls", 0),
                duration_ms=fm.get("duration_ms", 0),
                detected_at=fm.get("detected_at", ""),
                repeat_count=fm.get("repeat_count", 0),
                repeat_pattern=fm.get("repeat_pattern", ""),
                resolved=fm.get("resolved", False),
                recall_count=fm.get("recall_count", 0),
                last_recalled_at=fm.get("last_recalled_at", ""),
                feedback_score=fm.get("feedback_score", 0),
                feedback_at=fm.get("feedback_at", ""),
                dismissed=fm.get("dismissed", False),
            )
        return self._parse_old_format(text, path.stem)

    def _parse_frontmatter(self, text: str) -> Optional[dict]:
        if not text.startswith("---\n"):
            return None
        parts = text.split("---\n", 2)
        if len(parts) < 3:
            return None
        try:
            return yaml.safe_load(parts[1])
        except yaml.YAMLError:
            return None

    def _extract_content_after_fm(self, text: str) -> str:
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            return parts[2].strip()
        return ""

    def _parse_old_format(self, text: str, default_id: str) -> Memory:
        mem_id = _extract_field(text, "ID", default_id)
        mem_type = _extract_field(text, "Type", "lesson")
        created = _extract_field(text, "Created", "")
        updated = _extract_field(text, "Updated", "")
        tags_raw = _extract_field(text, "Tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        title = _extract_title(text)
        content = _extract_content(text)
        _types = [mem_type] if mem_type else []
        return Memory(
            id=mem_id,
            types=_types,
            title=title,
            content=content,
            tags=tags,
            created_at=created,
            updated_at=updated,
            recall_count=0,
            last_recalled_at="",
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
            lines.append(INDEX_ENTRY.format(id=m.id, type=m.types[0] if m.types else "", title=m.title, created_at=created))
        atomic_write(self.base_path / "INDEX.md", "".join(lines))

    def _log_operation(self, op: str, mem: Optional[Memory] = None, mem_id: str = ""):
        """Append an operation record to L2 operations log (JSONL)."""
        log_path = self.base_path / "operations.jsonl"
        record = {
            "op": op,
            "id": mem.id if mem else mem_id,
            "ts": _now(),
            "type": mem.types[0] if mem.types else "",
            "title": mem.title if mem else "",
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# Old format parsing helpers (kept for backward compatibility)

def _extract_field(text: str, field: str, default: str) -> str:
    m = re.search(rf"^[-*] \*\*{field}\*\*:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else default


def _extract_title(text: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _extract_content(text: str) -> str:
    parts = re.split(r"^- \*\*Tags\*\*:.*$(?:\n\s*)?", text, flags=re.MULTILINE)
    if len(parts) > 1:
        return parts[1].strip()
    return ""
