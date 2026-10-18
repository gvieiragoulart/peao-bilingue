"""Strider: the public jobs page (https://www.onstrider.com/jobs).

Long-term remote jobs at US companies, open to Latin America. No login: the logged-in
area has no job list (Strider matches candidates itself), so this reads the public
pages, which `robots.txt` allows. Gabriel read the Terms of Use (On Strider, Inc.,
2022-08-26) and found them fine for this; each job keeps its Strider link.

There is no API or feed, so it reads the HTML like a user, politely:

- **the listing** (~14 jobs on 2026-10-18, all in one page) once per collection,
  with the base's 6 h cache; each search term is filtered here, against the card's
  title and skill tags;
- **each new job's page** (only the unknown ones, up to the run's limit), with a
  random 2-5 s pause before each one. The page carries a schema.org `JobPosting`
  (JSON-LD, meant for search engines: date, countries, contract types) and the
  sections the description is made of (must-haves, nice-to-haves...).

Like VanHack, Strider never names the company: `company` is None.

What is read from the pages (they change; keep it all here):

- listing card: `li` whose class has `job-listing-item`; title in `h2`; facts
  (location, company size, experience, commitment) in `span`s outside a `label`;
  skill tags inside `label`s; the link in `a[aria-label="read more"]`;
- job page: `section[data-position-open]` ("1" = accepting applications); the
  header's `label` + `span` pairs (Seniority, Commitment, Industry...); the "Required
  skills" `p` followed by a list; `h2`/`h3` headings opening the sections in
  `DESCRIPTION_SECTIONS`.
"""

import asyncio
import json
import random
import re
from html.parser import HTMLParser
from typing import Any, ClassVar
from urllib.parse import urljoin

import httpx

from peao_bilingue.adapters.sources.api import ApiSource, Json, unexpected_format
from peao_bilingue.adapters.sources.html import (
    LINE_BREAK_TAGS,
    html_to_text,
    tidy_lines,
)
from peao_bilingue.domain.jobs import Job, JobSummary, Skill
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

SITE = "https://www.onstrider.com"
URL = f"{SITE}/jobs"

CARD_CLASS = "job-listing-item"
CARD_LINK_LABEL = "read more"
REQUIRED_SKILLS = "Required skills"
# The job page's sections that make up the description, in this order.
DESCRIPTION_SECTIONS = (
    "What you will work on",
    "Must-haves",
    "What makes you stand out",
    "Nice-to-haves",
)
IGNORED = {"script", "style", "svg"}
# On the job page, links and buttons are actions ("Apply now", "Refer a friend").
IGNORED_ON_PAGE = IGNORED | {"a", "button"}
# "back-end-engineer-9bb259a7": the suffix is the start of the job's UUID.
_ID = re.compile(r"-([0-9a-f]{8})$")


@sources.register("strider")
class Strider(ApiSource):
    name = "strider"
    label = "Strider"
    description = _(
        "Remote jobs at US companies, 100% remote for Latin America. Reads the "
        "public jobs page; no account needed."
    )
    about = _(
        "Strider matches candidates itself and its app has no job list, so only the "
        "public jobs page is read: once per collection, then each new job's page "
        "with a 2-5 s pause. The company is never named. Each job keeps its Strider "
        "link."
    )
    site = "https://www.onstrider.com/jobs"
    brand = "Strider"
    url = URL
    # Random pause before each job page, like a person reading one at a time.
    detail_pause_s: ClassVar[tuple[float, float]] = (2.0, 5.0)

    def decode(self, response: httpx.Response) -> Json:
        cards = read_listing(response.text)
        if not cards:
            # The board has always had openings; an empty list is more likely a
            # changed page than no jobs, and a silent zero would hide it.
            raise ValueError("no job cards on the jobs page")
        return cards

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, list):
            raise unexpected_format(self.brand, _("a list"))
        return [_listed(card) for card in data if isinstance(card, dict)]

    async def detail(self, summary: JobSummary) -> Job:
        listed = self._seen[summary.external_id]
        await _polite_pause(self.detail_pause_s)
        response = await self._get(listed.url, {})
        page = read_job_page(response.text)
        if not page.sections and not page.posting.get("description"):
            raise unexpected_format(self.brand, _("the job's requirements"))
        return _detailed(listed, page)


