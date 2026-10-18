"""The body of the job's dialog: the detail and what can be done with the job."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.domain.analysis import SavedAnalysis
from peao_bilingue.domain.jobs import JobStatus, ListedJob
from peao_bilingue.domain.profile import MANUAL_SOURCE
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation
from peao_bilingue.ui.tabs.jobs.job_status import JobStatusButtons


def no_profile_label() -> str:
    return _("(none)")


class JobPreview(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        *,
        on_analyze: Callable[[], None],
        on_open: Callable[[], None],
        on_change_status: Callable[[JobStatus], None],
        on_pick_llm: Callable[[str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._sources_with_profile: list[str] = []
        # The picker shows the label ("Ollama (local, free)"): the cost is in plain view.
        self._llms = {
            factories.llms.class_of(name).label: name
            for name in factories.llms.available()
        }

        self.detail = ctk.CTkTextbox(self, wrap="word")
        self.detail.pack(fill="both", expand=True)
        self.detail.configure(state="disabled")

        # In rows: the pickers and the buttons together don't fit the panel's width.
        choice = ctk.CTkFrame(self, fg_color="transparent")
        choice.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(choice, text="LLM").pack(side="left", padx=(0, 4))
        self.llm = ctk.CTkOptionMenu(
            choice,
            values=list(self._llms),
            width=180,
            command=lambda label: on_pick_llm(self._llms[label]),
        )
        self.llm.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(choice, text=_("Profile")).pack(side="left", padx=(0, 4))
        self.profile = ctk.CTkOptionMenu(choice, values=[no_profile_label()], width=120)
        self.profile.pack(side="left")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", pady=(6, 0))
        self.analyze_button = ctk.CTkButton(
            actions, text=_("Analyze"), width=110, command=on_analyze
        )
        self.analyze_button.pack(side="left")
        ctk.CTkButton(
            actions,
            text=_("Open job"),
            width=110,
            fg_color="transparent",
            border_width=1,
            command=on_open,
        ).pack(side="left", padx=6)

        JobStatusButtons(self, on_change=on_change_status).pack(fill="x", pady=(6, 0))

    def show_text(self, text: str) -> None:
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def show_job(self, item: ListedJob, analysis: SavedAnalysis | None) -> None:
        # By default, a job is analyzed with the profile from its own source, or with
        # the pasted CV when its source has none (the public APIs).
        if item.job.source in self._sources_with_profile:
            self.profile.set(item.job.source)
        elif MANUAL_SOURCE in self._sources_with_profile:
            self.profile.set(MANUAL_SOURCE)
        self.show_text(presentation.job_detail(item, analysis))

    def set_profiles(self, sources_with_profile: list[str]) -> None:
        self._sources_with_profile = sources_with_profile
        none = no_profile_label()
        self.profile.configure(values=sources_with_profile or [none])
        if self.profile.get() not in sources_with_profile:
            self.profile.set(sources_with_profile[0] if sources_with_profile else none)

    def set_llm(self, name: str) -> None:
        labels = {llm: label for label, llm in self._llms.items()}
        self.llm.set(labels.get(name, next(iter(self._llms))))

    def chosen_llm(self) -> str:
        return self._llms[self.llm.get()]

    def chosen_profile(self) -> str | None:
        profile: str = self.profile.get()
        return None if profile == no_profile_label() else profile

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.analyze_button.configure(state="disabled", text=_("Analyzing…"))
        else:
            self.analyze_button.configure(state="normal", text=_("Analyze"))
