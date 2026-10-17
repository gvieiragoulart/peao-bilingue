"""Jobs: what the sources bring, what the user tracks and where it is kept."""

import re
import unicodedata
from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


def strip_accents(text: str) -> str:
    """Lowercase with the accents removed, so an accented word and the same word
    typed without accents match."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(letter for letter in decomposed if not unicodedata.combining(letter))


def _only_words(text: str) -> str:
    # "Full-stack" and "Full Stack", "Lemon.io" and "lemon io": the same thing.
    return " ".join(re.findall(r"[a-z0-9]+", strip_accents(text)))


class JobStatus(StrEnum):
    new = "new"
    studying = "studying"
    applied = "applied"
    discarded = "discarded"


class Skill(BaseModel):
    name: str
    years: str | None = None


class JobSummary(BaseModel):
    """What a source's listing returns, before the job is opened."""

    source: str
    external_id: str
    url: str
    title: str
    location: str | None = None
    work_mode: str | None = None
    salary: str | None = None
    skills: list[str] = []
    published_at: str | None = None
    extras: dict[str, Any] = {}  # source-specific fields with no place in the model

    @property
    def key(self) -> str:
        """Unique across sources: ids from different sites collide."""
        return f"{self.source}:{self.external_id}"


class Job(JobSummary):
    # Not every source publishes the hiring company (VanHack never does).
    company: str | None = None
    description: str = ""
    required_skills: list[Skill] = []
    preferred_skills: list[Skill] = []
    languages: list[str] = []

    def searchable_text(self) -> str:
        """Title, headline, skills and description, lowercased: where a search's
        terms are looked for (by the filter and by sources that filter locally)."""
        skills = [
            *self.skills,
            *(skill.name for skill in self.required_skills),
            *(skill.name for skill in self.preferred_skills),
        ]
        parts = [
            self.title,
            str(self.extras.get("headline") or ""),
            self.description,
            " ".join(skills),
        ]
        return " ".join(parts).lower()

    def fingerprint(self) -> str:
        """Normalized company + title: recognizes the same job posted on different
        sites. Empty when the source doesn't publish the company (VanHack never
        does): the title alone would merge jobs that have nothing in common."""
        if not self.company or not _only_words(self.company):
            return ""
        return f"{_only_words(self.company)}|{_only_words(self.title)}"

    def matches(self, search_text: str) -> bool:
        """Every word of the search text appears in the title, company, location,
        skills or description, ignoring accents and case."""
        text = strip_accents(
            " ".join([self.searchable_text(), self.company or "", self.location or ""])
        )
        return all(word in text for word in strip_accents(search_text).split())


class Posting(BaseModel):
    """Where else the same job was posted."""

    source: str
    url: str


class ListedJob(BaseModel):
    job: Job
    status: JobStatus
    fit_score: int | None
    searches: list[str]
    seen_at: datetime
    # The same job on other sites: kept once, with the other links here.
    also_on: list[Posting] = []


class JobRepository(ABC):
    @abstractmethod
    def job_exists(self, key: str) -> bool: ...

    @abstractmethod
    def save_job(
        self, job: Job, searches: list[str], *, duplicate_of: str | None = None
    ) -> None:
        """`duplicate_of` is the key of the same job already saved from another
        source: this one is kept (so it isn't detailed again) but left off the list."""

    @abstractmethod
    def original_of(self, job: Job) -> str | None:
        """The key of the same job (`Job.fingerprint`) saved from **another** source.
        Within one source, equal title and company are different jobs (another
        country)."""

    @abstractmethod
    def get_job(self, key: str) -> Job | None: ...

    @abstractmethod
    def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        min_score: int | None = None,
        search: str | None = None,
        source: str | None = None,
        search_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ListedJob]:
        """With each job's current fit (None when not analyzed yet)."""

    @abstractmethod
    def change_status(self, key: str, status: JobStatus) -> None: ...
