"""What the page looked like: evidence when reading it failed, and the screenshots the
user asked for in a collection."""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import Page

from peao_bilingue.config import ARTIFACTS_DIR, settings


def file_label(label: str) -> str:
    """A label that is safe in a file name: "search_node.js" -> "search_node-js"."""
    return re.sub(r"[^a-z0-9_]+", "-", label.lower()).strip("-") or "page"


async def dump(page: Page, label: str, folder: Path = ARTIFACTS_DIR) -> Path:
    """Saves a screenshot + the page's HTML in `folder` and returns the base path."""
    now = datetime.now(tz=ZoneInfo(settings.timezone))
    base = folder / f"{now:%Y%m%d_%H%M%S}_{file_label(label)}"
    # Disk work off the event loop: the window shares the same loop.
    await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
    await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
    html = await page.content()
    await asyncio.to_thread(base.with_suffix(".html").write_text, html, "utf-8")
    return base
