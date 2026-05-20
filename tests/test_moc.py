"""Tests for MOC generation (v1.0 step4)."""

import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.moc import MocGenerator


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo" / "memory"
        yield MemoryStore(base_path=base)


@pytest.fixture
def generator(store):
    refined = RefinedStore(base_path=store.base_path)
    return MocGenerator(store, refined_store=refined)


class TestMocGeneration:
    def test_generate_creates_index(self, generator):
        generator.generate()
        index_file = generator.store.base_path / "INDEX.md"
        assert index_file.exists()

    def test_empty_store_index_has_header(self, generator):
        generator.generate()
        index = (generator.store.base_path / "INDEX.md").read_text()
        assert index.startswith("# Sisyphus Memory Index")

    def test_index_groups_by_type(self, generator):
        generator.store.create(title="A", type="lesson", content="C1")
        generator.store.create(title="B", type="decision", content="C2")
        generator.store.create(title="C", type="lesson", content="C3")
        generator.generate()
        index = (generator.store.base_path / "INDEX.md").read_text()
        assert "## lesson" in index
        assert "## decision" in index

    def test_index_uses_wikilinks(self, generator):
        mem = generator.store.create(title="My title", type="pattern", content="Content.")
        generator.generate()
        index = (generator.store.base_path / "INDEX.md").read_text()
        assert f"[[{mem.id}|My title]]" in index

    def test_refined_memories_included(self, generator):
        refined = RefinedStore(base_path=generator.store.base_path)
        refined.create_reflection(title="Reflection 1", content="Reflected.")
        refined.create_summary(title="Summary 1", content="Summarized.")
        generator.generate()
        index = (generator.store.base_path / "INDEX.md").read_text()
        assert "## reflection" in index
        assert "## summary" in index

    def test_multiple_entries_under_same_type(self, generator):
        m1 = generator.store.create(title="Lesson A", type="lesson", content="C1")
        m2 = generator.store.create(title="Lesson B", type="lesson", content="C2")
        generator.generate()
        index = (generator.store.base_path / "INDEX.md").read_text()
        assert f"[[{m1.id}|Lesson A]]" in index
        assert f"[[{m2.id}|Lesson B]]" in index

    def test_empty_type_not_in_index(self, generator):
        generator.generate()
        index = (generator.store.base_path / "INDEX.md").read_text()
        assert index.count("\n## ") == 0

    def test_generate_dimension_creates_moc_file(self, generator):
        generator.store.create(
            title="Project rule", type="lesson", content="C",
            tags=["project:sisyphus"],
        )
        generator.generate_dimension("project", tag="project:sisyphus")
        moc_file = generator.store.base_path / "MOC-project.md"
        assert moc_file.exists()
        content = moc_file.read_text()
        assert "# project维度 — project" in content
