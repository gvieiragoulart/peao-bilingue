from sqlmodel import col, select

from peao_bilingue.adaptadores.persistencia.sqlite.analises import ultima_analise
from peao_bilingue.adaptadores.persistencia.sqlite.banco import BaseSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.tabelas import VagaTabela
from peao_bilingue.dominio.vagas import (
    RepositorioVagas,
    StatusVaga,
    Vaga,
    VagaListada,
)


class VagasSQLite(BaseSQLite, RepositorioVagas):
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
        consulta = select(VagaTabela).order_by(col(VagaTabela.vista_em).desc())
        if status is not None:
            consulta = consulta.where(VagaTabela.status == status)
        if fonte is not None:
            consulta = consulta.where(VagaTabela.fonte == fonte)

        vagas = []
        with self._sessao() as sessao:
            for linha in sessao.exec(consulta):
                if busca and busca not in (linha.buscas or []):
                    continue
                vigente = ultima_analise(sessao, linha.chave)
                fit = vigente.dados["fit_score"] if vigente else None
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
