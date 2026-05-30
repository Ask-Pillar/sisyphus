"""SQLiteMemoryStore — SQLite-backed MemoryStore replacing file-based storage.

Uses SQLite with FTS5 for full-text search. Drop-in replacement for MemoryStore
with identical API. Migration from markdown files is automatic on init.
"""

import json
import sqlite3
import uuid
import hashlib
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

from sisyphus.memory.store import Memory, MemoryStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return "mem_" + uuid.uuid4().hex[:12]


class SQLiteMemoryStore:
    """SQLite-backed memory store. Drop-in replacement for MemoryStore."""

    def __init__(self, base_path: Path, max_raw: int = 0):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_path / "store.db"
        self.max_raw = max_raw
        self._dirty = False
        self._init_db()
        self._maybe_migrate()

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self):
        self._dirty = True

    def clear_dirty(self):
        self._dirty = False

    # ── DB init ──

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    types TEXT DEFAULT '[]',
                    tags TEXT DEFAULT '[]',
                    links TEXT DEFAULT '[]',
                    importance INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'active',
                    source TEXT DEFAULT '',
                    session_id TEXT DEFAULT '',
                    deleted INTEGER DEFAULT 0,
                    dismissed INTEGER DEFAULT 0,
                    refined_by TEXT DEFAULT '[]',
                    evidence TEXT DEFAULT '[]',
                    compressed_from TEXT DEFAULT '[]',
                    trigger TEXT DEFAULT '',
                    input_count INTEGER DEFAULT 0,
                    llm_calls INTEGER DEFAULT 0,
                    duration_ms INTEGER DEFAULT 0,
                    detected_at TEXT DEFAULT '',
                    repeat_count INTEGER DEFAULT 0,
                    repeat_pattern TEXT DEFAULT '',
                    resolved INTEGER DEFAULT 0,
                    recall_count INTEGER DEFAULT 0,
                    last_recalled_at TEXT DEFAULT '',
                    feedback_score INTEGER DEFAULT 0,
                    feedback_at TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(title, content, tags, types, content_rowid='rowid')
            """)
            conn.commit()

    def _maybe_migrate(self):
        """Migrate from markdown files if they exist and DB is empty."""
        with sqlite3.connect(str(self.db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            if count > 0:
                return
        old_store = MemoryStore(self.base_path)
        memories = old_store.list(include_deleted=True)
        if memories:
            for mem in memories:
                self._insert(conn := sqlite3.connect(str(self.db_path)), mem)
                conn.commit()
            self._dirty = True

    # ── Serialization ──

    def _insert(self, conn: sqlite3.Connection, mem: Memory):
        conn.execute("""
            INSERT INTO memories (id, title, content, types, tags, links,
                importance, status, source, session_id, deleted, dismissed,
                refined_by, evidence, compressed_from, trigger,
                input_count, llm_calls, duration_ms, detected_at,
                repeat_count, repeat_pattern, resolved,
                recall_count, last_recalled_at,
                feedback_score, feedback_at,
                created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            mem.id, mem.title, mem.content, json.dumps(mem.types), json.dumps(mem.tags),
            json.dumps(mem.links), mem.importance, mem.status, mem.source, mem.session_id,
            1 if mem.deleted else 0, 1 if mem.dismissed else 0,
            json.dumps(mem.refined_by), json.dumps(mem.evidence),
            json.dumps(mem.compressed_from), mem.trigger,
            mem.input_count, mem.llm_calls, mem.duration_ms, mem.detected_at,
            mem.repeat_count, mem.repeat_pattern, 1 if mem.resolved else 0,
            mem.recall_count, mem.last_recalled_at,
            mem.feedback_score, mem.feedback_at,
            mem.created_at, mem.updated_at,
        ))
        rowid = conn.execute("SELECT rowid FROM memories WHERE id = ?", (mem.id,)).fetchone()[0]
        conn.execute(
            "INSERT INTO memories_fts (rowid, title, content, tags, types) VALUES (?,?,?,?,?)",
            (rowid, mem.title, mem.content, json.dumps(mem.tags), json.dumps(mem.types)),
        )

    def _row_to_memory(self, row) -> Memory:
        return Memory(
            id=row[0],
            title=row[1],
            content=row[2] or "",
            types=json.loads(row[3]) if row[3] else [],
            tags=json.loads(row[4] or "[]"),
            links=json.loads(row[5] or "[]"),
            importance=row[6] or 5,
            status=row[7] or "active",
            source=row[8] or "",
            session_id=row[9] or "",
            deleted=bool(row[10]),
            dismissed=bool(row[11]),
            refined_by=json.loads(row[12] or "[]"),
            evidence=json.loads(row[13] or "[]"),
            compressed_from=json.loads(row[14] or "[]"),
            trigger=row[15] or "",
            input_count=row[16] or 0,
            llm_calls=row[17] or 0,
            duration_ms=row[18] or 0,
            detected_at=row[19] or "",
            repeat_count=row[20] or 0,
            repeat_pattern=row[21] or "",
            resolved=bool(row[22]),
            recall_count=row[23] or 0,
            last_recalled_at=row[24] or "",
            feedback_score=row[25] or 0,
            feedback_at=row[26] or "",
            created_at=row[27] or "",
            updated_at=row[28] or "",
        )

    # ── Public API ──

    def create(self, title: str, type: str = "", content: str = "",
               tags: Optional[List[str]] = None, importance: int = 5,
               links: Optional[List[str]] = None, status: str = "active",
               source: str = "", session_id: str = "",
               types: Optional[List[str]] = None) -> Memory:
        _types = types or ([type] if type else [])
        mem = Memory(id=_new_id(), types=_types, title=title, content=content,
                     tags=tags or [], importance=importance, links=links or [],
                     status=status, source=source, session_id=session_id,
                     created_at=_now(), updated_at=_now())
        with sqlite3.connect(str(self.db_path)) as conn:
            self._insert(conn, mem)
            conn.commit()
        self._dirty = True
        self._log_operation("create", mem)
        return mem

    def find_similar(self, title: str, types: Optional[List[str]] = None, type: str = "") -> Optional[Memory]:
        _types = types or ([type] if type else [])
        fp = hashlib.sha256(f"{':'.join(sorted(_types))}:{title}".encode()).hexdigest()[:12]
        for existing in self.list():
            if hashlib.sha256(f"{':'.join(sorted(existing.types))}:{existing.title}".encode()).hexdigest()[:12] == fp:
                return existing
        return None

    def create_if_new(self, **kwargs) -> Memory:
        title = kwargs.get("title", "")
        types = kwargs.get("types") or ([kwargs.get("type", "")] if kwargs.get("type") else [])
        existing = self.find_similar(title=title, types=types)
        if existing:
            return existing
        return self.create(**kwargs)

    def get(self, mem_id: str) -> Optional[Memory]:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
            if row:
                return self._row_to_memory(row)
        return None

    def list(self, type_filter: Optional[str] = None, include_deleted: bool = False) -> List[Memory]:
        with sqlite3.connect(str(self.db_path)) as conn:
            query = "SELECT * FROM memories WHERE 1=1"
            params: list = []
            if not include_deleted:
                query += " AND deleted = 0"
            query += " AND dismissed = 0"
            if type_filter:
                query += " AND types LIKE ?"
                params.append(f'%"{type_filter}"%')
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_memory(r) for r in rows]

    def update(self, mem_id: str, **kwargs) -> Optional[Memory]:
        mem = self.get(mem_id)
        if mem is None:
            return None
        for key, val in kwargs.items():
            if hasattr(mem, key) and val is not None:
                setattr(mem, key, val)
        mem.updated_at = _now()
        with sqlite3.connect(str(self.db_path)) as conn:
            self._insert(conn, mem)
            conn.commit()
        self._dirty = True
        self._log_operation("update", mem)
        return mem

    def delete(self, mem_id: str) -> bool:
        mem = self.get(mem_id)
        if mem is None:
            return False
        mem.deleted = True
        mem.updated_at = _now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE memories SET deleted=1, updated_at=? WHERE id=?", (mem.updated_at, mem_id))
            conn.commit()
        self._dirty = True
        self._log_operation("delete", mem)
        return True

    def restore(self, mem_id: str) -> bool:
        mem = self.get(mem_id)
        if mem is None or not mem.deleted:
            return False
        mem.deleted = False
        mem.updated_at = _now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE memories SET deleted=0, updated_at=? WHERE id=?", (mem.updated_at, mem_id))
            conn.commit()
        self._dirty = True
        self._log_operation("restore", mem)
        return True

    def rate(self, mem_id: str, score: int) -> bool:
        mem = self.get(mem_id)
        if mem is None:
            return False
        mem.feedback_score = max(1, min(5, score))
        mem.feedback_at = _now()
        mem.updated_at = _now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE memories SET feedback_score=?, feedback_at=?, updated_at=? WHERE id=?",
                         (mem.feedback_score, mem.feedback_at, mem.updated_at, mem_id))
            conn.commit()
        self._dirty = True
        self._log_operation("rate", mem)
        return True

    def dismiss(self, mem_id: str) -> bool:
        mem = self.get(mem_id)
        if mem is None:
            return False
        mem.dismissed = True
        mem.updated_at = _now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE memories SET dismissed=1, updated_at=? WHERE id=?", (mem.updated_at, mem_id))
            conn.commit()
        self._dirty = True
        self._log_operation("dismiss", mem)
        return True

    def search(self, query: str, top_k: int = 10) -> List[Memory]:
        if not query.strip():
            return []
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """SELECT m.* FROM memories_fts f
                   JOIN memories m ON f.rowid = m.rowid
                   WHERE memories_fts MATCH ? AND m.deleted = 0 AND m.dismissed = 0
                   ORDER BY rank LIMIT ?""",
                (query, top_k),
            ).fetchall()
            return [self._row_to_memory(r) for r in rows]

    def _log_operation(self, op: str, mem: Memory, mem_id: str = ""):
        log_path = self.base_path / "operations.jsonl"
        record = {"op": op, "id": mem.id, "ts": _now(),
                  "type": mem.types[0] if mem.types else "",
                  "title": mem.title}
        with open(log_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
