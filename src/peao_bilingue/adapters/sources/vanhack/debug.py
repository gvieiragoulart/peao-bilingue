"""Evidence of what the page looked like when reading it failed."""

import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import Page

from peao_bilingue.config import BASE_DIR, settings

ARTIFACTS_DIR = BASE_DIR / "artifacts"


async def dump(page: Page, label: str) -> Path:
    """Saves a screenshot + the page's HTML in artifacts/ and returns the base path."""
    now = datetime.now(tz=ZoneInfo(settings.timezone))
    base = ARTIFACTS_DIR / f"{now:%Y%m%d_%H%M%S}_{label}"
    # Disk work off the event loop: the window shares the same loop.
    await asyncio.to_thread(ARTIFACTS_DIR.mkdir, parents=True, exist_ok=True)
    await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
    html = await page.content()
    await asyncio.to_thread(base.with_suffix(".html").write_text, html, "utf-8")
    return base
