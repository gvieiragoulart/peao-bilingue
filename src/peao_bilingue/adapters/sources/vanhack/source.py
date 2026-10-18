"""The VanHack source: collects by reading the DOM, in the manually saved session."""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager, suppress
from pathlib import Path
from typing import Any, ClassVar, Self, TypeVar

from playwright.async_api import BrowserContext, Page

from peao_bilingue.adapters.sources.vanhack import (
    auth,
    debug,
    detail,
    listing,
    profile,
    session,
)
from peao_bilingue.adapters.sources.vanhack.browser import open_context, save_state
from peao_bilingue.config import settings
from peao_bilingue.domain.collection import JobSource, ManualSession
from peao_bilingue.domain.errors import CollectionError, HumanChallenge, SessionExpired
from peao_bilingue.domain.jobs import Job, JobSummary, Skill
from peao_bilingue.domain.profile import Profile, ProfileSource
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

logger = logging.getLogger(__name__)

T = TypeVar("T")

PAUSE_MIN_S = 2.0
PAUSE_MAX_S = 5.0


@sources.register("vanhack")
class VanHack(JobSource, ProfileSource, ManualSession):
    """Collects by reading the DOM with Playwright, in the session saved by the manual
    login.

    Never calls VanHack's internal API and never tries to get past a human challenge.
    """

    name = "vanhack"
    label = "VanHack"
    description = _(
        "Senior tech jobs at companies that sponsor visas and relocation, plus "
        "remote jobs with companies that hire internationally. Uses your account."
    )
    about = _(
        "The robot reads the jobs and your VanHack profile with the session saved "
        "when you log in by hand: it never fills in the login form or solves a "
        "human check. If the session expires, the collection stops and asks you to "
        "log in again."
    )
    site = "https://vanhack.com"
    fields: ClassVar[dict[str, str]] = {
        "headless": _("Hide the browser during the collection"),
        "max_listing_scrolls": _("Maximum listing scrolls"),
    }
    needs_browser = True

    @classmethod
    async def login_manual(cls, report: Callable[[str], None]) -> None:
        await session.login_manual(report)

    @classmethod
    async def check_session(
        cls, report: Callable[[str], None], *, headless: bool = True
    ) -> int:
        return await session.check_session(report, headless=headless)

    def __init__(
        self, *, headless: bool | None = None, max_scrolls: int | None = None
    ) -> None:
        self.headless = headless
        self.max_scrolls = max_scrolls
        self._browser: AbstractAsyncContextManager[BrowserContext] | None = None
        self._page: Page | None = None

    async def __aenter__(self) -> Self:
        self._browser = open_context(headless=self.headless)
        context = await self._browser.__aenter__()
        try:
            self._page = await context.new_page()

            await auth.goto(self._page, settings.vanhack_jobs_url)
            challenge = await auth.detect_challenge(self._page)
            if challenge:
                artifact = await self._save_evidence("challenge")
                raise HumanChallenge(
                    _("{reason} (evidence in {path})").format(
                        reason=challenge, path=artifact
                    )
                )
            await auth.ensure_logged_in(self._page)
            await save_state(context)
        except BaseException:
            # When entering fails, `async with` doesn't call __aexit__. Without closing
            # here, Chrome and the Playwright driver kept the process alive (a
            # scheduled collection with an expired session never ended).
            await self.__aexit__(None, None, None)
            raise
        return self

    async def __aexit__(self, *exception: object) -> None:
        if self._browser is not None:
            await self._browser.__aexit__(None, None, None)
        self._browser = self._page = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Use the source inside `async with`.")
        return self._page

    async def search(self, term: str) -> list[JobSummary]:
        await _polite_pause()
        cards = await self._with_evidence(
            f"search_{term}", listing.search(self.page, term, self.max_scrolls)
        )
        if self.capture_to is not None:
            await self._capture(f"search_{term}", self.capture_to)
        return [_summary(card) for card in cards]

    async def detail(self, summary: JobSummary) -> Job:
        await _polite_pause()
        data = await self._with_evidence(
            f"job_{summary.external_id}", detail.scrape(self.page, summary.url)
        )
        return _job(summary, data)

    async def read_profile(self) -> Profile:
        data = await self._with_evidence("profile", profile.scrape(self.page))
        return Profile(
            source=self.name,
            data=data,
            text=profile.to_text(data),
            content_hash=profile.content_hash(data),
        )

    async def _with_evidence(self, label: str, operation: Awaitable[T]) -> T:
        """Any reading failure leaves a screenshot + HTML in artifacts/."""
        try:
            return await operation
        except (SessionExpired, HumanChallenge):
            raise
        except Exception as failure:
            artifact = await self._save_evidence(label)
            raise CollectionError(f"VanHack, {label}: {failure}", artifact) from failure

    async def _capture(self, label: str, folder: Path) -> None:
        """The page as the robot read it (scrolled to the end), asked for by the user. A
        failed capture doesn't fail the search: the cards were already read."""
        try:
            await debug.dump(self.page, label, folder)
        except Exception as failure:  # noqa: BLE001 - only a missing screenshot
            logger.warning("Capturing %s failed: %s", label, failure)

    async def _save_evidence(self, label: str) -> str | None:
        # The page may have died along with the failure; don't hide the original error.
        with suppress(Exception):
            return str(await debug.dump(self.page, label))
        return None


async def _polite_pause() -> None:
    await asyncio.sleep(random.uniform(PAUSE_MIN_S, PAUSE_MAX_S))


def _summary(card: dict[str, Any]) -> JobSummary:
    return JobSummary(
        source=VanHack.name,
        external_id=card["id"],
        url=card["url"],
        title=card.get("title") or _("(untitled)"),
        location=card.get("location"),
        work_mode=card.get("work_mode"),
        salary=card.get("salary"),
        skills=card.get("skills") or [],
        published_at=card.get("published_at"),
        extras={
            "headline": card.get("headline"),
            "required_location": card.get("required_location"),
        },
    )


def _job(summary: JobSummary, data: dict[str, Any]) -> Job:
    def skills(key: str) -> list[Skill]:
        return [
            Skill(name=item["skill"], years=item.get("years"))
            for item in data.get(key) or []
        ]

    return Job(
        **{
            **summary.model_dump(),
            "title": data.get("title") or summary.title,
            "work_mode": data.get("work_mode") or summary.work_mode,
            "salary": data.get("salary") or summary.salary,
            "description": data.get("description") or "",
            "required_skills": skills("required_skills"),
            "preferred_skills": skills("preferred_skills"),
            "languages": data.get("languages") or [],
            "extras": {
                **summary.extras,
                "facts": data.get("facts") or [],
                "required_location": data.get("required_location")
                or summary.extras.get("required_location"),
            },
        }
    )
