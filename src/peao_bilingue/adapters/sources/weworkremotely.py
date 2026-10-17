"""We Work Remotely: public RSS feeds (https://weworkremotely.com/remote-job-rss-feed).

Terms (the feed's page): "Anyone can use the feed, all we ask is that you attribute
the links back to We Work Remotely." Each job keeps its WWR link.

The general feed only has the ~90 latest jobs from every field; on 2026-10-08 it was
missing 38 of the 57 programming ones. So it uses the three programming feeds
(back-end, full-stack, front-end): three calls per collection, with a pause and a
cache (the base's).
"""

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from peao_bilingue.adapters.sources.api import ApiSource, Json, unexpected_format
from peao_bilingue.adapters.sources.html import html_to_text
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

URL_BASE = "https://weworkremotely.com/categories/"
CATEGORIES = (
    "remote-back-end-programming-jobs",
    "remote-full-stack-programming-jobs",
    "remote-front-end-programming-jobs",
)


@sources.register("weworkremotely")
class WeWorkRemotely(ApiSource):
    name = "weworkremotely"
    label = _("We Work Remotely (public RSS, remote jobs)")
    brand = "We Work Remotely"
    url = f"{URL_BASE}{CATEGORIES[0]}.rss"
    pause_s = 2.0

    def queries(self) -> list[tuple[str, dict[str, str]]]:
        return [(f"{URL_BASE}{category}.rss", {}) for category in CATEGORIES]

    def decode(self, response: httpx.Response) -> Json:
        # Python's expat already guards against entity expansion (billion laughs).
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as failure:
            raise ValueError(f"invalid RSS: {failure}") from failure
        return [_item(node) for node in root.findall("./channel/item")]

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, list):
            raise unexpected_format(self.brand, _("a list"))
        return [
            _job(item) for item in data if isinstance(item, dict) and item.get("link")
        ]


def _item(node: ET.Element) -> dict[str, str]:
    # "{http://search.yahoo.com/mrss}content" -> "content"
    return {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in node}


def _company_and_title(title: str) -> tuple[str | None, str]:
    # The feed sends "Company: Role".
    if ": " in title:
        company, role = title.split(": ", 1)
        return company.strip() or None, role.strip()
    return None, title


def _skills(text: str) -> list[str]:
    # "Java, PostgreSQL, and Spring" -> ["Java", "PostgreSQL", "Spring"]
    parts = text.replace(" and ", ", ").split(",")
    return [part.strip() for part in parts if part.strip()]


def _published_at(date: str) -> str | None:
    try:
        return parsedate_to_datetime(date).isoformat() if date else None
    except (TypeError, ValueError):
        return None


def _job(item: dict[str, Any]) -> Job:
    company, title = _company_and_title(item.get("title") or "")
    link = item["link"]
    return Job(
        source=WeWorkRemotely.name,
        external_id=link.rstrip("/").rsplit("/", 1)[-1],
        url=link,  # the job on WWR: the attribution they ask for
        title=title or _("(untitled)"),
        company=company,
        location=item.get("region") or None,
        work_mode="Remote",
        skills=_skills(item.get("skills") or ""),
        published_at=_published_at(item.get("pubDate") or ""),
        description=html_to_text(item.get("description") or ""),
        extras={
            "via": WeWorkRemotely.brand,
            "category": item.get("category"),
            "job_type": item.get("type"),
            "countries": item.get("country"),
        },
    )
