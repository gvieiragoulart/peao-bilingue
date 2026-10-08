from sqlmodel import col, select

from peao_bilingue.adaptadores.persistencia.sqlite.banco import BaseSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.tabelas import BuscaTabela
from peao_bilingue.dominio.buscas import Busca, RepositorioBuscas


class BuscasSQLite(BaseSQLite, RepositorioBuscas):
    def listar_buscas(self, *, so_ativas: bool = False) -> list[Busca]:
        consulta = select(BuscaTabela).order_by(col(BuscaTabela.id))
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
