"""Companies' own job boards, through the public APIs of the applicant tracking
systems they use: Greenhouse, Lever and Ashby.

The three publish these endpoints for anyone to build a job site with, with no key:
Greenhouse ("Job Board data is publicly available, so authentication is not required
for any GET endpoints"), Lever (the Postings API, "designed to help you create a job
site") and Ashby (the public job posting API). Each job keeps its link on the company's
board.

The boards are the `company_boards` setting, one "ats:board" per company (the board's
name is the one in its URL: job-boards.greenhouse.io/**vtex**), with an optional
"=Company": Lever and Ashby don't name the company, and Greenhouse sometimes names it
oddly. **One call per
board per collection**, a 1 s pause and the base's 6 h cache: the whole board comes in
one response, descriptions included.

Most of these companies hire everywhere, so jobs are kept only when their location
names one of `company_boards_places` (Brazil, Brazilian cities, LATAM, the Americas,
worldwide...), compared without accents; an empty list keeps everything.
"""

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from peao_bilingue.adapters.sources.api import ApiSource, Json, unexpected_format
from peao_bilingue.adapters.sources.html import html_to_text, tidy_lines
from peao_bilingue.config import settings
from peao_bilingue.domain.errors import CollectionError
from peao_bilingue.domain.jobs import Job, strip_accents
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
    "lever": "https://api.lever.co/v0/postings/{board}",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}",
}
PARAMS = {
    "greenhouse": {"content": "true"},
    "lever": {"mode": "json"},
    "ashby": {"includeCompensation": "true"},
}
BRANDS = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby"}
_WORK_MODES = (
    (re.compile(r"hybrid|hibrido"), "Hybrid"),
    (re.compile(r"remote|remoto|home based|anywhere"), "Remote"),
    (re.compile(r"on-?site|onsite|presencial|office based"), "On-site"),
)


@dataclass(frozen=True)
class Board:
    ats: str
    name: str
    company: str | None

    @property
    def url(self) -> str:
        return URLS[self.ats].format(board=self.name)


def parse_board(entry: str) -> Board:
    """ "lever:dlocal=dLocal" -> Board("lever", "dlocal", "dLocal")."""
    ats, _sep, rest = entry.strip().partition(":")
    name, _sep, company = rest.partition("=")
    ats = ats.strip().lower()
    if ats not in URLS or not name.strip():
        raise CollectionError(
            _(
                "Invalid company board {entry!r}: use greenhouse:, lever: or ashby: "
                "followed by the board's name."
            ).format(entry=entry)
        )
    return Board(ats, name.strip(), company.strip() or None)


@sources.register("company_boards")
class CompanyBoards(ApiSource):
    name = "company_boards"
    label = _("Company job boards (Greenhouse, Lever, Ashby)")
    description = _(
        "Jobs straight from the boards of companies that hire in Brazil or remotely "
        "in Latin America (Nubank, Stone, QuintoAndar...). Public APIs, no account."
    )
    brand = _("company boards")
    url = URLS["greenhouse"].format(board="vtex")
    pause_s = 1.0

    def __init__(
        self,
        *,
        boards: list[str] | None = None,
        places: list[str] | None = None,
        client: httpx.AsyncClient | None = None,
        cache: Path | None = None,
    ) -> None:
        super().__init__(client=client, cache=cache)
        self.entries = settings.company_boards if boards is None else boards
        chosen = settings.company_boards_places if places is None else places
        self.places = [strip_accents(place) for place in chosen if place.strip()]

    def boards(self) -> list[Board]:
        # Parsed here, not in __init__: a typo fails this source's collection with a
        # readable message instead of the whole run.
        return [parse_board(entry) for entry in self.entries if entry.strip()]

    def queries(self) -> list[tuple[str, dict[str, str]]]:
        return [(board.url, PARAMS[board.ats]) for board in self.boards()]

    def decode(self, response: httpx.Response) -> Json:
        # The board travels with its response (and into the cache): convert() needs
        # to know which format it is and whose jobs they are.
        url = str(response.request.url.copy_with(query=None))
        board = next((board for board in self.boards() if board.url == url), None)
        if board is None:
            raise ValueError(f"unexpected board URL {url}")
        data = response.json()
        return {
            "ats": board.ats,
            "board": board.name,
            "company": board.company,
            "data": data,
        }

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, dict) or data.get("ats") not in URLS:
            raise unexpected_format(self.brand, _("an object"))
        board = Board(str(data["ats"]), str(data["board"]), data.get("company"))
        try:
            jobs = CONVERTERS[board.ats](board, data["data"])
        except (KeyError, TypeError, AttributeError) as failure:
            raise unexpected_format(BRANDS[board.ats], _("an object")) from failure
        return [job for job in jobs if self._open_here(job)]

    def _open_here(self, job: Job) -> bool:
        if not self.places:
            return True
        where = strip_accents(
            " ".join([job.location or "", *job.extras.get("places", [])])
        )
        return any(place in where for place in self.places)


