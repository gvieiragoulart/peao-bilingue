"""The run lock shared by the app and the scheduled task."""

from pathlib import Path

from filelock import FileLock, Timeout

from peao_bilingue.domain.collection import Lock


class FileRunLock(Lock):
    """A file lock: excludes the window and the scheduled task, which are different
    processes.

    It creates a new FileLock instance on every attempt: the same instance is
    reentrant and would let a second run from the same process through. Different
    instances exclude each other, within a process and across processes.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._active: FileLock | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(self.path)
        try:
            lock.acquire(timeout=0)
        except Timeout:
            return False
        self._active = lock
        return True

    def release(self) -> None:
        if self._active is not None:
            self._active.release()
            self._active = None
