"""The VanHack job listing, read from the DOM like a user would."""

import logging
import re
from typing import Any

from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from peao_bilingue.adapters.sources.vanhack import auth, selectors
from peao_bilingue.config import settings

logger = logging.getLogger(__name__)

RENDER_TIMEOUT_MS = 15_000
SCROLL_PAUSE_MS = 1_500


def search_url(term: str) -> str:
    """VanHack searches by URL: "python dev" -> /jobs/python-dev-jobs."""
    slug = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
    return (
        f"{settings.vanhack_jobs_url}/{slug}-jobs"
        if slug
        else settings.vanhack_jobs_url
    )


async def search(
    page: Page, term: str, max_scrolls: int | None = None
) -> list[dict[str, Any]]:
    url = search_url(term)
    await auth.goto(page, url)
    if not await _wait_for_result(page):
        # VanHack is sometimes slow to render: a second chance before giving up.
        logger.info("Listing for %r didn't render; reloading once.", term)
        await auth.goto(page, url)
        if not await _wait_for_result(page):
            raise PlaywrightTimeoutError(f"The listing for {term!r} didn't render.")

    if not await page.locator(selectors.CARD_LINK).count():
        logger.info("Search %r has no results.", term)
        return []
    await _scroll_to_end(page, max_scrolls)
    return await extract(page)


async def _wait_for_result(page: Page) -> bool:
    """Waits for a card or for the zero-jobs notice.

    "Attached to the DOM" is enough: the content is only read, nothing is clicked, and
    requiring "visible" made runs fail for nothing when the page was slow to paint.
    """
    target = page.locator(selectors.CARD_LINK).or_(
        page.get_by_text(selectors.EMPTY_STATE_TEXT)
    )
    try:
        await target.first.wait_for(state="attached", timeout=RENDER_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        return False
    return True


async def extract(page: Page) -> list[dict[str, Any]]:
    """The listing's cards, without duplicates, in the order they show up."""
    jobs: dict[str, dict[str, Any]] = {}
    for link in (
        await page.locator(selectors.CARDS_CONTAINER).locator(selectors.CARD_LINK).all()
    ):
        job = await _card(link)
        if job and job["id"] not in jobs:
            jobs[job["id"]] = job
    return list(jobs.values())


async def _scroll_to_end(page: Page, max_scrolls: int | None) -> None:
    """Infinite scroll: scrolls until the card count stops growing."""
    limit = settings.max_listing_scrolls if max_scrolls is None else max_scrolls
    cards = page.locator(selectors.CARDS_CONTAINER).locator(selectors.CARD_LINK)
    previous = await cards.count()
    for _scroll in range(limit):
        await page.mouse.wheel(0, 6_000)
        await page.wait_for_timeout(SCROLL_PAUSE_MS)
        current = await cards.count()
        if current == previous:
            return
        previous = current


async def _text(locator: Locator) -> str | None:
    if not await locator.count():
        return None
    text = " ".join((await locator.first.inner_text()).split())
    return text or None


async def _card(link: Locator) -> dict[str, Any] | None:
    href = await link.get_attribute("href")
    found = re.search(selectors.JOB_URL_ID, href or "")
    if not found:
        return None

    skills, required = [], []
    for chip in await link.locator(selectors.CARD_SKILL).all():
        name = await _text(chip)
        if not name:
            continue
        skills.append(name)
        classes = await chip.get_attribute("class") or ""
        if selectors.CARD_SKILL_MUST in classes:
            required.append(name)

    return {
        "id": found.group(1),
        "url": f"https://app.vanhack.com{href}",
        "title": await _text(link.locator(selectors.CARD_TITLE)),
        "headline": await _text(link.locator(selectors.CARD_EYEBROW)),
        "location": await _text(link.locator(selectors.CARD_LOCATION)),
        "work_mode": await _text(link.locator(selectors.CARD_MODE)),
        "skills": skills,
        "required_skills": required,
        "published_at": await _text(link.locator(selectors.CARD_POSTED)),
        "salary": await _text(link.locator(selectors.CARD_SALARY)),
        "required_location": await _text(
            link.locator(selectors.CARD_CANDIDATE_LOCATION)
        ),
    }
