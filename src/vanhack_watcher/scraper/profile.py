import hashlib
import json
import re

from playwright.async_api import Locator, Page

from vanhack_watcher.config import settings
from vanhack_watcher.scraper import auth, selectors

TIMEOUT_RENDER_MS = 20_000


async def scrape(page: Page) -> dict:
    """Abre /profile e devolve o perfil estruturado, já sem PII."""
    await auth.goto(page, settings.vanhack_profile_url)
    await page.wait_for_selector(
        selectors.PROFILE_READY, state="attached", timeout=TIMEOUT_RENDER_MS
    )
    return await extract(page)


async def extract(page: Page) -> dict:
    campos = await _mapa_de_campos(page)
    return {
        "cargo": campos.get(selectors.LABEL_CARGO),
        "anos_como_profissional_ti": campos.get(selectors.LABEL_ANOS_TI),
        "lideranca": campos.get(selectors.LABEL_LIDERANCA),
        "anos_de_lideranca": campos.get(selectors.LABEL_ANOS_LIDERANCA),
        "aberto_a_remoto": campos.get(selectors.LABEL_REMOTO),
        "skills_principais": await _skills(page, selectors.GRUPO_SKILLS_PRINCIPAIS),
        "skills_secundarias": await _skills(page, selectors.GRUPO_SKILLS_SECUNDARIAS),
        "idiomas": await _idiomas(page),
        "ingles_avaliado_no_video": await _nivel_ingles(page),
        "experiencias": await _experiencias(page),
        "formacao": await _formacao(page),
        "links": await _links(page),
        "outros_campos": campos,
    }


def to_text(dados: dict) -> str:
    """Versão legível do perfil, usada no prompt da análise."""
    linhas = [
        f"Cargo: {dados.get('cargo') or 'não informado'}",
        f"Anos como profissional de TI: {dados.get('anos_como_profissional_ti') or '-'}",
        f"Liderança: {dados.get('lideranca') or '-'} ({dados.get('anos_de_lideranca') or '-'})",
        f"Formação: {dados.get('formacao') or '-'}",
        f"Aberto a remoto: {dados.get('aberto_a_remoto') or '-'}",
        f"Inglês avaliado no vídeo: {dados.get('ingles_avaliado_no_video') or '-'}",
        "",
        "Skills principais: " + _skills_em_linha(dados.get("skills_principais")),
        "Skills secundárias: " + _skills_em_linha(dados.get("skills_secundarias")),
        "Idiomas: "
        + ", ".join(
            f"{i['idioma']} ({i.get('nivel') or '-'})"
            for i in dados.get("idiomas") or []
        ),
    ]

    # Só a presença do link: a URL carrega o nome real e o modelo não a acessa.
    links = dados.get("links") or {}
    if links:
        linhas.append(
            "Links no perfil: "
            + ", ".join(
                f"{nome} {'preenchido' if url else 'em branco'}"
                for nome, url in links.items()
            )
        )

    linhas += ["", "Experiências:"]
    for experiencia in dados.get("experiencias") or []:
        setor = f" ({experiencia['setor']})" if experiencia.get("setor") else ""
        linhas.append(
            f"- {experiencia.get('empresa') or 'empresa não informada'}{setor}"
        )
        for cargo in experiencia.get("cargos") or []:
            linhas.append(f"  {cargo.get('cargo_e_periodo') or '-'}")
            if cargo.get("descricao"):
                linhas.append(f"  {cargo['descricao']}")
            if cargo.get("skills"):
                linhas.append("  Skills: " + ", ".join(cargo["skills"]))

    outros = dados.get("outros_campos") or {}
    if outros:
        linhas += ["", "Preferências declaradas na VanHack:"]
        linhas += [
            f"- {chave}: {_valor_em_texto(valor)}"
            for chave, valor in outros.items()
            if valor
        ]

    return "\n".join(linhas)


def _skills_em_linha(skills: list[dict] | None) -> str:
    return ", ".join(f"{s['skill']} ({s.get('anos') or '-'})" for s in skills or [])


def _valor_em_texto(valor: object) -> str:
    return ", ".join(valor) if isinstance(valor, list) else str(valor)


