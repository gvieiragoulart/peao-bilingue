"""Remote OK: API pública de vagas remotas (https://remoteok.com/api).

Termos (primeiro item da própria resposta): linkar a vaga no Remote OK, sem
`nofollow`, e citar "Remote OK" como fonte; não usar o logo. A resposta traz as ~100
vagas mais recentes de todas as áreas, com a descrição **resumida** (o texto inteiro
só no site, que não é raspado). A base (`FonteDeApi`) faz uma chamada por coleta.

A descrição termina com uma frase anti-spam ("Please mention the word ... and tag
R...") cujo token é o **IP de quem fez a chamada** em base64. Ela sai antes de a vaga
ser guardada: não vai para o banco, para o prompt do LLM nem para os testes.
"""

import re
from typing import Any

from peao_bilingue.adaptadores.fontes.api import FonteDeApi, Json, consertar_codificacao
from peao_bilingue.adaptadores.fontes.html import html_para_texto
from peao_bilingue.dominio.entidades import Vaga
from peao_bilingue.dominio.erros import ErroDeColeta
from peao_bilingue.fabricas import fontes

URL = "https://remoteok.com/api"

FRASE_DE_RASTREIO = re.compile(
    r"Please mention the word.*?(?:see they're human\.|$)", re.DOTALL
)
# Rede de segurança caso a frase mude de texto: o token sozinho também sai.
TOKEN_DE_RASTREIO = re.compile(r"(?:tag |\(#)R[A-Za-z0-9+/=]{16,}\)?")
# Algumas descrições trazem <img> escapado (vira texto) com a imagem em base64,
# às vezes cortado pelo resumo da API: lixo na tela e no prompt.
IMAGEM_EM_TEXTO = re.compile(r"<img\b[^>]*>?")


@fontes.registrar("remoteok")
class RemoteOK(FonteDeApi):
    nome = "remoteok"
    rotulo = "Remote OK (API pública, vagas remotas)"
    marca = "Remote OK"
    url = URL

    def converter(self, dados: Json) -> list[Vaga]:
        if not isinstance(dados, list):
            raise ErroDeColeta(
                "Remote OK mudou o formato da resposta (esperava uma lista)."
            )
        # O primeiro item é o aviso legal, sem vaga.
        return [
            _vaga(item) for item in dados if isinstance(item, dict) and item.get("id")
        ]


def limpar_descricao(html: str) -> str:
    texto = html_para_texto(consertar_codificacao(html))
    texto = FRASE_DE_RASTREIO.sub("", texto)
    texto = TOKEN_DE_RASTREIO.sub("", texto)
    return IMAGEM_EM_TEXTO.sub("", texto).strip()


def _salario(minimo: int | None, maximo: int | None) -> str | None:
    valores = [f"${valor:,}" for valor in (minimo, maximo) if valor]
    return " - ".join(valores) + " /ano" if valores else None


def _texto(item: dict[str, Any], campo: str) -> str | None:
    valor = item.get(campo)
    return (
        consertar_codificacao(valor).strip() or None if isinstance(valor, str) else None
    )


def _vaga(item: dict[str, Any]) -> Vaga:
    return Vaga(
        fonte=RemoteOK.nome,
        id_externo=str(item["id"]),
        # O link do Remote OK, não o `apply_url`: os termos pedem tráfego para eles.
        url=item["url"],
        titulo=_texto(item, "position") or "(sem título)",
        empresa=_texto(item, "company"),
        local=_texto(item, "location"),
        modalidade="Remote",
        salario=_salario(item.get("salary_min"), item.get("salary_max")),
        skills=[consertar_codificacao(tag) for tag in item.get("tags") or []],
        publicada_em=item.get("date"),
        descricao=limpar_descricao(item.get("description") or ""),
        extras={"via": RemoteOK.marca},
    )
