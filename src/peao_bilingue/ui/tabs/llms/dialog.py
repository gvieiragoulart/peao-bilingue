"""One LLM in detail, over the LLMs tab when its card is clicked: what it is, how the
app uses it, where to get a key or the program, and its settings with their Save."""

import webbrowser
from collections.abc import Callable
from typing import Any

from peao_bilingue import factories
from peao_bilingue.config import SECRETS, settings
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation, theme
from peao_bilingue.ui.modal import EntityDialog
from peao_bilingue.ui.widgets import Form, Heading, Hint, OutlineButton, adapter_fields


class LLMDialog(EntityDialog):
    def __init__(
        self,
        master: Any,
        name: str,
        *,
        on_save: Callable[["LLMDialog"], bool],
        on_close: Callable[[], None],
    ) -> None:
        cls = factories.llms.class_of(name)
        super().__init__(master, name, presentation.short_llm_label(name), on_close)
        self.cls = cls
        self._on_save = on_save

        self.description = self._paragraph(cls.description, theme.TEXT)
        self.about = self._paragraph(cls.about, theme.MUTED) if cls.about else None
        if cls.site:
            OutlineButton(
                self.body,
                text=_("Open the site"),
                width=130,
                command=lambda: webbrowser.open(cls.site),
            ).pack(anchor="w", pady=(0, 14))

        Heading(self.body, _("Settings")).pack(anchor="w", pady=(6, 2))
        self.form = Form(self.body, adapter_fields(cls), fg_color="transparent")
        self.form.pack(fill="x", pady=(0, 6))
        self.form.load(settings)
        if any(field in SECRETS for field in cls.fields):
            Hint(
                self.body,
                _("The keys live in Windows Credential Manager, not in a file."),
            ).pack(anchor="w", pady=(0, 10))

        self._finish(save=True)

    def _save(self) -> bool:
        return self._on_save(self)
