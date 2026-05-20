"""Tests for Memory dataclass upgrades and frontmatter format (v1.0 step1)."""

import pytest
import yaml
from pathlib import Path
from sisyphus.memory.store import MemoryStore, Memory


class TestMemoryDataclass:

    def test_new_fields_exist_with_defaults(self):
        mem = Memory(id="mem_001", type="lesson", title="T", content="C")
        assert hasattr(mem, "importance")
        assert mem.importance == 5
        assert hasattr(mem, "links")
        assert mem.links == []
        assert hasattr(mem, "status")
        assert mem.status == "active"
        assert hasattr(mem, "source")
        assert mem.source == ""
        assert hasattr(mem, "session_id")
        assert mem.session_id == ""

    def test_recall_fields_have_defaults(self):
        mem = Memory(id="mem_001", type="lesson", title="T", content="C")
        assert mem.recall_count == 0
        assert mem.last_recalled_at == ""

    def test_create_memory_with_all_new_fields(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "store1")
        mem = store.create(
            title="New fields test",
            type="lesson",
            content="Test content",
            tags=["a", "b"],
            importance=9,
            links=["mem_prev1", "mem_prev2"],
            status="archived",
            source="manual",
            session_id="ses_abc123",
        )
        assert mem.importance == 9
        assert mem.links == ["mem_prev1", "mem_prev2"]
        assert mem.status == "archived"
        assert mem.source == "manual"
        assert mem.session_id == "ses_abc123"


class TestFrontmatterFormat:

    def test_writes_frontmatter(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "store2")
        mem = store.create(title="FM test", type="lesson", content="Hello frontmatter.")
        topic_file = tmp_path / "store2" / f"{mem.id}.md"
        text = topic_file.read_text()
        assert text.startswith("---\n")
        assert "id: " + mem.id in text
        assert "title: FM test" in text
        assert "type: lesson" in text
        assert "---" in text

    def test_parses_frontmatter_correctly(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "store3")
        mem = store.create(title="Parse test", type="pattern", content="Parsed content.",
                           tags=["x", "y"], importance=8, status="active")
        fetched = store.get(mem.id)
        assert fetched is not None
        assert fetched.title == "Parse test"
        assert fetched.type == "pattern"
        assert fetched.content == "Parsed content."
        assert fetched.tags == ["x", "y"]
        assert fetched.importance == 8
        assert fetched.status == "active"

    def test_list_works_with_frontmatter(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "store4")
        store.create(title="A", type="lesson", content="one")
        store.create(title="B", type="pattern", content="two")
        store.create(title="C", type="lesson", content="three")
        all_mems = store.list()
        assert len(all_mems) == 3
        lessons = store.list(type_filter="lesson")
        assert len(lessons) == 2

    def test_backward_compatible_old_format(self, tmp_path):
        base = tmp_path / "store5"
        base.mkdir(parents=True, exist_ok=True)
        old_file = base / "mem_old.md"
        old_file.write_text(
            "# Old Memory\n\n"
            "- **ID**: mem_old\n"
            "- **Type**: lesson\n"
            "- **Created**: 2026-05-20T00:00:00+00:00\n"
            "- **Updated**: 2026-05-20T00:00:00+00:00\n"
            "- **Tags**: test, old\n\n"
            "Old content here.\n"
        )
        store = MemoryStore(base_path=base)
        mem = store.get("mem_old")
        assert mem is not None
        assert mem.title == "Old Memory"
        assert mem.type == "lesson"
        assert mem.content == "Old content here."
        assert mem.tags == ["test", "old"]

    def test_frontmatter_is_valid_yaml(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "store6")
        mem = store.create(title="YAML test", type="lesson", content="yaml",
                           tags=["valid"], importance=7)
        topic_file = tmp_path / "store6" / f"{mem.id}.md"
        text = topic_file.read_text()
        parts = text.split("---\n")
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert fm["id"] == mem.id
        assert fm["title"] == "YAML test"
        assert fm["type"] == "lesson"
        assert fm["importance"] == 7
        assert fm["tags"] == ["valid"]
