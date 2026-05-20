"""Link analyzer — auto-association between memories.

Discovers relationships between memories (same tags, shared topics, etc.)
and creates bidirectional links via the `links` field.
"""

from typing import List, Set, Tuple

from sisyphus.memory.store import Memory, MemoryStore

LinkPair = Tuple[str, str]  # (mem_id_1, mem_id_2)


class LinkAnalyzer:
    """Analyzes memories and establishes bidirectional links."""

    def __init__(self, store: MemoryStore):
        self.store = store

    def analyze(self) -> List[LinkPair]:
        """Scan all memories and create bidirectional links.

        Returns list of (id1, id2) pairs that were linked.
        """
        memories = self.store.list()
        pairs = self._find_tag_pairs(memories)
        created = []
        for id_a, id_b in pairs:
            if self._link_pair(id_a, id_b):
                created.append((id_a, id_b))
        return created

    def _find_tag_pairs(self, memories: List[Memory]) -> Set[LinkPair]:
        """Find memory pairs that share at least one tag."""
        tag_groups = {}
        for m in memories:
            for tag in m.tags:
                tag_groups.setdefault(tag, []).append(m.id)

        pairs = set()
        for ids in tag_groups.values():
            if len(ids) < 2:
                continue
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    pair = tuple(sorted([ids[i], ids[j]]))
                    pairs.add(pair)
        return pairs

    def _link_pair(self, id_a: str, id_b: str) -> bool:
        """Bidirectionally link two memories. Returns True if changed."""
        ma = self.store.get(id_a)
        mb = self.store.get(id_b)
        if ma is None or mb is None:
            return False
        changed = False
        if id_b not in ma.links:
            ma.links = ma.links + [id_b]
            changed = True
        if id_a not in mb.links:
            mb.links = mb.links + [id_a]
            changed = True
        if changed:
            self.store.update(ma.id, links=ma.links)
            self.store.update(mb.id, links=mb.links)
        return changed
