"""The Profile tab: one profile per source, the pasted CV, and the user's notes.

The CV (`manual`) is the profile for jobs whose source has none, like the public APIs,
and for anyone without a VanHack account. Contact data is removed before it is saved.
"""

from pathlib import Path
from tkinter import filedialog
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.adapters.documents import read_document
from peao_bilingue.application.profile import clean_notes, manual_profile
from peao_bilingue.composition import read_profile_notes, save_profile_notes
from peao_bilingue.config import settings
from peao_bilingue.domain.profile import MANUAL_SOURCE, ProfileSource
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation
from peao_bilingue.ui.widgets import Table

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


def manual_label() -> str:
    return _("My CV (pasted)")


def profile_sources() -> list[str]:
    """Enabled sources that can read the profile the user keeps there."""
    return [
        name
        for name in settings.enabled_sources
        if issubclass(factories.sources.class_of(name), ProfileSource)
    ]


class ProfileTab(ctk.CTkFrame):
    """One profile per source: the one on VanHack is not the one on LinkedIn."""

    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        # What the picker shows -> the source's name (the CV has a friendlier label).
        self._labels: dict[str, str] = {}
        self._shown: str | None = None
        # Until the user picks a source, the tab shows the best default (see refresh).
        self._picked_by_user = False

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(top, text=_("Source")).pack(side="left", padx=(0, 4))
        self.source = ctk.CTkOptionMenu(
            top, values=[manual_label()], width=170, command=self._on_pick
        )
        self.source.pack(side="left", padx=(0, 12))
        self.status = ctk.CTkLabel(top, text="", wraplength=520, justify="left")
        self.status.pack(side="left")
        self.read_button = ctk.CTkButton(
            top, text=_("Read profile now"), width=140, command=self._read
        )
        self.save_button = ctk.CTkButton(
            top, text=_("Save profile"), width=120, command=self._save_manual
        )
        self.import_button = ctk.CTkButton(
            top,
            text=_("Import file…"),
            width=130,
            fg_color="transparent",
            border_width=1,
            command=self._import,
        )

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self.text = ctk.CTkTextbox(body, wrap="word")
        self.text.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.history = Table(
            body,
            [("read_at", _("Read on"), 120), ("fields", _("What changed"), 260)],
        )
        self.history.grid(row=0, column=1, sticky="nsew")

        notes = ctk.CTkFrame(self, fg_color="transparent")
        notes.pack(fill="x", pady=(12, 0))
        heading = ctk.CTkFrame(notes, fg_color="transparent")
        heading.pack(fill="x")
        ctk.CTkLabel(
            heading, text=_("Notes about you"), font=ctk.CTkFont(weight="bold")
        ).pack(side="left")
        ctk.CTkButton(
            heading, text=_("Save notes"), width=120, command=self._save_notes
        ).pack(side="right")
        ctk.CTkLabel(
            notes,
            text=_(
                "They go into every analysis, with any profile: what you want and don't "
                "want, and what the profile doesn't show (e.g. \"I want remote jobs "
                'only", "I\'ve led a team of 5").'
            ),
            text_color="gray55",
            wraplength=900,
            justify="left",
        ).pack(anchor="w")
        self.notes = ctk.CTkTextbox(notes, wrap="word", height=100)
        self.notes.pack(fill="x", pady=(4, 0))
        self._load_notes()

    def _on_pick(self, value: str) -> None:
        self.source.set(value)  # already set by a click; not when called directly
        self._picked_by_user = True
        self.refresh()

    def _picked(self) -> str:
        return self._labels.get(self.source.get(), MANUAL_SOURCE)

    def refresh(self) -> None:
        repository = self.app.repository
        # The CV, the sources that read a profile today and those that already have one
        # saved (even if turned off).
        names = (
            sorted(set(profile_sources()) | set(repository.sources_with_profile()))
            or []
        )
        names = [MANUAL_SOURCE, *(name for name in names if name != MANUAL_SOURCE)]
        self._labels = {
            (manual_label() if name == MANUAL_SOURCE else name): name for name in names
        }
        self.source.configure(values=list(self._labels))
        if not self._picked_by_user or self.source.get() not in self._labels:
            # A source's saved profile if there is one; otherwise the CV, to fill in.
            saved_sources = [
                label
                for label, name in self._labels.items()
                if name != MANUAL_SOURCE and repository.last_profile(name)
            ]
            self.source.set(saved_sources[0] if saved_sources else manual_label())
        name = self._picked()
        manual = name == MANUAL_SOURCE

        for button in (self.read_button, self.save_button, self.import_button):
            button.pack_forget()
        if manual:
            self.save_button.pack(side="right")
            self.import_button.pack(side="right", padx=6)
        else:
            self.read_button.pack(side="right")

        saved = repository.last_profile(name)
        if manual:
            self.status.configure(
                text=_(
                    "Paste your CV or profile (or import a file) and save. It's the "
                    "profile for jobs whose source has none. Emails, phones and links "
                    "are removed automatically."
                )
            )
        elif saved is None:
            self.status.configure(
                text=_("No {source} profile read yet.").format(source=name)
            )
        else:
            self.status.configure(
                text=_(
                    "The {source} profile, used to analyze its jobs (no personal data):"
                ).format(source=name)
            )
        # An unsaved paste survives a refresh (another tab saving, a collection ending).
        edited = self._shown == name and bool(self.text._textbox.edit_modified())
        if not edited:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            if saved is not None:
                self.text.insert("1.0", saved[1].text)
            elif not manual:
                self.text.insert("1.0", _("Click Read profile now."))
            self.text._textbox.edit_modified(False)
            self.text.configure(state="normal" if manual else "disabled")
        self._shown = name

        self.history.fill(
            [
                (
                    str(item["id"]),
                    (
                        f"{item['read_at']:%d/%m/%Y %H:%M}",
                        ", ".join(item["changed_fields"]),
                    ),
                )
                for item in repository.profile_history(name)
            ]
        )

    def _save_manual(self) -> None:
        text = self.text.get("1.0", "end").strip()
        if not text:
            self.app.show_error(ValueError(_("Paste your CV or profile first.")))
            return
        profile, removed = manual_profile(text)
        self.app.repository.save_profile(profile)
        self.text._textbox.edit_modified(False)
        self.app.on_change()
        self.app.inform(presentation.saved_without_contact_data(removed))

    def _import(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self,
            title=_("Import your CV"),
            filetypes=[(_("CV or profile"), "*.pdf *.txt *.md")],
        )
        if not chosen:
            return
        try:
            text = read_document(Path(chosen))
        except Exception as failure:  # noqa: BLE001 - a broken file is a notice
            self.app.show_error(failure)
            return
        if not text:
            self.app.show_error(
                ValueError(
                    _(
                        "No text found in the file (a scanned PDF is an image). Paste "
                        "the text instead."
                    )
                )
            )
            return
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.status.configure(
            text=_("Imported. Check the text and click Save profile.")
        )

    def _load_notes(self) -> None:
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", read_profile_notes())

    def _save_notes(self) -> None:
        text, removed = clean_notes(self.notes.get("1.0", "end"))
        save_profile_notes(text + "\n" if text else "")
        self._load_notes()
        self.app.inform(presentation.saved_without_contact_data(removed))

    def _read(self) -> None:
        name = self._picked()
        if name not in profile_sources():
            self.app.show_error(
                ValueError(
                    _("The {source} source is off or doesn't read a profile.").format(
                        source=name
                    )
                )
            )
            return
        self.read_button.configure(state="disabled", text=_("Reading…"))
        repository = self.app.repository

        async def read() -> bool:
            source = factories.sources.create(name)
            if not isinstance(source, ProfileSource):  # already filtered above
                raise TypeError(f"The {name} source doesn't read a profile.")
            async with source:
                profile = await source.read_profile()
            _id, changed = repository.save_profile(profile)
            return changed

        def finish(changed: bool) -> None:
            self.read_button.configure(state="normal", text=_("Read profile now"))
            self.app.on_change()
            self.app.inform(
                _("The {source} profile was updated.").format(source=name)
                if changed
                else _("The profile hasn't changed.")
            )

        def fail(failure: BaseException) -> None:
            self.read_button.configure(state="normal", text=_("Read profile now"))
            self.app.show_error(failure)

        self.app.run(read(), on_done=finish, on_error=fail)
