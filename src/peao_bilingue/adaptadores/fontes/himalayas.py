"""Himalayas: API pública de vagas remotas (https://himalayas.app/jobs/api/search).

Termos (https://himalayas.app/api): linkar a vaga no Himalayas **e** citar o Himalayas
como fonte; não republicar as vagas em outros sites; abuso devolve 429. No máximo 20
vagas por chamada e os dados mudam a cada 24 h.

Por isso a busca é **por termo** (a lista inteira passa de 5.000 vagas): uma chamada
para cada termo das buscas, com pausa entre elas e cache de 12 h. Só vagas abertas a
candidatos de `HIMALAYAS_PAIS` (padrão BR) ou ao mundo todo: sem o filtro, a maioria
é só para os EUA (3 de 18 serviam, em 07/10).
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from peao_bilingue.adaptadores.fontes.api import FonteDeApi, Json
from peao_bilingue.adaptadores.fontes.html import html_para_texto
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.erros import ErroDeColeta
from peao_bilingue.dominio.vagas import Vaga
from peao_bilingue.fabricas import fontes

URL = "https://himalayas.app/jobs/api/search"
# Até aqui a lista de países vira o "local"; mais que isso, só a contagem.
PAISES_NO_LOCAL = 3
PERIODOS = {"annual": "/ano", "monthly": "/mês", "weekly": "/semana", "hourly": "/hora"}


@fontes.registrar("himalayas")
class Himalayas(FonteDeApi):
    nome = "himalayas"
    rotulo = "Himalayas (API pública, vagas remotas)"
    marca = "Himalayas"
    url = URL
    validade_s = 12 * 3600
    pausa_s = 2.0

    def __init__(
        self,
        *,
        pais: str | None = None,
        cliente: httpx.AsyncClient | None = None,
        cache: Path | None = None,
    ) -> None:
        super().__init__(cliente=cliente, cache=cache)
        self.pais = settings.himalayas_pais if pais is None else pais

    def parametros_do_termo(self, termo: str) -> dict[str, str]:
        parametros = {"q": termo, "sort": "recent"}
        if self.pais:
            parametros["country"] = self.pais
        return parametros

    def converter(self, dados: Json) -> list[Vaga]:
        if not isinstance(dados, dict):
            raise ErroDeColeta(
                "Himalayas mudou o formato da resposta (esperava um objeto)."
            )
        return [_vaga(item) for item in dados.get("jobs", [])]


def _id(item: dict[str, Any]) -> str:
    # O slug da vaga sozinho se repete entre empresas ("software-engineer-backend").
    return (
        f"{item.get('companySlug') or 'sem-empresa'}/{item['guid'].rsplit('/', 1)[-1]}"
    )


def _local(paises: list[str]) -> str:
    if not paises:
        return "Worldwide"
    if len(paises) <= PAISES_NO_LOCAL:
        return ", ".join(paises)
    com_brasil = ", inclui Brazil" if "Brazil" in paises else ""
    return f"{len(paises)} países{com_brasil}"


def _salario(item: dict[str, Any]) -> str | None:
    valores = [v for v in (item.get("minSalary"), item.get("maxSalary")) if v]
    if not valores:
        return None
    faixa = (
        f"{valores[0]:,}"
        if len(set(valores)) == 1
        else f"{valores[0]:,} - {valores[1]:,}"
    )
    moeda = item.get("currency") or ""
    periodo = PERIODOS.get(item.get("salaryPeriod") or "", "")
    return " ".join(parte for parte in (moeda, faixa, periodo) if parte)


def _publicada_em(epoch: object) -> str | None:
    if not isinstance(epoch, int | float):
        return None
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


def _vaga(item: dict[str, Any]) -> Vaga:
    paises = list(item.get("locationRestrictions") or [])
    return Vaga(
        fonte=Himalayas.nome,
        id_externo=_id(item),
        url=item["guid"],  # a página da vaga no Himalayas, como os termos pedem
        titulo=item["title"],
        empresa=item.get("companyName") or None,
        local=_local(paises),
        modalidade="Remote",
        salario=_salario(item),
        skills=list(item.get("categories") or []),
        publicada_em=_publicada_em(item.get("pubDate")),
        descricao=html_para_texto(item.get("description") or ""),
        extras={
            "via": Himalayas.marca,
            "paises": paises,
            "senioridade": list(item.get("seniority") or []),
            "tipo": item.get("employmentType"),
        },
    )
