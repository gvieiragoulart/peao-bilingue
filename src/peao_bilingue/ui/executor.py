"""Ponte entre o Tkinter (síncrono, uma thread só) e o núcleo assíncrono.

O mainloop do Tk não pode esperar o Playwright navegar nem um LLM responder,
senão a janela congela. As corrotinas rodam num loop asyncio numa thread
própria; os resultados voltam para a thread da interface por `after()`.
Nenhum widget é tocado fora da thread da interface.
"""

import asyncio
import logging
import queue
import threading
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from typing import Any

INTERVALO_MS = 100


class ExecutorAssincrono:
    def __init__(self) -> None:
        # No Windows o loop padrão é Proactor, que o Playwright exige (subprocessos).
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._rodar, name="peao-async", daemon=True
        )
        self._thread.start()

    def _rodar(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submeter(self, corrotina: Coroutine[Any, Any, Any]) -> Future:
        return asyncio.run_coroutine_threadsafe(corrotina, self._loop)

    def encerrar(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)


def acompanhar(
    widget: Any,
    futuro: Future,
    ao_terminar: Callable[[Any], None] | None = None,
    ao_falhar: Callable[[BaseException], None] | None = None,
) -> None:
    """Chama o callback certo na thread da interface quando o futuro terminar."""

    def verificar() -> None:
        if not futuro.done():
            widget.after(INTERVALO_MS, verificar)
            return
        falha = futuro.exception()
        if falha is not None:
            if ao_falhar:
                ao_falhar(falha)
        elif ao_terminar:
            ao_terminar(futuro.result())

    widget.after(INTERVALO_MS, verificar)


class FilaDeLog(logging.Handler):
    """Leva os logs de qualquer thread para uma fila que a interface esvazia."""

    def __init__(self, fila: queue.Queue[str]) -> None:
        super().__init__(level=logging.INFO)
        self.fila = fila
        self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, registro: logging.LogRecord) -> None:
        self.fila.put(self.format(registro))
