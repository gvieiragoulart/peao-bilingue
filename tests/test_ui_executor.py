import asyncio
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from peao_bilingue.ui.executor import ExecutorAssincrono, FilaDeLog, acompanhar


@pytest.fixture
def executor() -> Iterator[ExecutorAssincrono]:
    executor = ExecutorAssincrono()
    yield executor
    executor.encerrar()


def test_corrotina_roda_em_outra_thread(executor: ExecutorAssincrono) -> None:
    async def onde() -> str:
        return threading.current_thread().name

    assert executor.submeter(onde()).result(timeout=5) == "peao-async"


def test_thread_principal_fica_livre_enquanto_a_corrotina_espera(
    executor: ExecutorAssincrono,
) -> None:
    async def demorada() -> str:
        await asyncio.sleep(0.5)
        return "pronto"

    futuro = executor.submeter(demorada())
    batidas = 0
    while not futuro.done():  # é o que o mainloop do Tk faria
        batidas += 1
        time.sleep(0.01)
    assert futuro.result() == "pronto"
    assert batidas > 10


def test_execucoes_seguidas_reaproveitam_o_mesmo_loop(
    executor: ExecutorAssincrono,
) -> None:
    async def loop_atual() -> int:
        return id(asyncio.get_running_loop())

    primeiro = executor.submeter(loop_atual()).result(timeout=5)
    segundo = executor.submeter(loop_atual()).result(timeout=5)
    assert primeiro == segundo


class WidgetFalso:
    """Imita o `after` do Tk rodando os callbacks na thread do teste."""

    def __init__(self) -> None:
        self.pendentes: list[Callable[[], None]] = []

    def after(self, _ms: int, funcao: Callable[[], None]) -> None:
        self.pendentes.append(funcao)

    def processar(self, ate: float = 5) -> None:
        limite = time.time() + ate
        while self.pendentes and time.time() < limite:
            self.pendentes.pop(0)()
            time.sleep(0.01)


def test_acompanhar_chama_o_callback_de_sucesso_na_thread_do_widget(
    executor: ExecutorAssincrono,
) -> None:
    async def valor() -> int:
        return 42

    widget, recebido = WidgetFalso(), list[tuple[Any, str]]()
    acompanhar(
        widget,
        executor.submeter(valor()),
        ao_terminar=lambda v: recebido.append((v, threading.current_thread().name)),
    )
    widget.processar()

    assert recebido == [(42, threading.current_thread().name)]


def test_acompanhar_entrega_a_falha(executor: ExecutorAssincrono) -> None:
    async def quebra() -> None:
        raise ValueError("deu ruim")

    widget, falhas = WidgetFalso(), list[BaseException]()
    acompanhar(widget, executor.submeter(quebra()), ao_falhar=falhas.append)
    widget.processar()

    assert len(falhas) == 1 and str(falhas[0]) == "deu ruim"


def test_fila_de_log_recebe_mensagens_de_qualquer_thread() -> None:
    fila: queue.Queue[str] = queue.Queue()
    logger = logging.getLogger("teste.fila")
    manipulador = FilaDeLog(fila)
    logger.addHandler(manipulador)
    logger.setLevel(logging.INFO)
    try:
        threading.Thread(target=lambda: logger.info("de outra thread")).start()
        assert "de outra thread" in fila.get(timeout=5)
    finally:
        logger.removeHandler(manipulador)
