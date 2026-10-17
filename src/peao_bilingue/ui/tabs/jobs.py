"""The Jobs tab: the list, filters, detail and the per-job analysis."""

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
from peao_bilingue.ui.widgets import Table

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App

LIMIT = 500


def no_profile_label() -> str:
    return _("(none)")


class JobsTab(ctk.CTkFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._jobs: dict[str, ListedJob] = {}
        self._sources_with_profile: list[str] = []
        # The picker shows the label ("Ollama (local, free)"): the cost is in plain view.
        self._llms = {
            factories.llms.class_of(name).label: name
            for name in factories.llms.available()
        }

        # Its own row: next to the filters the field wouldn't fit the window's width.
        self.search_text = ctk.CTkEntry(
            self,
            placeholder_text=_(
                "Search the title, company, location, skills and description (Enter "
                "to filter)"
            ),
        )
        self.search_text.pack(fill="x", pady=(0, 6))
        self.search_text.bind("<Return>", lambda _event: self.refresh())

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.pack(fill="x", pady=(0, 8))
        self.status = ctk.CTkOptionMenu(
            filters, values=presentation.status_options(), width=130
        )
        self.source = ctk.CTkOptionMenu(
            filters, values=[presentation.all_label()], width=130
        )
        self.search = ctk.CTkOptionMenu(
            filters, values=[presentation.all_label()], width=170
        )
        self.score = ctk.CTkEntry(filters, width=70, placeholder_text=_("fit ≥"))
        for label, widget in (
            (_("Status"), self.status),
            (_("Source"), self.source),
            (_("Search"), self.search),
            (_("Minimum fit"), self.score),
        ):
            ctk.CTkLabel(filters, text=label).pack(side="left", padx=(0, 4))
            widget.pack(side="left", padx=(0, 12))
        ctk.CTkButton(filters, text=_("Filter"), width=90, command=self.refresh).pack(
            side="left"
        )

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self.table = Table(
            body,
            [
                ("fit", _("Fit"), 45),
                ("title", _("Job"), 300),
                ("location", _("Location"), 160),
                ("source", _("Source"), 80),
                ("status", _("Status"), 90),
            ],
        )
        self.table.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.table.on_select(self._show_detail)

        side = ctk.CTkFrame(body, fg_color="transparent")
        side.grid(row=0, column=1, sticky="nsew")
        self.detail = ctk.CTkTextbox(side, wrap="word")
        self.detail.pack(fill="both", expand=True)
        self.detail.configure(state="disabled")

        # In rows: the pickers and the buttons together don't fit the panel's width.
        choice = ctk.CTkFrame(side, fg_color="transparent")
        choice.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(choice, text="LLM").pack(side="left", padx=(0, 4))
        self.llm = ctk.CTkOptionMenu(
            choice, values=list(self._llms), width=180, command=self._remember_llm
        )
        self.llm.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(choice, text=_("Profile")).pack(side="left", padx=(0, 4))
        self.profile = ctk.CTkOptionMenu(choice, values=[no_profile_label()], width=120)
        self.profile.pack(side="left")

        actions = ctk.CTkFrame(side, fg_color="transparent")
        actions.pack(fill="x", pady=(6, 0))
        self.analyze_button = ctk.CTkButton(
            actions, text=_("Analyze"), width=110, command=self._analyze
        )
        self.analyze_button.pack(side="left")
        ctk.CTkButton(
            actions,
            text=_("Open job"),
            width=110,
            fg_color="transparent",
            border_width=1,
            command=self._open,
        ).pack(side="left", padx=6)

        mark = ctk.CTkFrame(side, fg_color="transparent")
        mark.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(mark, text=_("Mark as:")).pack(side="left", padx=(0, 6))
        labels = presentation.job_status_labels()
        for status in (JobStatus.studying, JobStatus.applied, JobStatus.discarded):
            ctk.CTkButton(
                mark,
                text=labels[status],
                width=96,
                fg_color="transparent",
                border_width=1,
                command=lambda s=status: self._change_status(s),
            ).pack(side="left", padx=(0, 6))

    def refresh(self) -> None:
        repository = self.app.repository
        searches = [search.name for search in repository.list_searches()]
        everything = presentation.all_label()
        self.search.configure(values=[everything, *searches])
        self.source.configure(values=[everything, *factories.sources.available()])
        self._refresh_selectors()

        try:
            minimum = presentation.parse_min_score(self.score.get())
        except ValueError as failure:
            self.app.show_error(failure)
            return

        def selected_filter(widget: ctk.CTkOptionMenu) -> str | None:
            value = widget.get()
            return None if value == everything else value

        jobs = repository.list_jobs(
            status=presentation.status_from_label(self.status.get()),
            min_score=minimum,
            search=selected_filter(self.search),
            source=selected_filter(self.source),
            search_text=self.search_text.get().strip() or None,
            limit=LIMIT,
        )
        self._jobs = {item.job.key: item for item in jobs}
        self.table.fill(
            [(key, presentation.job_row(item)) for key, item in self._jobs.items()]
        )
        self._write_detail(
            _("{count} job(s). Pick one to see its analysis or to analyze it.").format(
                count=len(jobs)
            )
        )

    def _refresh_selectors(self) -> None:
        self._sources_with_profile = self.app.repository.sources_with_profile()
        none = no_profile_label()
        self.profile.configure(values=self._sources_with_profile or [none])
        if self.profile.get() not in self._sources_with_profile:
            self.profile.set(
                self._sources_with_profile[0] if self._sources_with_profile else none
            )
        labels = {name: label for label, name in self._llms.items()}
        self.llm.set(labels.get(settings.analysis_llm, next(iter(self._llms))))

    def _remember_llm(self, label: str) -> None:
        # The last one picked becomes the default next time.
        config.save({"analysis_llm": self._llms[label]})

    def _selected(self) -> ListedJob | None:
        key = self.table.selected()
        return self._jobs.get(key) if key else None

    def _select(self, key: str) -> None:
        if self.table.tree.exists(key):
            self.table.tree.selection_set(key)

    def _show_detail(self) -> None:
        item = self._selected()
        if item is None:
            return
        # By default, a job is analyzed with the profile from its own source.
        if item.job.source in self._sources_with_profile:
            self.profile.set(item.job.source)
        analysis = self.app.repository.current_analysis(item.job.key)
        self._write_detail(presentation.job_detail(item, analysis))

    def _write_detail(self, text: str) -> None:
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def _open(self) -> None:
        item = self._selected()
        if item is not None:
            webbrowser.open(item.job.url)

    def _change_status(self, status: JobStatus) -> None:
        item = self._selected()
        if item is None:
            return
        key = item.job.key
        self.app.repository.change_status(key, status)
        self.refresh()
        self._select(key)

    def _analyze(self) -> None:
        item = self._selected()
        if item is None:
            self.app.show_error(ValueError(_("Pick a job to analyze.")))
            return
        llm_name = self._llms[self.llm.get()]
        try:
            provider = build_llm(llm_name)
        except Exception as failure:  # noqa: BLE001 - a misconfigured provider is a notice
            self.app.show_error(failure)
            return
        profile = self.profile.get()
        job = item.job
        self.analyze_button.configure(state="disabled", text=_("Analyzing…"))
        self.app.log(
            _("Analyzing {title} ({key}) with {llm}…").format(
                title=job.title, key=job.key, llm=llm_name
            )
        )

        def release() -> None:
            self.analyze_button.configure(state="normal", text=_("Analyze"))

        def finish(analysis: JobAnalysis) -> None:
            release()
            self.app.log(
                _("Analysis ready: {title} — fit {score}.").format(
                    title=job.title, score=analysis.fit_score
                )
            )
            self.refresh()
            self._select(job.key)

        def fail(failure: BaseException) -> None:
            release()
            self.app.show_error(failure)

        self.app.run(
            analyze_job(
                job.key,
                provider,
                jobs=self.app.repository,
                profiles=self.app.repository,
                analyses=self.app.repository,
                profile_source=None if profile == no_profile_label() else profile,
                notes=read_profile_notes(),
            ),
            on_done=finish,
            on_error=fail,
        )
