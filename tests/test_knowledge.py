"""Tests for KnowledgeBase."""
import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.knowledge import KnowledgeBase


@pytest.fixture
def kb(tmp_path):
    return KnowledgeBase(tmp_path / ".omo", domain="test")


class TestKnowledgeBase:
    def test_init_creates_db(self, kb):
        assert kb.db_path.exists()

    def test_import_markdown(self, kb, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("# Hello\n\nThis is a test document with database config details.")
        count = kb.import_file(str(md))
        assert count >= 1

    def test_import_txt(self, kb, tmp_path):
        txt = tmp_path / "notes.txt"
        words = "word " * 600
        txt.write_text(words)
        count = kb.import_file(str(txt))
        assert count >= 2

    def test_search_finds_chunks(self, kb, tmp_path):
        md = tmp_path / "config.md"
        md.write_text("The database connection uses PostgreSQL on port 5432.")
        kb.import_file(str(md))
        results = kb.search("database")
        assert len(results) >= 1
        assert "PostgreSQL" in results[0]["content"]

    def test_search_empty_query(self, kb):
        assert kb.search("") == []

    def test_import_file_not_found(self, kb):
        with pytest.raises(FileNotFoundError):
            kb.import_file("/nonexistent/file.md")

    def test_import_unsupported_format(self, kb, tmp_path):
        f = tmp_path / "image.png"
        f.write_text("fake png")
        with pytest.raises(ValueError, match="Unsupported"):
            kb.import_file(str(f))

    def test_stats(self, kb, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("Test content.")
        kb.import_file(str(md))
        stats = kb.stats()
        assert stats["total_sources"] >= 1
        assert stats["total_chunks"] >= 1

    def test_import_directory(self, kb, tmp_path):
        (tmp_path / "a.md").write_text("doc a")
        (tmp_path / "b.txt").write_text("doc b")
        result = kb.import_directory(str(tmp_path), recursive=False)
        assert result["total_files"] == 2
        assert result["total_chunks"] >= 2

    def test_import_jsonl(self, kb, tmp_path):
        jl = tmp_path / "data.jsonl"
        jl.write_text('{"content": "item one"}\n{"content": "item two"}\n')
        count = kb.import_file(str(jl))
        assert count >= 1
        results = kb.search("item")
        assert len(results) >= 1
