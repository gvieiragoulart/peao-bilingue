"""Himalayas: public API of remote jobs (https://himalayas.app/jobs/api/search).

Terms (https://himalayas.app/api): link the job on Himalayas **and** credit Himalayas
as the source; don't republish the jobs on other sites; abuse gets a 429. At most 20
jobs per call, and the data changes every 24 h.

That's why it searches **per term** (the whole list has more than 5,000 jobs): one call
for each term of the searches, with a pause between them and a 12 h cache. Only jobs
open to candidates from `HIMALAYAS_COUNTRY` (default BR) or worldwide: without the
filter, most are US-only (3 out of 18 fit, on 2026-10-07).
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from peao_bilingue.adapters.sources.api import ApiSource, Json, unexpected_format
from peao_bilingue.adapters.sources.html import html_to_text
from peao_bilingue.config import settings
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

URL = "https://himalayas.app/jobs/api/search"
# Up to this many countries are listed as the location; above that, only the count.
MAX_LISTED_COUNTRIES = 3


def _periods() -> dict[str, str]:
    return {
        "annual": _("/year"),
        "monthly": _("/month"),
        "weekly": _("/week"),
        "hourly": _("/hour"),
    }


@sources.register("himalayas")
class Himalayas(ApiSource):
    name = "himalayas"
    label = _("Himalayas (public API, remote jobs)")
    brand = "Himalayas"
    url = URL
    validity_s = 12 * 3600
    pause_s = 2.0

    def __init__(
        self,
        *,
        country: str | None = None,
        client: httpx.AsyncClient | None = None,
        cache: Path | None = None,
    ) -> None:
        super().__init__(client=client, cache=cache)
        self.country = settings.himalayas_country if country is None else country

    def params_for_term(self, term: str) -> dict[str, str]:
        params = {"q": term, "sort": "recent"}
        if self.country:
            params["country"] = self.country
        return params

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, dict):
            raise unexpected_format(self.brand, _("an object"))
        return [_job(item) for item in data.get("jobs", [])]


def _id(item: dict[str, Any]) -> str:
    # The job's slug alone repeats across companies ("software-engineer-backend").
    company = item.get("companySlug") or "no-company"
    return f"{company}/{item['guid'].rsplit('/', 1)[-1]}"


def _location(countries: list[str]) -> str:
    if not countries:
        return "Worldwide"
    if len(countries) <= MAX_LISTED_COUNTRIES:
        return ", ".join(countries)
    if "Brazil" in countries:
        return _("{count} countries, including Brazil").format(count=len(countries))
    return _("{count} countries").format(count=len(countries))


def _salary(item: dict[str, Any]) -> str | None:
    values = [v for v in (item.get("minSalary"), item.get("maxSalary")) if v]
    if not values:
        return None
    amount_range = (
        f"{values[0]:,}" if len(set(values)) == 1 else f"{values[0]:,} - {values[1]:,}"
    )
    currency = item.get("currency") or ""
    period = _periods().get(item.get("salaryPeriod") or "", "")
    return " ".join(part for part in (currency, amount_range, period) if part)


def _published_at(epoch: object) -> str | None:
    if not isinstance(epoch, int | float):
        return None
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


def _job(item: dict[str, Any]) -> Job:
    countries = list(item.get("locationRestrictions") or [])
    return Job(
        source=Himalayas.name,
        external_id=_id(item),
        url=item["guid"],  # the job's page on Himalayas, as the terms ask
        title=item["title"],
        company=item.get("companyName") or None,
        location=_location(countries),
        work_mode="Remote",
        salary=_salary(item),
        skills=list(item.get("categories") or []),
        published_at=_published_at(item.get("pubDate")),
        description=html_to_text(item.get("description") or ""),
        extras={
            "via": Himalayas.brand,
            "countries": countries,
            "seniority": list(item.get("seniority") or []),
            "job_type": item.get("employmentType"),
        },
    )
