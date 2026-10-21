"""The Peão Bilíngue main window."""

import asyncio
import logging
import queue
import webbrowser
from collections.abc import Callable, Coroutine
from tkinter import messagebox
from types import TracebackType
from typing import Any

import customtkinter as ctk

from peao_bilingue import APP_NAME, __version__, config
from peao_bilingue.application.updates import newer_release
from peao_bilingue.composition import (
    build_release_feed,
    build_repository,
    build_scheduler,
)
from peao_bilingue.config import settings
from peao_bilingue.domain.repository import Repository
from peao_bilingue.domain.schedule import Scheduler
from peao_bilingue.domain.updates import Release, ReleaseFeed
from peao_bilingue.i18n import _
from peao_bilingue.logs import log_to_file, record_uncaught_exceptions
from peao_bilingue.ui import chrome, presentation, theme
from peao_bilingue.ui.executor import AsyncExecutor, LogQueue, track
from peao_bilingue.ui.navigation import Sidebar
from peao_bilingue.ui.onboarding import Onboarding, needs_onboarding
from peao_bilingue.ui.tabs.jobs import JobsTab
from peao_bilingue.ui.tabs.llms import LLMsTab
from peao_bilingue.ui.tabs.profile import ProfileTab
from peao_bilingue.ui.tabs.runs import RunsTab
from peao_bilingue.ui.tabs.searches import SearchesTab
from peao_bilingue.ui.tabs.settings import SettingsTab
from peao_bilingue.ui.tabs.sources import SourcesTab
from peao_bilingue.ui.widgets import OutlineButton, Toast

