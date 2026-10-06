from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import JSON, Column, Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select

from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import (
    AnaliseSalva,
    Busca,
    Execucao,
    Gatilho,
    JobAnalysis,
    Perfil,
    StatusExecucao,
    StatusVaga,
    Vaga,
    VagaListada,
)
from peao_bilingue.dominio.portas import RepositorioVagas

DB_PATH = Path("data/peao.db")


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
    dados: dict = Field(default_factory=dict, sa_column=Column(JSON))
    buscas: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: StatusVaga = StatusVaga.nova
    vista_em: datetime = Field(default_factory=agora)


class PerfilTabela(SQLModel, table=True):
    __tablename__ = "perfil"

    id: int | None = Field(default=None, primary_key=True)
    dados: dict = Field(default_factory=dict, sa_column=Column(JSON))
    texto: str = ""
    content_hash: str = Field(index=True)
    lido_em: datetime = Field(default_factory=agora)


class AnaliseTabela(SQLModel, table=True):
    __tablename__ = "analise"

    id: int | None = Field(default=None, primary_key=True)
    vaga_chave: str = Field(foreign_key="vaga.chave", index=True)
    dados: dict = Field(default_factory=dict, sa_column=Column(JSON))
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
    vagas_analisadas: int = 0
    perfil_mudou: bool = False
    erro: str | None = None
    artefato: str | None = None


def engine_padrao() -> Engine:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # A interface e o worker assíncrono usam o banco de threads diferentes.
    return create_engine(
        f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
    )


def _diferencas(antes: dict, depois: dict) -> list[str]:
    chaves = set(antes) | set(depois)
    return sorted(chave for chave in chaves if antes.get(chave) != depois.get(chave))


