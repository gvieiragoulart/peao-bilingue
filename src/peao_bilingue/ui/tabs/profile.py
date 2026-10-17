"""The Profile tab: one profile per source, with its history."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.config import settings
from peao_bilingue.domain.profile import ProfileSource
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Table

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


def none_label() -> str:
    return _("(none)")


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

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(top, text=_("Source")).pack(side="left", padx=(0, 4))
        self.source = ctk.CTkOptionMenu(
            top, values=[none_label()], width=140, command=lambda _value: self.refresh()
        )
        self.source.pack(side="left", padx=(0, 12))
        self.status = ctk.CTkLabel(top, text="")
        self.status.pack(side="left")
        self.button = ctk.CTkButton(
            top, text=_("Read profile now"), width=140, command=self._read
        )
        self.button.pack(side="right")

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

    def refresh(self) -> None:
        repository = self.app.repository
        # The sources that read a profile today and those that already have one saved
        # (even if turned off).
        sources = sorted(
            set(profile_sources()) | set(repository.sources_with_profile())
        )
        self.source.configure(values=sources or [none_label()])
        if self.source.get() not in sources:
            self.source.set(sources[0] if sources else none_label())
        name = self.source.get()

        saved = repository.last_profile(name) if sources else None
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if not sources:
            self.status.configure(text=_("No enabled source reads a profile."))
        elif saved is None:
            self.status.configure(
                text=_("No {source} profile read yet.").format(source=name)
            )
            self.text.insert("1.0", _("Click Read profile now."))
        else:
            self.status.configure(
                text=_(
                    "The {source} profile, used to analyze its jobs (no personal data):"
                ).format(source=name)
            )
            self.text.insert("1.0", saved[1].text)
        self.text.configure(state="disabled")

        self.history.fill(
            [
                (
                    str(item["id"]),
                    (
                        f"{item['read_at']:%d/%m/%Y %H:%M}",
                        ", ".join(item["changed_fields"]),
                    ),
                )
                for item in (repository.profile_history(name) if sources else [])
            ]
        )

    def _read(self) -> None:
        name = self.source.get()
        if name not in profile_sources():
            self.app.show_error(
                ValueError(
                    _("The {source} source is off or doesn't read a profile.").format(
                        source=name
                    )
                )
            )
            return
        self.button.configure(state="disabled", text=_("Reading…"))
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
            self.button.configure(state="normal", text=_("Read profile now"))
            self.app.on_change()
            self.app.inform(
                _("The {source} profile was updated.").format(source=name)
                if changed
                else _("The profile hasn't changed.")
            )

        def fail(failure: BaseException) -> None:
            self.button.configure(state="normal", text=_("Read profile now"))
            self.app.show_error(failure)

        self.app.run(read(), on_done=finish, on_error=fail)
