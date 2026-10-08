import webbrowser
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import configuracao, fabricas
from peao_bilingue.aplicacao.analise import analisar_vaga
from peao_bilingue.composicao import montar_llm
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import JobAnalysis, StatusVaga, VagaListada
from peao_bilingue.ui import apresentacao
from peao_bilingue.ui.componentes import Tabela

if TYPE_CHECKING:
    from peao_bilingue.ui.app import Aplicativo

LIMITE = 500
SEM_PERFIL = "(nenhum)"
COLUNAS = [
    ("fit", "Fit", 45),
    ("titulo", "Vaga", 300),
    ("local", "Local", 160),
    ("fonte", "Fonte", 80),
    ("status", "Status", 90),
]


class AbaVagas(ctk.CTkFrame):
    def __init__(self, mestre: Any, app: "Aplicativo") -> None:
        super().__init__(mestre, fg_color="transparent")
        self.app = app
        self._vagas: dict[str, VagaListada] = {}
        self._fontes_com_perfil: list[str] = []
        # O seletor mostra o rótulo ("Ollama (local, grátis)"): o custo fica à vista.
        self._llms = {
            fabricas.llms.classe(nome).rotulo: nome
            for nome in fabricas.llms.disponiveis()
        }

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

        # Em linhas: seletores e botões juntos não cabem na largura do painel.
        escolha = ctk.CTkFrame(lado, fg_color="transparent")
        escolha.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(escolha, text="LLM").pack(side="left", padx=(0, 4))
        self.llm = ctk.CTkOptionMenu(
            escolha, values=list(self._llms), width=180, command=self._lembrar_llm
        )
        self.llm.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(escolha, text="Perfil").pack(side="left", padx=(0, 4))
        self.perfil = ctk.CTkOptionMenu(escolha, values=[SEM_PERFIL], width=120)
        self.perfil.pack(side="left")

        acoes = ctk.CTkFrame(lado, fg_color="transparent")
        acoes.pack(fill="x", pady=(6, 0))
        self.botao_analisar = ctk.CTkButton(
            acoes, text="Analisar", width=110, command=self._analisar
        )
        self.botao_analisar.pack(side="left")
        ctk.CTkButton(
            acoes,
            text="Abrir vaga",
            width=110,
            fg_color="transparent",
            border_width=1,
            command=self._abrir,
        ).pack(side="left", padx=6)

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
        self._atualizar_seletores()

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
            f"{len(vagas)} vaga(s). Selecione uma para ver a análise ou analisar."
        )

    def _atualizar_seletores(self) -> None:
        self._fontes_com_perfil = self.app.repositorio.fontes_com_perfil()
        self.perfil.configure(values=self._fontes_com_perfil or [SEM_PERFIL])
        if self.perfil.get() not in self._fontes_com_perfil:
            self.perfil.set(
                self._fontes_com_perfil[0] if self._fontes_com_perfil else SEM_PERFIL
            )
        rotulos = {nome: rotulo for rotulo, nome in self._llms.items()}
        self.llm.set(rotulos.get(settings.llm_analise, next(iter(self._llms))))

    def _lembrar_llm(self, rotulo: str) -> None:
        # O último escolhido vira o padrão da próxima vez.
        configuracao.salvar({"llm_analise": self._llms[rotulo]})

    def _selecionada(self) -> VagaListada | None:
        chave = self.tabela.selecionado()
        return self._vagas.get(chave) if chave else None

    def _selecionar(self, chave: str) -> None:
        if self.tabela.arvore.exists(chave):
            self.tabela.arvore.selection_set(chave)

    def _mostrar_detalhe(self) -> None:
        item = self._selecionada()
        if item is None:
            return
        # Por padrão, a vaga é analisada com o perfil cadastrado na fonte dela.
        if item.vaga.fonte in self._fontes_com_perfil:
            self.perfil.set(item.vaga.fonte)
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
        self._selecionar(chave)

    def _analisar(self) -> None:
        item = self._selecionada()
        if item is None:
            self.app.mostrar_erro(ValueError("Selecione uma vaga para analisar."))
            return
        nome_llm = self._llms[self.llm.get()]
        try:
            provedor = montar_llm(nome_llm)
        except Exception as falha:  # noqa: BLE001 - provedor mal configurado vira aviso
            self.app.mostrar_erro(falha)
            return
        perfil = self.perfil.get()
        vaga = item.vaga
        self.botao_analisar.configure(state="disabled", text="Analisando…")
        self.app.registrar(f"Analisando {vaga.titulo} ({vaga.chave}) com {nome_llm}…")

        def liberar() -> None:
            self.botao_analisar.configure(state="normal", text="Analisar")

        def terminar(analise: JobAnalysis) -> None:
            liberar()
            self.app.registrar(
                f"Análise pronta: {vaga.titulo} — fit {analise.fit_score}."
            )
            self.atualizar()
            self._selecionar(vaga.chave)

        def falhar(falha: BaseException) -> None:
            liberar()
            self.app.mostrar_erro(falha)

        self.app.rodar(
            analisar_vaga(
                self.app.repositorio,
                provedor,
                vaga.chave,
                perfil_de=None if perfil == SEM_PERFIL else perfil,
            ),
            ao_terminar=terminar,
            ao_falhar=falhar,
        )
