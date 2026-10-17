"""Fakes of the ports: the whole pipeline runs with no browser, network or LLM."""

from pathlib import Path
from typing import Any, Self

import httpx
from builders import analysis
from pydantic import BaseModel

from peao_bilingue.domain.analysis import LLMProvider, LLMResponse, Message
from peao_bilingue.domain.collection import JobSource
from peao_bilingue.domain.jobs import Job, JobSummary
from peao_bilingue.domain.notifications import Notifier
from peao_bilingue.domain.profile import Profile, ProfileSource
from peao_bilingue.domain.schedule import Scheduler, ScheduleStatus
from peao_bilingue.domain.updates import Release, ReleaseFeed


class FakeSource(JobSource):
    label = "Fake"

    def __init__(
        self,
        name: str = "fake",
        jobs: list[Job] | None = None,
        failure: Exception | None = None,
    ) -> None:
        # Real sources name the class; the fake needs one name per instance.
        self.name = name  # type: ignore[misc]
        # Like a real source, every job comes out with this source's name.
        self.jobs = {
            job.external_id: job.model_copy(update={"source": name})
            for job in jobs or []
        }
        self.failure = failure
        self.detailed: list[str] = []
        self.is_open = False

    async def __aenter__(self) -> Self:
        if self.failure:
            raise self.failure
        self.is_open = True
        return self

    async def __aexit__(self, *exception: object) -> None:
        self.is_open = False

    async def search(self, term: str) -> list[JobSummary]:
        return [
            JobSummary(**job.model_dump(include=set(JobSummary.model_fields)))
            for job in self.jobs.values()
        ]

    async def detail(self, summary: JobSummary) -> Job:
        self.detailed.append(summary.external_id)
        return self.jobs[summary.external_id]


class FakeSourceWithProfile(FakeSource, ProfileSource):
    def __init__(
        self,
        profile: Profile,
        *,
        name: str = "fake",
        jobs: list[Job] | None = None,
        failure: Exception | None = None,
        profile_failure: Exception | None = None,
    ) -> None:
        super().__init__(name, jobs, failure)
        # Like a real source, the profile comes out with this source's name.
        self.profile = profile.model_copy(update={"source": self.name})
        self.profile_failure = profile_failure

    async def read_profile(self) -> Profile:
        if self.profile_failure:
            raise self.profile_failure
        return self.profile


class FakeProvider(LLMProvider):
    """Returns the responses in order; with none left, a valid analysis scored `fit`."""

    def __init__(
        self,
        responses: list[LLMResponse] | None = None,
        fit: int = 82,
        *,
        name: str = "fake",
        failure: Exception | None = None,
    ) -> None:
        # Real providers name the class; the fake needs one name per instance.
        self.name = name  # type: ignore[misc]
        self.model = f"{name}-1"
        self.responses = list(responses or [])
        self.fit = fit
        self.failure = failure
        self.calls: list[dict[str, Any]] = []

    async def generate_json(
        self, system: str, messages: list[Message], schema: type[BaseModel]
    ) -> LLMResponse:
        self.calls.append(
            {"system": system, "messages": list(messages), "schema": schema}
        )
        if self.failure:
            raise self.failure
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(text=analysis(self.fit).model_dump_json())


class FakeScheduler(Scheduler):
    """Keeps the schedule in memory: the tests never touch Windows Task Scheduler."""

    def __init__(self) -> None:
        self.current: ScheduleStatus | None = None

    def schedule(self, time: str) -> None:
        if len(time) != 5:
            raise ValueError(f"Invalid time: {time!r}.")
        self.current = ScheduleStatus(time=time, state="Ready")

    def cancel(self) -> None:
        self.current = None

    def status(self) -> ScheduleStatus | None:
        return self.current


class FakeNotifier(Notifier):
    name = "fake"

    def __init__(self, failure: Exception | None = None) -> None:
        self.received: list[list[Job]] = []
        self.problems: list[list[str]] = []
        self.failure = failure

    async def notify(self, jobs: list[Job]) -> None:
        if self.failure:
            raise self.failure
        self.received.append(jobs)

    async def notify_problem(self, problems: list[str]) -> None:
        if self.failure:
            raise self.failure
        self.problems.append(problems)


class FakeApi:
    """Answers like a public API, with the real response saved in the fixture, and
    counts the calls: these APIs' terms limit how many per day."""

    def __init__(self, fixture: Path, status: int = 200) -> None:
        self.fixture = fixture
        self.status = status
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={})
        return httpx.Response(200, content=self.fixture.read_bytes())

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))


class FakeReleaseFeed(ReleaseFeed):
    """No new version, unless the test says so: the tests never call GitHub."""

    def __init__(self, release: Release | None = None) -> None:
        self.release = release

    async def latest(self) -> Release | None:
        return self.release