async def _polite_pause(seconds: tuple[float, float]) -> None:
    await asyncio.sleep(random.uniform(*seconds))


# --- listing ---------------------------------------------------------------------


class _ListingReader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[dict[str, Any]] = []
        self._card: dict[str, Any] | None = None
        self._in: dict[str, int] = {"h2": 0, "label": 0, "span": 0}
        self._ignoring = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in IGNORED:
            self._ignoring += 1
        elif tag == "li" and CARD_CLASS in (attributes.get("class") or ""):
            self._card = {"title": "", "facts": [], "tags": [], "href": None}
        elif self._card is not None:
            if tag in self._in:
                self._in[tag] += 1
            if tag == "a" and attributes.get("aria-label") == CARD_LINK_LABEL:
                # The link is the card's last element.
                self._card["href"] = attributes.get("href")
                if self._card["href"]:
                    self.cards.append(self._card)
                self._card = None

    def handle_endtag(self, tag: str) -> None:
        if tag in IGNORED:
            self._ignoring = max(0, self._ignoring - 1)
        elif self._card is not None and tag in self._in:
            self._in[tag] = max(0, self._in[tag] - 1)

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if self._card is None or self._ignoring or not text:
            return
        if self._in["h2"]:
            self._card["title"] = f"{self._card['title']} {text}".strip()
        elif self._in["label"]:
            self._card["tags"].append(text)
        elif self._in["span"]:
            self._card["facts"].append(text)


def read_listing(html: str) -> list[dict[str, Any]]:
    """The cards of the jobs page: title, facts, skill tags and link."""
    reader = _ListingReader()
    reader.feed(html)
    reader.close()
    return reader.cards


def _external_id(href: str) -> str:
    slug = href.rstrip("/").rsplit("/", 1)[-1]
    found = _ID.search(slug)
    return found[1] if found else slug


def _listed(card: dict[str, Any]) -> Job:
    facts = [str(fact) for fact in card.get("facts") or []]
    return Job(
        source=Strider.name,
        external_id=_external_id(card["href"]),
        url=urljoin(SITE, card["href"]),  # the job on Strider: the credit it gets
        title=card.get("title") or _("(untitled)"),
        location=facts[0] if facts else None,
        work_mode="Remote",
        skills=[str(tag) for tag in card.get("tags") or []],
        extras={"via": Strider.brand, "highlights": facts[1:]},
    )


# --- job page --------------------------------------------------------------------


class JobPage:
    """What a job page says: the JSON-LD posting, the header's facts, the required
    skills and the description's sections."""

    def __init__(self) -> None:
        self.posting: dict[str, Any] = {}
        self.open: bool | None = None
        self.facts: dict[str, str] = {}
        self.required_skills: list[str] = []
        self.sections: dict[str, str] = {}