LOG_INTERVAL_MS = 200
PAGE_PADDING = 24
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
        release_feed: ReleaseFeed | None = None,
    ) -> None:
        theme.install()
        super().__init__()
        chrome.set_icon(self)
        theme.choose_fonts(self)
        # "job radar" is by the logo, in the sidebar: not repeated here.
        self.title(f"{APP_NAME} {__version__}")
        self.geometry("1280x800")
        self.minsize(1000, 640)

        self.repository = repository or build_repository()
        self.executor = executor or AsyncExecutor()
        self.scheduler = scheduler or build_scheduler()
        self.release_feed = release_feed or build_release_feed()
        self._queue: queue.Queue[str] = queue.Queue()
        self._log = LogQueue(self._queue)
        logging.getLogger().addHandler(self._log)

        # Shown above the tabs only when a newer version is out.
        self.update_banner = ctk.CTkFrame(self, fg_color=theme.ACCENT_SOFT)
        self.update_text = ctk.CTkLabel(
            self.update_banner, text="", text_color=theme.ACCENT_TEXT
        )
        self.update_text.pack(side="left", padx=12, pady=8)
        self.update_button = ctk.CTkButton(
            self.update_banner, text=_("Download"), width=110
        )
        self.update_button.pack(side="right", padx=(0, 12))
        OutlineButton(
            self.update_banner,
            text=_("Later"),
            width=80,
            command=self.update_banner.pack_forget,
        ).pack(side="right", padx=6)

        # The sidebar and the section shown, or the first-run guide in their place.
        self.body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.body.pack(fill="both", expand=True)
        self.onboarding: Onboarding | None = None
        sections = tabs()
        self._titles = {identifier: title for identifier, title, _cls in sections}
        self.sidebar = Sidebar(
            self.body,
            [(identifier, title) for identifier, title, _cls in sections],
            on_pick=self.show,
            on_collect=self.collect_now,
            on_toggle_mode=self.toggle_mode,
        )
        self.content = ctk.CTkFrame(self.body, fg_color="transparent", corner_radius=0)
        self.page_title = ctk.CTkLabel(
            self.content, text="", font=theme.title(), anchor="w"
        )
        self.page_title.pack(fill="x", padx=PAGE_PADDING, pady=(18, 10))
        # Keep the content geometry steady while switching sections. Without a
        # fixed host, every pack_forget/pack asks the whole page to resize.
        self.panel_host = ctk.CTkFrame(
            self.content, fg_color="transparent", corner_radius=0
        )
        self.panel_host.pack(
            fill="both", expand=True, padx=PAGE_PADDING, pady=(0, PAGE_PADDING)
        )
        self.panel_host.pack_propagate(False)
        self._pack_sections()
        self.panels: dict[str, Any] = {
            identifier: cls(self.panel_host, self)
            for identifier, _title, cls in sections
        }
        self.current: str | None = None
        self.show("jobs")

        self.toast = Toast(self)
        self.on_change()
        if needs_onboarding(self.repository):
            self.open_onboarding()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, lambda: chrome.paint_title_bar(self))
        self.after(LOG_INTERVAL_MS, self._drain_log)
        self._upgrade_legacy_task()
        if settings.check_for_updates:
            self._check_for_updates()

    def _pack_sections(self) -> None:
        self.sidebar.pack(side="left", fill="y")
        self.content.pack(side="left", fill="both", expand=True)

    def show(self, identifier: str) -> None:
        """Shows one section in the content area, the way a tab did."""
        if self.current == identifier:
            return
        if self.current is not None:
            self.panels[self.current].pack_forget()
        self.panels[identifier].pack(fill="both", expand=True)
        self.current = identifier
        self.page_title.configure(text=self._titles[identifier])
        self.sidebar.set_active(identifier)

    def collect_now(self) -> None:
        """The sidebar's button: the Runs section, where the log shows the collection."""
        self.show("runs")
        self.panels["runs"].collect()

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

    def _check_for_updates(self) -> None:
        def failed(failure: BaseException) -> None:
            logger.info("Update check failed: %s", failure)

        self.run(
            newer_release(self.release_feed, __version__),
            on_done=self.show_update,
            on_error=failed,
        )

    def show_update(self, release: Release | None) -> None:
        if release is None:
            return
        self.update_text.configure(
            text=_("Version {version} of {app} is available.").format(
                version=release.version, app=APP_NAME
            )
        )
        self.update_button.configure(command=lambda: webbrowser.open(release.url))
        self.update_banner.pack(fill="x", padx=12, pady=(12, 0), before=self.body)

    def open_onboarding(self) -> None:
        if self.onboarding is not None:
            return
        self.sidebar.pack_forget()
        self.content.pack_forget()
        self.onboarding = Onboarding(self.body, self, on_close=self._close_onboarding)
        self.onboarding.pack(fill="both", expand=True, padx=12, pady=12)

    def _close_onboarding(self) -> None:
        if self.onboarding is not None:
            self.onboarding.destroy()
            self.onboarding = None
        self._pack_sections()
        self.show("runs")
        self.on_change()

    def toggle_mode(self) -> None:
        """The sidebar's button: light to dark and back, saved like Settings' choice
        (which then reads "Light" or "Dark" instead of "System default")."""
        mode = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        config.save({"appearance": mode})
        ctk.set_appearance_mode(mode)

    def _set_appearance_mode(self, mode_string: str) -> None:
        # CustomTkinter calls it on every light/dark switch: the title bar follows.
        super()._set_appearance_mode(mode_string)
        chrome.paint_title_bar(self)
        if hasattr(self, "sidebar"):
            self.sidebar.show_mode(ctk.get_appearance_mode())
        # What isn't a CustomTkinter widget (the Canvas tables, ttk) repaints on
        # refresh. Called by CustomTkinter's own init too, before the panels exist.
        if hasattr(self, "panels"):
            self.after_idle(self.on_change)

    def on_change(self) -> None:
        for panel in self.panels.values():
            panel.refresh()
        self.refresh_badge()
        runs = self.repository.list_runs(1)
        self.sidebar.show_last_run(
            presentation.last_run_line(runs[0] if runs else None)
        )

    def refresh_badge(self) -> None:
        """The Jobs item's badge: the new jobs not opened yet."""
        unseen = self.repository.count_unviewed()
        self.sidebar.items["jobs"].set_badge(presentation.badge(unseen))

    def show_error(self, failure: BaseException) -> None:
        # In the log too: what the user saw is what support will ask about.
        logger.info("Error shown to the user: %s", failure, exc_info=failure)
        messagebox.showerror(APP_NAME, str(failure), parent=self)

    def report_callback_exception(
        self,
        kind: type[BaseException],
        value: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        """An unexpected error in a button or timer: Tk would print it to a console the
        app doesn't have. It goes to the log and to the user instead."""
        logger.error("Error in a window callback", exc_info=(kind, value, traceback))
        self.show_error(value)

    def inform(self, message: str) -> None:
        """A short notice at the bottom of the window: nothing to click."""
        self.notify(message)

    def notify(
        self, message: str, action: tuple[str, Callable[[], None]] | None = None
    ) -> None:
        """Like inform, with an optional action such as ("Undo", undo)."""
        logger.info("Notice shown to the user: %s", message)
        self.toast.show(message, action)

    def confirm(self, question: str) -> bool:
        return bool(messagebox.askyesno(APP_NAME, question, parent=self))

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
    # No console in a GUI app: the log goes to data/logs/app.log.
    log_to_file("app")
    record_uncaught_exceptions()
    ctk.set_appearance_mode(settings.appearance)
    App().mainloop()
