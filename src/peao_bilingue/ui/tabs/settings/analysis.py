"""The Settings tab's "Who analyzes": which LLM the Jobs tab picks by default. Each LLM
is configured on the LLMs tab."""

from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.config import Settings
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Heading, Hint


def llm_labels() -> dict[str, str]:
    """name -> label: the picker shows the label ("Ollama (local, free)"), so the cost
    is in plain view."""
    return {
        name: factories.llms.class_of(name).label for name in factories.llms.available()
    }


class AnalysisSection(ctk.CTkFrame):
    def __init__(self, master: Any) -> None:
        super().__init__(master, fg_color="transparent")
        Heading(self, _("Who analyzes")).pack(anchor="w")
        Hint(
            self,
            _(
                "The collection calls no LLM: analysis is requested job by job, on the "
                "Jobs tab, with the LLM picked there. The default below is the one "
                "already selected."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(row, text=_("Default LLM")).pack(side="left", padx=(8, 12))
        self.llm = ctk.CTkOptionMenu(row, values=list(llm_labels().values()), width=220)
        self.llm.pack(side="left")
        Hint(row, _("Each LLM's key and model are on the LLMs tab.")).pack(
            side="left", padx=12
        )

    def load(self, current: Settings) -> None:
        labels = llm_labels()
        self.llm.set(labels.get(current.analysis_llm, next(iter(labels.values()))))

    def values(self) -> dict[str, Any]:
        by_label = {label: name for name, label in llm_labels().items()}
        return {"analysis_llm": by_label[self.llm.get()]}
