"""Remotive: API pública de vagas remotas (https://remotive.com/api/remote-jobs).

Termos (aviso legal na própria resposta e github.com/remotive-io/remote-jobs-api):
linkar a vaga no Remotive e citar o Remotive como fonte; no máximo ~4 chamadas por
dia (mais de 2 por minuto são bloqueadas); dados com 24 h de atraso; não republicar
as vagas em outros sites. Por isso:

- **uma chamada por coleta**: a categoria vem inteira e cada termo é filtrado aqui;
- **cache de 6 h em disco**: coletar várias vezes no dia não passa de 4 chamadas,
  e com 24 h de atraso nos dados não se perde nada;
- a vaga guarda a URL do Remotive e `extras["via"] = "Remotive"`.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Self

import httpx

from peao_bilingue.adaptadores.fontes.html import html_para_texto
from peao_bilingue.aplicacao.filtros import texto_da_vaga
from peao_bilingue.configuracao import DIRETORIO_DADOS, settings
from peao_bilingue.dominio.entidades import Vaga, VagaResumo
from peao_bilingue.dominio.erros import ErroDeColeta
from peao_bilingue.dominio.portas import FonteDeVagas
from peao_bilingue.fabricas import fontes

URL = "https://remotive.com/api/remote-jobs"
AGENTE = "peao-bilingue/0.1 (radar pessoal de vagas)"
TIMEOUT_S = 30
VALIDADE_DO_CACHE_S = 6 * 3600
CACHE_PADRAO = DIRETORIO_DADOS / "cache" / "remotive.json"


@fontes.registrar("remotive")
class Remotive(FonteDeVagas):
    nome = "remotive"
    rotulo = "Remotive (API pública, vagas remotas)"

    def __init__(
        self,
        *,
        categoria: str | None = None,
        cliente: httpx.AsyncClient | None = None,
        cache: Path | None = None,
    ) -> None:
        self.categoria = categoria or settings.remotive_categoria
        self.cache = cache or CACHE_PADRAO
        self._cliente_externo = cliente
        self._cliente: httpx.AsyncClient | None = None
        self._vagas: dict[str, Vaga] | None = None

    async def __aenter__(self) -> Self:
        self._cliente = self._cliente_externo or httpx.AsyncClient(
            timeout=TIMEOUT_S, headers={"User-Agent": AGENTE}
        )
        return self

    async def __aexit__(self, *excecao: object) -> None:
        if self._cliente is not None and self._cliente_externo is None:
            await self._cliente.aclose()
        self._cliente = None

    async def buscar(self, termo: str) -> list[VagaResumo]:
        procurado = termo.lower()
        # O mesmo texto que o filtro das buscas olha: o termo casa aqui se e só
        # se casaria lá.
        encontradas: list[VagaResumo] = [
            vaga
            for vaga in (await self._todas()).values()
            if procurado in texto_da_vaga(vaga)
        ]
        return encontradas

    async def detalhar(self, resumo: VagaResumo) -> Vaga:
        # A listagem já traz a vaga inteira: nenhuma chamada a mais.
        return (await self._todas())[resumo.id_externo]

    async def _todas(self) -> dict[str, Vaga]:
        if self._vagas is None:
            dados = await asyncio.to_thread(self._ler_cache)
            if dados is None:
                dados = await self._baixar()
                await asyncio.to_thread(self._gravar_cache, dados)
            self._vagas = {}
            for item in dados.get("jobs", []):
                vaga = _vaga(item)
                self._vagas[vaga.id_externo] = vaga
        return self._vagas

    async def _baixar(self) -> dict[str, Any]:
        if self._cliente is None:
            raise RuntimeError("Use a fonte dentro de `async with`.")
        try:
            resposta = await self._cliente.get(URL, params={"category": self.categoria})
            resposta.raise_for_status()
            dados: dict[str, Any] = resposta.json()
        except httpx.HTTPStatusError as falha:
            codigo = falha.response.status_code
            if codigo == 429:
                raise ErroDeColeta(
                    "Remotive recusou por excesso de chamadas (o limite é ~4 por dia). "
                    "Tente de novo mais tarde."
                ) from falha
            raise ErroDeColeta(f"Remotive respondeu com erro {codigo}.") from falha
        except (httpx.HTTPError, ValueError) as falha:
            raise ErroDeColeta(f"Remotive fora do ar ou sem rede: {falha}") from falha
        return dados

    def _ler_cache(self) -> dict[str, Any] | None:
        if not self.cache.exists():
            return None
        if time.time() - self.cache.stat().st_mtime > VALIDADE_DO_CACHE_S:
            return None
        dados = json.loads(self.cache.read_text(encoding="utf-8"))
        # Cache de outra categoria não serve.
        return dados if dados.get("categoria") == self.categoria else None

    def _gravar_cache(self, dados: dict[str, Any]) -> None:
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache.write_text(
            json.dumps({**dados, "categoria": self.categoria}, ensure_ascii=False),
            encoding="utf-8",
        )


def _vaga(item: dict[str, Any]) -> Vaga:
    return Vaga(
        fonte=Remotive.nome,
        id_externo=str(item["id"]),
        url=item["url"],
        titulo=item["title"],
        empresa=item.get("company_name") or None,
        local=item.get("candidate_required_location") or None,
        modalidade="Remote",
        salario=item.get("salary") or None,  # vem "" quando a empresa não informa
        skills=list(item.get("tags") or []),
        publicada_em=item.get("publication_date"),
        descricao=html_para_texto(item.get("description") or ""),
        extras={
            "via": "Remotive",
            "categoria": item.get("category"),
            "tipo": item.get("job_type"),
        },
    )
