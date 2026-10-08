"""We Work Remotely: feeds RSS públicos (https://weworkremotely.com/remote-job-rss-feed).

Termos (página do feed): "Anyone can use the feed, all we ask is that you attribute
the links back to We Work Remotely." Cada vaga guarda o link dela no WWR.

O feed geral traz só as ~90 vagas mais recentes de todas as áreas — em 08/10 faltavam
nele 38 das 57 de programação. Por isso são os três feeds de programação (back-end,
full-stack, front-end): três chamadas por coleta, com pausa e cache (a base).
"""

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from peao_bilingue.adaptadores.fontes.api import FonteDeApi, Json
from peao_bilingue.adaptadores.fontes.html import html_para_texto
from peao_bilingue.dominio.erros import ErroDeColeta
from peao_bilingue.dominio.vagas import Vaga
from peao_bilingue.fabricas import fontes

URL_BASE = "https://weworkremotely.com/categories/"
CATEGORIAS = (
    "remote-back-end-programming-jobs",
    "remote-full-stack-programming-jobs",
    "remote-front-end-programming-jobs",
)


@fontes.registrar("weworkremotely")
class WeWorkRemotely(FonteDeApi):
    nome = "weworkremotely"
    rotulo = "We Work Remotely (RSS público, vagas remotas)"
    marca = "We Work Remotely"
    url = f"{URL_BASE}{CATEGORIAS[0]}.rss"
    pausa_s = 2.0

    def consultas(self) -> list[tuple[str, dict[str, str]]]:
        return [(f"{URL_BASE}{categoria}.rss", {}) for categoria in CATEGORIAS]

    def decodificar(self, resposta: httpx.Response) -> Json:
        # O expat do Python já se defende de expansão de entidades (billion laughs).
        try:
            raiz = ET.fromstring(resposta.content)
        except ET.ParseError as falha:
            raise ValueError(f"RSS inválido: {falha}") from falha
        return [_item(no) for no in raiz.findall("./channel/item")]

    def converter(self, dados: Json) -> list[Vaga]:
        if not isinstance(dados, list):
            raise ErroDeColeta("We Work Remotely: feed num formato inesperado.")
        return [
            _vaga(item) for item in dados if isinstance(item, dict) and item.get("link")
        ]


def _item(no: ET.Element) -> dict[str, str]:
    # "{http://search.yahoo.com/mrss}content" -> "content"
    return {filho.tag.rsplit("}", 1)[-1]: (filho.text or "").strip() for filho in no}


def _empresa_e_titulo(titulo: str) -> tuple[str | None, str]:
    # O feed manda "Empresa: Cargo".
    if ": " in titulo:
        empresa, cargo = titulo.split(": ", 1)
        return empresa.strip() or None, cargo.strip()
    return None, titulo


def _skills(texto: str) -> list[str]:
    # "Java, PostgreSQL, and Spring" -> ["Java", "PostgreSQL", "Spring"]
    partes = texto.replace(" and ", ", ").split(",")
    return [parte.strip() for parte in partes if parte.strip()]


def _publicada_em(data: str) -> str | None:
    try:
        return parsedate_to_datetime(data).isoformat() if data else None
    except (TypeError, ValueError):
        return None


def _vaga(item: dict[str, Any]) -> Vaga:
    empresa, titulo = _empresa_e_titulo(item.get("title") or "")
    link = item["link"]
    return Vaga(
        fonte=WeWorkRemotely.nome,
        id_externo=link.rstrip("/").rsplit("/", 1)[-1],
        url=link,  # a vaga no WWR: é a atribuição que eles pedem
        titulo=titulo or "(sem título)",
        empresa=empresa,
        local=item.get("region") or None,
        modalidade="Remote",
        skills=_skills(item.get("skills") or ""),
        publicada_em=_publicada_em(item.get("pubDate") or ""),
        descricao=html_para_texto(item.get("description") or ""),
        extras={
            "via": WeWorkRemotely.marca,
            "categoria": item.get("category"),
            "tipo": item.get("type"),
            "paises": item.get("country"),
        },
    )
