"""Janela principal do Peão Bilíngue."""

import logging
import queue
from collections.abc import Callable, Coroutine
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from peao_bilingue.adaptadores.persistencia.sqlite import RepositorioSQLite
from peao_bilingue.composicao import montar_agendador
from peao_bilingue.dominio.portas import Agendador, RepositorioVagas
from peao_bilingue.ui.abas.buscas import AbaBuscas
from peao_bilingue.ui.abas.configuracoes import AbaConfiguracoes
from peao_bilingue.ui.abas.execucoes import AbaExecucoes
from peao_bilingue.ui.abas.fontes import AbaFontes
from peao_bilingue.ui.abas.llms import AbaLLMs
from peao_bilingue.ui.abas.perfil import AbaPerfil
from peao_bilingue.ui.abas.vagas import AbaVagas
from peao_bilingue.ui.executor import ExecutorAssincrono, FilaDeLog, acompanhar

TITULO = "Peão Bilíngue"
INTERVALO_LOG_MS = 200
ABAS = [
    ("Vagas", AbaVagas),
    ("Buscas", AbaBuscas),
    ("Fontes", AbaFontes),
    ("LLMs", AbaLLMs),
    ("Perfil", AbaPerfil),
    ("Execuções", AbaExecucoes),
    ("Configurações", AbaConfiguracoes),
]


class Aplicativo(ctk.CTk):
    def __init__(
        self,
        repositorio: RepositorioVagas | None = None,
        executor: ExecutorAssincrono | None = None,
        agendador: Agendador | None = None,
    ) -> None:
        super().__init__()
        self.title(f"{TITULO} — radar de vagas")
        self.geometry("1280x800")
        self.minsize(1000, 640)

        self.repositorio = repositorio or RepositorioSQLite()
        self.executor = executor or ExecutorAssincrono()
        self.agendador = agendador or montar_agendador()
        self._fila: queue.Queue[str] = queue.Queue()
        self._log = FilaDeLog(self._fila)
        logging.getLogger().addHandler(self._log)

        self.abas = ctk.CTkTabview(self)
        self.abas.pack(fill="both", expand=True, padx=12, pady=12)
        self.paineis: dict[str, Any] = {}
        for titulo, classe in ABAS:
            painel = classe(self.abas.add(titulo), self)
            painel.pack(fill="both", expand=True)
            self.paineis[titulo] = painel

        self.ao_mudar_dados()
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self.after(INTERVALO_LOG_MS, self._drenar_log)

    def rodar(
        self,
        corrotina: Coroutine[Any, Any, Any],
        *,
        ao_terminar: Callable[[Any], None] | None = None,
        ao_falhar: Callable[[BaseException], None] | None = None,
    ) -> None:
        """Roda no loop assíncrono; os callbacks voltam na thread da interface."""
        acompanhar(
            self,
            self.executor.submeter(corrotina),
            ao_terminar,
            ao_falhar or self.mostrar_erro,
        )

    def registrar(self, mensagem: str) -> None:
        """Pode ser chamado de qualquer thread: só enfileira."""
        self._fila.put(mensagem)

    def _drenar_log(self) -> None:
        while True:
            try:
                linha = self._fila.get_nowait()
            except queue.Empty:
                break
            self.paineis["Execuções"].adicionar_log(linha)
        self.after(INTERVALO_LOG_MS, self._drenar_log)

    def ao_mudar_dados(self) -> None:
        for painel in self.paineis.values():
            painel.atualizar()

    def mostrar_erro(self, falha: BaseException) -> None:
        messagebox.showerror(TITULO, str(falha), parent=self)

    def informar(self, mensagem: str) -> None:
        messagebox.showinfo(TITULO, mensagem, parent=self)

    def fechar(self) -> None:
        logging.getLogger().removeHandler(self._log)
        self.executor.encerrar()
        # Timers pendentes (o do registro e os do CustomTkinter) disparariam depois
        # do destroy, e o Tcl reclamaria de comando inexistente no stderr. Só o timer
        # é cancelado: o comando é de quem agendou e sai no destroy de cada widget
        # (o `after_cancel` o apagaria antes, e o destroy do dono falharia).
        for pendente in self.tk.splitlist(self.tk.call("after", "info")):
            self.tk.call("after", "cancel", pendente)
        self.destroy()


def main() -> None:
    # Sem basicConfig: aberto como app de janela não há console para escrever.
    logging.getLogger().setLevel(logging.INFO)
    ctk.set_appearance_mode("system")
    Aplicativo().mainloop()
