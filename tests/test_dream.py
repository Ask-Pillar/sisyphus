"""Tests for DreamEngine — LLM reflection system (v1.1 step1)."""

import json
import pytest
import tempfile
from pathlib import Path
from typing import List, Optional
from sisyphus.memory.store import MemoryStore, Memory
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.dream import DreamEngine


def _make_mock_llm(responses: Optional[List[dict]] = None):
    """Create a mock LLM that returns structured JSON responses."""
    if responses is None:
        responses = [{
            "reflections": [{
                "title": "Pattern: TDD workflow",
                "content": "The project follows TDD with red-green-clean cycles.",
                "importance": 8,
                "evidence": [],
            }]
        }]

    class MockLLM:
        def __init__(self):
            self.call_count = 0

        def ask(self, prompt: str) -> str:
            idx = min(self.call_count, len(responses) - 1)
            self.call_count += 1
            return json.dumps(responses[idx])

    return MockLLM()


@pytest.fixture
def stores():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo" / "memory"
        store = MemoryStore(base_path=base)
        refined = RefinedStore(base_path=base)
        yield store, refined


@pytest.fixture
def populated_store(stores):
    store, refined = stores
    store.create(title="Use Optional not |", type="lesson",
                 content="Python 3.9 requires Optional[X] syntax.",
                 tags=["python"])
    store.create(title="TDD red-green-clean", type="pattern",
                 content="Write tests first, then implement, then refactor.",
                 tags=["workflow"])
    store.create(title="File-based storage", type="decision",
                 content="Using markdown files as SSOT, not a database.",
                 tags=["architecture"])
    return store, refined


class TestDreamEngineInit:
    def test_init_requires_store_refined_llm(self):
        mock_llm = _make_mock_llm()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".omo" / "memory"
            store = MemoryStore(base_path=base)
            refined = RefinedStore(base_path=base)
            engine = DreamEngine(store=store, refined_store=refined, llm_client=mock_llm)
            assert engine is not None


class TestDream:
    def test_dream_empty_store_returns_empty(self, stores):
        store, refined = stores
        mock_llm = _make_mock_llm([{"reflections": []}])
        engine = DreamEngine(store=store, refined_store=refined, llm_client=mock_llm)
        result = engine.dream()
        assert len(result) == 0

    def test_dream_generates_reflections(self, populated_store):
        store, refined = populated_store
        mock_llm = _make_mock_llm([{
            "reflections": [{
                "title": "Core conventions",
                "content": "The project has three key conventions: type annotations, TDD, SSOT.",
                "importance": 8,
                "evidence": [
                    store.list()[0].id,
                    store.list()[1].id,
                    store.list()[2].id,
                ],
            }]
        }])
        engine = DreamEngine(store=store, refined_store=refined, llm_client=mock_llm)
        result = engine.dream()
        assert len(result) == 1
        assert result[0].type == "reflection"
        assert result[0].title == "Core conventions"
        assert result[0].importance == 8

    def test_reflection_has_evidence_in_frontmatter(self, populated_store):
        store, refined = populated_store
        ids = [m.id for m in store.list()]
        mock_llm = _make_mock_llm([{
            "reflections": [{
                "title": "Core conventions",
                "content": "Three key conventions identified.",
                "importance": 7,
                "evidence": ids[:2],
            }]
        }])
        engine = DreamEngine(store=store, refined_store=refined, llm_client=mock_llm)
        result = engine.dream()
        assert result[0].evidence == ids[:2]

    def test_source_memories_get_refined_by(self, populated_store):
        store, refined = populated_store
        ids = [m.id for m in store.list()]
        mock_llm = _make_mock_llm([{
            "reflections": [{
                "title": "Core conventions",
                "content": "Key conventions summary.",
                "importance": 7,
                "evidence": ids[:2],
            }]
        }])
        engine = DreamEngine(store=store, refined_store=refined, llm_client=mock_llm)
        result = engine.dream()
        ref_id = result[0].id
        for m in store.list():
            if m.id in ids[:2]:
                assert ref_id in m.refined_by

    def test_dream_creates_log_entry(self, populated_store):
        store, refined = populated_store
        mock_llm = _make_mock_llm([{
            "reflections": [{
                "title": "Test log",
                "content": "Log test.",
                "importance": 5,
                "evidence": [],
            }]
        }])
        engine = DreamEngine(store=store, refined_store=refined, llm_client=mock_llm)
        result = engine.dream()
        assert engine.last_log is not None
        assert engine.last_log.command == "dream"
