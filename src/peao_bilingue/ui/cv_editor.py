"""The CV box: where the user pastes or imports the CV every job is analyzed with.
Settings and the first-run guide both use it; neither saves anything here."""

from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog
from typing import Any

import customtkinter as ctk

from peao_bilingue.adapters.documents import read_document
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import OutlineButton


class CVEditor(ctk.CTkFrame):
    """An Import button over a text box. A file's text replaces the box's, still to
    be checked and saved by whoever holds the editor (`content()`)."""

    def __init__(
        self,
        master: Any,
        *,
        on_error: Callable[[BaseException], None],
        height: int = 260,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._on_error = on_error
        OutlineButton(
            self, text=_("Import file…"), width=130, command=self._pick_file
        ).pack(anchor="w", pady=(0, 8))
        self.box = ctk.CTkTextbox(self, wrap="word", height=height)
        self.box.pack(fill="x")

    def _pick_file(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self,
            title=_("Import your CV"),
            filetypes=[(_("CV or profile"), "*.pdf *.txt *.md")],
        )
        if chosen:
            self.import_file(Path(chosen))

    def import_file(self, path: Path) -> None:
        try:
            text = read_document(path)
        except Exception as failure:  # noqa: BLE001 - a broken file is a notice
            self._on_error(failure)
            return
        if not text:
            self._on_error(
                ValueError(
                    _(
                        "No text found in the file (a scanned PDF is an image). Paste "
                        "the text instead."
                    )
                )
            )
            return
        self.box.delete("1.0", "end")
        self.box.insert("1.0", text)

    def show(self, text: str) -> None:
        """The saved CV: what is typed or imported after this counts as an edit."""
        self.box.delete("1.0", "end")
        self.box.insert("1.0", text)
        self.mark_saved()

    def content(self) -> str:
        text: str = self.box.get("1.0", "end").strip()
        return text

    def edited(self) -> bool:
        """Typed, pasted or imported since it was shown or saved."""
        return bool(self.box._textbox.edit_modified())

    def mark_saved(self) -> None:
        self.box._textbox.edit_modified(False)