def _work_mode(*texts: str | None) -> str | None:
    plain = strip_accents(" ".join(text for text in texts if text))
    for pattern, mode in _WORK_MODES:
        if pattern.search(plain):
            return mode
    return None


def _job_id(board: Board, job_id: object) -> str:
    return f"{board.ats}/{board.name}/{job_id}"


def _greenhouse(board: Board, data: Any) -> list[Job]:
    jobs = []
    for item in data["jobs"]:
        location = (item.get("location") or {}).get("name") or None
        offices = [office["name"] for office in item.get("offices") or []]
        jobs.append(
            Job(
                source=CompanyBoards.name,
                external_id=_job_id(board, item["id"]),
                url=item["absolute_url"],
                title=item.get("title") or _("(untitled)"),
                # "=Company" wins: some boards are named oddly ("Stone - Linkedin").
                company=board.company
                or str(item.get("company_name") or "").strip()
                or board.name,
                location=location,
                work_mode=_work_mode(location),
                published_at=item.get("first_published") or item.get("updated_at"),
                # The content comes HTML-escaped ("&lt;p&gt;").
                description=html_to_text(html.unescape(item.get("content") or "")),
                extras={
                    "via": BRANDS[board.ats],
                    "places": offices,
                    "departments": [
                        department["name"]
                        for department in item.get("departments") or []
                    ],
                },
            )
        )
    return jobs


def _lever(board: Board, data: Any) -> list[Job]:
    jobs = []
    for item in data:
        categories = item.get("categories") or {}
        places = list(categories.get("allLocations") or [])
        if not places and categories.get("location"):
            places = [categories["location"]]
        lists = [
            f"{part.get('text') or ''}\n{html_to_text(part.get('content') or '')}"
            for part in item.get("lists") or []
        ]
        description = "\n\n".join(
            text
            for text in [
                item.get("descriptionPlain") or "",
                *lists,
                item.get("additionalPlain") or "",
            ]
            if text.strip()
        )
        created = item.get("createdAt")
        jobs.append(
            Job(
                source=CompanyBoards.name,
                external_id=_job_id(board, item["id"]),
                url=item["hostedUrl"],
                title=item.get("text") or _("(untitled)"),
                company=board.company or board.name,
                location=", ".join(places) or None,
                work_mode=_work_mode(item.get("workplaceType"), *places),
                salary=_lever_salary(item.get("salaryRange")),
                published_at=(
                    datetime.fromtimestamp(created / 1000, UTC).isoformat()
                    if isinstance(created, int | float)
                    else None
                ),
                description=tidy_lines(description),
                extras={
                    "via": BRANDS[board.ats],
                    "places": places,
                    "team": categories.get("team"),
                    "commitment": categories.get("commitment"),
                },
            )
        )
    return jobs


def _lever_salary(salary: Any) -> str | None:
    if not isinstance(salary, dict) or not salary.get("min"):
        return None
    interval = str(salary.get("interval") or "").replace("-", " ")
    return (
        f"{salary.get('currency') or ''} {salary['min']:,}-{salary.get('max') or 0:,} "
        f"{interval}"
    ).strip()


def _ashby(board: Board, data: Any) -> list[Job]:
    jobs = []
    for item in data["jobs"]:
        if item.get("isListed") is False:
            continue
        secondary = [
            place["location"]
            for place in item.get("secondaryLocations") or []
            if place.get("location")
        ]
        address = (item.get("address") or {}).get("postalAddress") or {}
        location = ", ".join([item.get("location") or "", *secondary]).strip(", ")
        compensation = item.get("compensation") or {}
        jobs.append(
            Job(
                source=CompanyBoards.name,
                external_id=_job_id(board, item["id"]),
                url=item["jobUrl"],
                title=item.get("title") or _("(untitled)"),
                company=board.company or board.name,
                location=location or None,
                work_mode=_work_mode(item.get("workplaceType")),
                salary=compensation.get("compensationTierSummary") or None,
                published_at=item.get("publishedAt"),
                description=tidy_lines(item.get("descriptionPlain") or ""),
                extras={
                    "via": BRANDS[board.ats],
                    "places": [str(address.get("addressCountry") or "")],
                    "department": item.get("department"),
                    "employment_type": item.get("employmentType"),
                },
            )
        )
    return jobs


CONVERTERS = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby}
