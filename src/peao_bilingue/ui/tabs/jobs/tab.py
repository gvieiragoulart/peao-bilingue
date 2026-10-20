"""The Jobs tab: puts the filters, the table and the job's dialog together and does the
work they ask for (listing, marking, the per-job analysis). The components never touch
the repository, the settings or an LLM."""

import logging
import webbrowser
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config, factories
from peao_bilingue.application.analysis import analyze_job
from peao_bilingue.composition import build_llm, read_profile_notes
from peao_bilingue.config import settings
from peao_bilingue.domain.analysis import JobAnalysis
from peao_bilingue.domain.jobs import JobStatus, ListedJob
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation, theme
from peao_bilingue.ui.presentation import KeywordGroup
from peao_bilingue.ui.tabs.jobs.dialog import JobDialog
from peao_bilingue.ui.tabs.jobs.filters import JobFilters
from peao_bilingue.ui.tabs.jobs.table import JobTable

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App

LIMIT = 500

logger = logging.getLogger(__name__)


class JobsTab(ctk.CTkFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        # The job open in the dialog: what Analyze, Open and the status buttons act on.
        self._current: ListedJob | None = None
        self._keywords: dict[str, list[KeywordGroup]] = {}
        self._colors: dict[str, tuple[str, str]] = {}

        self.filters = JobFilters(self, on_apply=self.refresh)
        self.filters.pack(fill="x", pady=(0, 14))
        app.bind("<Control-f>", lambda _event: self._focus_search())

        # What the ticked boxes are for: only on screen while some are ticked, left of
        # the search box (the pickers' row has no room left at the minimum width).
        self.selection_bar = ctk.CTkFrame(
            self.filters.top,
            fg_color=theme.ACCENT_SOFT,
            corner_radius=8,
            height=34,
        )
        self.checked_count = ctk.CTkLabel(
            self.selection_bar,
            text="",
            text_color=theme.ACCENT_TEXT,
            font=theme.strong(),
        )
        self.checked_count.pack(side="left", padx=(12, 10))
        labels = presentation.job_status_labels()
        self.mark_checked = ctk.CTkOptionMenu(
            self.selection_bar,
            values=[labels[status] for status in JobStatus],
            width=130,
            height=28,
            command=self._mark_checked,
        )
        self.mark_checked.set(_("Mark as…"))
        self.mark_checked.pack(side="left", padx=(0, 6))
        self.discard_checked = ctk.CTkButton(
            self.selection_bar,
            text=_("Discard"),
            width=90,
            height=28,
            fg_color=theme.DANGER_SOFT,
            hover_color=theme.DANGER_SOFT_HOVER,
            text_color=theme.DANGER_TEXT,
            command=self._discard_checked,
        )
        self.discard_checked.pack(side="left", padx=(0, 4))
        # In the Discarded filter it takes Discard's place.
        self.delete_checked = ctk.CTkButton(
            self.selection_bar,
            text=_("Delete for good"),
            width=120,
            height=28,
            fg_color=theme.DANGER_SOFT,
            hover_color=theme.DANGER_SOFT_HOVER,
            text_color=theme.DANGER_TEXT,
            command=self._delete_checked,
        )
        self.clear_checked = ctk.CTkButton(
            self.selection_bar,
            text=_("Clear"),
            width=60,
            height=28,
            fg_color="transparent",
            hover_color=theme.RAISED,
            text_color=theme.ACCENT_TEXT,
            command=self._clear_checked,
        )
        self.clear_checked.pack(side="left", padx=(0, 4))

        self.table = JobTable(self)
        self.table.pack(fill="both", expand=True)
        self.table.on_click(self.open_job)
        self.table.on_check_change(self._show_checked)
        self._show_checked()

        # Created last, so it can cover the rest of the tab.
        self.dialog = JobDialog(
            self,
            on_analyze=self._analyze,
            on_open=self._open,
            on_change_status=self._change_status,
            on_pick_llm=self._remember_llm,
        )
        self.preview = self.dialog.preview

    def refresh(self) -> None:
        repository = self.app.repository
        searches = repository.list_searches()
        self.filters.set_options(
            [search.name for search in searches],
            factories.sources.available(),
        )
        self.preview.set_profiles(repository.sources_with_profile())
        self.preview.set_llm(settings.analysis_llm)

        try:
            chosen = self.filters.current()
        except ValueError as failure:
            self.app.show_error(failure)
            return

        jobs = repository.list_jobs(
            status=chosen.status,
            min_score=chosen.min_score,
            search=chosen.search,
            source=chosen.source,
            search_text=chosen.search_text,
            limit=LIMIT,
        )
        self._keywords = {
            item.job.key: presentation.job_keywords(item, searches) for item in jobs
        }
        self._colors = presentation.search_colors([search.name for search in searches])
        self.table.show(jobs, self._keywords, self._colors)

    def open_job(self, key: str) -> None:
        """Opens the job's dialog (a click on its row)."""
        item = self.table.job(key)
        if item is None and self._current and self._current.job.key == key:
            item = self._current  # left the filtered list, but still open
        if item is None:
            return
        if not item.viewed:
            self.app.repository.mark_viewed(key)
            item = item.model_copy(update={"viewed": True})
            self.table.mark_viewed(item)
            self.app.refresh_badge()
        self._current = item
        self.dialog.show(
            item,
            self.app.repository.current_analysis(key),
            self._keywords.get(key, []),
            self._colors,
        )

    def _remember_llm(self, name: str) -> None:
        # The last one picked becomes the default next time.
        config.save({"analysis_llm": name})

    def _open(self) -> None:
        if self._current is not None:
            webbrowser.open(self._current.job.url)

    def _change_status(self, status: JobStatus) -> None:
        item = self._current
        if item is None:
            return
        key = item.job.key
        self.app.repository.change_status(key, status)
        if status is JobStatus.discarded:
            # Done with this job: the dialog closes and the toast can bring it back.
            self.dialog.close()
            self.refresh()
            self.app.notify(
                _("Job discarded."),
                (_("Undo"), lambda: self._restore({key: item.status})),
            )
            return
        # The dialog stays open, showing the new status: the job may even have left
        # the filtered list.
        self.refresh()
        self.table.select(key)
        self._current = item.model_copy(update={"status": status})
        self.open_job(key)

    def _focus_search(self) -> None:
        self.app.show("jobs")
        self.filters.focus_search()

    def _show_checked(self) -> None:
        count = len(self.table.checked())
        self.checked_count.configure(text=_("{count} selected").format(count=count))
        state = "normal" if count else "disabled"
        for button in (
            self.mark_checked,
            self.discard_checked,
            self.delete_checked,
            self.clear_checked,
        ):
            button.configure(state=state)
        # Discarded jobs can only be deleted; the others, only discarded.
        shown, hidden = (self.discard_checked, self.delete_checked)
        if self._listing_discarded():
            shown, hidden = hidden, shown
        hidden.pack_forget()
        if not shown.winfo_manager():
            shown.pack(side="left", padx=(0, 4), before=self.clear_checked)
        if count and not self.selection_bar.winfo_manager():
            self.selection_bar.pack(side="left")
        elif not count:
            self.selection_bar.pack_forget()

    def _mark_checked(self, label: str) -> None:
        """The selection bar's "Mark as…": every ticked job gets the status picked."""
        self.mark_checked.set(_("Mark as…"))
        status = presentation.status_from_label(label)
        keys = self.table.checked()
        if status is None or not keys:
            return
        if status is JobStatus.discarded:
            self._discard_checked()
            return
        self._mark(keys, status)

    def _mark(self, keys: list[str], status: JobStatus) -> None:
        """Gives `keys` a status, offering to undo it."""
        before = {
            key: item.status
            for key in keys
            if (item := self.table.job(key)) is not None
        }
        self.app.repository.change_statuses(keys, status)
        logger.info("Marked %d job(s) as %s.", len(keys), status)
        self._after_marking(keys, status)
        self.app.notify(
            _("{count} job(s) marked as {status}.").format(
                count=len(keys), status=presentation.job_status_labels()[status]
            ),
            (_("Undo"), lambda: self._restore(before)),
        )

    def _restore(self, before: dict[str, JobStatus]) -> None:
        """Undo: each job gets back the status it had."""
        for status in set(before.values()):
            keys = [key for key, old in before.items() if old is status]
            self.app.repository.change_statuses(keys, status)
        logger.info("Restored the status of %d job(s).", len(before))
        self.refresh()
        current = self._current
        if self.dialog.is_open and current and current.job.key in before:
            self._current = current.model_copy(
                update={"status": before[current.job.key]}
            )
            self.open_job(current.job.key)

    def _after_marking(self, keys: list[str], status: JobStatus) -> None:
        self.table.clear_checked()
        self.refresh()
        # Like a single change: the dialog closes on a discarded job, else it stays open
        # showing the new status.
        current = self._current
        if not (self.dialog.is_open and current and current.job.key in keys):
            return
        if status is JobStatus.discarded:
            self.dialog.close()
            return
        self._current = current.model_copy(update={"status": status})
        self.open_job(current.job.key)

    def _listing_discarded(self) -> bool:
        label = self.filters.status.get()
        return presentation.status_from_label(label) is JobStatus.discarded

    def _delete_checked(self) -> None:
        """The selection bar's "Delete for good", in the Discarded filter: asks first,
        and there is no Undo."""
        keys = self.table.checked()
        if not keys:
            return
        question = _(
            "Delete {count} job(s) for good? This can't be undone; if a source still "
            "lists a job, it comes back on the next collection."
        ).format(count=len(keys))
        if not self.app.confirm(question):
            return
        self.app.repository.delete_jobs(keys)
        logger.info("Deleted %d job(s).", len(keys))
        current = self._current
        if current and current.job.key in keys:
            self.dialog.close()
            self._current = None
        self.table.clear_checked()
        self.app.on_change()
        self.app.inform(_("{count} job(s) deleted.").format(count=len(keys)))

    def _clear_checked(self) -> None:
        self.table.clear_checked()

    def _discard_checked(self) -> None:
        keys = self.table.checked()
        if not keys:
            return
        if not self.app.confirm(_("Discard {count} job(s)?").format(count=len(keys))):
            return
        self._mark(keys, JobStatus.discarded)

    def _analyze(self) -> None:
        item = self._current
        if item is None:
            self.app.show_error(ValueError(_("Pick a job to analyze.")))
            return
        llm_name = self.preview.chosen_llm()
        try:
            provider = build_llm(llm_name)
        except Exception as failure:  # noqa: BLE001 - a misconfigured provider is a notice
            self.app.show_error(failure)
            return
        profile = self.preview.chosen_profile()
        job = item.job
        self.preview.set_busy(True)
        self.app.log(
            _("Analyzing {title} ({key}) with {llm}…").format(
                title=job.title, key=job.key, llm=llm_name
            )
        )

        def finish(analysis: JobAnalysis) -> None:
            self.preview.set_busy(False)
            self.app.log(
                _("Analysis ready: {title} — fit {score}.").format(
                    title=job.title, score=analysis.fit_score
                )
            )
            self.refresh()
            self.table.select(job.key)
            # Shows the analysis, unless the dialog was closed or moved to another job.
            current = self._current
            if self.dialog.is_open and current and current.job.key == job.key:
                self.open_job(job.key)

        def fail(failure: BaseException) -> None:
            self.preview.set_busy(False)
            self.app.show_error(failure)

        self.app.run(
            analyze_job(
                job.key,
                provider,
                jobs=self.app.repository,
                profiles=self.app.repository,
                analyses=self.app.repository,
                profile_source=profile,
                notes=read_profile_notes(),
            ),
            on_done=finish,
            on_error=fail,
        )
