from sqlmodel import col, select

from peao_bilingue.adaptadores.persistencia.sqlite.banco import BaseSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.tabelas import ExecucaoTabela, agora
from peao_bilingue.dominio.coleta import (
    Execucao,
    Gatilho,
    RepositorioExecucoes,
    StatusExecucao,
)


class ExecucoesSQLite(BaseSQLite, RepositorioExecucoes):
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
            if linha is None:
                raise LookupError(f"Execução {execucao.id} não encontrada.")
            for campo, valor in execucao.model_dump(exclude={"id"}).items():
                setattr(linha, campo, valor)
            linha.finalizada_em = agora()
            sessao.add(linha)
            sessao.commit()

    def encerrar_execucoes_orfas(self, motivo: str) -> int:
        consulta = select(ExecucaoTabela).where(
            ExecucaoTabela.status == StatusExecucao.rodando
        )
        with self._sessao() as sessao:
            orfas = sessao.exec(consulta).all()
            for linha in orfas:
                # finalizada_em fica vazio: não se sabe quando o processo morreu.
                linha.status = StatusExecucao.erro
                linha.erro = motivo
                sessao.add(linha)
            sessao.commit()
            return len(orfas)

    def listar_execucoes(self, limite: int = 20) -> list[Execucao]:
        consulta = (
            select(ExecucaoTabela).order_by(col(ExecucaoTabela.id).desc()).limit(limite)
        )
        with self._sessao() as sessao:
            return [
                Execucao.model_validate(linha, from_attributes=True)
                for linha in sessao.exec(consulta)
            ]
