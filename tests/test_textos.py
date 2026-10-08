from datetime import datetime
from zoneinfo import ZoneInfo

from peao_bilingue.dominio.agenda import SituacaoAgenda
from peao_bilingue.textos import descrever_agenda

AGORA = datetime(2026, 10, 6, 9, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_descreve_agenda_vazia():
    assert descrever_agenda(None) == "Nenhuma coleta agendada."


def test_descreve_agenda_com_proxima_e_ultima():
    situacao = SituacaoAgenda(
        horario="08:00",
        estado="Ready",
        proxima_execucao=AGORA,
        ultima_execucao=AGORA,
        ultimo_resultado=1,
    )
    texto = descrever_agenda(situacao)
    assert "Todo dia às 08:00" in texto
    assert "Próxima: 06/10 09:30" in texto
    assert "código 1" in texto  # a última execução falhou
