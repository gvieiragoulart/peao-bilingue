import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import Page

from peao_bilingue.configuracao import PASTA_BASE, settings

ARTIFACTS_DIR = PASTA_BASE / "artifacts"


async def dump(page: Page, label: str) -> Path:
    """Salva screenshot + HTML da página em artifacts/ e devolve o caminho base."""
    agora = datetime.now(tz=ZoneInfo(settings.timezone))
    base = ARTIFACTS_DIR / f"{agora:%Y%m%d_%H%M%S}_{label}"
    # Disco fora do loop assíncrono: a interface usa o mesmo loop.
    await asyncio.to_thread(ARTIFACTS_DIR.mkdir, parents=True, exist_ok=True)
    await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
    html = await page.content()
    await asyncio.to_thread(base.with_suffix(".html").write_text, html, "utf-8")
    return base
