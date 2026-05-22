"""Tests for atomic_write and DirLock."""
import os
import time
from pathlib import Path

import pytest

from sisyphus.memory.utils import atomic_write, DirLock


class TestAtomicWrite:
    def test_writes_content(self, tmp_path: Path):
        f = tmp_path / "hello.md"
        atomic_write(f, "hello world")
        assert f.read_text() == "hello world"

    def test_overwrites_existing(self, tmp_path: Path):
        f = tmp_path / "overwrite.md"
        atomic_write(f, "first")
        atomic_write(f, "second")
        assert f.read_text() == "second"

    def test_original_intact_after_crash(self, tmp_path: Path):
        """.tmp file written but rename not yet done — original protected."""
        f = tmp_path / "crash.md"
        atomic_write(f, "original content")
        tmp = f.with_suffix(f.suffix + ".tmp")
        tmp.write_text("partial data")
        atomic_write(f, "new content")
        assert f.read_text() == "new content"
        assert not tmp.exists()

    def test_no_tmp_left_behind(self, tmp_path: Path):
        f = tmp_path / "clean.md"
        atomic_write(f, "clean write")
        tmp = f.with_suffix(f.suffix + ".tmp")
        assert not tmp.exists()

    def test_unicode_content(self, tmp_path: Path):
        f = tmp_path / "unicode.md"
        atomic_write(f, "你好世界 🎉")
        assert f.read_text() == "你好世界 🎉"

    def test_empty_content(self, tmp_path: Path):
        f = tmp_path / "empty.md"
        atomic_write(f, "")
        assert f.read_text() == ""


class TestDirLock:
    def test_acquire_release(self, tmp_path: Path):
        lock = DirLock(tmp_path, "test")
        lock.acquire()
        assert (tmp_path / "test" / "pid").exists()
        lock.release()
        assert not (tmp_path / "test").exists()

    def test_context_manager(self, tmp_path: Path):
        with DirLock(tmp_path, "ctx"):
            assert (tmp_path / "ctx" / "pid").exists()
        assert not (tmp_path / "ctx").exists()

    def test_mutual_exclusion(self, tmp_path: Path):
        """Same-name locks held simultaneously raises TimeoutError."""
        a = DirLock(tmp_path, "mutex", timeout=0.5)
        b = DirLock(tmp_path, "mutex", timeout=0.5)
        a.acquire()
        with pytest.raises(TimeoutError):
            b.acquire()
        a.release()
        b.acquire()
        assert (tmp_path / "mutex" / "pid").exists()
        b.release()

    def test_stale_pid_cleaned(self, tmp_path: Path):
        """Dead PID in lock file is auto-detected and cleaned on next acquire."""
        lock = DirLock(tmp_path, "stale", pid=99999999)
        lock.acquire()
        assert (tmp_path / "stale" / "pid").exists()
        fresh = DirLock(tmp_path, "stale")
        fresh.acquire()
        pid_text = (tmp_path / "stale" / "pid").read_text()
        assert pid_text == str(os.getpid())
        fresh.release()

    def test_double_acquire_noop(self, tmp_path: Path):
        lock = DirLock(tmp_path, "double")
        lock.acquire()
        lock.acquire()
        lock.release()
        assert not (tmp_path / "double").exists()

    def test_sequential_write_via_lock(self, tmp_path: Path):
        f = tmp_path / "shared.txt"

        def _writer(pid_suffix: str):
            for _ in range(5):
                with DirLock(tmp_path, "concurrent"):
                    content = f.read_text() if f.exists() else ""
                    content += f"line from {pid_suffix}\n"
                    atomic_write(f, content)
                    time.sleep(0.01)

        _writer("A")
        _writer("B")
        lines = f.read_text().strip().split("\n")
        assert len(lines) == 10
        assert any("line from A" in l for l in lines)
        assert any("line from B" in l for l in lines)
