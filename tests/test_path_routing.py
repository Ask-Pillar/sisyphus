import tempfile
from pathlib import Path

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.tree import TreeStore
from sisyphus.memory.tree_builder import TreeBuilder
from sisyphus.memory.retrieval import ContextRetriever

TOPIC_ITEMS = {
    "Storage": ["存储架构: 四层 (RAW/REFINED/DREAM/RECALL), append-only文件存储",
                 "RAW层: 原始记忆append-only, 前端matter解析"],
    "Subagent": ["子进程调度: SubagentLauncher通过stdin/stdout JSON-RPC通信"],
}


def _setup():
    tmp = Path(tempfile.mkdtemp()) / "mem"
    store = MemoryStore(base_path=tmp)
    refined = RefinedStore(base_path=tmp)
    for topic, items in TOPIC_ITEMS.items():
        for idx, content in enumerate(items):
            store.create(title="{}_{}".format(topic, idx), type=topic, content=content,
                         tags=[topic.lower()], importance=0.5 + idx * 0.1)
    tree = TreeStore(base_path=tmp)
    TreeBuilder(tree, store, refined).build()
    return store, refined, tree


def test_choose_path_short_query():
    assert ContextRetriever._choose_path("存储") == "A"


def test_choose_path_fuzzy_query():
    assert ContextRetriever._choose_path("存储有哪些内容") == "A"


def test_choose_path_precise_query():
    assert ContextRetriever._choose_path("BM25参数k1的默认值具体设置为多少") == "B"


def test_retrieve_path_a_with_tree():
    store, refined, tree = _setup()
    cr = ContextRetriever(store, refined, subagent=None, tree=tree)
    results = cr.retrieve("有什么存储相关的", top_k=3)
    assert results
    titles = [m.title for m, _ in results]
    assert any(t.startswith("Storage") for t in titles)


def test_retrieve_path_b_without_tree():
    store, refined, _ = _setup()
    cr = ContextRetriever(store, refined, subagent=None, tree=None)
    results = cr.retrieve("SubagentLauncher通信协议", top_k=3)
    assert results


def test_retrieve_null_tree_falls_back():
    store, refined, _ = _setup()
    cr = ContextRetriever(store, refined, subagent=None, tree=None)
    results = cr.retrieve("有哪些存储", top_k=3)
    assert results
