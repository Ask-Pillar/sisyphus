"""Tests for TreeStore."""
import json
import tempfile
from pathlib import Path

import pytest

from sisyphus.memory.tree import TreeStore, TreeNode
from sisyphus.memory.store import MemoryStore


@pytest.fixture
def tree_store():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo" / "memory"
        yield TreeStore(base_path=base)


class TestTreeStoreInit:
    def test_init_creates_dirs(self, tree_store):
        assert tree_store._tree_root.exists()
        assert tree_store._l1_dir.exists()
        assert tree_store._l2_dir.exists()

    def test_init_creates_l0(self, tree_store):
        l0 = tree_store.get_node("l0")
        assert l0 is not None
        assert l0.level == 0
        assert l0.title == "Memory Root"

    def test_init_creates_meta(self, tree_store):
        meta = tree_store._load_meta()
        assert "l0" in meta
        assert meta["l0"]["level"] == 0


class TestTreeStoreCRUD:
    def test_add_leaf_updates_meta(self, tree_store):
        leaf = tree_store.add_leaf("l0", "Test Memory", "A test leaf")
        meta = tree_store._load_meta()
        assert leaf.id in meta
        assert meta[leaf.id]["parent_id"] == "l0"
        assert meta[leaf.id]["level"] == 2
        assert meta[leaf.id]["title"] == "Test Memory"

    def test_add_leaf_creates_only_l2_file(self, tree_store):
        before = set(tree_store._l2_dir.glob("*.json"))
        leaf = tree_store.add_leaf("l0", "Isolated", "content")
        after = set(tree_store._l2_dir.glob("*.json"))
        new_files = after - before
        assert len(new_files) == 1
        assert leaf.id in new_files.pop().stem

    def test_add_leaf_updates_parent_children(self, tree_store):
        leaf = tree_store.add_leaf("l0", "Child", "content")
        l0 = tree_store.get_node("l0")
        assert leaf.id in l0.children

    def test_get_node_returns_correct(self, tree_store):
        leaf = tree_store.add_leaf("l0", "GetTest", "content")
        fetched = tree_store.get_node(leaf.id)
        assert fetched is not None
        assert fetched.id == leaf.id
        assert fetched.title == "GetTest"
        assert fetched.level == 2
        assert fetched.parent_id == "l0"

    def test_get_node_not_found(self, tree_store):
        assert tree_store.get_node("nonexistent") is None

    def test_get_subtree(self, tree_store):
        l1 = TreeNode(id="l1_abc", parent_id="l0", level=1, title="Cluster", summary="")
        tree_store._write_node(l1)
        tree_store._update_meta_add(l1)
        leaf_a = tree_store.add_leaf("l1_abc", "A", "content a")
        leaf_b = tree_store.add_leaf("l1_abc", "B", "content b")

        subtree = tree_store.get_subtree("l1_abc")
        assert len(subtree) == 3
        assert subtree[0].id == "l1_abc"
        leaf_ids = {n.id for n in subtree[1:]}
        assert leaf_a.id in leaf_ids
        assert leaf_b.id in leaf_ids

    def test_get_path(self, tree_store):
        l1 = TreeNode(id="l1_path", parent_id="l0", level=1, title="PathCluster", summary="")
        tree_store._write_node(l1)
        tree_store._update_meta_add(l1)
        leaf = tree_store.add_leaf("l1_path", "Deep", "content")
        path = tree_store.get_path(leaf.id)
        assert len(path) == 3
        assert path[0].id == "l0"
        assert path[1].id == "l1_path"
        assert path[2].id == leaf.id

    def test_get_path_root(self, tree_store):
        path = tree_store.get_path("l0")
        assert len(path) == 1
        assert path[0].id == "l0"

    def test_list_nodes_by_level(self, tree_store):
        l1 = TreeNode(id="l1_list", parent_id="l0", level=1, title="ListCluster", summary="")
        tree_store._write_node(l1)
        tree_store._update_meta_add(l1)
        tree_store.add_leaf("l1_list", "Leaf1", "x")
        tree_store.add_leaf("l1_list", "Leaf2", "y")

        l0_nodes = tree_store.list_nodes(level=0)
        assert len(l0_nodes) == 1
        assert l0_nodes[0].id == "l0"

        l1_nodes = tree_store.list_nodes(level=1)
        assert len(l1_nodes) == 1

        l2_nodes = tree_store.list_nodes(level=2)
        assert len(l2_nodes) == 2

    def test_backward_compatible_raw_store(self):
        """TreeStore does not interfere with existing MemoryStore."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".omo" / "memory"
            mem_store = MemoryStore(base_path=base)
            mem_store.create(title="Legacy", type="lesson", content="old data")

            tree_store = TreeStore(base_path=base)
            leaf = tree_store.add_leaf("l0", "New", "new data")

            mems = mem_store.list()
            assert len(mems) == 1
            assert mems[0].title == "Legacy"


class TestTreeStoreConcurrency:
    def test_concurrent_meta_write(self, tree_store):
        """Two sequential adds should not corrupt _meta.json."""
        a = tree_store.add_leaf("l0", "A", "aaa")
        b = tree_store.add_leaf("l0", "B", "bbb")
        meta = tree_store._load_meta()
        assert a.id in meta
        assert b.id in meta
        assert meta[a.id]["parent_id"] == "l0"
        assert meta[b.id]["parent_id"] == "l0"

    def test_meta_is_valid_json(self, tree_store):
        tree_store.add_leaf("l0", "X", "x")
        tree_store.add_leaf("l0", "Y", "y")
        raw = tree_store._meta_path.read_text()
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_meta_rename_atomic(self, tree_store):
        """_meta.json written via atomic_write — content complete, .tmp cleaned."""
        tree_store.add_leaf("l0", "Atomic", "test")
        raw = tree_store._meta_path.read_text()
        data = json.loads(raw)
        assert "l0" in data
        assert not tree_store._meta_path.with_suffix(".json.tmp").exists()
