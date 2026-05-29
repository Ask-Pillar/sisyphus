"""CacheStore — SQLite cache over file-based memory store.

Files are the source of truth. The database is a rebuildable cache
for fast queries, filtering, and search across all layers.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore


class CacheStore:
    def __init__(self, base_path: Path, db_name: str = ".omo_cache.db"):
        self.db_path = Path(base_path) / db_name
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA wal_autocheckpoint=1000")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT, title TEXT, content TEXT,
                    tags TEXT, importance INTEGER, status TEXT,
                    links TEXT, evidence TEXT, compressed_from TEXT,
                    refined_by TEXT, source TEXT, session_id TEXT,
                    trigger TEXT, detected_at TEXT,
                    repeat_count INTEGER DEFAULT 0,
                    repeat_pattern TEXT,
                    resolved INTEGER DEFAULT 0,
                    created_at TEXT, updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_type
                ON memories(type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_created
                ON memories(created_at)
            """)

    def rebuild(self, store: MemoryStore, refined: Optional[RefinedStore] = None) -> dict:
        raw_memories = store.list()
        refined_memories = refined.list_refined() if refined else []
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM memories")
            for m in raw_memories + refined_memories:
                conn.execute("""
                    INSERT OR REPLACE INTO memories
                    (id, type, title, content, tags, importance, status,
                     links, evidence, compressed_from, refined_by,
                     source, session_id, trigger, detected_at,
                     repeat_count, repeat_pattern, resolved,
                     created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    m.id, m.types[0] if m.types else "", m.title, m.content,
                    ",".join(m.tags), m.importance, m.status,
                    ",".join(m.links), ",".join(m.evidence),
                    ",".join(m.compressed_from), ",".join(m.refined_by),
                    m.source, m.session_id, m.trigger, m.detected_at,
                    m.repeat_count, m.repeat_pattern,
                    1 if m.resolved else 0,
                    m.created_at, m.updated_at,
                ))
            conn.execute(
                "INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)",
                ("last_rebuild", str(len(raw_memories) + len(refined_memories))),
            )
        return {"cached": len(raw_memories) + len(refined_memories)}

    def status(self) -> dict:
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            last = conn.execute(
                "SELECT value FROM cache_meta WHERE key=?", ("last_rebuild",)
            ).fetchone()
            by_type = dict(conn.execute(
                "SELECT type, COUNT(*) FROM memories GROUP BY type"
            ).fetchall())
        return {
            "total": total,
            "last_rebuild": last[0] if last else "never",
            "by_type": by_type,
        }

    def search(self, query: str, limit: int = 20) -> list:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute("""
                SELECT id, type, title, content, tags, importance, created_at
                FROM memories
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", f"%{query}%", limit)).fetchall()
        return [
            {"id": r[0], "type": r[1], "title": r[2],
             "content": r[3][:200], "tags": r[4],
             "importance": r[5], "created_at": r[6]}
            for r in rows
        ]
