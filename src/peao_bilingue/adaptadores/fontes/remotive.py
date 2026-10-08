"""Remotive: API pública de vagas remotas (https://remotive.com/api/remote-jobs).

Termos (aviso legal na própria resposta e github.com/remotive-io/remote-jobs-api):
linkar a vaga no Remotive e citar o Remotive como fonte; no máximo ~4 chamadas por
dia (mais de 2 por minuto são bloqueadas); dados com 24 h de atraso; não republicar
as vagas em outros sites. A base (`FonteDeApi`) faz uma chamada por coleta com cache
de 6 h, o que mantém o uso abaixo de 4 por dia.
"""

from pathlib import Path
from typing import Any

import httpx

from peao_bilingue.adaptadores.fontes.api import FonteDeApi, Json
from peao_bilingue.adaptadores.fontes.html import html_para_texto
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import Vaga
from peao_bilingue.dominio.erros import ErroDeColeta
from peao_bilingue.fabricas import fontes

URL = "https://remotive.com/api/remote-jobs"


@fontes.registrar("remotive")
class Remotive(FonteDeApi):
    nome = "remotive"
    rotulo = "Remotive (API pública, vagas remotas)"
    marca = "Remotive"
    url = URL

    def __init__(
        self,
        *,
        categoria: str | None = None,
        cliente: httpx.AsyncClient | None = None,
        cache: Path | None = None,
    ) -> None:
        super().__init__(cliente=cliente, cache=cache)
        self.categoria = categoria or settings.remotive_categoria

    def parametros(self) -> dict[str, str]:
        return {"category": self.categoria}

    def converter(self, dados: Json) -> list[Vaga]:
        if not isinstance(dados, dict):
            raise ErroDeColeta(
                "Remotive mudou o formato da resposta (esperava um objeto)."
            )
        return [_vaga(item) for item in dados.get("jobs", [])]


def _vaga(item: dict[str, Any]) -> Vaga:
    return Vaga(
        fonte=Remotive.nome,
        id_externo=str(item["id"]),
        url=item["url"],  # o link volta ao Remotive, como os termos pedem
        titulo=item["title"],
        empresa=item.get("company_name") or None,
        local=item.get("candidate_required_location") or None,
        modalidade="Remote",
        salario=item.get("salary") or None,  # vem "" quando a empresa não informa
        skills=list(item.get("tags") or []),
        publicada_em=item.get("publication_date"),
        descricao=html_para_texto(item.get("description") or ""),
        extras={
            "via": Remotive.marca,
            "categoria": item.get("category"),
            "tipo": item.get("job_type"),
        },
    )
