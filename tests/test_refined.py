"""Tests for refined memory store (v1.0 step2)."""

import yaml
import pytest
import tempfile
from pathlib import Path
from typing import Optional
from sisyphus.memory.store import Memory
from sisyphus.memory.refined import RefinedStore


@pytest.fixture
def refined_store():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo" / "memory"
        yield RefinedStore(base_path=base)


def _read_frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n")
    parts = text.split("---\n", 2)
    return yaml.safe_load(parts[1])


class TestRefinedStoreInit:
    def test_creates_refined_directory(self, refined_store):
        assert refined_store.base_path.exists()
        assert refined_store.base_path.is_dir()

    def test_creates_index(self, refined_store):
        index_file = refined_store.base_path / "INDEX.md"
        assert index_file.exists()


class TestCreateReflection:
    def test_creates_reflection_with_correct_type(self, refined_store):
        mem = refined_store.create_reflection(
            title="Test reflection",
            content="This is a reflection.",
            evidence=["mem_001", "mem_002"],
            importance=8,
            trigger="importance_sum=65",
            input_count=5,
        )
        assert mem.id.startswith("ref_")
        assert mem.type == "reflection"
        assert mem.title == "Test reflection"
        assert mem.content == "This is a reflection."
        assert mem.evidence == ["mem_001", "mem_002"]
        assert mem.importance == 8

    def test_reflection_has_trigger_in_frontmatter(self, refined_store):
        mem = refined_store.create_reflection(
            title="Triggered",
            content="Reflection content.",
            trigger="importance_sum=65",
            input_count=5,
            llm_calls=2,
            duration_ms=2300,
        )
        topic_file = refined_store.base_path / f"{mem.id}.md"
        fm = _read_frontmatter(topic_file)
        assert fm["trigger"] == "importance_sum=65"
        assert fm["input_count"] == 5
        assert fm["llm_calls"] == 2
        assert fm["duration_ms"] == 2300


class TestCreateSummary:
    def test_creates_summary_with_correct_type(self, refined_store):
        mem = refined_store.create_summary(
            title="Test summary",
            content="Summarized content.",
            compressed_from=["mem_001", "mem_002", "mem_003"],
        )
        assert mem.id.startswith("sum_")
        assert mem.type == "summary"
        assert mem.compressed_from == ["mem_001", "mem_002", "mem_003"]

    def test_summary_has_compressed_from_in_frontmatter(self, refined_store):
        mem = refined_store.create_summary(
            title="Summary",
            content="Summary content.",
            compressed_from=["mem_001", "mem_002"],
        )
        topic_file = refined_store.base_path / f"{mem.id}.md"
        fm = _read_frontmatter(topic_file)
        assert fm["compressed_from"] == ["mem_001", "mem_002"]


class TestCreateLoopRecord:
    def test_creates_loop_record_with_correct_type(self, refined_store):
        mem = refined_store.create_loop_record(
            title="Loop detected",
            content="Repeated pytest calls.",
            repeat_count=5,
            repeat_pattern="pytest test_xxx.py",
            resolved=True,
        )
        assert mem.id.startswith("loop_")
        assert mem.type == "loop_record"
        assert mem.repeat_count == 5
        assert mem.repeat_pattern == "pytest test_xxx.py"
        assert mem.resolved is True

    def test_loop_record_has_detected_at_in_frontmatter(self, refined_store):
        mem = refined_store.create_loop_record(
            title="Loop",
            content="Loop content.",
            repeat_count=3,
        )
        topic_file = refined_store.base_path / f"{mem.id}.md"
        fm = _read_frontmatter(topic_file)
        assert "detected_at" in fm


class TestListAndGet:
    def test_list_refined_returns_all(self, refined_store):
        r1 = refined_store.create_reflection(title="R1", content="C1")
        s1 = refined_store.create_summary(title="S1", content="C2")
        l1 = refined_store.create_loop_record(title="L1", content="C3")
        all_mems = refined_store.list_refined()
        assert len(all_mems) == 3

    def test_list_refined_filter_by_type(self, refined_store):
        refined_store.create_reflection(title="R1", content="C1")
        refined_store.create_summary(title="S1", content="C2")
        refined_store.create_loop_record(title="L1", content="C3")
        reflections = refined_store.list_refined(type_filter="reflection")
        assert len(reflections) == 1
        summaries = refined_store.list_refined(type_filter="summary")
        assert len(summaries) == 1
        loops = refined_store.list_refined(type_filter="loop_record")
        assert len(loops) == 1

    def test_get_refined_by_id(self, refined_store):
        created = refined_store.create_reflection(
            title="Get me", content="To be retrieved.",
            evidence=["mem_001"],
        )
        retrieved = refined_store.get_refined(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == "Get me"
        assert retrieved.type == "reflection"

    def test_get_nonexistent_returns_none(self, refined_store):
        assert refined_store.get_refined("nonexistent") is None


class TestBackwardCompatibility:
    def test_old_format_refined_file_still_readable(self, refined_store):
        old_file = refined_store.base_path / "ref_old001.md"
        old_file.write_text(
            "# Old reflection\n\n"
            "- **ID**: ref_old001\n"
            "- **Type**: reflection\n"
            "- **Created**: 2026-01-01\n"
            "- **Tags**: old\n\n"
            "Old content.\n"
        )
        mem = refined_store.get_refined("ref_old001")
        assert mem is not None
        assert mem.title == "Old reflection"
        assert mem.content == "Old content."
