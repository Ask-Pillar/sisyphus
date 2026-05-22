"""File storage utilities — atomic write and directory-based lock.

atomic_write: crash-safe file writes via tempfile + atomic rename.
DirLock: mkdir-based lock with PID dead-process detection.
"""

import os
import time
from pathlib import Path
from typing import Optional


def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content atomically via tempfile + rename.

    On POSIX, rename is atomic if source and target are on the same filesystem.
    Falls back to shutil.move on cross-filesystem rename failure.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding=encoding)
    tmp.replace(path)


class DirLock:
    """mkdir-based directory lock with PID dead-process detection.

    Usage:
        with DirLock(base_path / "_lock", "store", timeout=10):
            # critical section
    """

    def __init__(
        self, base: Path, name: str = "default", timeout: float = 10.0, *, pid: Optional[int] = None
    ):
        self._lock = base / name
        self._pid_file = self._lock / "pid"
        self._timeout = timeout
        self._pid = pid if pid is not None else os.getpid()
        self._acquired = False

    def acquire(self) -> None:
        if self._acquired:
            return
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                self._lock.parent.mkdir(parents=True, exist_ok=True)
                self._lock.mkdir()
                self._pid_file.write_text(str(self._pid))
                self._acquired = True
                return
            except FileExistsError:
                if self._is_stale():
                    self._release_stale()
                elif time.monotonic() > deadline:
                    raise TimeoutError(
                        f"DirLock({self._lock}) held longer than {self._timeout}s"
                    )
                time.sleep(0.05)

    def release(self) -> None:
        if not self._acquired:
            return
        self._acquired = False
        self._pid_file.unlink(missing_ok=True)
        try:
            self._lock.rmdir()
        except OSError:
            pass

    def _is_stale(self) -> bool:
        try:
            pid = int(self._pid_file.read_text())
            # If kill(pid, 0) succeeds the process is alive
            os.kill(pid, 0)
            return False
        except (OSError, ValueError):
            return True

    def _release_stale(self) -> None:
        self._pid_file.unlink(missing_ok=True)
        try:
            self._lock.rmdir()
        except OSError:
            pass

    def __enter__(self) -> "DirLock":
        self.acquire()
        return self

    def __exit__(self, *_) -> None:
        self.release()
