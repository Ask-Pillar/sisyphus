"""Integration tests for subprocess pipeline with fixture mode.

Tests SubagentLauncher + subprocess spawning + task serialization +
result deserialization — all without calling any LLM API.
"""

import json
import pytest
from pathlib import Path

from sisyphus.memory.store import Memory, MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.subagent import SubagentLauncher

FIXTURE = Path(__file__).parent / "fixtures" / "full.json"


class TestSubprocessFixture:
    """Verify subprocess pipeline works with fixture (no LLM calls)."""

    def test_dream_returns_reflections(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        refined = RefinedStore(base_path=tmp_path / "mem")
        subagent = SubagentLauncher(store_path=tmp_path / "mem", fixture_path=str(FIXTURE))
        mem1 = store.create(title="Fact A", type="lesson", content="x")
        mem2 = store.create(title="Fact B", type="lesson", content="y")
        result = subagent.dream([mem1, mem2])
        assert result["status"] == "ok"
        assert len(result["reflections"]) == 2

    def test_recall_search_returns_ids(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        subagent = SubagentLauncher(store_path=tmp_path / "mem", fixture_path=str(FIXTURE))
        mem = store.create(title="Fact", type="lesson", content="z")
        result = subagent.recall_search([mem], "test query")
        assert result["status"] == "ok"
        assert len(result["memory_ids"]) == 3

    def test_recall_relevant_returns_score(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        subagent = SubagentLauncher(store_path=tmp_path / "mem", fixture_path=str(FIXTURE))
        mem = store.create(title="Fact", type="lesson", content="z")
        result = subagent.recall_relevant(mem, "query")
        assert result["status"] == "ok"
        assert 0 <= result["relevance"] <= 1

    def test_classify_types_returns_types(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        subagent = SubagentLauncher(store_path=tmp_path / "mem", fixture_path=str(FIXTURE))
        result = subagent.classify_types(["lesson", "pattern"], "query")
        assert result["status"] == "ok"
        assert "lesson" in result["types"]

    def test_compress_returns_deleted_count(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        subagent = SubagentLauncher(store_path=tmp_path / "mem", fixture_path=str(FIXTURE))
        result = subagent.compress(threshold=10, keep_recent=3)
        assert result["status"] == "ok"
        assert result["deleted_count"] == 5

    def test_subprocess_writes_result_file(self, tmp_path):
        """Verify the subprocess actually creates the result file on disk."""
        import tempfile, os, subprocess, sys

        store = MemoryStore(base_path=tmp_path / "mem")
        mem = store.create(title="Test", type="lesson", content="x")

        # Manually build task JSON matching SubagentLauncher format
        from dataclasses import asdict
        task = {
            "task_type": "recall_search",
            "store_path": str(tmp_path / "mem"),
            "memories": [asdict(mem)],
            "query": "test",
        }

        fd, task_path = tempfile.mkstemp(suffix=".json", prefix="sisy_task_")
        with os.fdopen(fd, "w") as f:
            json.dump(task, f)

        # Spawn subprocess with fixture
        proc = subprocess.run(
            [sys.executable, "-m", "sisyphus.memory.subagent", task_path, "--fixture", str(FIXTURE)],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"

        # Check result file exists and is valid JSON
        result_path = task_path + ".result"
        assert os.path.exists(result_path), "result file not created"
        with open(result_path) as f:
            result = json.load(f)
        assert result["status"] == "ok"
        assert "memory_ids" in result

        # Cleanup
        os.unlink(task_path)
        os.unlink(result_path)

    def test_unknown_task_type(self, tmp_path):
        store = MemoryStore(base_path=tmp_path / "mem")
        subagent = SubagentLauncher(store_path=tmp_path / "mem", fixture_path=str(FIXTURE))
        # Use a fixture file that doesn't have 'nonexistent' task type
        mem = store.create(title="X", type="lesson", content="y")
        # Send a task type that the fixture doesn't have
        import tempfile, os, subprocess, sys
        task = {
            "task_type": "nonexistent",
            "store_path": str(tmp_path / "mem"),
            "memories": [],
        }
        fd, task_path = tempfile.mkstemp(suffix=".json", prefix="sisy_task_")
        with os.fdopen(fd, "w") as f:
            json.dump(task, f)
        proc = subprocess.run(
            [sys.executable, "-m", "sisyphus.memory.subagent", task_path, "--fixture", str(FIXTURE)],
            capture_output=True, text=True, timeout=30,
        )
        result_path = task_path + ".result"
        with open(result_path) as f:
            result = json.load(f)
        # No fixture for 'nonexistent' → error
        assert "error" in result.get("status", "") or "error" in result.get("message", "").lower()
        os.unlink(task_path)
        os.unlink(result_path)

    def test_corrupt_fixture_handled(self, tmp_path):
        """Fixture file with invalid JSON → graceful error."""
        import tempfile, os, subprocess, sys

        # Create corrupt fixture
        bad_fixture = tmp_path / "bad_fixture.json"
        bad_fixture.write_text("{not valid json")

        task = {
            "task_type": "recall_search",
            "store_path": str(tmp_path / "mem"),
            "memories": [],
            "query": "x",
        }
        fd, task_path = tempfile.mkstemp(suffix=".json", prefix="sisy_task_")
        with os.fdopen(fd, "w") as f:
            json.dump(task, f)

        proc = subprocess.run(
            [sys.executable, "-m", "sisyphus.memory.subagent", task_path, "--fixture", str(bad_fixture)],
            capture_output=True, text=True, timeout=30,
        )
        result_path = task_path + ".result"
        with open(result_path) as f:
            result = json.load(f)
        assert result["status"] == "error"
        os.unlink(task_path)
        os.unlink(result_path)
