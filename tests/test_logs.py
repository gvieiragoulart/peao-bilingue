"""Log files and the record of uncaught exceptions."""

import faulthandler
import logging
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from peao_bilingue import logs


@pytest.fixture
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setattr(logs, "LOG_DIR", tmp_path / "logs")
    root = logging.getLogger()
    before = list(root.handlers)
    yield tmp_path / "logs"
    for handler in root.handlers[:]:
        if handler not in before:
            root.removeHandler(handler)
            handler.close()


def test_logs_go_to_a_file_in_the_logs_folder(log_dir: Path) -> None:
    path = logs.log_to_file("app")
    logging.getLogger("peao_bilingue.test").info("written")

    assert path == log_dir / "app.log"
    assert "written" in path.read_text(encoding="utf-8")


def test_the_same_file_is_not_added_twice(log_dir: Path) -> None:
    logs.log_to_file("app")
    logs.log_to_file("app")
    logging.getLogger("peao_bilingue.test").info("once")
    assert (log_dir / "app.log").read_text(encoding="utf-8").count("once") == 1


def test_uncaught_exceptions_are_recorded(
    log_dir: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # The hooks are process-wide: every one of them is restored after the test.
    monkeypatch.setattr(sys, "excepthook", lambda *_args: None)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(logs, "_crash_file", [])
    enabled: list[Any] = []
    monkeypatch.setattr(faulthandler, "enable", enabled.append)

    logs.record_uncaught_exceptions()
    try:
        raise RuntimeError("main thread")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    thread = threading.Thread(target=lambda: 1 / 0, name="worker")
    thread.start()
    thread.join()

    assert "main thread" in caplog.text
    assert "thread worker" in caplog.text and "ZeroDivisionError" in caplog.text
    assert len(enabled) == 1  # faulthandler writes hard crashes to crash.log
    logs._crash_file[0].close()


def test_it_installs_once(log_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(logs, "_crash_file", [])
    monkeypatch.setattr(faulthandler, "enable", lambda _file: None)

    logs.record_uncaught_exceptions()
    hook = sys.excepthook
    logs.record_uncaught_exceptions()

    assert sys.excepthook is hook
    logs._crash_file[0].close()
