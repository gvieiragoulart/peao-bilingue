import asyncio
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import configuracao
from peao_bilingue.aplicacao.execucao import executar
from peao_bilingue.composicao import montar_servicos
from peao_bilingue.configuracao import settings
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
    ("erro", "Erro", 440),
]
LINHAS_DE_LOG = 2_000


class AbaExecucoes(ctk.CTkFrame):
    def __init__(self, mestre: Any, app: "Aplicativo") -> None:
        super().__init__(mestre, fg_color="transparent")
        self.app = app

        controles = ctk.CTkFrame(self, fg_color="transparent")
        controles.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            controles,
            text="A coleta busca e guarda as vagas novas, sem chamar LLM: "
            "analise as que quiser na aba Vagas.",
            text_color="gray55",
        ).pack(side="left")
        self.botao = ctk.CTkButton(
            controles, text="Coletar agora", width=140, command=self._coletar
        )
        self.botao.pack(side="right")

        agenda = ctk.CTkFrame(self)
        agenda.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            agenda, text="Coleta diária automática", font=ctk.CTkFont(weight="bold")
        ).pack(side="left", padx=12, pady=10)
        self.horario = ctk.CTkEntry(agenda, width=70)
        self.horario.pack(side="left")
        self.horario.insert(0, settings.horario_coleta)
        ctk.CTkButton(agenda, text="Agendar", width=90, command=self._agendar).pack(
            side="left", padx=6
        )
        ctk.CTkButton(
            agenda,
            text="Cancelar",
            width=90,
            fg_color="transparent",
            border_width=1,
            command=self._cancelar_agenda,
        ).pack(side="left")
        self.situacao_agenda = ctk.CTkLabel(
            agenda, text="Consultando…", text_color="gray55"
        )
        self.situacao_agenda.pack(side="left", padx=12)

        self.historico = Tabela(self, COLUNAS, height=220)
        self.historico.pack(fill="x")

        ctk.CTkLabel(self, text="Registro").pack(anchor="w", pady=(12, 4))
        self.log = ctk.CTkTextbox(self, wrap="word", height=220)
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")
        self._consultar_agenda()

    # O PowerShell leva ~1 s para responder: tudo da agenda passa pelo executor,
    # e a consulta não entra no atualizar(), que roda a cada mudança de dados.
    def _consultar_agenda(self) -> None:
        def mostrar(situacao: object) -> None:
            self.situacao_agenda.configure(text=apresentacao.descrever_agenda(situacao))

        def falhar(falha: BaseException) -> None:
            self.situacao_agenda.configure(
                text=f"Não consegui consultar a agenda: {falha}"
            )

        self.app.rodar(
            asyncio.to_thread(self.app.agendador.situacao),
            ao_terminar=mostrar,
            ao_falhar=falhar,
        )

    def _agendar(self) -> None:
        horario = self.horario.get().strip()
        self.situacao_agenda.configure(text="Agendando…")

        def terminar(_resultado: object) -> None:
            # Aqui já na thread da interface: só ela mexe no `settings` compartilhado.
            configuracao.salvar({"horario_coleta": horario})
            self._consultar_agenda()

        self.app.rodar(
            asyncio.to_thread(self.app.agendador.agendar, horario),
            ao_terminar=terminar,
            ao_falhar=self._falha_na_agenda,
        )

    def _cancelar_agenda(self) -> None:
        self.situacao_agenda.configure(text="Cancelando…")
        self.app.rodar(
            asyncio.to_thread(self.app.agendador.cancelar),
            ao_terminar=lambda _r: self._consultar_agenda(),
            ao_falhar=self._falha_na_agenda,
        )

    def _falha_na_agenda(self, falha: BaseException) -> None:
        self._consultar_agenda()
        self.app.mostrar_erro(falha)

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
        try:
            servicos = montar_servicos(repositorio=self.app.repositorio)
        except Exception as falha:  # noqa: BLE001 - fonte mal configurada vira aviso
            self.app.mostrar_erro(falha)
            return

        self.botao.configure(state="disabled", text="Coletando…")
        self.app.registrar("Coleta iniciada.")

        def terminar(execucao: Execucao) -> None:
            self.botao.configure(state="normal", text="Coletar agora")
            self.app.ao_mudar_dados()
            self.app.registrar(
                f"Coleta {execucao.status.value}: {execucao.vagas_listadas} listada(s), "
                f"{execucao.vagas_novas} nova(s)."
            )

        def falhar(falha: BaseException) -> None:
            self.botao.configure(state="normal", text="Coletar agora")
            self.app.mostrar_erro(falha)

        # Sem avisos: quem pediu a coleta está olhando a tela.
        self.app.rodar(
            executar(servicos, Gatilho.manual),
            ao_terminar=terminar,
            ao_falhar=falhar,
        )
