import tempfile
from pathlib import Path

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.tree import TreeStore
from sisyphus.memory.tree_builder import TreeBuilder
from sisyphus.memory.tree_retriever import TreeRetriever


TOPIC_ITEMS = {
    "Storage": ["存储架构: 四层 (RAW/REFINED/DREAM/RECALL), append-only文件存储",
                 "RAW层: 原始记忆append-only, 前端matter解析, 永不删改",
                 "BM25参数: k1=1.2, b=0.75, CJK二分词+EN分词"],
    "Subagent": ["子进程调度: SubagentLauncher通过stdin/stdout JSON-RPC通信",
                  "离线模式: fixture读JSON模拟响应零API验证"],
    "Pipeline": ["流水线: 按序执行recall->compress->dream->refine"],
}


def _setup_tree():
    tmp = Path(tempfile.mkdtemp()) / "mem"
    store = MemoryStore(base_path=tmp)
    refined = RefinedStore(base_path=tmp)
    for topic, items in TOPIC_ITEMS.items():
        for idx, content in enumerate(items):
            store.create(title="{}_{}".format(topic, idx), type=topic, content=content,
                         tags=[topic.lower()], importance=0.5 + idx * 0.1)
    tree = TreeStore(base_path=tmp)
    TreeBuilder(tree, store, refined).build()
    return tree


def test_browse_finds_subtree():
    tree = _setup_tree()
    tr = TreeRetriever(tree)
    results = tr.browse("SubagentLauncher通信", top_k=3)
    assert results, "expected results for SubagentLauncher query"
    titles = [n.title for n, _ in results]
    assert "Subagent_0" in titles, "should find Subagent_0"
    assert len(results) <= 3


def test_browse_empty_query():
    tree = _setup_tree()
    tr = TreeRetriever(tree)
    results = tr.browse("", top_k=3)
    assert results == [], "empty query should return empty"


def test_browse_returns_correct_l1():
    tree = _setup_tree()
    tr = TreeRetriever(tree)
    results = tr.browse("Pipeline流水线顺序", top_k=2)
    assert results
    pipelines = [n for n, _ in results if n.title.startswith("Pipeline")]
    assert pipelines, "should find Pipeline leaves"


def test_match_l1_picks_storage():
    tree = _setup_tree()
    tr = TreeRetriever(tree)
    l1_nodes = tree.list_nodes(level=1)
    best = tr._match_l1("存储架构有几层", l1_nodes)
    assert best is not None
    assert "Storage" in best.title


def test_search_subtree_ranks_correctly():
    tree = _setup_tree()
    tr = TreeRetriever(tree)
    l1_nodes = tree.list_nodes(level=1)
    storage_l1 = [n for n in l1_nodes if "Storage" in n.title][0]
    results = tr._search_subtree(storage_l1, "BM25参数", top_k=3)
    titles = [n.title for n, _ in results]
    assert titles[0] == "Storage_2", "BM25参数 query should rank Storage_2 first"
