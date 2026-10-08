"""Base das fontes que leem uma API pública JSON (Remotive, RemoteOK...).

Os termos dessas APIs pedem poucas chamadas, então:

- **uma chamada por coleta** quando a API devolve a lista inteira: cada termo é
  filtrado aqui, com o mesmo texto que o filtro das buscas olha;
- **uma chamada por termo** quando a API só busca (ex.: Himalayas, 20 por página):
  a fonte define `parametros_do_termo`, e há pausa entre as chamadas;
- **algumas chamadas fixas** quando a lista vem em partes (ex.: um feed RSS por
  categoria no We Work Remotely): a fonte define `consultas`;
- **cache em disco** por consulta (`validade_s`): coletar várias vezes no dia não
  chama de novo;
- `detalhar` não chama nada: a listagem já traz a vaga inteira.

Cada fonte só diz a URL, os parâmetros e como uma resposta vira vagas.
"""

import asyncio
import hashlib
import json
import time
from abc import abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Self

import httpx

from peao_bilingue.configuracao import DIRETORIO_DADOS
from peao_bilingue.dominio.coleta import FonteDeVagas
from peao_bilingue.dominio.erros import ErroDeColeta
from peao_bilingue.dominio.vagas import Vaga, VagaResumo

# O que um JSON de API devolve no topo; o conteúdo cada fonte confere.
Json = dict[str, Any] | list[Any]

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
    # Pausa entre duas chamadas de verdade na mesma coleta (cache não conta).
    pausa_s: ClassVar[float] = 0.0

    def __init__(
        self, *, cliente: httpx.AsyncClient | None = None, cache: Path | None = None
    ) -> None:
        self.cache = cache or DIRETORIO_DADOS / "cache" / f"{self.nome}.json"
        self._cliente_externo = cliente
        self._cliente: httpx.AsyncClient | None = None
        self._vistas: dict[str, Vaga] = {}
        self._todas: dict[str, Vaga] | None = None
        self._ja_chamou = False

    def parametros(self) -> dict[str, str]:
        """A consulta única, quando a API devolve a lista inteira."""
        return {}

    def parametros_do_termo(self, termo: str) -> dict[str, str] | None:
        """A consulta de um termo, quando a API só busca. None = consulta única."""
        return None

    def consultas(self) -> list[tuple[str, dict[str, str]]]:
        """(url, parâmetros) de cada chamada que monta a lista inteira."""
        return [(self.url, self.parametros())]

    def decodificar(self, resposta: httpx.Response) -> Json:
        """O corpo da resposta como Json; fontes que não falam JSON (RSS) trocam."""
        dados = resposta.json()
        if not isinstance(dados, dict | list):
            raise ValueError("o topo da resposta não é objeto nem lista")
        return dados

    @abstractmethod
    def converter(self, dados: Json) -> list[Vaga]:
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
        do_termo = self.parametros_do_termo(termo)
        if do_termo is not None:
            # A própria API já buscou o termo.
            encontradas: list[VagaResumo] = list(
                (await self._consultar(self.url, do_termo)).values()
            )
            return encontradas
        if self._todas is None:
            self._todas = {}
            for url, parametros in self.consultas():
                self._todas.update(await self._consultar(url, parametros))
        procurado = termo.lower()
        return [
            vaga
            for vaga in self._todas.values()
            if procurado in vaga.texto_pesquisavel()
        ]

    async def detalhar(self, resumo: VagaResumo) -> Vaga:
        return self._vistas[resumo.id_externo]

    async def _consultar(self, url: str, parametros: dict[str, str]) -> dict[str, Vaga]:
        consulta = {"url": url, "parametros": parametros}
        arquivo = self._arquivo_do_cache(url, parametros)
        dados = await asyncio.to_thread(self._ler_cache, arquivo, consulta)
        if dados is None:
            dados = await self._baixar(url, parametros)
            await asyncio.to_thread(self._gravar_cache, arquivo, consulta, dados)
        vagas = {vaga.id_externo: vaga for vaga in self.converter(dados)}
        self._vistas.update(vagas)
        return vagas

    def _arquivo_do_cache(self, url: str, parametros: dict[str, str]) -> Path:
        if (url, parametros) == self.consultas()[0]:
            return self.cache
        # As outras consultas (por termo ou por parte): um arquivo para cada.
        chave = hashlib.sha1(
            json.dumps([url, parametros], sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        return self.cache.with_name(f"{self.cache.stem}-{chave}{self.cache.suffix}")

    async def _baixar(self, url: str, parametros: dict[str, str]) -> Json:
        if self._cliente is None:
            raise RuntimeError("Use a fonte dentro de `async with`.")
        if self._ja_chamou and self.pausa_s:
            await asyncio.sleep(self.pausa_s)
        self._ja_chamou = True
        try:
            resposta = await self._cliente.get(url, params=parametros)
            resposta.raise_for_status()
            dados = self.decodificar(resposta)
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
        if not isinstance(dados, dict | list):
            raise ErroDeColeta(f"{self.marca} respondeu num formato inesperado.")
        return dados

    def _ler_cache(self, arquivo: Path, consulta: dict[str, Any]) -> Json | None:
        if not arquivo.exists():
            return None
        if time.time() - arquivo.stat().st_mtime > self.validade_s:
            return None
        salvo = json.loads(arquivo.read_text(encoding="utf-8"))
        # Cache de outra consulta (ex.: outra categoria) não serve.
        if salvo.get("consulta") != consulta:
            return None
        dados = salvo.get("dados")
        return dados if isinstance(dados, dict | list) else None

    def _gravar_cache(
        self, arquivo: Path, consulta: dict[str, Any], dados: Json
    ) -> None:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(
            json.dumps({"consulta": consulta, "dados": dados}, ensure_ascii=False),
            encoding="utf-8",
        )
