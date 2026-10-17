import asyncio
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from peao_bilingue.ui.executor import AsyncExecutor, LogQueue, track


@pytest.fixture
def executor() -> Iterator[AsyncExecutor]:
    executor = AsyncExecutor()
    yield executor
    executor.close()


def test_coroutine_runs_on_another_thread(executor: AsyncExecutor) -> None:
    async def where() -> str:
        return threading.current_thread().name

    assert executor.submit(where()).result(timeout=5) == "peao-async"


def test_main_thread_stays_free_while_coroutine_waits(
    executor: AsyncExecutor,
) -> None:
    async def slow() -> str:
        await asyncio.sleep(0.5)
        return "ready"

    future = executor.submit(slow())
    hits = 0
    while not future.done():  # what Tk's mainloop would do
        hits += 1
        time.sleep(0.01)
    assert future.result() == "ready"
    assert hits > 10


def test_consecutive_runs_reuse_the_loop(
    executor: AsyncExecutor,
) -> None:
    async def current_loop() -> int:
        return id(asyncio.get_running_loop())

    first = executor.submit(current_loop()).result(timeout=5)
    second = executor.submit(current_loop()).result(timeout=5)
    assert first == second


class FakeWidget:
    """Imitates Tk's `after`, running the callbacks on the test's thread."""

    def __init__(self) -> None:
        self.pending: list[Callable[[], None]] = []

    def after(self, _ms: int, function: Callable[[], None]) -> None:
        self.pending.append(function)

    def process(self, until: float = 5) -> None:
        limit = time.time() + until
        while self.pending and time.time() < limit:
            self.pending.pop(0)()
            time.sleep(0.01)


def test_track_calls_success_callback_on_widget_thread(
    executor: AsyncExecutor,
) -> None:
    async def value() -> int:
        return 42

    widget, received = FakeWidget(), list[tuple[Any, str]]()
    track(
        widget,
        executor.submit(value()),
        on_done=lambda v: received.append((v, threading.current_thread().name)),
    )
    widget.process()

    assert received == [(42, threading.current_thread().name)]


def test_track_delivers_the_failure(executor: AsyncExecutor) -> None:
    async def breaks() -> None:
        raise ValueError("went wrong")

    widget, failures = FakeWidget(), list[BaseException]()
    track(widget, executor.submit(breaks()), on_error=failures.append)
    widget.process()

    assert len(failures) == 1 and str(failures[0]) == "went wrong"


def test_log_queue_accepts_messages_from_any_thread() -> None:
    destination: queue.Queue[str] = queue.Queue()
    logger = logging.getLogger("test.queue")
    handler = LogQueue(destination)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        threading.Thread(target=lambda: logger.info("from another thread")).start()
        assert "from another thread" in destination.get(timeout=5)
    finally:
        logger.removeHandler(handler)
