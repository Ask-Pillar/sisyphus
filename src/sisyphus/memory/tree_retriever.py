from typing import List, Optional, Tuple

from sisyphus.memory.retrieval import BM25Ranker, _tokenize
from sisyphus.memory.tree import TreeStore, TreeNode


class TreeRetriever:
    def __init__(self, tree: TreeStore):
        self.tree = tree

    def browse(self, query: str, top_k: int = 5) -> List[Tuple[TreeNode, float]]:
        l1_nodes = self.tree.list_nodes(level=1)
        if not l1_nodes:
            return []
        best_l1 = self._match_l1(query, l1_nodes)
        if not best_l1:
            return []
        return self._search_subtree(best_l1, query, top_k)

    def _match_l1(self, query: str, l1_nodes: List[TreeNode]) -> Optional[TreeNode]:
        class FakeMem:
            def __init__(self, title, content):
                self.title = title
                self.content = content
                self.tags = []
        best_score = -1.0
        best_l1 = None
        for l1 in l1_nodes:
            children = self.tree.get_subtree(l1.id)
            leaves = [n for n in children if n.level == 2]
            if not leaves:
                continue
            fake = [FakeMem(n.title, n.summary) for n in leaves]
            bm = BM25Ranker(fake, k1=1.2, b=0.75)
            results = bm.search(query, top_k=1)
            if results and results[0][1] > best_score:
                best_score = results[0][1]
                best_l1 = l1
        return best_l1

    def _search_subtree(self, l1_node: TreeNode, query: str, top_k: int) -> List[Tuple[TreeNode, float]]:
        children = self.tree.get_subtree(l1_node.id)
        leaves = [n for n in children if n.level == 2]
        if not leaves:
            return []
        class FakeMem:
            def __init__(self, title, content):
                self.title = title
                self.content = content
                self.tags = []
        fake = [FakeMem(n.title, n.summary) for n in leaves]
        bm = BM25Ranker(fake, k1=1.2, b=0.75)
        results = bm.search(query, top_k=top_k)
        title_map = {n.title: n for n in leaves}
        return [(title_map[m.title], s) for m, s in results if m.title in title_map]