class RepositorioSQLite(RepositorioVagas):
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or engine_padrao()
        SQLModel.metadata.create_all(self._engine)

    def _sessao(self) -> Session:
        return Session(self._engine)

    # buscas -----------------------------------------------------------------

    def listar_buscas(self, *, so_ativas: bool = False) -> list[Busca]:
        consulta = select(BuscaTabela).order_by(BuscaTabela.id)
        if so_ativas:
            consulta = consulta.where(BuscaTabela.ativa)
        with self._sessao() as sessao:
            return [
                Busca.model_validate(linha, from_attributes=True)
                for linha in sessao.exec(consulta)
            ]

    def salvar_busca(self, busca: Busca) -> Busca:
        with self._sessao() as sessao:
            linha = sessao.get(BuscaTabela, busca.id) if busca.id else None
            linha = linha or BuscaTabela(nome=busca.nome)
            for campo, valor in busca.model_dump(exclude={"id"}).items():
                setattr(linha, campo, valor)
            sessao.add(linha)
            sessao.commit()
            sessao.refresh(linha)
            return Busca.model_validate(linha, from_attributes=True)

    def remover_busca(self, busca_id: int) -> None:
        with self._sessao() as sessao:
            linha = sessao.get(BuscaTabela, busca_id)
            if linha is None:
                raise LookupError(f"Busca {busca_id} não encontrada.")
            sessao.delete(linha)
            sessao.commit()

    # vagas ------------------------------------------------------------------

    def vaga_existe(self, chave: str) -> bool:
        with self._sessao() as sessao:
            return sessao.get(VagaTabela, chave) is not None

    def salvar_vaga(self, vaga: Vaga, buscas: list[str]) -> None:
        with self._sessao() as sessao:
            linha = sessao.get(VagaTabela, vaga.chave) or VagaTabela(
                chave=vaga.chave, fonte=vaga.fonte
            )
            linha.dados = vaga.model_dump(mode="json")
            linha.buscas = sorted(set(linha.buscas or []) | set(buscas))
            sessao.add(linha)
            sessao.commit()

    def obter_vaga(self, chave: str) -> Vaga | None:
        with self._sessao() as sessao:
            linha = sessao.get(VagaTabela, chave)
            return Vaga.model_validate(linha.dados) if linha else None

    def listar_vagas(
        self,
        *,
        status: StatusVaga | None = None,
        min_score: int | None = None,
        busca: str | None = None,
        fonte: str | None = None,
        limite: int = 50,
        offset: int = 0,
    ) -> list[VagaListada]:
        consulta = select(VagaTabela).order_by(VagaTabela.vista_em.desc())
        if status is not None:
            consulta = consulta.where(VagaTabela.status == status)
        if fonte is not None:
            consulta = consulta.where(VagaTabela.fonte == fonte)

        vagas = []
        with self._sessao() as sessao:
            for linha in sessao.exec(consulta):
                if busca and busca not in (linha.buscas or []):
                    continue
                vigente = self._analise_vigente(sessao, linha.chave)
                fit = vigente.analise.fit_score if vigente else None
                if min_score is not None and (fit is None or fit < min_score):
                    continue
                vagas.append(
                    VagaListada(
                        vaga=Vaga.model_validate(linha.dados),
                        status=linha.status,
                        fit_score=fit,
                        buscas=linha.buscas or [],
                        vista_em=linha.vista_em,
                    )
                )
        return vagas[offset : offset + limite]

    def mudar_status(self, chave: str, status: StatusVaga) -> None:
        with self._sessao() as sessao:
            linha = sessao.get(VagaTabela, chave)
            if linha is None:
                raise LookupError(f"Vaga {chave} não encontrada.")
            linha.status = status
            sessao.add(linha)
            sessao.commit()

    def vagas_para_reanalisar(self, limite: int) -> list[Vaga]:
        consulta = (
            select(VagaTabela)
            .where(VagaTabela.status.in_([StatusVaga.nova, StatusVaga.estudando]))
            .order_by(VagaTabela.vista_em.desc())
            .limit(limite)
        )
        with self._sessao() as sessao:
            return [Vaga.model_validate(linha.dados) for linha in sessao.exec(consulta)]

    # análises ---------------------------------------------------------------

    def salvar_analise(
        self,
        chave: str,
        analise: JobAnalysis,
        *,
        provedor: str,
        modelo: str,
        perfil_id: int | None,
    ) -> None:
        with self._sessao() as sessao:
            sessao.add(
                AnaliseTabela(
                    vaga_chave=chave,
                    dados=analise.model_dump(),
                    provedor=provedor,
                    modelo=modelo,
                    perfil_id=perfil_id,
                )
            )
            sessao.commit()

    def analise_vigente(self, chave: str) -> AnaliseSalva | None:
        with self._sessao() as sessao:
            return self._analise_vigente(sessao, chave)

    @staticmethod
    def _analise_vigente(sessao: Session, chave: str) -> AnaliseSalva | None:
        consulta = (
            select(AnaliseTabela)
            .where(AnaliseTabela.vaga_chave == chave)
            .order_by(AnaliseTabela.id.desc())
        )
        linha = sessao.exec(consulta).first()
        if linha is None:
            return None
        return AnaliseSalva(
            analise=JobAnalysis.model_validate(linha.dados),
            provedor=linha.provedor,
            modelo=linha.modelo,
            criada_em=linha.criada_em,
        )

    # perfil -----------------------------------------------------------------

    def salvar_perfil(self, perfil: Perfil) -> tuple[int, bool]:
        with self._sessao() as sessao:
            atual = sessao.exec(
                select(PerfilTabela).order_by(PerfilTabela.id.desc())
            ).first()
            if atual and atual.content_hash == perfil.content_hash:
                return atual.id, False
            linha = PerfilTabela(
                dados=perfil.dados, texto=perfil.texto, content_hash=perfil.content_hash
            )
            sessao.add(linha)
            sessao.commit()
            sessao.refresh(linha)
            return linha.id, True

    def ultimo_perfil(self) -> tuple[int, Perfil] | None:
        with self._sessao() as sessao:
            linha = sessao.exec(
                select(PerfilTabela).order_by(PerfilTabela.id.desc())
            ).first()
            if linha is None:
                return None
            return linha.id, Perfil(
                dados=linha.dados, texto=linha.texto, content_hash=linha.content_hash
            )

    def historico_perfil(self) -> list[dict]:
        """Snapshots do mais novo ao mais antigo, com os campos que mudaram."""
        with self._sessao() as sessao:
            linhas = list(
                sessao.exec(select(PerfilTabela).order_by(PerfilTabela.id.desc()))
            )
        historico = []
        for indice, linha in enumerate(linhas):
            anterior = linhas[indice + 1] if indice + 1 < len(linhas) else None
            historico.append(
                {
                    "id": linha.id,
                    "lido_em": linha.lido_em,
                    "content_hash": linha.content_hash,
                    "campos_alterados": _diferencas(
                        anterior.dados if anterior else {}, linha.dados
                    ),
                }
            )
        return historico

    # execuções --------------------------------------------------------------

    def iniciar_execucao(self, gatilho: Gatilho) -> Execucao:
        with self._sessao() as sessao:
            linha = ExecucaoTabela(gatilho=gatilho)
            sessao.add(linha)
            sessao.commit()
            sessao.refresh(linha)
            return Execucao.model_validate(linha, from_attributes=True)

    def finalizar_execucao(self, execucao: Execucao) -> None:
        with self._sessao() as sessao:
            linha = sessao.get(ExecucaoTabela, execucao.id)
            for campo, valor in execucao.model_dump(exclude={"id"}).items():
                setattr(linha, campo, valor)
            linha.finalizada_em = agora()
            sessao.add(linha)
            sessao.commit()

    def listar_execucoes(self, limite: int = 20) -> list[Execucao]:
        consulta = (
            select(ExecucaoTabela).order_by(ExecucaoTabela.id.desc()).limit(limite)
        )
        with self._sessao() as sessao:
            return [
                Execucao.model_validate(linha, from_attributes=True)
                for linha in sessao.exec(consulta)
            ]
