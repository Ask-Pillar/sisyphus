"""L3 Semantic Index — SQLite FTS5 full-text search.

Zero dependencies beyond Python stdlib (sqlite3).
Rebuildable from RAW .md files via 'sisyphus rebuild'.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sisyphus.memory.store import MemoryStore, Memory

logger = logging.getLogger(__name__)

_FTS_DB_NAME = ".omo/cache/memory.db"
_FTS_TABLE = "fts_memory"


class FtsIndex:
    """SQLite FTS5 index for memory full-text search."""

    def __init__(self, store: MemoryStore):
        self.store = store
        self.db_path = store.base_path.parent.parent / _FTS_DB_NAME
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _ensure_table(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_TABLE}
                USING fts5(id, type, title, content, tags, created_at,
                           tokenize='unicode61')
            """)

    def rebuild(self):
        """Rebuild FTS5 index from all RAW .md files."""
        memories = self.store.list()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(f"DELETE FROM {_FTS_TABLE}")
            for m in memories:
                self._insert(conn, m)
        logger.info("FTS5 rebuilt: %d memories indexed", len(memories))
        return len(memories)

    def _insert(self, conn: sqlite3.Connection, mem: Memory):
        conn.execute(
            f"INSERT INTO {_FTS_TABLE} (id, type, title, content, tags, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                mem.id,
                mem.types[0] if mem.types else "",
                mem.title,
                mem.content,
                " ".join(mem.tags),
                mem.created_at or "",
            ),
        )

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Memory, float]]:
        """Full-text search returning (memory, score) pairs sorted by relevance."""
        with sqlite3.connect(str(self.db_path)) as conn:
            try:
                rows = conn.execute(
                    f"SELECT id, rank FROM {_FTS_TABLE} "
                    f"WHERE {_FTS_TABLE} MATCH ? "
                    f"ORDER BY rank LIMIT ?",
                    (query, top_k),
                ).fetchall()
            except sqlite3.OperationalError:
                return []

        results = []
        for mem_id, rank in rows:
            mem = self.store.get(mem_id)
            if mem:
                results.append((mem, -rank))
        return results

    def index_memory(self, mem: Memory):
        """Insert or update a single memory in FTS5."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(f"DELETE FROM {_FTS_TABLE} WHERE id=?", (mem.id,))
            self._insert(conn, mem)

    def remove_memory(self, mem_id: str):
        """Remove a single memory from FTS5."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(f"DELETE FROM {_FTS_TABLE} WHERE id=?", (mem_id,))

    @property
    def is_populated(self) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM {_FTS_TABLE}").fetchone()
            return row[0] > 0 if row else False
