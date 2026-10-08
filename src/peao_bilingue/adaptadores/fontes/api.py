"""Base das fontes que leem uma API pública JSON (Remotive, RemoteOK...).

Os termos dessas APIs pedem poucas chamadas, então:

- **uma chamada por coleta**: a lista vem inteira e cada termo é filtrado aqui,
  com o mesmo texto que o filtro das buscas olha;
- **cache em disco** (`validade_s`): coletar várias vezes no dia não chama de novo;
- `detalhar` não chama nada: a listagem já traz a vaga inteira.

Cada fonte só diz a URL, os parâmetros e como uma resposta vira vagas.
"""

import asyncio
import json
import time
from abc import abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Self

import httpx

from peao_bilingue.aplicacao.filtros import texto_da_vaga
from peao_bilingue.configuracao import DIRETORIO_DADOS
from peao_bilingue.dominio.entidades import Vaga, VagaResumo
from peao_bilingue.dominio.erros import ErroDeColeta
from peao_bilingue.dominio.portas import FonteDeVagas

AGENTE = "peao-bilingue/0.1 (radar pessoal de vagas)"
TIMEOUT_S = 30


def consertar_codificacao(texto: str) -> str:
    """Desfaz UTF-8 lido como Latin-1 ("â€“" no lugar de "–"), que algumas APIs
    mandam. Texto que não tem esse defeito volta igual."""
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


class FonteDeApi(FonteDeVagas):
    url: ClassVar[str]
    marca: ClassVar[str]  # como a fonte pede para ser citada ("Remote OK")
    validade_s: ClassVar[int] = 6 * 3600

    def __init__(
        self, *, cliente: httpx.AsyncClient | None = None, cache: Path | None = None
    ) -> None:
        self.cache = cache or DIRETORIO_DADOS / "cache" / f"{self.nome}.json"
        self._cliente_externo = cliente
        self._cliente: httpx.AsyncClient | None = None
        self._vagas: dict[str, Vaga] | None = None

    def parametros(self) -> dict[str, str]:
        return {}

    @abstractmethod
    def converter(self, dados: Any) -> list[Vaga]:
        """A resposta da API (já do JSON) vira vagas."""

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
        encontradas: list[VagaResumo] = [
            vaga
            for vaga in (await self._todas()).values()
            if procurado in texto_da_vaga(vaga)
        ]
        return encontradas

    async def detalhar(self, resumo: VagaResumo) -> Vaga:
        return (await self._todas())[resumo.id_externo]

    async def _todas(self) -> dict[str, Vaga]:
        if self._vagas is None:
            dados = await asyncio.to_thread(self._ler_cache)
            if dados is None:
                dados = await self._baixar()
                await asyncio.to_thread(self._gravar_cache, dados)
            self._vagas = {vaga.id_externo: vaga for vaga in self.converter(dados)}
        return self._vagas

    async def _baixar(self) -> Any:
        if self._cliente is None:
            raise RuntimeError("Use a fonte dentro de `async with`.")
        try:
            resposta = await self._cliente.get(self.url, params=self.parametros())
            resposta.raise_for_status()
            return resposta.json()
        except httpx.HTTPStatusError as falha:
            codigo = falha.response.status_code
            if codigo == 429:
                raise ErroDeColeta(
                    f"{self.marca} recusou por excesso de chamadas. Tente mais tarde."
                ) from falha
            raise ErroDeColeta(f"{self.marca} respondeu com erro {codigo}.") from falha
        except (httpx.HTTPError, ValueError) as falha:
            raise ErroDeColeta(
                f"{self.marca} fora do ar ou sem rede: {falha}"
            ) from falha

    def _consulta(self) -> dict[str, Any]:
        return {"url": self.url, "parametros": self.parametros()}

    def _ler_cache(self) -> Any:
        if not self.cache.exists():
            return None
        if time.time() - self.cache.stat().st_mtime > self.validade_s:
            return None
        salvo = json.loads(self.cache.read_text(encoding="utf-8"))
        # Cache de outra consulta (ex.: outra categoria) não serve.
        if salvo.get("consulta") != self._consulta():
            return None
        return salvo.get("dados")

    def _gravar_cache(self, dados: Any) -> None:
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache.write_text(
            json.dumps(
                {"consulta": self._consulta(), "dados": dados}, ensure_ascii=False
            ),
            encoding="utf-8",
        )
