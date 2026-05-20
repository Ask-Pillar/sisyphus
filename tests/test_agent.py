"""Tests for AgentSandbox — isolated memory sandbox per agent (v1.3)."""

import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.agent import AgentSandbox, AgentRegistry


@pytest.fixture
def registry():
    with tempfile.TemporaryDirectory() as tmp:
        yield AgentRegistry(Path(tmp) / ".omo")


class TestAgentSandbox:
    def test_create_sandbox_creates_dir(self, registry):
        sandbox = registry.create("alice")
        assert sandbox.root.exists()
        assert sandbox.name == "alice"

    def test_sandbox_has_store_and_refined(self, registry):
        sandbox = registry.create("bob")
        mem = sandbox.store.create(title="Test", type="lesson", content="x")
        assert sandbox.store.get(mem.id) is not None
        ref = sandbox.refined.create_reflection(title="Ref", content="y")
        assert sandbox.refined.get_refined(ref.id) is not None

    def test_sandbox_list_memories(self, registry):
        sandbox = registry.create("charlie")
        sandbox.store.create(title="M1", type="lesson", content="a")
        sandbox.store.create(title="M2", type="lesson", content="b")
        assert len(sandbox.list_memories()) == 2

    def test_sandbox_stats(self, registry):
        sandbox = registry.create("dave")
        sandbox.store.create(title="M1", type="lesson", content="a")
        ref = sandbox.refined.create_reflection(title="R1", content="b")
        stats = sandbox.stats()
        assert stats["agent"] == "dave"
        assert stats["raw"] == 1
        assert stats["refined"] == 1

    def test_agents_are_isolated(self, registry):
        a = registry.create("agent_a")
        b = registry.create("agent_b")
        a.store.create(title="Only A", type="lesson", content="a")
        m = b.store.create(title="Only B", type="lesson", content="b")
        assert len(a.list_memories()) == 1
        assert len(b.list_memories()) == 1
        assert a.store.get(m.id) is None

    def test_registry_lists_all_agents(self, registry):
        registry.create("x")
        registry.create("y")
        assert registry.all() == ["x", "y"]

    def test_registry_get_existing_agent(self, registry):
        registry.create("existing")
        sb = registry.get("existing")
        assert sb.name == "existing"
        assert sb.root.exists()
