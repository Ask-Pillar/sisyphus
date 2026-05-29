"""Tests for background memory extraction."""

import json
import pytest
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.extraction import Extractor, EXTRACT_PROMPT


class MockLLM:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.default_response = '{"memories": []}'
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        prompt = messages[-1]["content"] if messages else ""
        for key, resp in self.responses.items():
            if key in prompt:
                return resp
        return self.default_response


@pytest.fixture
def store(tmp_path):
    return MemoryStore(base_path=tmp_path / ".omo" / "memory")


@pytest.fixture
def llm():
    return MockLLM()


class TestExtractor:

    def test_extract_empty_turn_returns_nothing(self, store, llm):
        xt = Extractor(store=store, llm_client=llm)
        result = xt.extract("")
        assert result == []

    def test_extract_saves_memories(self, store, llm):
        llm.responses = {
            "debugging": json.dumps({
                "memories": [
                    {
                        "type": "lesson",
                        "title": "Found a bug in pagination",
                        "content": "Offset-based pagination breaks when items are deleted mid-page.",
                        "tags": ["bug", "pagination"],
                    }
                ]
            }),
        }
        xt = Extractor(store=store, llm_client=llm)
        results = xt.extract("We spent 3 hours debugging the pagination bug.")
        assert len(results) == 1
        assert results[0].title == "Found a bug in pagination"
        assert results[0].types[0] == "lesson"
        # Memory should be in the store
        all_mems = store.list()
        assert len(all_mems) == 1

    def test_extract_multiple_memories(self, store, llm):
        llm.responses = {
            "discussed": json.dumps({
                "memories": [
                    {"type": "decision", "title": "Use FastAPI", "content": "Chose FastAPI over Flask.", "tags": ["architecture"]},
                    {"type": "lesson", "title": "Async pitfalls", "content": "Need httpx for async HTTP.", "tags": ["async"]},
                ]
            }),
        }
        xt = Extractor(store=store, llm_client=llm)
        results = xt.extract("We discussed the framework choice.")
        assert len(results) == 2
        assert store.list(type_filter="decision")[0].title == "Use FastAPI"

    def test_dedup_existing_memory(self, store, llm):
        store.create(title="Already known", type="lesson", content="Existing content.")
        llm.responses = {
            "same": json.dumps({
                "memories": [
                    {"type": "lesson", "title": "Already known", "content": "Existing content.", "tags": []},
                ]
            }),
        }
        xt = Extractor(store=store, llm_client=llm)
        results = xt.extract("same stuff again")
        # Dedup: should not create duplicate
        assert len(results) == 0
        all_mems = store.list()
        assert len(all_mems) == 1

    def test_partial_dedup(self, store, llm):
        store.create(title="Existing", type="lesson", content="Old content.", tags=[])
        llm.responses = {
            "new": json.dumps({
                "memories": [
                    {"type": "lesson", "title": "Existing", "content": "Old content.", "tags": []},
                    {"type": "decision", "title": "New decision", "content": "Fresh content.", "tags": []},
                ]
            }),
        }
        xt = Extractor(store=store, llm_client=llm)
        results = xt.extract("new stuff")
        # Only the new one should be added
        assert len(results) == 1
        assert results[0].title == "New decision"

    def test_llm_returns_invalid_json(self, store, llm):
        llm.responses = {"": "not json"}
        xt = Extractor(store=store, llm_client=llm)
        results = xt.extract("something happened")
        assert results == []

    def test_llm_timeout(self, store):
        class SlowLLM:
            def chat(self, messages):
                raise TimeoutError("timeout")
        xt = Extractor(store=store, llm_client=SlowLLM())
        results = xt.extract("something happened")
        assert results == []

    def test_prompt_contains_instructions(self, store, llm):
        xt = Extractor(store=store, llm_client=llm)
        xt.extract("some work happened")
        prompt = llm.calls[0][-1]["content"]
        assert "type" in prompt.lower()
        assert "title" in prompt.lower()
        assert "content" in prompt.lower()

    def test_skip_memory_with_no_content(self, store, llm):
        llm.responses = {
            "work": json.dumps({
                "memories": [
                    {"type": "lesson", "title": "Empty", "content": "", "tags": []},
                ]
            }),
        }
        xt = Extractor(store=store, llm_client=llm)
        results = xt.extract("some work happened")
        assert results == []
