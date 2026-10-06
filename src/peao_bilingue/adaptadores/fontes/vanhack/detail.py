import re

from playwright.async_api import Locator, Page

from peao_bilingue.adaptadores.fontes.vanhack import auth, selectors

TIMEOUT_RENDER_MS = 20_000


async def scrape(page: Page, url: str) -> dict:
    await auth.goto(page, url)
    await page.wait_for_selector(selectors.JD_ROOT, timeout=TIMEOUT_RENDER_MS)
    return await extract(page, url)


async def extract(page: Page, url: str | None = None) -> dict:
    url = url or page.url
    achado = re.search(selectors.JOB_URL_ID, url)
    must, nice, idiomas = await _skills(page)
    return {
        "id": achado.group(1) if achado else None,
        "url": url,
        "titulo": await _texto(page.locator(selectors.JD_TITLE)),
        # A VanHack nunca expõe a empresa contratante, nem no card nem aqui.
        "empresa": None,
        "fatos": await _fatos(page),
        "modalidade": await _texto(page.locator(selectors.JD_MODE)),
        "local_exigido": await _texto(page.locator(selectors.JD_CANDIDATE_LOCATION)),
        "salario": await _texto(page.locator(selectors.JD_SALARY)),
        "skills_obrigatorias": must,
        "skills_desejaveis": nice,
        "idiomas": idiomas,
        "descricao": await _texto_em_paragrafos(page.locator(selectors.JD_DESCRIPTION)),
    }


async def _texto(locator: Locator) -> str | None:
    if not await locator.count():
        return None
    texto = " ".join((await locator.first.inner_text()).split())
    return texto or None


async def _texto_em_paragrafos(locator: Locator) -> str | None:
    """Como `_texto`, mas mantém uma linha por parágrafo/item.

    A descrição achatada numa linha só fica ilegível na tela e tira a estrutura
    (responsabilidades, requisitos) que ajuda o LLM a ler a vaga.
    """
    if not await locator.count():
        return None
    linhas = (
        " ".join(linha.split())
        for linha in (await locator.first.inner_text()).splitlines()
    )
    texto = "\n".join(linha for linha in linhas if linha)
    return texto or None


async def _fatos(page: Page) -> list[str]:
    """Linha do topo: local, anos de experiência, data de publicação."""
    fatos = []
    for fato in await page.locator(selectors.JD_FACT).all():
        texto = " ".join((await fato.inner_text()).split())
        if texto:
            fatos.append(texto)
    return fatos


async def _skills(page: Page) -> tuple[list[dict], list[dict], list[str]]:
    must: list[dict] = []
    nice: list[dict] = []
    idiomas: list[str] = []
    for bloco in await page.locator(selectors.JD_SUBBLOCK).all():
        cabecalho = (
            await _texto(bloco.locator(selectors.JD_SUBBLOCK_HEAD)) or ""
        ).upper()
        chips = await _chips(bloco)
        if selectors.JD_HEAD_LANGUAGES in cabecalho:
            idiomas = [chip["skill"] for chip in chips]
        elif selectors.JD_HEAD_MUST in cabecalho:
            must = chips
        elif selectors.JD_HEAD_NICE in cabecalho:
            nice = chips
    return must, nice, idiomas


async def _chips(bloco: Locator) -> list[dict]:
    """Cada chip é "C#" + <small>5 Year(s)</small>; separar nome e anos."""
    chips = []
    for chip in await bloco.locator(selectors.JD_CHIP).all():
        inteiro = " ".join((await chip.inner_text()).split())
        anos = await _texto(chip.locator(selectors.JD_CHIP_YEARS))
        nome = (
            inteiro[: -len(anos)].strip()
            if anos and inteiro.endswith(anos)
            else inteiro
        )
        if nome:
            chips.append({"skill": nome, "anos": anos})
    return chips
