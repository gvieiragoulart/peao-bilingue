"""The bridge between Tkinter (synchronous, one thread) and the async core.

Tk's mainloop can't wait for Playwright to browse or an LLM to answer, or the window
freezes. The coroutines run on an asyncio loop in a thread of their own; results come
back to the window's thread through `after()`. No widget is touched outside the
window's thread.
"""

import asyncio
import logging
import queue
import threading
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from typing import Any

INTERVAL_MS = 100


class AsyncExecutor:
    def __init__(self) -> None:
        # On Windows the default loop is Proactor, which Playwright needs (subprocesses).
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run, name="peao-async", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coroutine: Coroutine[Any, Any, Any]) -> Future[Any]:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)


def track(
    widget: Any,
    future: Future[Any],
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[BaseException], None] | None = None,
) -> None:
    """Calls the right callback on the window's thread when the future finishes."""

    def check() -> None:
        if not future.done():
            widget.after(INTERVAL_MS, check)
            return
        failure = future.exception()
        if failure is not None:
            if on_error:
                on_error(failure)
        elif on_done:
            on_done(future.result())

    widget.after(INTERVAL_MS, check)


class LogQueue(logging.Handler):
    """Carries logs from any thread to a queue the window drains."""

    def __init__(self, destination: queue.Queue[str]) -> None:
        super().__init__(level=logging.INFO)
        self.destination = destination
        self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        self.destination.put(self.format(record))
