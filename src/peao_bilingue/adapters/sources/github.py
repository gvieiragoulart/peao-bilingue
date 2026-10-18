"""Jobs posted as issues in Brazilian developer communities' repositories
(github.com/backend-br/vagas and others), through GitHub's public REST API.

Each repository is a job board: a company opens an issue from the template (company,
description, location, requirements, hiring, how to apply) and tags it with labels
(seniority, CLT/PJ, remote, technologies). backend-br/vagas is MIT-licensed and its
README points at an outside aggregator that links back to each issue: this one does the
same, each job keeps its issue's link.

GitHub allows 60 calls an hour per IP without a token; this makes **one call per
repository per collection** (the 100 newest open issues), a 1 s pause between them and
the base's 6 h cache. Pull requests come in the same list and are skipped.

The body goes through `remove_contact_data`: recruiters' emails and phone numbers don't
go into the database or the LLM's prompt, and the links (application forms) are on the
issue anyway.
"""

import re
from pathlib import Path
from typing import Any

import httpx

from peao_bilingue.adapters.sources.api import ApiSource, Json, unexpected_format
from peao_bilingue.config import settings
from peao_bilingue.domain.jobs import Job, strip_accents
from peao_bilingue.domain.privacy import remove_contact_data
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

API = "https://api.github.com/repos/"

# Labels that aren't skills, compared without accents ("Junior" = the accented one).
SENIORITY = {"estagio", "junior", "pleno", "senior", "especialista", "lead"}
CONTRACT = {"clt", "pj", "freela", "freelancer", "temporario"}
WORK_MODES = {"remoto": "Remote", "hibrido": "Hybrid", "presencial": "On-site"}
# "[Remoto] Role na Company": the place in brackets, the company after "na"/"at"/"@".
_PLACE = re.compile(r"^\s*\[([^\]]+)\]\s*")
_COMPANY_MARK = re.compile(r"\s(?:na|at|@)\s+", re.IGNORECASE)
_TRAILING_NOTE = re.compile(r"\s*\([^)]*\)\s*$")  # "Company (PJ, LATAM)"
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@sources.register("github")
class GitHubJobs(ApiSource):
    name = "github"
    label = _("GitHub job repositories (Brazilian communities)")
    description = _(
        "Jobs posted as issues in Brazilian developer communities' repositories "
        "(backend-br/vagas and others). Public API, no account."
    )
    brand = "GitHub"
    url = f"{API}backend-br/vagas/issues"
    pause_s = 1.0

    def __init__(
        self,
        *,
        repositories: list[str] | None = None,
        client: httpx.AsyncClient | None = None,
        cache: Path | None = None,
    ) -> None:
        super().__init__(client=client, cache=cache)
        self.repositories = repositories or settings.github_job_repositories

    def queries(self) -> list[tuple[str, dict[str, str]]]:
        params = {"state": "open", "per_page": "100"}
        return [
            (f"{API}{repository}/issues", params) for repository in self.repositories
        ]

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, list):
            raise unexpected_format(self.brand, _("a list"))
        return [
            _job(issue)
            for issue in data
            if isinstance(issue, dict)
            and "pull_request" not in issue
            and issue.get("html_url")
        ]


def _repository(url: str) -> str:
    # "https://github.com/backend-br/vagas/issues/12472" -> "backend-br/vagas"
    return "/".join(url.split("/")[3:5])


def _title_parts(title: str) -> tuple[str | None, str, str | None]:
    """(place, role, company) from "[Remoto] Dev PHP na Company"."""
    place = _PLACE.match(title)
    rest = title[place.end() :] if place else title
    marks = list(_COMPANY_MARK.finditer(rest))
    # The last "na": "Dev na area de dados na Company" names the company at the end.
    company = _TRAILING_NOTE.sub("", rest[marks[-1].end() :]).strip() if marks else ""
    return (place[1].strip() if place else None, rest.strip(), company or None)


def _job(issue: dict[str, Any]) -> Job:
    labels = [
        str(label["name"])
        for label in issue.get("labels") or []
        if isinstance(label, dict) and label.get("name")
    ]
    plain = {label: strip_accents(label) for label in labels}
    place, role, company = _title_parts(str(issue.get("title") or ""))
    # The label says it; without one, the title often does ("[Remoto]", "Hibrido ...").
    words = [*plain.values(), *strip_accents(str(issue.get("title") or "")).split()]
    modes = [
        WORK_MODES[word.strip("[]-,")]
        for word in words
        if word.strip("[]-,") in WORK_MODES
    ]
    body, _removed = remove_contact_data(_COMMENT.sub("", issue.get("body") or ""))
    url = str(issue["html_url"])
    return Job(
        source=GitHubJobs.name,
        external_id=f"{_repository(url)}#{issue['number']}",
        url=url,  # the issue: where the job was posted
        title=role or _("(untitled)"),
        company=company,
        location=place,
        work_mode=modes[0] if modes else None,
        skills=[
            label
            for label in labels
            if plain[label] not in SENIORITY | CONTRACT | WORK_MODES.keys()
        ],
        published_at=issue.get("created_at"),
        description=body,
        extras={
            "via": _repository(url),
            "seniority": [label for label in labels if plain[label] in SENIORITY],
            "contract": [label for label in labels if plain[label] in CONTRACT],
        },
    )
