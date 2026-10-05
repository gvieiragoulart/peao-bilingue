from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import BrowserContext, async_playwright

from vanhack_watcher.config import settings

STATE_PATH = Path("data/state.json")


def has_state() -> bool:
    return STATE_PATH.exists()


@asynccontextmanager
async def open_context(
    *, headless: bool | None = None, channel: str | None = None
) -> AsyncIterator[BrowserContext]:
    """Abre um contexto reaproveitando data/state.json quando existir.

    Usa o Chrome instalado (`channel`) em vez do Chromium empacotado: o
    Cloudflare da VanHack recusa navegadores atípicos.
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
