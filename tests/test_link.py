"""Tests for LinkAnalyzer — auto-association (v1.1 step3)."""

import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.store import MemoryStore, Memory
from sisyphus.memory.link import LinkAnalyzer


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ".omo" / "memory"
        yield MemoryStore(base_path=base)


@pytest.fixture
def analyzer(store):
    return LinkAnalyzer(store)


class TestLinkAnalyzerInit:
    def test_init_requires_store(self, store):
        a = LinkAnalyzer(store)
        assert a is not None


class TestAnalyze:
    def test_empty_store_returns_empty(self, analyzer):
        result = analyzer.analyze()
        assert len(result) == 0

    def test_same_tag_creates_link(self, analyzer):
        m1 = analyzer.store.create(
            title="Python typing", type="lesson", content="Use Optional.",
            tags=["python"],
        )
        m2 = analyzer.store.create(
            title="Python f-strings", type="lesson", content="Use f-strings.",
            tags=["python"],
        )
        result = analyzer.analyze()
        assert len(result) >= 1
        updated_m1 = analyzer.store.get(m1.id)
        updated_m2 = analyzer.store.get(m2.id)
        assert m2.id in updated_m1.links
        assert m1.id in updated_m2.links

    def test_different_tags_no_link(self, analyzer):
        m1 = analyzer.store.create(
            title="Python", type="lesson", content="About python.",
            tags=["python"],
        )
        m2 = analyzer.store.create(
            title="React", type="lesson", content="About react.",
            tags=["javascript"],
        )
        result = analyzer.analyze()
        updated_m1 = analyzer.store.get(m1.id)
        assert len(updated_m1.links) == 0

    def test_does_not_duplicate_links(self, analyzer):
        m1 = analyzer.store.create(
            title="A", type="lesson", content="Content A.",
            tags=["common"],
            links=[],
        )
        m2 = analyzer.store.create(
            title="B", type="lesson", content="Content B.",
            tags=["common"],
            links=[],
        )
        analyzer.analyze()
        analyzer.analyze()
        updated_m1 = analyzer.store.get(m1.id)
        assert updated_m1.links.count(m2.id) == 1

    def test_preserves_existing_links(self, analyzer):
        m1 = analyzer.store.create(
            title="A", type="lesson", content="Content A.",
            tags=["common"],
            links=["pre_existing"],
        )
        m2 = analyzer.store.create(
            title="B", type="lesson", content="Content B.",
            tags=["common"],
        )
        analyzer.analyze()
        updated_m1 = analyzer.store.get(m1.id)
        assert "pre_existing" in updated_m1.links
        assert m2.id in updated_m1.links

    def test_skips_already_linked(self, analyzer):
        m1 = analyzer.store.create(
            title="A", type="lesson", content="A.",
            tags=["x"],
        )
        m2 = analyzer.store.create(
            title="B", type="lesson", content="B.",
            tags=["x"],
        )
        analyzer.analyze()
        updated_m1 = analyzer.store.get(m1.id)
        analyzer.analyze()
        updated_m1_again = analyzer.store.get(m1.id)
        assert updated_m1.links == updated_m1_again.links
