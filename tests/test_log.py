"""Tests for structured logging (v1.0 step3)."""

import yaml
import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.log import LogStore, LogEntry


@pytest.fixture
def log_store():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo"
        yield LogStore(base_path=base)


def _read_log_frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n")
    parts = text.split("---\n", 2)
    return yaml.safe_load(parts[1])


class TestLogStoreInit:
    def test_creates_logs_directory(self, log_store):
        assert log_store.base_path.exists()
        assert log_store.base_path.is_dir()


class TestCreateLog:
    def test_creates_log_file(self, log_store):
        log = log_store.create_log(
            command="dream",
            body="## Input\n- mem_001\n",
            trigger="auto (importance_sum=65)",
        )
        assert log.id is not None
        assert log.command == "dream"
        log_file = log_store.base_path / f"{log.id}.log"
        assert log_file.exists()

    def test_log_has_frontmatter(self, log_store):
        log = log_store.create_log(command="extract", body="Extracted 3 memories.")
        log_file = log_store.base_path / f"{log.id}.log"
        text = log_file.read_text()
        assert text.startswith("---\n")

    def test_frontmatter_contains_required_fields(self, log_store):
        log = log_store.create_log(
            command="compress",
            body="Compressed 10 into 1.",
            trigger="threshold exceeded",
        )
        log_file = log_store.base_path / f"{log.id}.log"
        fm = _read_log_frontmatter(log_file)
        assert fm["command"] == "compress"
        assert "started" in fm
        assert fm["trigger"] == "threshold exceeded"
        assert fm["status"] == "running"
        assert fm["duration_ms"] == 0

    def test_log_body_after_frontmatter(self, log_store):
        log = log_store.create_log(
            command="dream",
            body="## Phase 1\nLLM call 1\n\n## Phase 2\nLLM call 2",
        )
        log_file = log_store.base_path / f"{log.id}.log"
        text = log_file.read_text()
        parts = text.split("---\n", 2)
        assert "## Phase 1" in parts[2]
        assert "LLM call 1" in parts[2]


class TestUpdateLog:
    def test_update_status_and_duration(self, log_store):
        log = log_store.create_log(command="dream", body="Running...")
        updated = log_store.update_log(
            log.id,
            status="completed",
            duration_ms=2300,
        )
        assert updated is not None
        assert updated.status == "completed"
        assert updated.duration_ms == 2300
        log_file = log_store.base_path / f"{log.id}.log"
        fm = _read_log_frontmatter(log_file)
        assert fm["status"] == "completed"
        assert fm["duration_ms"] == 2300

    def test_update_body(self, log_store):
        log = log_store.create_log(command="dream", body="Initial body.")
        updated = log_store.update_log(log.id, body="Updated body with results.")
        assert updated.body == "Updated body with results."
        log_file = log_store.base_path / f"{log.id}.log"
        text = log_file.read_text()
        assert "Updated body" in text


class TestListLogs:
    def test_list_logs_in_order(self, log_store):
        log1 = log_store.create_log(command="extract", body="First.")
        log2 = log_store.create_log(command="dream", body="Second.")
        logs = log_store.list_logs()
        assert len(logs) == 2

    def test_get_log_by_id(self, log_store):
        created = log_store.create_log(command="test", body="Get me.")
        retrieved = log_store.get_log(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.command == "test"

    def test_get_nonexistent_returns_none(self, log_store):
        assert log_store.get_log("nonexistent") is None
