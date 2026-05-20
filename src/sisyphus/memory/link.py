"""Link cleaner — validates and cleans up memory links.

Removes dead links (pointing to non-existent memories),
duplicates, and self-references. Does NOT auto-discover links.
"""

from typing import List, Set

from sisyphus.memory.store import MemoryStore


class LinkCleaner:
    def __init__(self, store: MemoryStore):
        self.store = store

    def clean(self) -> dict:
        memories = self.store.list()
        valid_ids: Set[str] = {m.id for m in memories}
        stats = {"removed_dead": 0, "removed_duplicates": 0,
                 "removed_self_refs": 0, "total_cleaned": 0}
        for mem in memories:
            original = list(mem.links)
            cleaned, dead, dupes, selfs = self._clean_links(mem.id, original, valid_ids)
            stats["removed_dead"] += dead
            stats["removed_duplicates"] += dupes
            stats["removed_self_refs"] += selfs
            if cleaned != original:
                self.store.update(mem.id, links=cleaned)
                stats["total_cleaned"] += 1
        return stats

    @staticmethod
    def _clean_links(mem_id: str, links: List[str], valid_ids: Set[str]) -> tuple:
        seen = set()
        result = []
        dead = dupes = selfs = 0
        for id_ in links:
            if id_ == mem_id:
                selfs += 1
                continue
            if id_ in seen:
                dupes += 1
                continue
            if id_ not in valid_ids:
                dead += 1
                continue
            seen.add(id_)
            result.append(id_)
        return result, dead, dupes, selfs
