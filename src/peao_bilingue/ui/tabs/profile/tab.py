"""The Profile tab: one profile per source, the pasted CV, and the user's notes.

The CV (`manual`) is the profile for jobs whose source has none, like the public APIs,
and for anyone without a VanHack account. Contact data is removed before it is saved.
The tab puts the components together and does the reading, saving and importing.
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
from peao_bilingue.ui.tabs.profile.history import ProfileHistory
from peao_bilingue.ui.tabs.profile.notes import NotesEditor
from peao_bilingue.ui.tabs.profile.profile_text import ProfileText
from peao_bilingue.ui.tabs.profile.toolbar import ProfileToolbar

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

        self.toolbar = ProfileToolbar(
            self,
            manual_label(),
            on_pick=self._on_pick,
            on_read=self._read,
            on_save=self._save_manual,
            on_import=self._import,
        )
        self.toolbar.pack(fill="x", pady=(0, 8))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self.text = ProfileText(body)
        self.text.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.history = ProfileHistory(body)
        self.history.grid(row=0, column=1, sticky="nsew")

        self.notes = NotesEditor(self, on_save=self._save_notes)
        self.notes.pack(fill="x", pady=(12, 0))
        self.notes.show(read_profile_notes())

    def _on_pick(self, value: str) -> None:
        self.toolbar.pick(value)  # already set by a click; not when called directly
        self._picked_by_user = True
        self.refresh()

    def _picked(self) -> str:
        return self._labels.get(self.toolbar.picked(), MANUAL_SOURCE)

    def refresh(self) -> None:
        repository = self.app.repository
        # The CV, the sources that read a profile today and those that already have one
        # saved (even if turned off).
        names = sorted(set(profile_sources()) | set(repository.sources_with_profile()))
        names = [MANUAL_SOURCE, *(name for name in names if name != MANUAL_SOURCE)]
        self._labels = {
            (manual_label() if name == MANUAL_SOURCE else name): name for name in names
        }
        self.toolbar.set_choices(list(self._labels))
        if not self._picked_by_user or self.toolbar.picked() not in self._labels:
            # A source's saved profile if there is one; otherwise the CV, to fill in.
            saved_sources = [
                label
                for label, name in self._labels.items()
                if name != MANUAL_SOURCE and repository.last_profile(name)
            ]
            self.toolbar.pick(saved_sources[0] if saved_sources else manual_label())
        name = self._picked()
        manual = name == MANUAL_SOURCE
        self.toolbar.show_actions(manual=manual)

        saved = repository.last_profile(name)
        if manual:
            self.toolbar.show_status(
                _(
                    "Paste your CV or profile (or import a file) and save. It's the "
                    "profile for jobs whose source has none. Emails, phones and links "
                    "are removed automatically."
                )
            )
        elif saved is None:
            self.toolbar.show_status(
                _("No {source} profile read yet.").format(source=name)
            )
        else:
            self.toolbar.show_status(
                _(
                    "The {source} profile, used to analyze its jobs (no personal data):"
                ).format(source=name)
            )
        # An unsaved paste survives a refresh (another tab saving, a collection ending).
        if not (self._shown == name and self.text.edited()):
            if saved is not None:
                text = saved[1].text
            elif not manual:
                text = _("Click Read profile now.")
            else:
                text = ""
            self.text.show(text, editable=manual)
        self._shown = name

        self.history.show(repository.profile_history(name))

    def _save_manual(self) -> None:
        text = self.text.content()
        if not text:
            self.app.show_error(ValueError(_("Paste your CV or profile first.")))
            return
        profile, removed = manual_profile(text)
        self.app.repository.save_profile(profile)
        self.text.mark_saved()
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
        self.text.replace(text)
        self.toolbar.show_status(_("Imported. Check the text and click Save profile."))

    def _save_notes(self) -> None:
        text, removed = clean_notes(self.notes.content())
        save_profile_notes(text + "\n" if text else "")
        self.notes.show(read_profile_notes())
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
        self.toolbar.set_reading(True)
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
            self.toolbar.set_reading(False)
            self.app.on_change()
            self.app.inform(
                _("The {source} profile was updated.").format(source=name)
                if changed
                else _("The profile hasn't changed.")
            )

        def fail(failure: BaseException) -> None:
            self.toolbar.set_reading(False)
            self.app.show_error(failure)

        self.app.run(read(), on_done=finish, on_error=fail)
