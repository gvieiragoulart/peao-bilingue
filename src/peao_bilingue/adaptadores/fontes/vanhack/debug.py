from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import Page

from peao_bilingue.configuracao import settings

ARTIFACTS_DIR = Path("artifacts")


async def dump(page: Page, label: str) -> Path:
    """Salva screenshot + HTML da página em artifacts/ e devolve o caminho base."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    agora = datetime.now(tz=ZoneInfo(settings.timezone))
    base = ARTIFACTS_DIR / f"{agora:%Y%m%d_%H%M%S}_{label}"
    await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
    base.with_suffix(".html").write_text(await page.content(), encoding="utf-8")
    return base
