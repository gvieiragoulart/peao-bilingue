import logging
import re

from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from peao_bilingue.adaptadores.fontes.vanhack import auth, selectors
from peao_bilingue.configuracao import settings

logger = logging.getLogger(__name__)

TIMEOUT_RENDER_MS = 15_000
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
    url = url_de_busca(termo)
    await auth.goto(page, url)
    if not await _esperar_resultado(page):
        # A VanHack às vezes demora a renderizar: uma segunda chance antes de desistir.
        logger.info("Listagem de %r não renderizou; recarregando uma vez.", termo)
        await auth.goto(page, url)
        if not await _esperar_resultado(page):
            raise PlaywrightTimeoutError(f"A listagem de {termo!r} não renderizou.")

    if not await page.locator(selectors.CARD_LINK).count():
        logger.info("Busca %r sem resultados.", termo)
        return []
    await _rolar_ate_o_fim(page, max_scrolls)
    return await extract(page)


async def _esperar_resultado(page: Page) -> bool:
    """Espera um card ou o aviso de zero vagas.

    "Anexado ao DOM" basta: só lemos o conteúdo, ninguém clica, e exigir
    "visível" fazia a execução cair à toa quando a página demorava a pintar.
    """
    alvo = page.locator(selectors.CARD_LINK).or_(
        page.get_by_text(selectors.EMPTY_STATE_TEXT)
    )
    try:
        await alvo.first.wait_for(state="attached", timeout=TIMEOUT_RENDER_MS)
    except PlaywrightTimeoutError:
        return False
    return True


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
