"""The Runs tab: collect now, the daily schedule, the history and the live log."""

import asyncio
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config
from peao_bilingue.application.collect import run_collection
from peao_bilingue.composition import build_services
from peao_bilingue.config import settings
from peao_bilingue.domain.collection import Run, Trigger
from peao_bilingue.domain.schedule import ScheduleStatus
from peao_bilingue.i18n import _
from peao_bilingue.texts import describe_schedule
from peao_bilingue.ui import presentation
from peao_bilingue.ui.widgets import Table

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App

LOG_LINES = 2_000


class RunsTab(ctk.CTkFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            controls,
            text=_(
                "The collection looks for new jobs and saves them, with no LLM: analyze "
                "the ones you want on the Jobs tab."
            ),
            text_color="gray55",
        ).pack(side="left")
        self.button = ctk.CTkButton(
            controls, text=_("Collect now"), width=140, command=self._collect
        )
        self.button.pack(side="right")

        schedule = ctk.CTkFrame(self)
        schedule.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            schedule,
            text=_("Daily automatic collection"),
            font=ctk.CTkFont(weight="bold"),
        ).pack(side="left", padx=12, pady=10)
        self.time = ctk.CTkEntry(schedule, width=70)
        self.time.pack(side="left")
        self.time.insert(0, settings.collection_time)
        ctk.CTkButton(
            schedule, text=_("Schedule"), width=90, command=self._schedule
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            schedule,
            text=_("Cancel"),
            width=90,
            fg_color="transparent",
            border_width=1,
            command=self._cancel_schedule,
        ).pack(side="left")
        self.schedule_status = ctk.CTkLabel(
            schedule, text=_("Checking…"), text_color="gray55"
        )
        self.schedule_status.pack(side="left", padx=12)

        self.history = Table(
            self,
            [
                ("started", _("Start"), 90),
                ("trigger", _("Trigger"), 80),
                ("status", _("Status"), 110),
                ("listed", _("Listed"), 70),
                ("new", _("New"), 60),
                ("error", _("Error"), 440),
            ],
            height=220,
        )
        self.history.pack(fill="x")

        ctk.CTkLabel(self, text=_("Log")).pack(anchor="w", pady=(12, 4))
        self.log_box = ctk.CTkTextbox(self, wrap="word", height=220)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")
        self._query_schedule()

    # PowerShell takes ~1 s to answer: everything about the schedule goes through the
    # executor, and the query stays out of refresh(), which runs on every data change.
    def _query_schedule(self) -> None:
        def show(status: ScheduleStatus | None) -> None:
            self.schedule_status.configure(text=describe_schedule(status))

        def fail(failure: BaseException) -> None:
            self.schedule_status.configure(
                text=_("Couldn't read the schedule: {error}").format(error=failure)
            )

        self.app.run(
            asyncio.to_thread(self.app.scheduler.status),
            on_done=show,
            on_error=fail,
        )

    def _schedule(self) -> None:
        time = self.time.get().strip()
        self.schedule_status.configure(text=_("Scheduling…"))

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
        self.schedule_status.configure(text=_("Cancelling…"))
        self.app.run(
            asyncio.to_thread(self.app.scheduler.cancel),
            on_done=lambda _result: self._query_schedule(),
            on_error=self._schedule_failure,
        )

    def _schedule_failure(self, failure: BaseException) -> None:
        self._query_schedule()
        self.app.show_error(failure)

    def refresh(self) -> None:
        self.history.fill(
            [
                (str(run.id), presentation.run_row(run))
                for run in self.app.repository.list_runs(50)
            ]
        )

    def add_log(self, line: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n")
        excess = int(self.log_box.index("end-1c").split(".")[0]) - LOG_LINES
        if excess > 0:
            self.log_box.delete("1.0", f"{excess + 1}.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _collect(self) -> None:
        try:
            services = build_services(repository=self.app.repository)
        except Exception as failure:  # noqa: BLE001 - a misconfigured source is a notice
            self.app.show_error(failure)
            return

        self.button.configure(state="disabled", text=_("Collecting…"))
        self.app.log(_("Collection started."))

        def finish(run: Run) -> None:
            self.button.configure(state="normal", text=_("Collect now"))
            self.app.on_change()
            self.app.log(
                _("Collection {status}: {listed} listed, {new} new.").format(
                    status=presentation.run_status_labels()[run.status],
                    listed=run.listed_jobs,
                    new=run.new_jobs,
                )
            )

        def fail(failure: BaseException) -> None:
            self.button.configure(state="normal", text=_("Collect now"))
            self.app.show_error(failure)

        # No notices: whoever asked for the collection is looking at the screen.
        self.app.run(
            run_collection(services, Trigger.manual),
            on_done=finish,
            on_error=fail,
        )
