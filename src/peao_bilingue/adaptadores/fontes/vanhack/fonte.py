import asyncio
import random
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager, suppress
from typing import Self, TypeVar

from playwright.async_api import BrowserContext, Page

from peao_bilingue.adaptadores.fontes.vanhack import (
    auth,
    debug,
    detail,
    listing,
    profile,
    sessao,
)
from peao_bilingue.adaptadores.fontes.vanhack.browser import open_context, save_state
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import Perfil, Skill, Vaga, VagaResumo
from peao_bilingue.dominio.erros import DesafioHumano, ErroDeColeta, SessaoExpirada
from peao_bilingue.dominio.portas import FonteDePerfil, FonteDeVagas, SessaoManual
from peao_bilingue.fabricas import fontes

T = TypeVar("T")

PAUSA_MIN_S = 2.0
PAUSA_MAX_S = 5.0


@fontes.registrar("vanhack")
class VanHack(FonteDeVagas, FonteDePerfil, SessaoManual):
    """Coleta lendo o DOM com Playwright, na sessão salva pelo login manual.

    Nunca chama a API interna da VanHack e nunca tenta passar por desafio humano.
    """

    nome = "vanhack"
    rotulo = "VanHack"
    precisa_navegador = True

    @classmethod
    async def login_manual(cls, aviso: Callable[[str], None]) -> None:
        await sessao.login_manual(aviso)

    @classmethod
    async def verificar_sessao(
        cls, aviso: Callable[[str], None], *, headless: bool = True
    ) -> int:
        return await sessao.verificar_sessao(aviso, headless=headless)

    def __init__(
        self, *, headless: bool | None = None, max_scrolls: int | None = None
    ) -> None:
        self.headless = headless
        self.max_scrolls = max_scrolls
        self._navegador: AbstractAsyncContextManager[BrowserContext] | None = None
        self._pagina: Page | None = None

    async def __aenter__(self) -> Self:
        self._navegador = open_context(headless=self.headless)
        contexto = await self._navegador.__aenter__()
        self._pagina = await contexto.new_page()

        await auth.goto(self._pagina, settings.vanhack_jobs_url)
        desafio = await auth.detect_challenge(self._pagina)
        if desafio:
            artefato = await self._salvar_evidencia("desafio")
            raise DesafioHumano(f"{desafio} (evidência em {artefato})")
        await auth.ensure_logged_in(self._pagina)
        await save_state(contexto)
        return self

    async def __aexit__(self, *excecao: object) -> None:
        if self._navegador is not None:
            await self._navegador.__aexit__(None, None, None)
        self._navegador = self._pagina = None

    @property
    def pagina(self) -> Page:
        if self._pagina is None:
            raise RuntimeError("Use a fonte dentro de `async with`.")
        return self._pagina

    async def buscar(self, termo: str) -> list[VagaResumo]:
        await _pausa_educada()
        cards = await self._com_evidencia(
            f"busca_{termo}", listing.search(self.pagina, termo, self.max_scrolls)
        )
        return [_resumo(card) for card in cards]

    async def detalhar(self, resumo: VagaResumo) -> Vaga:
        await _pausa_educada()
        dados = await self._com_evidencia(
            f"vaga_{resumo.id_externo}", detail.scrape(self.pagina, resumo.url)
        )
        return _vaga(resumo, dados)

    async def ler_perfil(self) -> Perfil:
        dados = await self._com_evidencia("perfil", profile.scrape(self.pagina))
        return Perfil(
            fonte=self.nome,
            dados=dados,
            texto=profile.to_text(dados),
            content_hash=profile.content_hash(dados),
        )

    async def _com_evidencia(self, rotulo: str, operacao: Awaitable[T]) -> T:
        """Qualquer falha de leitura deixa screenshot + HTML em artifacts/."""
        try:
            return await operacao
        except (SessaoExpirada, DesafioHumano):
            raise
        except Exception as falha:
            artefato = await self._salvar_evidencia(rotulo)
            raise ErroDeColeta(f"VanHack, {rotulo}: {falha}", artefato) from falha

    async def _salvar_evidencia(self, rotulo: str) -> str | None:
        # A página pode ter morrido junto com a falha; não mascarar o erro original.
        with suppress(Exception):
            return str(await debug.dump(self.pagina, rotulo))
        return None


async def _pausa_educada() -> None:
    await asyncio.sleep(random.uniform(PAUSA_MIN_S, PAUSA_MAX_S))


def _resumo(card: dict) -> VagaResumo:
    return VagaResumo(
        fonte=VanHack.nome,
        id_externo=card["id"],
        url=card["url"],
        titulo=card.get("titulo") or "Vaga sem título",
        local=card.get("local"),
        modalidade=card.get("modalidade"),
        salario=card.get("salario"),
        skills=card.get("skills") or [],
        publicada_em=card.get("publicada_em"),
        extras={
            "chamada": card.get("chamada"),
            "local_exigido": card.get("local_exigido"),
        },
    )


def _vaga(resumo: VagaResumo, dados: dict) -> Vaga:
    def skills(chave: str) -> list[Skill]:
        return [
            Skill(nome=item["skill"], anos=item.get("anos"))
            for item in dados.get(chave) or []
        ]

    return Vaga(
        **{
            **resumo.model_dump(),
            "titulo": dados.get("titulo") or resumo.titulo,
            "modalidade": dados.get("modalidade") or resumo.modalidade,
            "salario": dados.get("salario") or resumo.salario,
            "descricao": dados.get("descricao") or "",
            "skills_obrigatorias": skills("skills_obrigatorias"),
            "skills_desejaveis": skills("skills_desejaveis"),
            "idiomas": dados.get("idiomas") or [],
            "extras": {
                **resumo.extras,
                "fatos": dados.get("fatos") or [],
                "local_exigido": dados.get("local_exigido")
                or resumo.extras.get("local_exigido"),
            },
        }
    )
