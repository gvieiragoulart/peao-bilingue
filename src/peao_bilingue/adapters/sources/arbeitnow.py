"""Arbeitnow: public API of jobs in Germany (https://www.arbeitnow.com/api/job-board-api).

Terms (`meta.terms` in the response itself and section 11 of the site's terms): free
API, "don't abuse it"; link back to Arbeitnow; access may be revoked. Limit of 50
calls (`X-RateLimit-Limit` header). The base (`ApiSource`) makes one call per
collection, with a cache.

Only jobs **with visa sponsorship** (`visa_sponsorship=true`): the relocation path,
like VanHack; the default list is local jobs, many in German. On 2026-10-07 it
returned 312 jobs in a single page. The API ignores `remote=true`.
"""

import re
from datetime import UTC, datetime
from typing import Any

from peao_bilingue.adapters.sources.api import ApiSource, Json, unexpected_format
from peao_bilingue.adapters.sources.html import html_to_text
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

URL = "https://www.arbeitnow.com/api/job-board-api"


@sources.register("arbeitnow")
class Arbeitnow(ApiSource):
    name = "arbeitnow"
    label = _("Arbeitnow (public API, Germany with a visa)")
    description = _(
        "Jobs in Germany with visa sponsorship, a path to relocation. Many are "
        "written in German."
    )
    brand = "Arbeitnow"
    url = URL

    def params(self) -> dict[str, str]:
        return {"visa_sponsorship": "true"}

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, dict):
            raise unexpected_format(self.brand, _("an object"))
        return [_job(item) for item in data.get("data", [])]


# A closing tag left in the text: a sign the HTML arrived escaped.
LEFTOVER_TAG = re.compile(
    r"</(?:p|div|li|ul|ol|strong|em|b|i|span|h[1-6]|table|tr|td)>", re.IGNORECASE
)


def description_as_text(description: str) -> str:
    """The API sends escaped HTML (&lt;p&gt;...), sometimes only partly: the first
    conversion gives markup back as text, and a second one removes it. Text that only
    mentions "<br>" (no closing tag) is left alone."""
    text = html_to_text(description)
    if LEFTOVER_TAG.search(text):
        text = html_to_text(text)
    return text


def _published_at(epoch: object) -> str | None:
    if not isinstance(epoch, int | float):
        return None
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


def _job(item: dict[str, Any]) -> Job:
    return Job(
        source=Arbeitnow.name,
        external_id=item["slug"],
        url=item["url"],  # the link goes back to Arbeitnow, as the terms ask
        title=item["title"],
        company=item.get("company_name") or None,
        location=item.get("location") or None,
        work_mode="Remote" if item.get("remote") else "On-site",
        skills=list(item.get("tags") or []),
        published_at=_published_at(item.get("created_at")),
        description=description_as_text(item.get("description") or ""),
        extras={
            "via": Arbeitnow.brand,
            "visa_sponsorship": True,  # only jobs with visa sponsorship come in
            "job_types": list(item.get("job_types") or []),
        },
    )
