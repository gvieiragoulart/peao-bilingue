"""A VanHack job page, read from the DOM like a user would."""

import re
from typing import Any

from playwright.async_api import Locator, Page

from peao_bilingue.adapters.sources.vanhack import auth, selectors

RENDER_TIMEOUT_MS = 20_000


async def scrape(page: Page, url: str) -> dict[str, Any]:
    await auth.goto(page, url)
    await page.wait_for_selector(selectors.JD_ROOT, timeout=RENDER_TIMEOUT_MS)
    return await extract(page, url)


async def extract(page: Page, url: str | None = None) -> dict[str, Any]:
    url = url or page.url
    found = re.search(selectors.JOB_URL_ID, url)
    must, nice, languages = await _skills(page)
    return {
        "id": found.group(1) if found else None,
        "url": url,
        "title": await _text(page.locator(selectors.JD_TITLE)),
        # VanHack never shows the hiring company, not on the card and not here.
        "company": None,
        "facts": await _facts(page),
        "work_mode": await _text(page.locator(selectors.JD_MODE)),
        "required_location": await _text(page.locator(selectors.JD_CANDIDATE_LOCATION)),
        "salary": await _text(page.locator(selectors.JD_SALARY)),
        "required_skills": must,
        "preferred_skills": nice,
        "languages": languages,
        "description": await _text_as_paragraphs(
            page.locator(selectors.JD_DESCRIPTION)
        ),
    }


async def _text(locator: Locator) -> str | None:
    if not await locator.count():
        return None
    text = " ".join((await locator.first.inner_text()).split())
    return text or None


async def _text_as_paragraphs(locator: Locator) -> str | None:
    """Like `_text`, but keeps one line per paragraph/item.

    A description flattened into one line is unreadable on screen and loses the
    structure (responsibilities, requirements) that helps the LLM read the job.
    """
    if not await locator.count():
        return None
    lines = (
        " ".join(line.split())
        for line in (await locator.first.inner_text()).splitlines()
    )
    text = "\n".join(line for line in lines if line)
    return text or None


async def _facts(page: Page) -> list[str]:
    """The top line: location, years of experience, posting date."""
    facts = []
    for fact in await page.locator(selectors.JD_FACT).all():
        text = " ".join((await fact.inner_text()).split())
        if text:
            facts.append(text)
    return facts


async def _skills(
    page: Page,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    must: list[dict[str, Any]] = []
    nice: list[dict[str, Any]] = []
    languages: list[str] = []
    for block in await page.locator(selectors.JD_SUBBLOCK).all():
        header = (await _text(block.locator(selectors.JD_SUBBLOCK_HEAD)) or "").upper()
        chips = await _chips(block)
        if selectors.JD_HEAD_LANGUAGES in header:
            languages = [chip["skill"] for chip in chips]
        elif selectors.JD_HEAD_MUST in header:
            must = chips
        elif selectors.JD_HEAD_NICE in header:
            nice = chips
    return must, nice, languages


async def _chips(block: Locator) -> list[dict[str, Any]]:
    """Each chip is "C#" + <small>5 Year(s)</small>; split the name from the years."""
    chips = []
    for chip in await block.locator(selectors.JD_CHIP).all():
        whole = " ".join((await chip.inner_text()).split())
        years = await _text(chip.locator(selectors.JD_CHIP_YEARS))
        name = (
            whole[: -len(years)].strip() if years and whole.endswith(years) else whole
        )
        if name:
            chips.append({"skill": name, "years": years})
    return chips
