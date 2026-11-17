"""Picking and reading the CV file, for Settings (which saves it at once) and the
first-run guide (a box the user can also paste into, saved at Finish)."""

from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog
from typing import Any

import customtkinter as ctk

from peao_bilingue.adapters.documents import read_document
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import OutlineButton


def pick_cv_file(parent: Any) -> Path | None:
    chosen = filedialog.askopenfilename(
        parent=parent,
        title=_("Import your CV"),
        filetypes=[(_("CV or profile"), "*.pdf *.txt *.md")],
    )
    return Path(chosen) if chosen else None


def read_cv_file(path: Path) -> str:
    """The file's text. ValueError when it has none (a scanned PDF is an image)."""
    text = read_document(path)
    if not text:
        raise ValueError(
            _(
                "No text found in the file (a scanned PDF is an image). Use a PDF with "
                "selectable text, or a .txt file."
            )
        )
    return text


class CVEditor(ctk.CTkFrame):
    """The guide's CV: an Import button over a text box. A file's text replaces the
    box's; the guide saves `content()` at Finish."""

    def __init__(
        self, master: Any, *, on_error: Callable[[BaseException], None]
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._on_error = on_error
        OutlineButton(
            self, text=_("Import file…"), width=130, command=self._pick_file
        ).pack(anchor="w", pady=(0, 8))
        self.box = ctk.CTkTextbox(self, wrap="word", height=260)
        self.box.pack(fill="x")

    def _pick_file(self) -> None:
        chosen = pick_cv_file(self)
        if chosen is not None:
            self.import_file(chosen)

    def import_file(self, path: Path) -> None:
        try:
            text = read_cv_file(path)
        except Exception as failure:  # noqa: BLE001 - a broken file is a notice
            self._on_error(failure)
            return
        self.box.delete("1.0", "end")
        self.box.insert("1.0", text)

    def content(self) -> str:
        text: str = self.box.get("1.0", "end").strip()
        return text
