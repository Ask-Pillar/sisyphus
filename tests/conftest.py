"""Shared fixtures for Sisyphus tests."""

import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.store import MemoryStore


@pytest.fixture
def memory_store():
    """Create a temporary MemoryStore."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo" / "memory"
        yield MemoryStore(base_path=base)
