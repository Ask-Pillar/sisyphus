"""Loop detection — identifies repeated patterns across memories.

Scans RAW memories and flags repeats by updating the original memory's
detected_at / repeat_count / repeat_pattern fields, and creating a
loop_record in the RefinedStore.
"""

from typing import List, Dict
from datetime import datetime, timezone

from sisyphus.memory.store import Memory, MemoryStore
from sisyphus.memory.refined import RefinedStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LoopDetector:
    def __init__(self, store: MemoryStore, refined: RefinedStore):
        self.store = store
        self.refined = refined

    def detect(self, threshold: int = 3) -> List[Dict]:
        """Scan RAW memories and detect repeat patterns.

        Groups memories by (type, normalized title). When a group
        reaches `threshold`, marks the earliest memory with loop
        metadata and creates a loop_record in the RefinedStore.

        Returns list of dicts describing each detected loop.
        """
        memories = sorted(self.store.list(), key=lambda m: m.created_at)
        groups = self._group_by_type_title(memories)
        results = []
        for key, members in groups.items():
            if len(members) < threshold:
                continue
            mem_type, title = key
            first = members[0]
            count = len(members)
            pattern = f"{mem_type}: {title}"
            self.store.update(
                first.id,
                detected_at=_now(),
                repeat_count=count,
                repeat_pattern=pattern,
            )
            record = self.refined.create_loop_record(
                title=f"Loop: {pattern}",
                content=f"Repeated {count} times in type '{mem_type}'",
                repeat_count=count,
                repeat_pattern=pattern,
            )
            results.append({
                "pattern": pattern,
                "count": count,
                "original_id": first.id,
                "record_id": record.id,
            })
        return results

    @staticmethod
    def _group_by_type_title(memories: List[Memory]) -> Dict:
        groups = {}
        for m in memories:
            if not m.title:
                continue
            key = (m.types[0] if m.types else "", m.title.lower().strip())
            groups.setdefault(key, []).append(m)
        return groups
