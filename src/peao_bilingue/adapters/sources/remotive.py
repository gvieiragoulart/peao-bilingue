"""Remotive: public API of remote jobs (https://remotive.com/api/remote-jobs).

Terms (legal notice in the response itself and github.com/remotive-io/remote-jobs-api):
link the job on Remotive and credit Remotive as the source; at most ~4 calls a day
(more than 2 a minute get blocked); data is 24 h behind; don't republish the jobs on
other sites. The base (`ApiSource`) makes one call per collection with a 6 h cache,
which keeps usage under 4 a day.
"""

from pathlib import Path
from typing import Any

import httpx

from peao_bilingue.adapters.sources.api import ApiSource, Json, unexpected_format
from peao_bilingue.adapters.sources.html import html_to_text
from peao_bilingue.config import settings
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

URL = "https://remotive.com/api/remote-jobs"


@sources.register("remotive")
class Remotive(ApiSource):
    name = "remotive"
    label = _("Remotive (public API, remote jobs)")
    brand = "Remotive"
    url = URL

    def __init__(
        self,
        *,
        category: str | None = None,
        client: httpx.AsyncClient | None = None,
        cache: Path | None = None,
    ) -> None:
        super().__init__(client=client, cache=cache)
        self.category = category or settings.remotive_category

    def params(self) -> dict[str, str]:
        return {"category": self.category}

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, dict):
            raise unexpected_format(self.brand, _("an object"))
        return [_job(item) for item in data.get("jobs", [])]


def _job(item: dict[str, Any]) -> Job:
    return Job(
        source=Remotive.name,
        external_id=str(item["id"]),
        url=item["url"],  # the link goes back to Remotive, as the terms ask
        title=item["title"],
        company=item.get("company_name") or None,
        location=item.get("candidate_required_location") or None,
        work_mode="Remote",
        salary=item.get("salary") or None,  # "" when the company doesn't say
        skills=list(item.get("tags") or []),
        published_at=item.get("publication_date"),
        description=html_to_text(item.get("description") or ""),
        extras={
            "via": Remotive.brand,
            "category": item.get("category"),
            "job_type": item.get("job_type"),
        },
    )
