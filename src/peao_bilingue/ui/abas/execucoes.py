from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue.aplicacao.execucao import executar
from peao_bilingue.composicao import montar_servicos
from peao_bilingue.dominio.entidades import Execucao, Gatilho
from peao_bilingue.ui import apresentacao
from peao_bilingue.ui.componentes import Tabela

if TYPE_CHECKING:
    from peao_bilingue.ui.app import Aplicativo

COLUNAS = [
    ("inicio", "Início", 90),
    ("gatilho", "Gatilho", 80),
    ("status", "Status", 110),
    ("listadas", "Listadas", 70),
    ("novas", "Novas", 60),
    ("analisadas", "Analisadas", 80),
    ("barradas", "Barradas", 70),
    ("erro", "Erro", 340),
]
LINHAS_DE_LOG = 2_000


class AbaExecucoes(ctk.CTkFrame):
    def __init__(self, mestre: Any, app: "Aplicativo") -> None:
        super().__init__(mestre, fg_color="transparent")
        self.app = app

        controles = ctk.CTkFrame(self, fg_color="transparent")
        controles.pack(fill="x", pady=(0, 8))
        self.sem_analise = ctk.CTkSwitch(
            controles, text="Só coletar (não gasta crédito)"
        )
        self.sem_analise.pack(side="left", padx=(0, 16))
        self.simulacao = ctk.CTkSwitch(controles, text="Analisar sem enviar avisos")
        self.simulacao.pack(side="left")
        self.botao = ctk.CTkButton(
            controles, text="Coletar agora", width=140, command=self._coletar
        )
        self.botao.pack(side="right")

        self.historico = Tabela(self, COLUNAS, height=220)
        self.historico.pack(fill="x")

        ctk.CTkLabel(self, text="Registro").pack(anchor="w", pady=(12, 4))
        self.log = ctk.CTkTextbox(self, wrap="word", height=220)
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

    def atualizar(self) -> None:
        self.historico.preencher(
            [
                (str(execucao.id), apresentacao.linha_de_execucao(execucao))
                for execucao in self.app.repositorio.listar_execucoes(50)
            ]
        )

    def adicionar_log(self, linha: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", linha + "\n")
        excesso = int(self.log.index("end-1c").split(".")[0]) - LINHAS_DE_LOG
        if excesso > 0:
            self.log.delete("1.0", f"{excesso + 1}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _coletar(self) -> None:
        so_coletar = bool(self.sem_analise.get())
        try:
            servicos = montar_servicos(
                analisar=not so_coletar, repositorio=self.app.repositorio
            )
        except Exception as falha:  # noqa: BLE001 - provedor mal configurado vira aviso
            self.app.mostrar_erro(falha)
            return

        self.botao.configure(state="disabled", text="Coletando…")
        self.app.registrar("Coleta iniciada.")

        def terminar(execucao: Execucao) -> None:
            self.botao.configure(state="normal", text="Coletar agora")
            self.app.ao_mudar_dados()
            self.app.registrar(
                f"Coleta {execucao.status.value}: {execucao.vagas_novas} nova(s), "
                f"{execucao.vagas_analisadas} analisada(s)."
            )

        def falhar(falha: BaseException) -> None:
            self.botao.configure(state="normal", text="Coletar agora")
            self.app.mostrar_erro(falha)

        self.app.rodar(
            executar(
                servicos,
                Gatilho.manual,
                dry_run=bool(self.simulacao.get()) or None,
                analisar_vagas=not so_coletar,
            ),
            ao_terminar=terminar,
            ao_falhar=falhar,
        )
