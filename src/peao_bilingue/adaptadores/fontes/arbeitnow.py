"""Arbeitnow: API pública de vagas na Alemanha (https://www.arbeitnow.com/api/job-board-api).

Termos (`meta.terms` da própria resposta e a seção 11 dos termos do site): API
gratuita, "não abuse"; linkar de volta para o Arbeitnow; o acesso pode ser revogado.
Limite de 50 chamadas (cabeçalho `X-RateLimit-Limit`). A base (`FonteDeApi`) faz uma
chamada por coleta, com cache.

Só as vagas **com patrocínio de visto** (`visa_sponsorship=true`): é o caminho de
relocação, como na VanHack — a lista padrão é de vagas locais, muitas em alemão. Em
07/10 vieram 312 vagas numa página só. O filtro `remote=true` é ignorado pela API.
"""

import re
from datetime import UTC, datetime
from typing import Any

from peao_bilingue.adaptadores.fontes.api import FonteDeApi, Json
from peao_bilingue.adaptadores.fontes.html import html_para_texto
from peao_bilingue.dominio.erros import ErroDeColeta
from peao_bilingue.dominio.vagas import Vaga
from peao_bilingue.fabricas import fontes

URL = "https://www.arbeitnow.com/api/job-board-api"


@fontes.registrar("arbeitnow")
class Arbeitnow(FonteDeApi):
    nome = "arbeitnow"
    rotulo = "Arbeitnow (API pública, Alemanha com visto)"
    marca = "Arbeitnow"
    url = URL

    def parametros(self) -> dict[str, str]:
        return {"visa_sponsorship": "true"}

    def converter(self, dados: Json) -> list[Vaga]:
        if not isinstance(dados, dict):
            raise ErroDeColeta(
                "Arbeitnow mudou o formato da resposta (esperava um objeto)."
            )
        return [_vaga(item) for item in dados.get("data", [])]


# Tag de fechamento que sobrou no texto: sinal de HTML que veio escapado.
TAG_QUE_SOBROU = re.compile(
    r"</(?:p|div|li|ul|ol|strong|em|b|i|span|h[1-6]|table|tr|td)>", re.IGNORECASE
)


def descricao_em_texto(descricao: str) -> str:
    """A API manda o HTML escapado (&lt;p&gt;...), às vezes só em parte: a primeira
    conversão devolve marcação como texto, e uma segunda a desfaz. Texto que só cita
    "<br>" (sem tag de fechamento) fica como está."""
    texto = html_para_texto(descricao)
    if TAG_QUE_SOBROU.search(texto):
        texto = html_para_texto(texto)
    return texto


def _publicada_em(epoch: object) -> str | None:
    if not isinstance(epoch, int | float):
        return None
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


def _vaga(item: dict[str, Any]) -> Vaga:
    return Vaga(
        fonte=Arbeitnow.nome,
        id_externo=item["slug"],
        url=item["url"],  # o link volta ao Arbeitnow, como os termos pedem
        titulo=item["title"],
        empresa=item.get("company_name") or None,
        local=item.get("location") or None,
        modalidade="Remote" if item.get("remote") else "On-site",
        skills=list(item.get("tags") or []),
        publicada_em=_publicada_em(item.get("created_at")),
        descricao=descricao_em_texto(item.get("description") or ""),
        extras={
            "via": Arbeitnow.marca,
            "visto": True,  # só vêm vagas com patrocínio de visto
            "tipos": list(item.get("job_types") or []),
        },
    )
