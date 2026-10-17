"""The Runs tab's top row: what a collection does, and the button to start one."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Hint


class CollectBar(ctk.CTkFrame):
    def __init__(self, master: Any, on_collect: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        Hint(
            self,
            _(
                "The collection looks for new jobs and saves them, with no LLM: analyze "
                "the ones you want on the Jobs tab."
            ),
        ).pack(side="left")
        self.button = ctk.CTkButton(
            self, text=_("Collect now"), width=140, command=on_collect
        )
        self.button.pack(side="right")

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.button.configure(state="disabled", text=_("Collecting…"))
        else:
            self.button.configure(state="normal", text=_("Collect now"))
