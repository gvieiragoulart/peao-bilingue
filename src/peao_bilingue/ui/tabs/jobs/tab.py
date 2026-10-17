"""The Jobs tab: puts the filters, the table and the preview together and does the work
they ask for (listing, marking, the per-job analysis). The components never touch the
repository, the settings or an LLM."""

import webbrowser
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config, factories
from peao_bilingue.application.analysis import analyze_job
from peao_bilingue.composition import build_llm, read_profile_notes
from peao_bilingue.config import settings
from peao_bilingue.domain.analysis import JobAnalysis
from peao_bilingue.domain.jobs import JobStatus
from peao_bilingue.i18n import _
from peao_bilingue.ui.tabs.jobs.filters import JobFilters
from peao_bilingue.ui.tabs.jobs.preview import JobPreview
from peao_bilingue.ui.tabs.jobs.table import JobTable

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App

LIMIT = 500


class JobsTab(ctk.CTkFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.filters = JobFilters(self, on_apply=self.refresh)
        self.filters.pack(fill="x", pady=(0, 8))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self.table = JobTable(body)
        self.table.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.table.on_select(self._show_detail)

        self.preview = JobPreview(
            body,
            on_analyze=self._analyze,
            on_open=self._open,
            on_change_status=self._change_status,
            on_pick_llm=self._remember_llm,
        )
        self.preview.grid(row=0, column=1, sticky="nsew")

    def refresh(self) -> None:
        repository = self.app.repository
        self.filters.set_options(
            [search.name for search in repository.list_searches()],
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
        self.table.show(jobs)
        self.preview.show_text(
            _("{count} job(s). Pick one to see its analysis or to analyze it.").format(
                count=len(jobs)
            )
        )

    def _remember_llm(self, name: str) -> None:
        # The last one picked becomes the default next time.
        config.save({"analysis_llm": name})

    def _show_detail(self) -> None:
        item = self.table.selected_job()
        if item is None:
            return
        analysis = self.app.repository.current_analysis(item.job.key)
        self.preview.show_job(item, analysis)

    def _open(self) -> None:
        item = self.table.selected_job()
        if item is not None:
            webbrowser.open(item.job.url)

    def _change_status(self, status: JobStatus) -> None:
        item = self.table.selected_job()
        if item is None:
            return
        key = item.job.key
        self.app.repository.change_status(key, status)
        self.refresh()
        self.table.select(key)

    def _analyze(self) -> None:
        item = self.table.selected_job()
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
