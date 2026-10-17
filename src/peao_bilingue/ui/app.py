"""The Peão Bilíngue main window."""

import asyncio
import logging
import queue
from collections.abc import Callable, Coroutine
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from peao_bilingue.composition import build_repository, build_scheduler
from peao_bilingue.domain.repository import Repository
from peao_bilingue.domain.schedule import Scheduler
from peao_bilingue.i18n import _
from peao_bilingue.ui.executor import AsyncExecutor, LogQueue, track
from peao_bilingue.ui.tabs.jobs import JobsTab
from peao_bilingue.ui.tabs.llms import LLMsTab
from peao_bilingue.ui.tabs.profile import ProfileTab
from peao_bilingue.ui.tabs.runs import RunsTab
from peao_bilingue.ui.tabs.searches import SearchesTab
from peao_bilingue.ui.tabs.settings import SettingsTab
from peao_bilingue.ui.tabs.sources import SourcesTab

APP_NAME = "Peão Bilíngue"
LOG_INTERVAL_MS = 200
logger = logging.getLogger(__name__)


def tabs() -> list[tuple[str, str, type[Any]]]:
    """(id, title, class). The tabs inherit from CustomTkinter widgets, which have no
    types: for mypy, Any."""
    return [
        ("jobs", _("Jobs"), JobsTab),
        ("searches", _("Searches"), SearchesTab),
        ("sources", _("Sources"), SourcesTab),
        ("llms", _("LLMs"), LLMsTab),
        ("profile", _("Profile"), ProfileTab),
        ("runs", _("Runs"), RunsTab),
        ("settings", _("Settings"), SettingsTab),
    ]


class App(ctk.CTk):
    def __init__(
        self,
        repository: Repository | None = None,
        executor: AsyncExecutor | None = None,
        scheduler: Scheduler | None = None,
    ) -> None:
        super().__init__()
        self.title(_("{app} — job radar").format(app=APP_NAME))
        self.geometry("1280x800")
        self.minsize(1000, 640)

        self.repository = repository or build_repository()
        self.executor = executor or AsyncExecutor()
        self.scheduler = scheduler or build_scheduler()
        self._queue: queue.Queue[str] = queue.Queue()
        self._log = LogQueue(self._queue)
        logging.getLogger().addHandler(self._log)

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.panels: dict[str, Any] = {}
        for identifier, title, cls in tabs():
            panel = cls(self.tabs.add(title), self)
            panel.pack(fill="both", expand=True)
            self.panels[identifier] = panel

        self.on_change()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(LOG_INTERVAL_MS, self._drain_log)
        self._upgrade_legacy_task()

    def run(
        self,
        coroutine: Coroutine[Any, Any, Any],
        *,
        on_done: Callable[[Any], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        """Runs on the async loop; the callbacks come back on the window's thread."""
        track(
            self,
            self.executor.submit(coroutine),
            on_done,
            on_error or self.show_error,
        )

    def log(self, message: str) -> None:
        """Safe to call from any thread: it only queues."""
        self._queue.put(message)

    def _drain_log(self) -> None:
        while True:
            try:
                line = self._queue.get_nowait()
            except queue.Empty:
                break
            self.panels["runs"].add_log(line)
        self.after(LOG_INTERVAL_MS, self._drain_log)

    def _upgrade_legacy_task(self) -> None:
        """A daily task registered before the code was in English calls an old
        command: it is registered again (PowerShell, off the window's thread)."""

        def done(upgraded: bool) -> None:
            if upgraded:
                logger.info(
                    "Daily collection task registered again under its new name."
                )
                self.on_change()

        def failed(failure: BaseException) -> None:
            logger.warning("Couldn't upgrade the daily collection task: %s", failure)

        self.run(
            asyncio.to_thread(self.scheduler.upgrade_legacy_task),
            on_done=done,
            on_error=failed,
        )

    def on_change(self) -> None:
        for panel in self.panels.values():
            panel.refresh()

    def show_error(self, failure: BaseException) -> None:
        messagebox.showerror(APP_NAME, str(failure), parent=self)

    def inform(self, message: str) -> None:
        messagebox.showinfo(APP_NAME, message, parent=self)

    def close(self) -> None:
        logging.getLogger().removeHandler(self._log)
        self.executor.close()
        # Pending timers (the log's and CustomTkinter's) would fire after destroy, and
        # Tcl would complain about a missing command on stderr. Only the timer is
        # cancelled: the command belongs to whoever scheduled it and goes away when
        # each widget is destroyed (`after_cancel` would delete it first, and the
        # owner's destroy would fail).
        for pending in self.tk.splitlist(self.tk.call("after", "info")):
            self.tk.call("after", "cancel", pending)
        self.destroy()


def main() -> None:
    # No basicConfig: opened as a GUI app there is no console to write to.
    logging.getLogger().setLevel(logging.INFO)
    ctk.set_appearance_mode("system")
    App().mainloop()
