"""Get on Board: the public API of a Latin American tech job board
(https://www.getonbrd.com/api/v0/search/jobs).

Get on Board's help page on its API says the public API needs no setup and can be used
to "Display published jobs on another site" and to "Build a custom job search or job
board using public listings". Its Terms and Conditions (v1.1, 2026-09-17) are the
contract with the companies that post jobs, and limit API calls by throttling; each job
here keeps its Get on Board link.

Most of its jobs are on-site or remote within one country (Chile, mostly), so it
searches only **fully remote** jobs (`remote=true`, which returns only
`remote_modality: fully_remote`), **per term**: one call per search keyword (up to
100 jobs), a 2 s pause between real calls and a 12 h cache per term.
"""

from datetime import UTC, datetime
from typing import Any

from peao_bilingue.adapters.sources.api import ApiSource, Json, unexpected_format
from peao_bilingue.adapters.sources.html import html_to_text
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

URL = "https://www.getonbrd.com/api/v0/search/jobs"
# The job's text comes in parts, each with its own heading.
SECTIONS = (
    ("functions_headline", "functions"),
    ("description_headline", "description"),
    ("desirable_headline", "desirable"),
    ("benefits_headline", "benefits"),
)


@sources.register("getonbrd")
class GetOnBoard(ApiSource):
    name = "getonbrd"
    label = _("Get on Board (public API, remote in LATAM)")
    description = _(
        "Fully remote tech jobs from a Latin American job board, searched once per "
        "keyword of your searches."
    )
    brand = "Get on Board"
    url = URL
    validity_s = 12 * 3600
    pause_s = 2.0

    def params_for_term(self, term: str) -> dict[str, str]:
        return {
            "query": term,
            "remote": "true",
            "per_page": "100",
            "expand": '["company"]',
        }

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise unexpected_format(self.brand, _("an object"))
        return [
            _job(item)
            for item in data["data"]
            if isinstance(item, dict)
            and item.get("type") == "job"
            and (item.get("links") or {}).get("public_url")
        ]


def _company(attributes: dict[str, Any]) -> str | None:
    company = (attributes.get("company") or {}).get("data") or {}
    name = str((company.get("attributes") or {}).get("name") or "").strip()
    return name or None


def _salary(attributes: dict[str, Any]) -> str | None:
    # Get on Board publishes salaries in US dollars a month.
    low, high = attributes.get("min_salary"), attributes.get("max_salary")
    if not low and not high:
        return None
    amount = f"{low:,}-{high:,}" if low and high and low != high else f"{low or high:,}"
    return _("USD {amount}/month").format(amount=amount)


def _description(attributes: dict[str, Any]) -> str:
    parts = []
    for headline, body in SECTIONS:
        text = html_to_text(str(attributes.get(body) or ""))
        if text:
            parts.append(f"{attributes.get(headline) or ''}\n{text}".strip())
    return "\n\n".join(parts)


def _job(item: dict[str, Any]) -> Job:
    attributes = item.get("attributes") or {}
    published = attributes.get("published_at")
    countries = [str(country) for country in attributes.get("countries") or []]
    return Job(
        source=GetOnBoard.name,
        external_id=str(item["id"]),
        url=item["links"]["public_url"],  # the job on Get on Board
        title=attributes.get("title") or _("(untitled)"),
        company=_company(attributes),
        location=", ".join(countries) or None,
        work_mode="Remote",
        salary=_salary(attributes),
        published_at=(
            datetime.fromtimestamp(published, UTC).isoformat()
            if isinstance(published, int | float)
            else None
        ),
        description=_description(attributes),
        extras={
            "via": GetOnBoard.brand,
            "category": attributes.get("category_name"),
            "language": attributes.get("lang"),
            "perks": attributes.get("perks"),
        },
    )
