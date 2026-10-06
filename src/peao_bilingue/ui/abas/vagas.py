import webbrowser
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import fabricas
from peao_bilingue.aplicacao.execucao import reanalisar_vaga
from peao_bilingue.composicao import montar_servicos
from peao_bilingue.dominio.entidades import StatusVaga, VagaListada
from peao_bilingue.ui import apresentacao
from peao_bilingue.ui.componentes import Tabela

if TYPE_CHECKING:
    from peao_bilingue.ui.app import Aplicativo

LIMITE = 500
COLUNAS = [
    ("fit", "Fit", 45),
    ("titulo", "Vaga", 280),
    ("local", "Local", 150),
    ("fonte", "Fonte", 75),
    ("status", "Status", 80),
    ("triagem", "Triagem", 100),
]


class AbaVagas(ctk.CTkFrame):
    def __init__(self, mestre: Any, app: "Aplicativo") -> None:
        super().__init__(mestre, fg_color="transparent")
        self.app = app
        self._vagas: dict[str, VagaListada] = {}

        filtros = ctk.CTkFrame(self, fg_color="transparent")
        filtros.pack(fill="x", pady=(0, 8))
        self.status = ctk.CTkOptionMenu(
            filtros, values=apresentacao.OPCOES_STATUS, width=130
        )
        self.fonte = ctk.CTkOptionMenu(filtros, values=[apresentacao.TODAS], width=130)
        self.busca = ctk.CTkOptionMenu(filtros, values=[apresentacao.TODAS], width=170)
        self.score = ctk.CTkEntry(filtros, width=70, placeholder_text="fit ≥")
        for rotulo, widget in (
            ("Status", self.status),
            ("Fonte", self.fonte),
            ("Busca", self.busca),
            ("Fit mínimo", self.score),
        ):
            ctk.CTkLabel(filtros, text=rotulo).pack(side="left", padx=(0, 4))
            widget.pack(side="left", padx=(0, 12))
        ctk.CTkButton(filtros, text="Filtrar", width=90, command=self.atualizar).pack(
            side="left"
        )

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True)
        corpo.grid_columnconfigure(0, weight=3)
        corpo.grid_columnconfigure(1, weight=2)
        corpo.grid_rowconfigure(0, weight=1)

        self.tabela = Tabela(corpo, COLUNAS)
        self.tabela.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.tabela.ao_selecionar(self._mostrar_detalhe)

        lado = ctk.CTkFrame(corpo, fg_color="transparent")
        lado.grid(row=0, column=1, sticky="nsew")
        self.detalhe = ctk.CTkTextbox(lado, wrap="word")
        self.detalhe.pack(fill="both", expand=True)
        self.detalhe.configure(state="disabled")

        # Duas linhas: cinco botões numa só não cabem no painel e cortavam o texto.
        acoes = ctk.CTkFrame(lado, fg_color="transparent")
        acoes.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(acoes, text="Abrir vaga", width=110, command=self._abrir).pack(
            side="left"
        )
        self.botao_reanalisar = ctk.CTkButton(
            acoes, text="Analisar de novo", width=140, command=self._reanalisar
        )
        self.botao_reanalisar.pack(side="left", padx=6)

        marcar = ctk.CTkFrame(lado, fg_color="transparent")
        marcar.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(marcar, text="Marcar como:").pack(side="left", padx=(0, 6))
        for status in (
            StatusVaga.estudando,
            StatusVaga.aplicada,
            StatusVaga.descartada,
        ):
            ctk.CTkButton(
                marcar,
                text=status.value.capitalize(),
                width=96,
                fg_color="transparent",
                border_width=1,
                command=lambda s=status: self._mudar_status(s),
            ).pack(side="left", padx=(0, 6))

    def atualizar(self) -> None:
        repositorio = self.app.repositorio
        buscas = [busca.nome for busca in repositorio.listar_buscas()]
        self.busca.configure(values=[apresentacao.TODAS, *buscas])
        self.fonte.configure(
            values=[apresentacao.TODAS, *fabricas.fontes.disponiveis()]
        )

        try:
            minimo = apresentacao.score_minimo(self.score.get())
        except ValueError as falha:
            self.app.mostrar_erro(falha)
            return

        def filtro(widget: ctk.CTkOptionMenu) -> str | None:
            valor = widget.get()
            return None if valor == apresentacao.TODAS else valor

        status = filtro(self.status)
        vagas = repositorio.listar_vagas(
            status=StatusVaga(status) if status else None,
            min_score=minimo,
            busca=filtro(self.busca),
            fonte=filtro(self.fonte),
            limite=LIMITE,
        )
        self._vagas = {item.vaga.chave: item for item in vagas}
        self.tabela.preencher(
            [
                (chave, apresentacao.linha_de_vaga(item))
                for chave, item in self._vagas.items()
            ]
        )
        self._escrever_detalhe(
            f"{len(vagas)} vaga(s). Selecione uma para ver a análise."
        )

    def _selecionada(self) -> VagaListada | None:
        chave = self.tabela.selecionado()
        return self._vagas.get(chave) if chave else None

    def _mostrar_detalhe(self) -> None:
        item = self._selecionada()
        if item is not None:
            analise = self.app.repositorio.analise_vigente(item.vaga.chave)
            self._escrever_detalhe(apresentacao.detalhe_da_vaga(item, analise))

    def _escrever_detalhe(self, texto: str) -> None:
        self.detalhe.configure(state="normal")
        self.detalhe.delete("1.0", "end")
        self.detalhe.insert("1.0", texto)
        self.detalhe.configure(state="disabled")

    def _abrir(self) -> None:
        item = self._selecionada()
        if item is not None:
            webbrowser.open(item.vaga.url)

    def _mudar_status(self, status: StatusVaga) -> None:
        item = self._selecionada()
        if item is None:
            return
        chave = item.vaga.chave
        self.app.repositorio.mudar_status(chave, status)
        self.atualizar()
        if self.tabela.arvore.exists(chave):
            self.tabela.arvore.selection_set(chave)

    def _reanalisar(self) -> None:
        item = self._selecionada()
        if item is None:
            return
        try:
            servicos = montar_servicos(repositorio=self.app.repositorio)
        except Exception as falha:  # noqa: BLE001 - provedor mal configurado vira aviso
            self.app.mostrar_erro(falha)
            return
        self.botao_reanalisar.configure(state="disabled", text="Analisando…")

        def terminar(_resultado: object = None) -> None:
            self.botao_reanalisar.configure(state="normal", text="Analisar de novo")
            self.atualizar()

        def falhar(falha: BaseException) -> None:
            terminar()
            self.app.mostrar_erro(falha)

        # Reanálise avulsa nunca notifica: quem pediu está olhando a tela.
        self.app.rodar(
            reanalisar_vaga(servicos, item.vaga.chave, dry_run=True),
            ao_terminar=terminar,
            ao_falhar=falhar,
        )
