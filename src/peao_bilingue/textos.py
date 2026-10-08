"""Textos para o usuário que a CLI e a interface compartilham (sem Tk).

A CLI não importa nada de `ui/`: os dois são pontas de entrada independentes.
"""

from peao_bilingue.dominio.agenda import SituacaoAgenda


def descrever_agenda(situacao: SituacaoAgenda | None) -> str:
    if situacao is None:
        return "Nenhuma coleta agendada."
    partes = [f"Todo dia às {situacao.horario} (tarefa: {situacao.estado})."]
    if situacao.proxima_execucao:
        partes.append(f"Próxima: {situacao.proxima_execucao:%d/%m %H:%M}.")
    if situacao.ultima_execucao:
        resultado = (
            "ok"
            if situacao.ultimo_resultado == 0
            else f"código {situacao.ultimo_resultado}"
        )
        partes.append(f"Última: {situacao.ultima_execucao:%d/%m %H:%M} ({resultado}).")
    return " ".join(partes)
