"""Tests for TreeBuilder."""
import tempfile
from pathlib import Path

import pytest

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.tree import TreeStore
from sisyphus.memory.tree_builder import TreeBuilder


@pytest.fixture
def builder():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo" / "memory"
        store = MemoryStore(base)
        refined = RefinedStore(base)
        tree = TreeStore(base)
        yield TreeBuilder(tree, store, refined)


class TestTitleSimilarity:
    def test_exact_match(self):
        assert TreeBuilder._title_similarity("hello world", "hello world") == 1.0

    def test_partial_overlap(self):
        sim = TreeBuilder._title_similarity("python typing", "python list")
        assert 0.3 < sim < 0.6

    def test_no_overlap(self):
        assert TreeBuilder._title_similarity("aaa bbb", "ccc ddd") == 0.0

    def test_empty(self):
        assert TreeBuilder._title_similarity("", "hello") == 0.0
        assert TreeBuilder._title_similarity("hello", "") == 0.0


class TestSummaryFromTitles:
    def test_single(self):
        assert TreeBuilder._summary_from_titles(["A"]) == "A"

    def test_multiple(self):
        assert TreeBuilder._summary_from_titles(["A", "B"]) == "A; B"

    def test_empty(self):
        assert TreeBuilder._summary_from_titles([]) == ""


class TestTreeBuilderBuild:
    def test_build_with_mixed_types(self, builder):
        builder.store.create(title="Python typing", type="lesson", content="use Optional")
        builder.store.create(title="Python list", type="lesson", content="use List")
        builder.store.create(title="React state", type="idea", content="useState")
        builder.store.create(title="React effect", type="idea", content="useEffect")

        l1_ids = builder.build()
        assert len(l1_ids) == 2

    def test_l0_summary_exists(self, builder):
        builder.store.create(title="Test", type="lesson", content="x")
        builder.build()
        l0 = builder.tree.get_node("l0")
        assert l0 is not None
        assert l0.summary != ""

    def test_l1_summary_is_title_concat(self, builder):
        builder.store.create(title="First", type="lesson", content="a")
        builder.store.create(title="Second", type="lesson", content="b")
        builder.build()
        l1_nodes = builder.tree.list_nodes(level=1)
        assert len(l1_nodes) == 1
        assert "First" in l1_nodes[0].summary
        assert "Second" in l1_nodes[0].summary

    def test_fine_cluster_threshold(self, builder):
        """Similar titles cluster together, different one stays separate."""
        builder.store.create(title="python typing", type="lesson", content="x")
        builder.store.create(title="python list", type="lesson", content="y")
        builder.store.create(title="completely different topic", type="lesson", content="z")
        l1_ids = builder.build()
        l1 = builder.tree.get_node(l1_ids[0])
        assert l1 is not None
        assert len(l1.children) >= 2

    def test_build_empty_no_crash(self, builder):
        l1_ids = builder.build()
        assert l1_ids == []

    def test_idempotent_build(self, builder):
        builder.store.create(title="Python", type="lesson", content="x")
        builder.store.create(title="React", type="idea", content="y")
        builder.build()
        first_l1 = len(builder.tree.list_nodes(level=1))
        builder.build()
        second_l1 = len(builder.tree.list_nodes(level=1))
        assert second_l1 == first_l1, f"idempotent build: {second_l1} != {first_l1}"

    def test_backward_compatible(self, builder):
        """Existing MemoryStore data still works after TreeBuilder build."""
        mem = builder.store.create(title="Legacy", type="lesson", content="keep")
        builder.build()
        fetched = builder.store.get(mem.id)
        assert fetched is not None
        assert fetched.title == "Legacy"

    def test_refined_memories_included(self, builder):
        builder.refined.create_reflection(title="Reflection A", content="ref")
        builder.refined.create_reflection(title="Reflection B", content="ref")
        l1_ids = builder.build()
        assert len(l1_ids) >= 1
