"""Remote OK: public API of remote jobs (https://remoteok.com/api).

Terms (first item of the response itself): link the job on Remote OK, without
`nofollow`, and credit "Remote OK" as the source; don't use the logo. The response has
the ~100 latest jobs from every field, with a **shortened** description (the full text
is only on the site, which isn't scraped). The base (`ApiSource`) makes one call per
collection.

Each description ends with an anti-spam sentence ("Please mention the word ... and tag
R...") whose token is **the caller's IP address** in base64. It is removed before the
job is saved: it never reaches the database, the LLM prompt or the tests.
"""

import re
from typing import Any

from peao_bilingue.adapters.sources.api import (
    ApiSource,
    Json,
    fix_encoding,
    unexpected_format,
)
from peao_bilingue.adapters.sources.html import html_to_text
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

URL = "https://remoteok.com/api"

TRACKING_SENTENCE = re.compile(
    r"Please mention the word.*?(?:see they're human\.|$)", re.DOTALL
)
# Safety net in case the sentence changes: the token alone goes too.
TRACKING_TOKEN = re.compile(r"(?:tag |\(#)R[A-Za-z0-9+/=]{16,}\)?")
# Some descriptions carry an escaped <img> (it turns into text) with a base64 image,
# sometimes cut off by the API's summary: junk on screen and in the prompt.
INLINE_IMAGE = re.compile(r"<img\b[^>]*>?")


@sources.register("remoteok")
class RemoteOK(ApiSource):
    name = "remoteok"
    label = "Remote OK"
    description = _(
        "One of the biggest remote job boards, with open salaries: the ~100 latest "
        "remote jobs from every field. Public API, no account."
    )
    about = _(
        "One call per collection, kept for 6 hours. The API brings a shortened "
        "description; the full text is on the site. Each job links back to Remote "
        "OK, as its terms ask."
    )
    site = "https://remoteok.com"
    brand = "Remote OK"
    url = URL

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, list):
            raise unexpected_format(self.brand, _("a list"))
        # The first item is the legal notice, not a job.
        return [
            _job(item) for item in data if isinstance(item, dict) and item.get("id")
        ]


def clean_description(html: str) -> str:
    text = html_to_text(fix_encoding(html))
    text = TRACKING_SENTENCE.sub("", text)
    text = TRACKING_TOKEN.sub("", text)
    return INLINE_IMAGE.sub("", text).strip()


def _salary(minimum: int | None, maximum: int | None) -> str | None:
    values = [f"${value:,}" for value in (minimum, maximum) if value]
    return " - ".join(values) + " " + _("/year") if values else None


def _text(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    return fix_encoding(value).strip() or None if isinstance(value, str) else None


def _job(item: dict[str, Any]) -> Job:
    return Job(
        source=RemoteOK.name,
        external_id=str(item["id"]),
        # Remote OK's link, not `apply_url`: the terms ask for traffic to them.
        url=item["url"],
        title=_text(item, "position") or _("(untitled)"),
        company=_text(item, "company"),
        location=_text(item, "location"),
        work_mode="Remote",
        salary=_salary(item.get("salary_min"), item.get("salary_max")),
        skills=[fix_encoding(tag) for tag in item.get("tags") or []],
        published_at=item.get("date"),
        description=clean_description(item.get("description") or ""),
        extras={"via": RemoteOK.brand},
    )
