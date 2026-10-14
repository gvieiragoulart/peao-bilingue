"""Tabelas do SQLite (SQLModel). Só aqui o domínio vira linha; nada de SQL fora."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.coleta import Gatilho, StatusExecucao
from peao_bilingue.dominio.vagas import StatusVaga


def agora() -> datetime:
    return datetime.now(tz=ZoneInfo(settings.timezone))


class BuscaTabela(SQLModel, table=True):
    __tablename__ = "busca"

    id: int | None = Field(default=None, primary_key=True)
    nome: str
    keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    exclude: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    fontes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    ativa: bool = True
    criada_em: datetime = Field(default_factory=agora)


class VagaTabela(SQLModel, table=True):
    __tablename__ = "vaga"

    # "fonte:id_externo": ids de sites diferentes colidem.
    chave: str = Field(primary_key=True)
    fonte: str = Field(index=True)
    # A vaga inteira em JSON: cada fonte traz campos próprios em `extras`.
    dados: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    buscas: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: StatusVaga = StatusVaga.nova
    vista_em: datetime = Field(default_factory=agora)
    # `Vaga.assinatura()`; None = ainda não calculada (linha de antes da coluna).
    assinatura: str | None = None
    # Chave da mesma vaga já guardada por outra fonte: esta não aparece na lista.
    repete: str | None = None


class PerfilTabela(SQLModel, table=True):
    __tablename__ = "perfil"

    id: int | None = Field(default=None, primary_key=True)
    # O padrão só vale para a migração: antes do perfil por fonte, todos os
    # snapshots vinham da VanHack. Os novos sempre gravam a fonte.
    fonte: str = "vanhack"
    dados: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    texto: str = ""
    content_hash: str = Field(index=True)
    lido_em: datetime = Field(default_factory=agora)


class AnaliseTabela(SQLModel, table=True):
    __tablename__ = "analise"

    id: int | None = Field(default=None, primary_key=True)
    vaga_chave: str = Field(foreign_key="vaga.chave", index=True)
    dados: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    provedor: str
    modelo: str
    perfil_id: int | None = Field(default=None, foreign_key="perfil.id")
    criada_em: datetime = Field(default_factory=agora)


class ExecucaoTabela(SQLModel, table=True):
    __tablename__ = "execucao"

    id: int | None = Field(default=None, primary_key=True)
    gatilho: Gatilho = Gatilho.manual
    status: StatusExecucao = StatusExecucao.rodando
    iniciada_em: datetime = Field(default_factory=agora)
    finalizada_em: datetime | None = None
    vagas_listadas: int = 0
    vagas_novas: int = 0
    # Sem uso desde que a análise saiu da coleta. Ficam no model porque os bancos
    # criados antes têm essas colunas NOT NULL sem default: sem elas, o INSERT falha.
    vagas_analisadas: int = 0
    perfil_mudou: bool = False
    erro: str | None = None
    artefato: str | None = None
