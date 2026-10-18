"""Jobicy: public API of remote jobs (https://jobicy.com/api/v2/remote-jobs).

Terms (the API page and the `friendlyNotice` in every response): credit Jobicy with a
direct link to the source, and every application button goes to the job's original
URL; don't present the jobs as your own. No key. It asks for few passes a day, at most
one an hour, and for caching.

`geo=brazil` (`JOBICY_GEO`) brings the jobs open to Brazil, which already include
those open to LATAM and to anyone, anywhere (61 on 2026-10-18; `geo=latam` only added
jobs for other countries). **One call per collection** with the base's 6 h cache. The
feed only has the last 7 days of jobs: a job seen once stays saved.
"""

from pathlib import Path
from typing import Any, ClassVar

import httpx

from peao_bilingue.adapters.sources.api import ApiSource, Json, unexpected_format
from peao_bilingue.adapters.sources.html import html_to_text
from peao_bilingue.config import settings
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

URL = "https://jobicy.com/api/v2/remote-jobs"


@sources.register("jobicy")
class Jobicy(ApiSource):
    name = "jobicy"
    label = "Jobicy"
    description = _(
        "A global remote job board: jobs open to Brazil, Latin America or anywhere, "
        "from the last 7 days. Public API, no account."
    )
    about = _(
        "One call per collection, kept for 6 hours. The region is Jobicy's geo "
        'filter: "brazil" already includes the Latin America and anywhere jobs. '
        "Each job links back to Jobicy, as its terms ask."
    )
    site = "https://jobicy.com"
    fields: ClassVar[dict[str, str]] = {
        "jobicy_geo": _("Region"),
    }
    brand = "Jobicy"
    url = URL

    def __init__(
        self,
        *,
        geo: str | None = None,
        client: httpx.AsyncClient | None = None,
        cache: Path | None = None,
    ) -> None:
        super().__init__(client=client, cache=cache)
        self.geo = settings.jobicy_geo if geo is None else geo

    def params(self) -> dict[str, str]:
        params = {"count": "100"}
        if self.geo:
            params["geo"] = self.geo
        return params

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise unexpected_format(self.brand, _("an object"))
        return [
            _job(item)
            for item in data["jobs"]
            if isinstance(item, dict) and item.get("url")
        ]


def _number(value: object) -> int | None:
    try:
        number = int(float(str(value)))
    except ValueError:
        return None
    return number or None


def _salary(item: dict[str, Any]) -> str | None:
    low, high = _number(item.get("salaryMin")), _number(item.get("salaryMax"))
    if not low and not high:
        return None
    # "167,000" rather than "167,000-167,000" when the range is one value.
    amount = f"{low:,}-{high:,}" if low and high and low != high else f"{low or high:,}"
    period = str(item.get("salaryPeriod") or "")
    return " ".join(
        part for part in [item.get("salaryCurrency"), amount, period] if part
    )


def _job(item: dict[str, Any]) -> Job:
    return Job(
        source=Jobicy.name,
        external_id=str(item["id"]),
        url=item["url"],  # the job on Jobicy: the credit and link they ask for
        title=item.get("jobTitle") or _("(untitled)"),
        company=item.get("companyName") or None,
        location=" ".join(str(item.get("jobGeo") or "").split()) or None,
        work_mode="Remote",
        salary=_salary(item),
        published_at=item.get("pubDate"),
        description=html_to_text(item.get("jobDescription") or ""),
        extras={
            "via": Jobicy.brand,
            "industry": item.get("jobIndustry"),
            "job_type": item.get("jobType"),
            "level": item.get("jobLevel"),
        },
    )
