"""Audit layer — coverage monitoring for memory system.

Reads L2 operation logs and L3 FTS5 index to compute:
- Events per source per day
- Memories captured per day
- Coverage ratio
- Missing time windows
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from sisyphus.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class Auditor:
    """Coverage auditor using L2 operation log and memory counts."""

    def __init__(self, store: MemoryStore):
        self.store = store
        self.log_path = store.base_path / "operations.jsonl"

    def audit(self, days: int = 1) -> dict:
        """Audit recent coverage. Returns report dict."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        ops = self._read_ops_since(cutoff)
        memories = self._count_memories_since(cutoff)

        op_count = len(ops)
        mem_count = len(memories)
        coverage = (mem_count / op_count * 100) if op_count > 0 else 100.0

        return {
            "period": f"last {days} day(s)",
            "operations": op_count,
            "memories": mem_count,
            "coverage_pct": round(coverage, 1),
            "status": "ok" if coverage >= 20 or mem_count >= op_count else "low",
        }

    def _read_ops_since(self, cutoff: str) -> list:
        if not self.log_path.exists():
            return []
        ops = []
        for line in self.log_path.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if record.get("ts", "") >= cutoff:
                    ops.append(record)
            except json.JSONDecodeError:
                pass
        return ops

    def _count_memories_since(self, cutoff: str) -> list:
        all_mems = self.store.list()
        return [m for m in all_mems if m.created_at and m.created_at >= cutoff]

    def report(self, days: int = 1) -> str:
        result = self.audit(days=days)
        if result["operations"] == 0:
            return f"No operations in the last {days} day(s)."
        status_icon = "✅" if result["status"] == "ok" else "⚠️"
        return (
            f"{status_icon} Audit ({result['period']}): "
            f"{result['operations']} ops, {result['memories']} memories, "
            f"coverage {result['coverage_pct']}% "
            f"[{result['status']}]"
        )
