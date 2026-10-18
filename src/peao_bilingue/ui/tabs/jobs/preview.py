"""The body of the job's panel: the fit, the analysis one part at a time, and a footer
with what can be done with the job."""

import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.domain.jobs import JobStatus, ListedJob
from peao_bilingue.domain.profile import MANUAL_SOURCE
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation, theme
from peao_bilingue.ui.presentation import JobPanel
from peao_bilingue.ui.tabs.jobs.job_status import JobStatusButtons
from peao_bilingue.ui.widgets import OutlineButton

PADDING = 20
RING_SIZE = 76
RING_WIDTH = 7
RING_TRACK = ("#DCE0E5", "#343A44")


def no_profile_label() -> str:
    return _("(none)")


class FitRing(tk.Canvas):
    """The fit as a ring filled to its score, in the color of its range."""

    def __init__(self, master: Any) -> None:
        self._scale = float(ctk.ScalingTracker.get_widget_scaling(master))
        size = round(RING_SIZE * self._scale)
        super().__init__(
            master, width=size, height=size, highlightthickness=0, borderwidth=0
        )
        self.score: int | None = None

    def draw(self, score: int) -> None:
        self.score = score
        self.delete("all")
        self.configure(background=theme.pick(theme.RAISED))
        size = round(RING_SIZE * self._scale)
        width = round(RING_WIDTH * self._scale)
        box = (width, width, size - width, size - width)
        self.create_oval(*box, outline=theme.pick(RING_TRACK), width=width)
        if score:
            self.create_arc(
                *box,
                start=90,
                extent=-3.6 * min(score, 99.9),  # 360 would draw nothing
                style="arc",
                outline=theme.pick(presentation.fit_color(score)),
                width=width,
            )
        self.create_text(
            size // 2,
            size // 2,
            text=str(score),
            fill=theme.pick(theme.TEXT),
            font=(theme.text_family(), -round(21 * self._scale), "bold"),
        )


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
        self._panel: JobPanel | None = None
        self._section = "preparation"  # kept from one job to the next
        # The picker shows the label ("Ollama (local, free)"): the cost is in plain view.
        self._llms = {
            factories.llms.class_of(name).label: name
            for name in factories.llms.available()
        }

        # The footer first, from the bottom: it stays whole however short the panel.
        footer = ctk.CTkFrame(self, fg_color=theme.RAISED, corner_radius=0)
        footer.pack(side="bottom", fill="x")
        choice = ctk.CTkFrame(footer, fg_color="transparent")
        choice.pack(fill="x", padx=PADDING, pady=(14, 0))
        ctk.CTkLabel(choice, text="LLM", text_color=theme.MUTED).pack(
            side="left", padx=(0, 6)
        )
        self.llm = ctk.CTkOptionMenu(
            choice,
            values=list(self._llms),
            width=150,
            command=lambda label: on_pick_llm(self._llms[label]),
        )
        self.llm.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(choice, text=_("Profile"), text_color=theme.MUTED).pack(
            side="left", padx=(0, 6)
        )
        self.profile = ctk.CTkOptionMenu(choice, values=[no_profile_label()], width=100)
        self.profile.pack(side="left")
        self.analyze_button = ctk.CTkButton(
            choice,
            text=_("Analyze"),
            width=110,
            font=ctk.CTkFont(weight="bold"),
            command=on_analyze,
        )
        self.analyze_button.pack(side="right")

        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.pack(fill="x", padx=PADDING, pady=(10, 0))
        self.status_buttons = JobStatusButtons(actions, on_change=on_change_status)
        self.status_buttons.pack(side="left")
        OutlineButton(actions, text=_("Open job"), width=110, command=on_open).pack(
            side="right"
        )
        ctk.CTkFrame(footer, fg_color="transparent", height=14).pack()

        # The body, packed again on every job: what shows depends on the analysis.
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=PADDING, pady=(0, 12))
        self.fit_card = ctk.CTkFrame(self.body, fg_color=theme.RAISED, corner_radius=12)
        self.ring = FitRing(self.fit_card)
        self.ring.pack(side="left", padx=14, pady=14)
        words = ctk.CTkFrame(self.fit_card, fg_color="transparent")
        words.pack(side="left", fill="both", expand=True, padx=(0, 14), pady=12)
        self.fit_label = ctk.CTkLabel(
            words, text="", font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
        )
        self.fit_label.pack(fill="x")
        self.summary = ctk.CTkLabel(words, text="", anchor="w", justify="left")
        self.summary.pack(fill="x")
        self.notes = ctk.CTkLabel(
            self.body,
            text="",
            font=theme.small(),
            text_color=theme.MUTED,
            anchor="w",
            justify="left",
        )
        self.sections = ctk.CTkSegmentedButton(
            self.body, values=[""], command=self._pick_title
        )
        self.detail = ctk.CTkTextbox(self.body, wrap="word", border_width=0)
        self.detail.configure(state="disabled")
        self.outdated = ctk.CTkLabel(
            self.body,
            text="",
            fg_color=theme.ACCENT_SOFT,
            text_color=theme.ACCENT_TEXT,
            corner_radius=8,
            anchor="w",
            justify="left",
            padx=12,
            pady=8,
        )
        self.footnote = ctk.CTkLabel(
            self.body,
            text="",
            font=theme.small(),
            text_color=theme.MUTED,
            anchor="w",
            justify="left",
        )
        self.body.bind("<Configure>", lambda event: self._wrap(event.width))

    # ---- what the panel shows

    def show_job(self, item: ListedJob, panel: JobPanel) -> None:
        # By default, a job is analyzed with the profile from its own source, or with
        # the pasted CV when its source has none (the public APIs).
        if item.job.source in self._sources_with_profile:
            self.profile.set(item.job.source)
        elif MANUAL_SOURCE in self._sources_with_profile:
            self.profile.set(MANUAL_SOURCE)
        self.status_buttons.show(item.status)
        self._panel = panel

        for widget in self.body.winfo_children():
            widget.pack_forget()
        if panel.fit is not None:
            self.ring.draw(panel.fit)
            self.fit_label.configure(
                text=panel.fit_label.upper(),
                text_color=presentation.soft(
                    presentation.fit_color(panel.fit), theme.RAISED
                )[1],
            )
            self.summary.configure(text=panel.summary)
            self.fit_card.pack(fill="x", pady=(0, 10))
        self.notes.configure(text="\n".join(panel.notes))
        self.notes.pack(fill="x", pady=(0, 10))
        if panel.sections:
            keys = [section.key for section in panel.sections]
            if self._section not in keys:
                self._section = keys[0]
            self.sections.configure(
                values=[section.title for section in panel.sections]
            )
            self.sections.pack(anchor="w", pady=(0, 8))
            self.detail.pack(fill="both", expand=True)
            self.pick_section(self._section)
            if panel.outdated:
                self.outdated.configure(text=panel.outdated)
                self.outdated.pack(fill="x", pady=(10, 0))
            self.footnote.configure(text=panel.footer)
            self.footnote.pack(fill="x", pady=(8, 0))
        else:
            self.detail.pack(fill="both", expand=True)
            self.show_text(panel.footer)

    def pick_section(self, key: str) -> None:
        """Shows one part of the analysis: preparation, questions, gaps, profile."""
        panel = self._panel
        if panel is None:
            return
        for section in panel.sections:
            if section.key == key:
                self._section = key
                self.sections.set(section.title)
                self.show_text(section.text)

    def _pick_title(self, title: str) -> None:
        panel = self._panel
        if panel is None:
            return
        for section in panel.sections:
            if section.title == title:
                self.pick_section(section.key)

    def show_text(self, text: str) -> None:
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def _wrap(self, width: int) -> None:
        for label in (self.notes, self.outdated, self.footnote):
            label.configure(wraplength=max(width - 24, 120))
        ring = round(RING_SIZE * float(ctk.ScalingTracker.get_widget_scaling(self)))
        self.summary.configure(wraplength=max(width - ring - 60, 120))

    # ---- the pickers

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
