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
from peao_bilingue.ui import presentation
from peao_bilingue.ui.presentation import KeywordGroup
from peao_bilingue.ui.tabs.jobs.dialog import JobDialog
from peao_bilingue.ui.tabs.jobs.filters import JobFilters
from peao_bilingue.ui.tabs.jobs.table import JobTable
from peao_bilingue.ui.widgets import Hint

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
        self.filters.pack(fill="x", pady=(0, 4))
        self.count = Hint(self, text="", anchor="w")
        self.count.pack(fill="x", pady=(0, 4))

        # What the ticked boxes are for.
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 4))
        self.checked_count = Hint(bar, text="", anchor="w")
        self.checked_count.pack(side="left", padx=(0, 12))
        self.discard_checked = ctk.CTkButton(
            bar, text=_("Discard selected"), width=150, command=self._discard_checked
        )
        self.discard_checked.pack(side="left", padx=(0, 6))
        self.clear_checked = ctk.CTkButton(
            bar,
            text=_("Clear selection"),
            width=120,
            fg_color="transparent",
            border_width=1,
            command=self._clear_checked,
        )
        self.clear_checked.pack(side="left")

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
        self.count.configure(text=presentation.job_count(len(jobs)))

    def open_job(self, key: str) -> None:
        """Opens the job's dialog (a click on its row)."""
        item = self.table.job(key)
        if item is None and self._current and self._current.job.key == key:
            item = self._current  # left the filtered list, but still open
        if item is None:
            return
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
        if self._current is None:
            return
        key = self._current.job.key
        self.app.repository.change_status(key, status)
        # The dialog stays open: the job may even have left the filtered list.
        self.refresh()
        self.table.select(key)

    def _show_checked(self) -> None:
        count = len(self.table.checked())
        self.checked_count.configure(text=_("{count} selected").format(count=count))
        state = "normal" if count else "disabled"
        self.discard_checked.configure(state=state)
        self.clear_checked.configure(state=state)

    def _clear_checked(self) -> None:
        self.table.clear_checked()

    def _discard_checked(self) -> None:
        keys = self.table.checked()
        if not keys:
            return
        if not self.app.confirm(_("Discard {count} job(s)?").format(count=len(keys))):
            return
        self.app.repository.change_statuses(keys, JobStatus.discarded)
        logger.info("Discarded %d job(s).", len(keys))
        self.table.clear_checked()
        self.refresh()
        # The dialog stays open, showing the new status, like a single change.
        current = self._current
        if self.dialog.is_open and current and current.job.key in keys:
            self._current = current.model_copy(update={"status": JobStatus.discarded})
            self.open_job(current.job.key)

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
