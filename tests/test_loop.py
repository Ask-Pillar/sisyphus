"""Tests for LoopDetector — loop pattern detection (v1.2)."""

import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.loop import LoopDetector


@pytest.fixture
def stores():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo" / "memory"
        store = MemoryStore(base)
        refined = RefinedStore(base)
        yield store, refined


@pytest.fixture
def detector(stores):
    store, refined = stores
    return LoopDetector(store, refined)


class TestLoopDetect:
    def test_empty_store_no_loops(self, detector):
        assert detector.detect() == []

    def test_below_threshold_no_loops(self, detector):
        for i in range(2):
            detector.store.create(title="Same title", type="lesson", content=str(i))
        assert detector.detect() == []

    def test_detects_exact_duplicate_titles(self, detector):
        for i in range(3):
            detector.store.create(title="User likes dark mode", type="lesson", content=str(i))
        results = detector.detect()
        assert len(results) == 1
        assert results[0]["count"] == 3

    def test_marks_original_memories(self, detector):
        mems = []
        for i in range(3):
            m = detector.store.create(title="Repeat pattern", type="lesson", content=str(i))
            mems.append(m)
        detector.detect()
        updated = detector.store.get(mems[0].id)
        assert updated.detected_at != ""
        assert updated.repeat_count == 3
        assert updated.repeat_pattern != ""

    def test_creates_loop_record_in_refined(self, detector):
        for i in range(3):
            detector.store.create(title="Loop item", type="lesson", content=str(i))
        detector.detect()
        records = detector.refined.list_refined(type_filter="loop_record")
        assert len(records) == 1
        assert records[0].repeat_count == 3

    def test_multiple_distinct_patterns(self, detector):
        for i in range(3):
            detector.store.create(title="Pattern A", type="lesson", content=str(i))
            detector.store.create(title="Pattern B", type="lesson", content=str(i))
        results = detector.detect()
        assert len(results) == 2

    def test_different_titles_no_loops(self, detector):
        for i in range(5):
            detector.store.create(title=f"Unique title {i}", type="lesson", content=str(i))
        assert detector.detect() == []
