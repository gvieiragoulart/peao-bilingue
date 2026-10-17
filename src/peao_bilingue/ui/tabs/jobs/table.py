"""The Jobs tab's table: one row per job, keyed by the job's key."""

from typing import Any

from peao_bilingue.domain.jobs import ListedJob
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation
from peao_bilingue.ui.widgets import Table


class JobTable(Table):
    def __init__(self, master: Any) -> None:
        super().__init__(
            master,
            [
                ("fit", _("Fit"), 45),
                ("title", _("Job"), 300),
                ("location", _("Location"), 160),
                ("source", _("Source"), 80),
                ("status", _("Status"), 90),
            ],
        )
        self._jobs: dict[str, ListedJob] = {}

    def show(self, jobs: list[ListedJob]) -> None:
        self._jobs = {item.job.key: item for item in jobs}
        self.fill(
            [(key, presentation.job_row(item)) for key, item in self._jobs.items()]
        )

    def selected_job(self) -> ListedJob | None:
        key = self.selected()
        return self._jobs.get(key) if key else None

    def select(self, key: str) -> None:
        if self.tree.exists(key):
            self.tree.selection_set(key)
