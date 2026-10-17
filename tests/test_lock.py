import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

from peao_bilingue.adapters.persistence import sqlite as sqlite_module
from peao_bilingue.adapters.persistence.lock import FileRunLock
from peao_bilingue.application.collect import ProcessLock


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "run.lock"


def test_two_locks_on_same_file_exclude_each_other(path: Path) -> None:
    # like the app and the scheduled task: each with its own instance
    first, second = FileRunLock(path), FileRunLock(path)
    assert first.acquire()
    assert not second.acquire()
    first.release()
    assert second.acquire()
    second.release()


def test_same_lock_cannot_be_acquired_twice(path: Path) -> None:
    # a FileLock instance is reentrant: that's why the lock makes a new one each time
    lock = FileRunLock(path)
    assert lock.acquire()
    assert not lock.acquire()
    lock.release()


@pytest.mark.integration  # starts another Python process
def test_other_process_is_blocked(path: Path) -> None:
    lock = FileRunLock(path)
    assert lock.acquire()
    try:
        code = (
            "import sys, pathlib\n"
            "from peao_bilingue.adapters.persistence.lock import FileRunLock\n"
            f"sys.exit(0 if FileRunLock(pathlib.Path(r'{path}')).acquire() else 3)\n"
        )
        result = subprocess.run([sys.executable, "-c", code], check=False, timeout=60)
        assert result.returncode == 3
    finally:
        lock.release()


def test_release_without_acquire_does_not_crash(path: Path) -> None:
    FileRunLock(path).release()


def test_process_lock() -> None:
    lock = ProcessLock()
    assert lock.acquire()
    assert not lock.acquire()
    lock.release()
    assert lock.acquire()
    lock.release()


def test_default_database_uses_wal() -> None:
    # WAL: the window reads while the scheduled task, another process, writes.
    engine = sqlite_module.default_engine()
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert connection.execute(text("PRAGMA busy_timeout")).scalar() == 5000
    engine.dispose()
