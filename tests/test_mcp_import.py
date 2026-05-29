import tempfile
from pathlib import Path

from sisyphus.memory.store import MemoryStore
from sisyphus.server.importer import import_memories


def _make_store():
    tmp = Path(tempfile.mkdtemp()) / "mem"
    return MemoryStore(base_path=tmp)


def test_import_md_with_frontmatter():
    store = _make_store()
    md = Path(tempfile.mkdtemp()) / "test.md"
    md.write_text("""---
title: test import
type: lesson
tags: python,typing
importance: 7
---
Python 类型标注内容""")
    result = import_memories(store, str(md))
    assert result["imported"] == 1
    mems = store.list()
    assert len(mems) == 1
    assert mems[0].title == "test import"
    assert mems[0].types[0] == "lesson"
    assert mems[0].importance == 7


def test_import_md_without_frontmatter():
    store = _make_store()
    md = Path(tempfile.mkdtemp()) / "note.md"
    md.write_text("Just some plain text without frontmatter")
    result = import_memories(store, str(md))
    assert result["imported"] == 1
    mems = store.list()
    assert mems[0].title == "note"
    assert mems[0].types[0] == "note"


def test_import_duplicate_skipped():
    store = _make_store()
    md = Path(tempfile.mkdtemp()) / "dup.md"
    md.write_text("""---
title: dup test
type: note
---
Content""")
    result1 = import_memories(store, str(md))
    result2 = import_memories(store, str(md))
    assert result1["imported"] == 1
    assert result2["imported"] == 0
    assert len(store.list()) == 1


def test_import_directory():
    store = _make_store()
    d = Path(tempfile.mkdtemp())
    (d / "a.md").write_text("""---
title: memory a
type: note
---
Content a""")
    (d / "b.md").write_text("""---
title: memory b
type: note
---
Content b""")
    result = import_memories(store, str(d))
    assert result["imported"] == 2
