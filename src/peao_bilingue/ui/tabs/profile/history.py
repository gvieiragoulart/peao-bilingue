"""The Profile tab's history: when a source's profile was read and what changed."""

from typing import Any

from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Table


class ProfileHistory(Table):
    def __init__(self, master: Any) -> None:
        super().__init__(
            master,
            [("read_at", _("Read on"), 120), ("fields", _("What changed"), 260)],
        )

    def show(self, history: list[dict[str, Any]]) -> None:
        self.fill(
            [
                (
                    str(item["id"]),
                    (
                        f"{item['read_at']:%d/%m/%Y %H:%M}",
                        ", ".join(item["changed_fields"]),
                    ),
                )
                for item in history
            ]
        )
