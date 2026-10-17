"""The installed Chrome under Playwright, with the session the user saved by hand."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import BrowserContext, async_playwright

from peao_bilingue.config import DATA_DIR, settings

STATE_PATH = DATA_DIR / "state.json"


def has_state() -> bool:
    return STATE_PATH.exists()


@asynccontextmanager
async def open_context(
    *, headless: bool | None = None, channel: str | None = None
) -> AsyncIterator[BrowserContext]:
    """Opens a context that reuses data/state.json when it exists.

    Uses the installed Chrome (`channel`) instead of the bundled Chromium: VanHack's
    Cloudflare rejects unusual browsers.
    """
    headless = settings.headless if headless is None else headless
    channel = settings.browser_channel if channel is None else channel
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless, channel=channel or None
        )
        context = await browser.new_context(
            storage_state=STATE_PATH if has_state() else None
        )
        try:
            yield context
        finally:
            await context.close()
            await browser.close()


async def save_state(context: BrowserContext) -> Path:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=STATE_PATH)
    return STATE_PATH
