"""Log files: where the app and the scheduled collection leave a trace.

A GUI app (pythonw, the .exe) has no console: without a file, an error would leave no
trace at all, and nobody could help the user. Each entry point logs to its own rotating
file in `data/logs/`, uncaught exceptions included. Logs are for whoever maintains the
app, so they stay in English.
"""

import faulthandler
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import TextIO

from peao_bilingue.config import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
MAX_BYTES = 1_000_000
BACKUPS = 3

logger = logging.getLogger("peao_bilingue.crash")
# Kept open for the whole process: faulthandler writes to it when Python itself crashes.
_crash_file: list[TextIO] = []


def log_file(name: str) -> Path:
    return LOG_DIR / f"{name}.log"


def log_to_file(name: str, *, level: int = logging.INFO) -> Path:
    """Sends the root logger to `data/logs/<name>.log` (1 MB × 3). Calling it again for
    the same file adds nothing. Entry points also call `record_uncaught_exceptions()`."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = log_file(name)
    root = logging.getLogger()
    if not any(
        isinstance(handler, RotatingFileHandler)
        and Path(handler.baseFilename) == path.resolve()
        for handler in root.handlers
    ):
        handler = RotatingFileHandler(
            path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(handler)
    root.setLevel(level)
    return path


def record_uncaught_exceptions() -> None:
    """Uncaught exceptions (main thread, other threads, a hard crash) go to the log.
    Installed once per process."""
    if _crash_file:
        return
    previous = sys.excepthook

    def main_thread(
        kind: type[BaseException],
        value: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        logger.critical("Uncaught exception", exc_info=(kind, value, traceback))
        previous(kind, value, traceback)

    def other_threads(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit or args.exc_value is None:
            return
        name = args.thread.name if args.thread else "?"
        logger.critical(
            "Uncaught exception in thread %s",
            name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = main_thread
    threading.excepthook = other_threads
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _crash_file.append(log_file("crash").open("a", encoding="utf-8"))
    faulthandler.enable(_crash_file[0])
