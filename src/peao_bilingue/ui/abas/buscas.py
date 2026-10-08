from typing import TYPE_CHECKING, Any

import customtkinter as ctk
from pydantic import ValidationError

from peao_bilingue import fabricas
from peao_bilingue.dominio.buscas import Busca
from peao_bilingue.ui import apresentacao
from peao_bilingue.ui.componentes import Tabela

if TYPE_CHECKING:
    from peao_bilingue.ui.app import Aplicativo

COLUNAS = [
    ("nome", "Nome", 150),
    ("keywords", "Palavras-chave", 230),
    ("exclude", "Excluir", 140),
    ("fontes", "Fontes", 120),
    ("ativa", "Ativa", 60),
]


class AbaBuscas(ctk.CTkFrame):
    def __init__(self, mestre: Any, app: "Aplicativo") -> None:
        super().__init__(mestre, fg_color="transparent")
        self.app = app
        self._buscas: dict[str, Busca] = {}
        self._editando: int | None = None

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self.tabela = Tabela(self, COLUNAS)
        self.tabela.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.tabela.ao_selecionar(self._carregar_selecionada)

        form = ctk.CTkFrame(self)
        form.grid(row=0, column=1, sticky="nsew")
        self.titulo = ctk.CTkLabel(
            form, text="Nova busca", font=ctk.CTkFont(weight="bold")
        )
        self.titulo.pack(anchor="w", padx=12, pady=(12, 8))

        self.nome = self._entrada(form, "Nome")
        self.keywords = self._entrada(form, "Palavras-chave (separadas por vírgula)")
        self.exclude = self._entrada(form, "Excluir se aparecer (opcional)")
        ctk.CTkLabel(
            form,
            text='Cuidado: "junior" também casa com "mentor junior engineers".',
            text_color="gray55",
        ).pack(anchor="w", padx=12)

        ctk.CTkLabel(form, text="Fontes (nenhuma marcada = todas)").pack(
            anchor="w", padx=12, pady=(12, 4)
        )
        self.fontes: dict[str, ctk.CTkCheckBox] = {}
        for nome in fabricas.fontes.disponiveis():
            caixa = ctk.CTkCheckBox(form, text=fabricas.fontes.classe(nome).rotulo)
            caixa.pack(anchor="w", padx=16, pady=2)
            self.fontes[nome] = caixa

        self.ativa = ctk.CTkSwitch(form, text="Ativa")
        self.ativa.pack(anchor="w", padx=12, pady=(12, 0))

        botoes = ctk.CTkFrame(form, fg_color="transparent")
        botoes.pack(fill="x", padx=12, pady=12)
        ctk.CTkButton(botoes, text="Salvar", width=90, command=self._salvar).pack(
            side="left"
        )
        ctk.CTkButton(
            botoes,
            text="Nova",
            width=80,
            fg_color="transparent",
            border_width=1,
            command=self._limpar,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            botoes, text="Remover", width=90, fg_color="#B33A3A", command=self._remover
        ).pack(side="right")
        self._limpar()

    @staticmethod
    def _entrada(mestre: Any, rotulo: str) -> ctk.CTkEntry:
        ctk.CTkLabel(mestre, text=rotulo).pack(anchor="w", padx=12)
        entrada = ctk.CTkEntry(mestre)
        entrada.pack(fill="x", padx=12, pady=(0, 8))
        return entrada

    def atualizar(self) -> None:
        self._buscas = {str(b.id): b for b in self.app.repositorio.listar_buscas()}
        self.tabela.preencher(
            [
                (chave, apresentacao.linha_de_busca(b))
                for chave, b in self._buscas.items()
            ]
        )

    def _limpar(self) -> None:
        self._editando = None
        self.titulo.configure(text="Nova busca")
        for entrada in (self.nome, self.keywords, self.exclude):
            entrada.delete(0, "end")
        for caixa in self.fontes.values():
            caixa.deselect()
        self.ativa.select()

    def _carregar_selecionada(self) -> None:
        chave = self.tabela.selecionado()
        busca = self._buscas.get(chave) if chave else None
        if busca is None:
            return
        self._editando = busca.id
        self.titulo.configure(text=f"Editando: {busca.nome}")
        for entrada, valor in (
            (self.nome, busca.nome),
            (self.keywords, ", ".join(busca.keywords)),
            (self.exclude, ", ".join(busca.exclude)),
        ):
            entrada.delete(0, "end")
            entrada.insert(0, valor)
        for nome, caixa in self.fontes.items():
            caixa.select() if nome in busca.fontes else caixa.deselect()
        self.ativa.select() if busca.ativa else self.ativa.deselect()

    def _salvar(self) -> None:
        try:
            busca = Busca(
                id=self._editando,
                nome=self.nome.get().strip(),
                keywords=apresentacao.termos(self.keywords.get()),
                exclude=apresentacao.termos(self.exclude.get()),
                fontes=[nome for nome, caixa in self.fontes.items() if caixa.get()],
                ativa=bool(self.ativa.get()),
            )
        except ValidationError:
            self.app.mostrar_erro(
                ValueError("Dê um nome e ao menos uma palavra-chave.")
            )
            return
        self.app.repositorio.salvar_busca(busca)
        self._limpar()
        self.app.ao_mudar_dados()

    def _remover(self) -> None:
        if self._editando is None:
            return
        self.app.repositorio.remover_busca(self._editando)
        self._limpar()
        self.app.ao_mudar_dados()
