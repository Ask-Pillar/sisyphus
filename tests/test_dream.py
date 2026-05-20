"""Tests for DreamEngine — subagent-based reflection (v1.1 step1)."""

import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.dream import DreamEngine


class MockSubagent:
    def __init__(self, reflections=None):
        self.reflections = reflections or []
        self.last_memories = None

    def dream(self, memories):
        self.last_memories = memories
        return {"status": "ok", "created_ids": [r["id"] for r in self.reflections],
                "reflections": self.reflections}


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
    def test_init_requires_store_refined_subagent(self):
        subagent = MockSubagent()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".omo" / "memory"
            store = MemoryStore(base_path=base)
            refined = RefinedStore(base_path=base)
            engine = DreamEngine(store=store, refined_store=refined, subagent=subagent)
            assert engine is not None


class TestDream:
    def test_dream_empty_store_returns_empty(self, stores):
        store, refined = stores
        subagent = MockSubagent()
        engine = DreamEngine(store=store, refined_store=refined, subagent=subagent)
        result = engine.dream()
        assert len(result) == 0

    def test_dream_delegates_to_subagent(self, populated_store):
        store, refined = populated_store
        subagent = MockSubagent(reflections=[
            {"id": "ref_001", "title": "Core conventions", "content": "...",
             "importance": 8, "evidence": []},
        ])
        engine = DreamEngine(store=store, refined_store=refined, subagent=subagent)
        result = engine.dream()
        assert subagent.last_memories is not None
        assert len(result) == 1

    def test_reflection_has_proper_attributes(self, populated_store):
        store, refined = populated_store
        subagent = MockSubagent(reflections=[
            {"id": "ref_002", "title": "Core conventions",
             "content": "Three key conventions identified.",
             "importance": 7, "evidence": [m.id for m in store.list()[:2]]},
        ])
        engine = DreamEngine(store=store, refined_store=refined, subagent=subagent)
        result = engine.dream()
        assert len(result) == 1
        mem = result[0]
        assert mem.type == "reflection"
        assert mem.title == "Core conventions"
        assert mem.importance == 7
        assert len(mem.evidence) == 2

    def test_source_memories_get_refined_by(self, populated_store):
        store, refined = populated_store
        ids = [m.id for m in store.list()]
        subagent = MockSubagent(reflections=[
            {"id": "ref_003", "title": "Core conventions",
             "content": "Key conventions summary.",
             "importance": 7, "evidence": ids[:2]},
        ])
        engine = DreamEngine(store=store, refined_store=refined, subagent=subagent)
        result = engine.dream()
        ref_id = result[0].id
        for m in store.list():
            if m.id in ids[:2]:
                assert ref_id in m.refined_by

    def test_dream_creates_log_entry(self, populated_store):
        store, refined = populated_store
        subagent = MockSubagent(reflections=[
            {"id": "ref_004", "title": "Test log", "content": "Log test.",
             "importance": 5, "evidence": []},
        ])
        engine = DreamEngine(store=store, refined_store=refined, subagent=subagent)
        engine.dream()
        assert engine.last_log is not None
        assert engine.last_log.command == "dream"

    def test_subagent_empty_result_returns_empty(self, populated_store):
        store, refined = populated_store
        subagent = MockSubagent(reflections=[])
        engine = DreamEngine(store=store, refined_store=refined, subagent=subagent)
        result = engine.dream()
        assert len(result) == 0

    def test_subagent_skipped_returns_empty(self, populated_store):
        store, refined = populated_store
        subagent = MockSubagent()
        subagent.reflections = []
        subagent.dream = lambda m: {"status": "skipped", "message": "No API key"}
        engine = DreamEngine(store=store, refined_store=refined, subagent=subagent)
        result = engine.dream()
        assert len(result) == 0

    def test_subagent_error_returns_empty(self, populated_store):
        store, refined = populated_store
        subagent = MockSubagent()
        subagent.reflections = []
        subagent.dream = lambda m: {"status": "error", "message": "timeout"}
        engine = DreamEngine(store=store, refined_store=refined, subagent=subagent)
        result = engine.dream()
        assert len(result) == 0
