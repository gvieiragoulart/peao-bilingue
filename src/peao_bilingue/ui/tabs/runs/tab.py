"""The Runs tab: collect now, the daily schedule, the history and the live log. Puts the
components together and runs the collection and the scheduler through the executor."""

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config
from peao_bilingue.application.collect import run_collection
from peao_bilingue.composition import build_services, capture_folder
from peao_bilingue.config import settings
from peao_bilingue.domain.collection import Run, Trigger
from peao_bilingue.domain.schedule import ScheduleStatus
from peao_bilingue.i18n import _
from peao_bilingue.texts import describe_schedule
from peao_bilingue.ui import presentation
from peao_bilingue.ui.tabs.runs.collect_bar import CollectBar
from peao_bilingue.ui.tabs.runs.history import RunHistory
from peao_bilingue.ui.tabs.runs.log_view import LogView
from peao_bilingue.ui.tabs.runs.schedule_panel import SchedulePanel

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


class RunsTab(ctk.CTkFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.collect_bar = CollectBar(self, on_collect=self._collect)
        self.collect_bar.pack(fill="x", pady=(0, 8))
        self.schedule = SchedulePanel(
            self,
            settings.collection_time,
            on_schedule=self._schedule,
            on_cancel=self._cancel_schedule,
        )
        self.schedule.pack(fill="x", pady=(0, 8))
        self.history = RunHistory(self)
        self.history.pack(fill="x")
        self.log = LogView(self)
        self.log.pack(fill="both", expand=True, pady=(12, 0))
        self._query_schedule()

    # PowerShell takes ~1 s to answer: everything about the schedule goes through the
    # executor, and the query stays out of refresh(), which runs on every data change.
    def _query_schedule(self) -> None:
        def show(status: ScheduleStatus | None) -> None:
            self.schedule.show_status(describe_schedule(status))

        def fail(failure: BaseException) -> None:
            self.schedule.show_status(
                _("Couldn't read the schedule: {error}").format(error=failure)
            )

        self.app.run(
            asyncio.to_thread(self.app.scheduler.status),
            on_done=show,
            on_error=fail,
        )

    def _schedule(self) -> None:
        time = self.schedule.chosen_time()
        self.schedule.show_status(_("Scheduling…"))

        def finish(_result: object) -> None:
            # Back on the window's thread: only it touches the shared `settings`.
            config.save({"collection_time": time})
            self._query_schedule()

        self.app.run(
            asyncio.to_thread(self.app.scheduler.schedule, time),
            on_done=finish,
            on_error=self._schedule_failure,
        )

    def _cancel_schedule(self) -> None:
        self.schedule.show_status(_("Cancelling…"))
        self.app.run(
            asyncio.to_thread(self.app.scheduler.cancel),
            on_done=lambda _result: self._query_schedule(),
            on_error=self._schedule_failure,
        )

    def _schedule_failure(self, failure: BaseException) -> None:
        self._query_schedule()
        self.app.show_error(failure)

    def _show_screenshots(self, folder: Path) -> None:
        # The folder only exists if a source that reads web pages saved something.
        if not folder.exists():
            self.app.log(
                _("No screenshots: no source in this collection reads web pages.")
            )
            return
        self.app.log(_("Screenshots saved in {path}.").format(path=folder))
        os.startfile(folder)

    def refresh(self) -> None:
        self.history.show(self.app.repository.list_runs(50))
        self.collect_bar.set_sources(
            {presentation.source_label(name): name for name in settings.enabled_sources}
        )

    def add_log(self, line: str) -> None:
        self.log.add(line)

    def _collect(self) -> None:
        # None = every enabled source; one picked = only it.
        source = self.collect_bar.chosen_source()
        folder = capture_folder() if self.collect_bar.capture() else None
        try:
            services = build_services(
                sources=[source] if source else None,
                repository=self.app.repository,
                capture_to=folder,
            )
        except Exception as failure:  # noqa: BLE001 - a misconfigured source is a notice
            self.app.show_error(failure)
            return

        self.collect_bar.set_busy(True)
        if source:
            self.app.log(
                _("Collection started: {source}.").format(
                    source=presentation.source_label(source)
                )
            )
        else:
            self.app.log(_("Collection started."))

        def finish(run: Run) -> None:
            self.collect_bar.set_busy(False)
            self.app.on_change()
            self.app.log(
                _("Collection {status}: {listed} listed, {new} new.").format(
                    status=presentation.run_status_labels()[run.status],
                    listed=run.listed_jobs,
                    new=run.new_jobs,
                )
            )
            if folder is not None:
                self._show_screenshots(folder)

        def fail(failure: BaseException) -> None:
            self.collect_bar.set_busy(False)
            self.app.show_error(failure)

        # No notices: whoever asked for the collection is looking at the screen.
        self.app.run(
            run_collection(services, Trigger.manual),
            on_done=finish,
            on_error=fail,
        )
