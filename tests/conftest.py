from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from playwright.async_api import Page, async_playwright
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from peao_bilingue.adaptadores.persistencia.sqlite import RepositorioSQLite


@pytest_asyncio.fixture
async def page() -> AsyncIterator[Page]:
    """Página em branco no Chromium empacotado, sem rede."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context()
        yield await context.new_page()
        await browser.close()


@pytest.fixture
def repositorio() -> RepositorioSQLite:
    """Repositório real sobre SQLite em memória: nunca toca em data/peao.db."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    return RepositorioSQLite(engine)