class _JobPageReader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page = JobPage()
        self._json_ld: list[str] | None = None
        self._in_main = False
        self._ignoring = 0
        self._heading: list[str] | None = None
        self._label: list[str] | None = None
        self._pending_label: str | None = None
        self._section: str | None = None
        self._in_header = True  # before the first h2: where the labeled facts are
        self._parts: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type") == "application/ld+json":
            self._json_ld = []
            return
        if tag == "main":
            self._in_main = True
        if not self._in_main:
            return
        if tag in IGNORED_ON_PAGE:
            self._ignoring += 1
        elif tag == "section" and "data-position-open" in attributes:
            self.page.open = attributes["data-position-open"] == "1"
        elif attributes.get("role") == "dialog":
            # The referral dialog sits after the last section: it ends it.
            self._section = None
        elif tag in {"h1", "h2", "h3"}:
            self._heading = []
            self._in_header = self._in_header and tag == "h1"
        elif tag == "label" and self._in_header:
            self._label = []
        elif self._section is not None and tag in LINE_BREAK_TAGS:
            self._parts[self._section].append("\n- " if tag == "li" else "\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_ld is not None:
            self._read_json_ld("".join(self._json_ld))
            self._json_ld = None
        elif tag == "main":
            self._in_main = False
        elif tag in IGNORED_ON_PAGE:
            self._ignoring = max(0, self._ignoring - 1)
        elif tag in {"h1", "h2", "h3"} and self._heading is not None:
            self._open_section(" ".join("".join(self._heading).split()))
            self._heading = None
        elif tag == "label" and self._label is not None:
            self._pending_label = " ".join("".join(self._label).split()) or None
            self._label = None
        elif self._section is not None and tag in LINE_BREAK_TAGS:
            self._parts[self._section].append("\n")

    def handle_data(self, data: str) -> None:
        if self._json_ld is not None:
            self._json_ld.append(data)
            return
        if not self._in_main or self._ignoring:
            return
        if self._heading is not None:
            self._heading.append(data)
        elif self._label is not None:
            self._label.append(data)
        elif self._pending_label and data.strip():
            self.page.facts[self._pending_label] = " ".join(data.split())
            self._pending_label = None
        elif data.strip() == REQUIRED_SKILLS:
            self._open_section(REQUIRED_SKILLS)
        elif self._section is not None:
            self._parts[self._section].append(data)

    def _open_section(self, heading: str) -> None:
        # Only the known sections, and only their first appearance: the page repeats
        # the title further down and ends with other jobs.
        known = heading in (REQUIRED_SKILLS, *DESCRIPTION_SECTIONS)
        if known and heading not in self._parts:
            self._parts[heading] = []
            self._section = heading
        else:
            self._section = None

    def _read_json_ld(self, text: str) -> None:
        try:
            data = json.loads(text)
        except ValueError:
            return
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            self.page.posting = data

    def close(self) -> None:
        super().close()
        for heading, parts in self._parts.items():
            text = tidy_lines("".join(parts))
            if heading == REQUIRED_SKILLS:
                self.page.required_skills = [
                    line.removeprefix("- ") for line in text.splitlines()
                ]
            elif text:
                self.page.sections[heading] = text


def read_job_page(html: str) -> JobPage:
    reader = _JobPageReader()
    reader.feed(html)
    reader.close()
    return reader.page


def _countries(posting: dict[str, Any]) -> list[str]:
    places = posting.get("applicantLocationRequirements") or []
    return [
        str(place["name"])
        for place in places
        if isinstance(place, dict) and place.get("name")
    ]


def _description(listed: Job, page: JobPage) -> str:
    facts = [f"{label}: {value}" for label, value in page.facts.items()]
    # The card's other facts repeat the page's, except the company's size.
    facts += [
        f"Company: {fact}"
        for fact in listed.extras.get("highlights") or []
        if "employees" in str(fact)
    ]
    if page.sections:
        body = [
            f"{heading}\n{page.sections[heading]}"
            for heading in DESCRIPTION_SECTIONS
            if heading in page.sections
        ]
    else:
        # The page changed its sections: the JSON-LD has the lists without headings.
        body = [html_to_text(str(page.posting.get("description") or ""))]
    return "\n\n".join(part for part in ["\n".join(facts), *body] if part)


def _detailed(listed: Job, page: JobPage) -> Job:
    posting = page.posting
    identifier = posting.get("identifier")
    required = page.required_skills
    return listed.model_copy(
        update={
            "description": _description(listed, page),
            "published_at": posting.get("datePosted") or None,
            "skills": required or listed.skills,
            "required_skills": [Skill(name=name) for name in required],
            "extras": {
                **listed.extras,
                "countries": _countries(posting),
                "employment_type": posting.get("employmentType"),
                "listing_id": (
                    identifier.get("value") if isinstance(identifier, dict) else None
                ),
                "accepting_applications": page.open,
                "facts": page.facts,
            },
        }
    )
