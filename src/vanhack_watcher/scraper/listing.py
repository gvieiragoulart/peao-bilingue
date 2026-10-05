import re

from playwright.async_api import Locator, Page

from vanhack_watcher.config import settings
from vanhack_watcher.scraper import auth, selectors

TIMEOUT_RENDER_MS = 20_000
PAUSA_SCROLL_MS = 1_500


def url_de_busca(termo: str) -> str:
    """A busca da VanHack é feita por URL: "python dev" -> /jobs/python-dev-jobs."""
    slug = re.sub(r"[^a-z0-9]+", "-", termo.lower()).strip("-")
    return (
        f"{settings.vanhack_jobs_url}/{slug}-jobs"
        if slug
        else settings.vanhack_jobs_url
    )


async def search(page: Page, termo: str, max_scrolls: int | None = None) -> list[dict]:
    await auth.goto(page, url_de_busca(termo))
    await page.wait_for_selector(selectors.CARD_LINK, timeout=TIMEOUT_RENDER_MS)
    await _rolar_ate_o_fim(page, max_scrolls)
    return await extract(page)


async def extract(page: Page) -> list[dict]:
    """Cards da listagem, sem duplicatas, na ordem em que aparecem."""
    vagas: dict[str, dict] = {}
    for link in (
        await page.locator(selectors.CARDS_CONTAINER).locator(selectors.CARD_LINK).all()
    ):
        vaga = await _card(link)
        if vaga and vaga["id"] not in vagas:
            vagas[vaga["id"]] = vaga
    return list(vagas.values())


async def _rolar_ate_o_fim(page: Page, max_scrolls: int | None) -> None:
    """Scroll infinito: rola até a contagem de cards parar de crescer."""
    limite = settings.max_listing_scrolls if max_scrolls is None else max_scrolls
    cards = page.locator(selectors.CARDS_CONTAINER).locator(selectors.CARD_LINK)
    anterior = await cards.count()
    for _ in range(limite):
        await page.mouse.wheel(0, 6_000)
        await page.wait_for_timeout(PAUSA_SCROLL_MS)
        atual = await cards.count()
        if atual == anterior:
            return
        anterior = atual


async def _texto(locator: Locator) -> str | None:
    if not await locator.count():
        return None
    texto = " ".join((await locator.first.inner_text()).split())
    return texto or None


async def _card(link: Locator) -> dict | None:
    href = await link.get_attribute("href")
    achado = re.search(selectors.JOB_URL_ID, href or "")
    if not achado:
        return None

    skills, obrigatorias = [], []
    for chip in await link.locator(selectors.CARD_SKILL).all():
        nome = await _texto(chip)
        if not nome:
            continue
        skills.append(nome)
        classes = await chip.get_attribute("class") or ""
        if selectors.CARD_SKILL_MUST in classes:
            obrigatorias.append(nome)

    return {
        "id": achado.group(1),
        "url": f"https://app.vanhack.com{href}",
        "titulo": await _texto(link.locator(selectors.CARD_TITLE)),
        "chamada": await _texto(link.locator(selectors.CARD_EYEBROW)),
        "local": await _texto(link.locator(selectors.CARD_LOCATION)),
        "modalidade": await _texto(link.locator(selectors.CARD_MODE)),
        "skills": skills,
        "skills_obrigatorias": obrigatorias,
        "publicada_em": await _texto(link.locator(selectors.CARD_POSTED)),
        "salario": await _texto(link.locator(selectors.CARD_SALARY)),
        "local_exigido": await _texto(link.locator(selectors.CARD_CANDIDATE_LOCATION)),
    }
