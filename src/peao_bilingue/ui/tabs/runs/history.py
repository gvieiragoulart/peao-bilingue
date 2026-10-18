"""The Runs tab's history: one row per run, the latest first."""

from typing import Any

from peao_bilingue.domain.collection import Run
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation
from peao_bilingue.ui.widgets import Table


class RunHistory(Table):
    def __init__(self, master: Any) -> None:
        super().__init__(
            master,
            [
                ("started", _("Start"), 90),
                ("trigger", _("Trigger"), 80),
                ("sources", _("Sources"), 150),
                ("status", _("Status"), 110),
                ("listed", _("Listed"), 70),
                ("new", _("New"), 60),
                ("error", _("Error"), 330),
            ],
            height=220,
        )

    def show(self, runs: list[Run]) -> None:
        self.fill([(str(run.id), presentation.run_row(run)) for run in runs])