def normalizar(dados: dict) -> str:
    """JSON canônico do perfil, base para o hash de mudança."""
    return json.dumps(dados, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(dados: dict) -> str:
    return hashlib.sha256(normalizar(dados).encode("utf-8")).hexdigest()


def _sensivel(rotulo: str) -> bool:
    return any(termo in rotulo.lower() for termo in selectors.PII_LABELS)


def _limpar(texto: str | None) -> str | None:
    if texto is None:
        return None
    texto = " ".join(texto.split())
    return None if not texto or texto in selectors.VALORES_VAZIOS else texto


def _sem_separadores_vazios(texto: str | None) -> str | None:
    """ "Internet - -" vira "Internet": a VanHack concatena subcampos vazios."""
    return _limpar(re.sub(r"(\s*-\s*)+$", "", texto)) if texto else None


def _reduzir(valores: list[str | None]) -> str | list[str] | None:
    """Um valor vira escalar; vários viram lista; nenhum vira None."""
    limpos = [v for v in valores if v]
    if not limpos:
        return None
    return limpos[0] if len(limpos) == 1 else limpos


async def _textos(locator: Locator) -> list[str | None]:
    return [_limpar(await item.inner_text()) for item in await locator.all()]


async def _valores(locator: Locator) -> list[str | None]:
    return [_limpar(await item.input_value()) for item in await locator.all()]


async def _valor(campo: Locator) -> str | list[str] | None:
    for seletor in (selectors.RADIO_MARCADO, selectors.CHECKBOX_MARCADO):
        marcados = campo.locator(seletor)
        if await marcados.count():
            return _reduzir(await _textos(marcados))
    dropdowns = campo.locator(selectors.DROPDOWN)
    if await dropdowns.count():
        return _reduzir(await _textos(dropdowns))
    entradas = campo.locator(selectors.AUTOCOMPLETE_INPUT)
    if await entradas.count():
        return _reduzir(await _valores(entradas))
    return None


async def _mapa_de_campos(page: Page) -> dict[str, str | None]:
    """Todos os pares pergunta/resposta da página, menos os sensíveis.

    Guardar o mapa inteiro (e não só os rótulos conhecidos) faz o snapshot
    sobreviver a mudanças de texto das perguntas na VanHack.
    """
    mapa: dict[str, str | None] = {}
    for campo in await page.locator(selectors.FIELD).all():
        rotulo = campo.locator(selectors.FIELD_LABEL)
        if not await rotulo.count():
            continue
        chave = _limpar(await rotulo.first.inner_text())
        if chave and not _sensivel(chave):
            mapa[chave] = await _valor(campo)
    return mapa


async def _skills(page: Page, titulo: str) -> list[dict[str, str | None]]:
    for grupo in await page.locator(selectors.SKILL_GROUP).all():
        cabecalho = _limpar(
            await grupo.locator(selectors.SKILL_GROUP_TITLE).first.inner_text()
        )
        if cabecalho != titulo:
            continue
        skills = []
        for linha in await grupo.locator(selectors.SKILL_ROW).all():
            nome = _limpar(
                await linha.locator(selectors.SKILL_SELECT)
                .locator(selectors.AUTOCOMPLETE_INPUT)
                .first.input_value()
            )
            if nome:
                anos = linha.locator(selectors.SKILL_YEARS)
                skills.append(
                    {
                        "skill": nome,
                        "anos": _limpar(await anos.first.inner_text())
                        if await anos.count()
                        else None,
                    }
                )
        return skills
    return []


async def _idiomas(page: Page) -> list[dict[str, str | None]]:
    idiomas = []
    for linha in await page.locator(selectors.LANG_ROW).all():
        nome = _limpar(
            await linha.locator(selectors.LANG_SELECT)
            .locator(selectors.AUTOCOMPLETE_INPUT)
            .first.input_value()
        )
        if nome:
            idiomas.append(
                {
                    "idioma": nome,
                    "nivel": _limpar(
                        await linha.locator(selectors.LANG_LEVEL).first.inner_text()
                    ),
                }
            )
    return idiomas


async def _experiencias(page: Page) -> list[dict]:
    experiencias = []
    for bloco in await page.locator(selectors.EXPERIENCE).all():
        cargos = []
        for cargo in await bloco.locator(selectors.EXP_ROLE).all():
            descricao = cargo.locator(selectors.EXP_ROLE_DESC)
            cargos.append(
                {
                    "cargo_e_periodo": _limpar(
                        await cargo.locator(selectors.EXP_ROLE_HEAD).first.inner_text()
                    ),
                    "descricao": _limpar(await descricao.first.inner_text())
                    if await descricao.count()
                    else None,
                    "skills": [
                        chip
                        for chip in await _textos(
                            cargo.locator(selectors.EXP_ROLE_CHIPS)
                        )
                        if chip
                    ],
                }
            )
        setor = _limpar(await bloco.locator(selectors.EXP_INDUSTRY).first.inner_text())
        experiencias.append(
            {
                "empresa": _limpar(
                    await bloco.locator(selectors.EXP_COMPANY).first.inner_text()
                ),
                "setor": _sem_separadores_vazios(setor),
                "cargos": cargos,
            }
        )
    return experiencias


async def _nivel_ingles(page: Page) -> str | None:
    card = page.locator(selectors.INTRO_VIDEO_CARD)
    if not await card.count():
        return None
    achado = re.search(selectors.INTRO_VIDEO_NIVEL, await card.first.inner_text())
    return achado.group(1) if achado else None


async def _formacao(page: Page) -> str | None:
    grau = page.locator(selectors.EDUCATION_DEGREE).locator(selectors.DROPDOWN)
    return _limpar(await grau.first.inner_text()) if await grau.count() else None


async def _links(page: Page) -> dict[str, str | None]:
    links = {}
    for nome, seletor in selectors.LINK_INPUTS.items():
        campo = page.locator(seletor)
        links[nome] = (
            _limpar(await campo.first.input_value()) if await campo.count() else None
        )
    return links
