from collections.abc import AsyncIterator

import pytest_asyncio
from playwright.async_api import Page, async_playwright


@pytest_asyncio.fixture
async def page() -> AsyncIterator[Page]:
    """Página em branco no Chromium empacotado, sem rede."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context()
        yield await context.new_page()
        await browser.close()
