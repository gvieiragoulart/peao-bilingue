"""Raiz de composição: o único lugar que liga as portas aos adapters concretos.

CLI e interface montam os serviços por aqui; a camada de aplicação nunca
importa um adapter diretamente.
"""

from peao_bilingue import fabricas
from peao_bilingue.adaptadores.persistencia.sqlite import RepositorioSQLite
from peao_bilingue.aplicacao.execucao import Servicos
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.portas import RepositorioVagas


def montar_servicos(
    *,
    fontes: list[str] | None = None,
    llm: str | None = None,
    triagem: str | None = None,
    analisar: bool = True,
    repositorio: RepositorioVagas | None = None,
) -> Servicos:
    nome_triagem = triagem or settings.llm_triagem
    return Servicos(
        repositorio=repositorio or RepositorioSQLite(),
        fontes=[
            fabricas.fontes.criar(nome)
            for nome in fontes or settings.fontes_habilitadas
        ],
        # Sem análise não se cria o provedor: dispensa chave de API na coleta pura.
        analise=fabricas.llms.criar(llm or settings.llm_analise) if analisar else None,
        notificadores=[
            fabricas.notificadores.criar(nome) for nome in settings.notificadores
        ],
        triagem=fabricas.llms.criar(nome_triagem)
        if analisar and nome_triagem
        else None,
    )
