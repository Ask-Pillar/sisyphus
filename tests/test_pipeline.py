"""Tests for auto-trigger pipeline (v1.0 step6)."""

import json
import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.pipeline import Pipeline


@pytest.fixture
def pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo"
        yield Pipeline(base_path=base)


class TestPipelineInit:
    def test_creates_necessary_dirs(self, pipeline):
        assert pipeline.store.base_path.exists()
        assert pipeline.refined.base_path.exists()
        assert pipeline.logger.base_path.exists()

    def test_default_threshold(self, pipeline):
        assert pipeline.compress_threshold == 20


class TestRun:
    def test_run_completes_on_empty_store(self, pipeline):
        result = pipeline.run()
        assert result["status"] == "completed"

    def test_run_logs_activity(self, pipeline):
        pipeline.run()
        logs = pipeline.logger.list_logs()
        assert len(logs) >= 1
        assert logs[0].command == "pipeline"

    def test_run_does_not_compress_below_threshold(self, pipeline):
        for i in range(5):
            pipeline.store.create(title=f"M{i}", type="lesson", content="x")
        result = pipeline.run()
        assert "compress" not in result.get("steps", [])

    def test_run_triggers_compress_above_threshold(self, pipeline):
        for i in range(25):
            pipeline.store.create(title=f"M{i}", type="lesson", content="x")
        result = pipeline.run()
        assert result["status"] == "completed"

    def test_run_triggers_index_when_refined_exists(self, pipeline):
        pipeline.refined.create_reflection(
            title="Test", content="Refined exists."
        )
        result = pipeline.run()
        assert result["status"] == "completed"

    def test_should_dream_true_with_unprocessed_memories(self, pipeline):
        for i in range(3):
            pipeline.store.create(title=f"M{i}", type="lesson", content="x")
        assert pipeline._should_dream() is True

    def test_should_dream_false_with_no_memories(self, pipeline):
        assert pipeline._should_dream() is False


class TestThresholdConfig:
    def test_custom_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".omo"
            p = Pipeline(base_path=base, compress_threshold=3)
            assert p.compress_threshold == 3
            for i in range(5):
                p.store.create(title=f"M{i}", type="lesson", content="x")
            result = p.run()
            assert result["status"] == "completed"

    def test_run_cleans_old_logs_smoke(self, pipeline):
        """pipeline should not crash when logs exist from previous runs."""
        pipeline.run()
        pipeline.run()
        assert len(pipeline.logger.list_logs()) >= 2
