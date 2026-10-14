from sqlalchemy import Engine
from sqlmodel import Session, col, select

from peao_bilingue.adaptadores.persistencia.sqlite.analises import ultima_analise
from peao_bilingue.adaptadores.persistencia.sqlite.banco import BaseSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.tabelas import VagaTabela
from peao_bilingue.dominio.vagas import (
    Anuncio,
    RepositorioVagas,
    StatusVaga,
    Vaga,
    VagaListada,
)


class VagasSQLite(BaseSQLite, RepositorioVagas):
    def __init__(self, engine: Engine | None = None) -> None:
        super().__init__(engine)
        _assinar_vagas_antigas(self._engine)

    def vaga_existe(self, chave: str) -> bool:
        with self._sessao() as sessao:
            return sessao.get(VagaTabela, chave) is not None

    def salvar_vaga(
        self, vaga: Vaga, buscas: list[str], *, repete: str | None = None
    ) -> None:
        with self._sessao() as sessao:
            linha = sessao.get(VagaTabela, vaga.chave) or VagaTabela(
                chave=vaga.chave, fonte=vaga.fonte
            )
            linha.dados = vaga.model_dump(mode="json")
            linha.buscas = sorted(set(linha.buscas or []) | set(buscas))
            linha.assinatura = vaga.assinatura()
            linha.repete = repete or linha.repete
            sessao.add(linha)
            sessao.commit()

    def original_de(self, vaga: Vaga) -> str | None:
        assinatura = vaga.assinatura()
        if not assinatura:
            return None
        with self._sessao() as sessao:
            return sessao.exec(
                select(VagaTabela.chave)
                .where(
                    VagaTabela.assinatura == assinatura,
                    VagaTabela.fonte != vaga.fonte,
                    col(VagaTabela.repete).is_(None),
                )
                .order_by(col(VagaTabela.vista_em))
            ).first()

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
        pesquisa: str | None = None,
        limite: int = 50,
        offset: int = 0,
    ) -> list[VagaListada]:
        consulta = (
            select(VagaTabela)
            .where(col(VagaTabela.repete).is_(None))
            .order_by(col(VagaTabela.vista_em).desc())
        )
        if status is not None:
            consulta = consulta.where(VagaTabela.status == status)
        if fonte is not None:
            consulta = consulta.where(VagaTabela.fonte == fonte)

        vagas = []
        with self._sessao() as sessao:
            for linha in sessao.exec(consulta):
                if busca and busca not in (linha.buscas or []):
                    continue
                vaga = Vaga.model_validate(linha.dados)
                if pesquisa and not vaga.contem(pesquisa):
                    continue
                vigente = ultima_analise(sessao, linha.chave)
                fit = vigente.dados["fit_score"] if vigente else None
                if min_score is not None and (fit is None or fit < min_score):
                    continue
                vagas.append(
                    VagaListada(
                        vaga=vaga,
                        status=linha.status,
                        fit_score=fit,
                        buscas=linha.buscas or [],
                        vista_em=linha.vista_em,
                        tambem_em=_repeticoes(sessao, linha.chave),
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


def _repeticoes(sessao: Session, chave: str) -> list[Anuncio]:
    linhas = sessao.exec(
        select(VagaTabela)
        .where(VagaTabela.repete == chave)
        .order_by(col(VagaTabela.vista_em))
    )
    return [Anuncio(fonte=linha.fonte, url=linha.dados["url"]) for linha in linhas]


def _assinar_vagas_antigas(engine: Engine) -> None:
    """Vagas guardadas antes da assinatura existir: calcula e junta as repetidas
    entre fontes, na ordem em que foram vistas (a primeira fica como original)."""
    with Session(engine) as sessao:
        linhas = list(
            sessao.exec(select(VagaTabela).order_by(col(VagaTabela.vista_em)))
        )
        if all(linha.assinatura is not None for linha in linhas):
            return
        originais: dict[str, VagaTabela] = {}
        for linha in linhas:
            if linha.assinatura is None:
                linha.assinatura = Vaga.model_validate(linha.dados).assinatura()
                original = originais.get(linha.assinatura)
                if original is not None and original.fonte != linha.fonte:
                    linha.repete = original.chave
                sessao.add(linha)
            if linha.assinatura and linha.repete is None:
                originais.setdefault(linha.assinatura, linha)
        sessao.commit()
