"""Dream engine — LLM-driven reflection and insight generation via subagent."""

import logging
from typing import List

from sisyphus.memory.store import MemoryStore, Memory
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.log import LogStore

logger = logging.getLogger(__name__)


class DreamEngine:
    """Reflection engine: dispatches dream to subagent, handles bookkeeping."""

    def __init__(self, store: MemoryStore, refined_store: RefinedStore, subagent):
        self.store = store
        self.refined = refined_store
        self.subagent = subagent
        self.logger = LogStore(store.base_path.parent)
        self.last_log = None

    def dream(self) -> List[Memory]:
        """Run one reflection cycle via subagent."""
        memories = self._gather_memories()
        if not memories:
            return []

        result = self.subagent.dream(memories)
        if result.get("status") not in ("ok", "skipped"):
            logger.warning("Dream subagent failed: %s", result.get("message"))
            return []

        created = []
        for ref_data in result.get("reflections", []):
            mem = Memory(
                id=ref_data["id"],
                title=ref_data["title"],
                type="reflection",
                content=ref_data.get("content", ""),
                evidence=ref_data.get("evidence", []),
                importance=ref_data.get("importance", 5),
                status="active",
            )
            self._update_refined_by(mem.id, mem.evidence)
            created.append(mem)

        log_body = f"Generated {len(created)} reflections from {len(memories)} memories."
        self.last_log = self.logger.create_log("dream", body=log_body)
        return created

    def _gather_memories(self) -> List[Memory]:
        return self.store.list()

    def _update_refined_by(self, ref_id: str, evidence_ids: List[str]):
        for mem_id in evidence_ids:
            mem = self.store.get(mem_id)
            if mem is None:
                continue
            if ref_id not in mem.refined_by:
                mem.refined_by = mem.refined_by + [ref_id]
                self.store.update(mem.id, status=mem.status)
                self.store._write_topic(mem)
