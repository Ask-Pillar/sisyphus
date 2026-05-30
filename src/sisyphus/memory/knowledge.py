"""KnowledgeBase — large-scale document import with SQLite FTS5 chunked storage.

Supports: .md, .txt, .jsonl, .csv
Storage: ~/.omo/knowledge/{domain}/chunks.db (FTS5 indexed)
"""

import sqlite3
import json
import csv
from pathlib import Path
from typing import Optional, List, Dict, Iterator
from datetime import datetime, timezone

CHUNK_SIZE = 500


class KnowledgeBase:
    """SQLite FTS5-backed knowledge base with chunked document storage.

    Usage:
        kb = KnowledgeBase(domain="docs")
        kb.import_file("/path/to/doc.md")
        results = kb.search("database config", top_k=5)
    """

    def __init__(self, base_path: Optional[Path] = None, domain: str = "default"):
        self.base_path = (base_path or Path.home() / ".omo") / "knowledge" / domain
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_path / "chunks.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    imported_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                USING fts5(content, source, metadata, content_rowid='id')
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS import_log (
                    source TEXT PRIMARY KEY,
                    chunks_count INTEGER,
                    size_bytes INTEGER,
                    imported_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def import_file(self, filepath: str) -> int:
        """Import a single file into the knowledge base. Returns chunk count."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        suffix = path.suffix.lower()
        content = ""

        if suffix == ".md":
            content = path.read_text(encoding="utf-8")
        elif suffix == ".txt":
            content = path.read_text(encoding="utf-8")
        elif suffix == ".jsonl":
            content = self._read_jsonl(path)
        elif suffix == ".csv":
            content = self._read_csv(path)
        else:
            raise ValueError(f"Unsupported format: {suffix}")

        return self._store_chunks(str(path), content)

    def _read_jsonl(self, path: Path) -> str:
        chunks = []
        with open(path) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    chunks.append(data.get("content", data.get("text", json.dumps(data))))
                except json.JSONDecodeError:
                    chunks.append(line.strip())
        return "\n".join(chunks)

    def _read_csv(self, path: Path) -> str:
        chunks = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                chunks.append(str(dict(row)))
        return "\n".join(chunks)

    def _store_chunks(self, source: str, content: str) -> int:
        """Split content into chunks and store in SQLite."""
        words = content.split()
        total_chunks = max(1, (len(words) + CHUNK_SIZE - 1) // CHUNK_SIZE)
        now = _now()
        chunk_count = 0

        with sqlite3.connect(str(self.db_path)) as conn:
            for i in range(total_chunks):
                start = i * CHUNK_SIZE
                end = start + CHUNK_SIZE
                chunk_text = " ".join(words[start:end])
                if not chunk_text.strip():
                    continue

                cursor = conn.execute(
                    "INSERT INTO chunks (source, chunk_index, content, imported_at) VALUES (?, ?, ?, ?)",
                    (source, i, chunk_text, now),
                )
                chunk_id = cursor.lastrowid
                conn.execute(
                    "INSERT INTO chunks_fts (rowid, content, source) VALUES (?, ?, ?)",
                    (chunk_id, chunk_text, source),
                )
                chunk_count += 1

            conn.execute(
                "INSERT OR REPLACE INTO import_log (source, chunks_count, size_bytes, imported_at) VALUES (?, ?, ?, ?)",
                (source, chunk_count, len(content.encode("utf-8")), now),
            )
            conn.commit()

        return chunk_count

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Full-text search across imported knowledge chunks."""
        if not query.strip():
            return []

        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """SELECT c.id, c.source, c.chunk_index, c.content, c.imported_at,
                          snippet(chunks_fts, 1, '<mark>', '</mark>', '...', 40) as snippet
                   FROM chunks_fts f
                   JOIN chunks c ON f.rowid = c.id
                   WHERE chunks_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, top_k),
            ).fetchall()

        return [
            {
                "id": r[0],
                "source": r[1],
                "chunk_index": r[2],
                "content": r[3][:500],
                "imported_at": r[4],
                "snippet": r[5] or r[3][:200],
            }
            for r in rows
        ]

    def import_directory(self, dirpath: str, recursive: bool = True) -> Dict:
        """Import all supported files from a directory."""
        path = Path(dirpath)
        if not path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dirpath}")

        supported = {".md", ".txt", ".jsonl", ".csv"}
        files = path.rglob("*") if recursive else path.glob("*")
        results = {"total_files": 0, "total_chunks": 0, "errors": []}

        for f in sorted(files):
            if f.suffix.lower() not in supported:
                continue
            try:
                count = self.import_file(str(f))
                results["total_files"] += 1
                results["total_chunks"] += count
            except Exception as e:
                results["errors"].append({"file": str(f), "error": str(e)})

        return results

    def stats(self) -> Dict:
        """Return knowledge base statistics."""
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            sources = conn.execute("SELECT COUNT(*) FROM import_log").fetchone()[0]
            size = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM import_log").fetchone()[0]
        return {"total_chunks": total, "total_sources": sources, "total_bytes": size}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
