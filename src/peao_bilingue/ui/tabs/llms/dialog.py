"""One LLM in detail, over the LLMs tab when its card is clicked: what it is, how the
app uses it, where to get a key or the program, and its settings with their Save."""

import webbrowser
from collections.abc import Callable
from typing import Any

from peao_bilingue import factories
from peao_bilingue.config import SECRETS, settings
from peao_bilingue.domain.models import (
    MODEL_FIELDS,
    AIProvider,
    ModelSource,
    model_values,
)
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
        model_source: ModelSource | None = None,
        on_refresh_models: Callable[[str, str], None] | None = None,
    ) -> None:
        cls = factories.llms.class_of(name)
        super().__init__(master, name, presentation.short_llm_label(name), on_close)
        self.cls = cls
        self._on_save = on_save
        self._provider = AIProvider(name)
        self._on_refresh_models = on_refresh_models

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
        fields = adapter_fields(cls)
        if model_source is not None:
            choices = model_values(self._provider, model_source)
            if choices:
                model_field = next(
                    field
                    for field in fields
                    if field.name == MODEL_FIELDS[self._provider]
                )
                model_field.kind = "combo"
                model_field.options = choices
        self.form = Form(self.body, fields, fg_color="transparent")
        self.form.pack(fill="x", pady=(0, 6))
        self.form.load(settings)
        if name != AIProvider.OLLAMA and on_refresh_models is not None:
            OutlineButton(
                self.body,
                text=_("Refresh provider models"),
                command=self._refresh_models,
            ).pack(anchor="w", pady=(2, 6))
            self.model_status = Hint(self.body, text="", anchor="w")
            self.model_status.pack(fill="x", pady=(0, 8))
        if any(field in SECRETS for field in cls.fields):
            Hint(
                self.body,
                _("The keys live in the system keyring, not in a file."),
            ).pack(anchor="w", pady=(0, 10))

        self._finish(save=True)

    def _save(self) -> bool:
        return self._on_save(self)

    def _refresh_models(self) -> None:
        if self._on_refresh_models is None:
            return
        key = str(self.form._widgets[f"{self._provider.value}_api_key"].get()).strip()
        self.model_status.configure(text=_("Checking provider models…"))
        self._on_refresh_models(self._provider.value, key)

    def update_model_choices(self, choices: list[str]) -> None:
        if choices:
            self.form.set_choices(MODEL_FIELDS[self._provider], choices)
            self.model_status.configure(
                text=_("{count} models loaded from the provider.").format(
                    count=len(choices)
                )
            )
        else:
            self.model_status.configure(text=_("The provider returned no models."))
