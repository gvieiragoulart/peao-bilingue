from sqlmodel import Session, col, select

from peao_bilingue.adaptadores.persistencia.sqlite.banco import BaseSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.perfis import ultimo_perfil_da_fonte
from peao_bilingue.adaptadores.persistencia.sqlite.tabelas import (
    AnaliseTabela,
    PerfilTabela,
)
from peao_bilingue.dominio.analise import AnaliseSalva, JobAnalysis, RepositorioAnalises


def ultima_analise(sessao: Session, chave: str) -> AnaliseTabela | None:
    consulta = (
        select(AnaliseTabela)
        .where(AnaliseTabela.vaga_chave == chave)
        .order_by(col(AnaliseTabela.id).desc())
    )
    return sessao.exec(consulta).first()


class AnalisesSQLite(BaseSQLite, RepositorioAnalises):
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
            linha = ultima_analise(sessao, chave)
            if linha is None:
                return None
            perfil = (
                sessao.get(PerfilTabela, linha.perfil_id) if linha.perfil_id else None
            )
            # Um snapshot mais novo da mesma fonte: a análise usou um perfil antigo.
            ultimo = ultimo_perfil_da_fonte(sessao, perfil.fonte) if perfil else None
            desatualizado = (
                perfil is not None and ultimo is not None and ultimo.id != perfil.id
            )
            return AnaliseSalva(
                analise=JobAnalysis.model_validate(linha.dados),
                provedor=linha.provedor,
                modelo=linha.modelo,
                criada_em=linha.criada_em,
                perfil_fonte=perfil.fonte if perfil else None,
                perfil_desatualizado=desatualizado,
            )
