from dataclasses import dataclass, field
from tkinter import ttk
from typing import Any, Literal

import customtkinter as ctk

from peao_bilingue.configuracao import SEGREDOS, Settings

Tipo = Literal["texto", "inteiro", "booleano", "segredo", "opcoes"]


def tipo_do_campo(nome: str) -> Tipo:
    """O tipo do widget sai do próprio Settings: nada de lista paralela para manter."""
    if nome in SEGREDOS:
        return "segredo"
    anotacao = Settings.model_fields[nome].annotation
    if anotacao is bool:
        return "booleano"
    if anotacao is int:
        return "inteiro"
    return "texto"


def cor_do_tema(widget: str, propriedade: str) -> str:
    """O tema guarda [claro, escuro]; escolhe pelo modo atual."""
    par = ctk.ThemeManager.theme[widget][propriedade]
    return par[1] if ctk.get_appearance_mode() == "Dark" else par[0]


class Tabela(ctk.CTkFrame):
    """ttk.Treeview com as cores do tema (o CustomTkinter não tem tabela)."""

    def __init__(
        self, mestre: Any, colunas: list[tuple[str, str, int]], **kwargs: Any
    ) -> None:
        super().__init__(mestre, **kwargs)
        estilo = ttk.Style(self)
        estilo.theme_use("default")
        fundo = cor_do_tema("CTkFrame", "fg_color")
        texto = cor_do_tema("CTkLabel", "text_color")
        destaque = cor_do_tema("CTkButton", "fg_color")
        estilo.configure(
            "Peao.Treeview",
            background=fundo,
            fieldbackground=fundo,
            foreground=texto,
            rowheight=26,
            borderwidth=0,
        )
        estilo.map("Peao.Treeview", background=[("selected", destaque)])
        estilo.configure(
            "Peao.Treeview.Heading", background=fundo, foreground=texto, relief="flat"
        )

        self.arvore = ttk.Treeview(
            self,
            columns=[c[0] for c in colunas],
            show="headings",
            style="Peao.Treeview",
        )
        # Só a coluna mais larga estica (ou encolhe): as outras mantêm a largura,
        # senão as da direita somem pela borda quando o painel é estreito.
        mais_larga = max(colunas, key=lambda coluna: coluna[2])[0]
        for identificador, titulo, largura in colunas:
            self.arvore.heading(identificador, text=titulo, anchor="w")
            self.arvore.column(
                identificador,
                width=largura,
                minwidth=40,
                stretch=identificador == mais_larga,
                anchor="w",
            )
        rolagem = ctk.CTkScrollbar(self, command=self.arvore.yview)
        self.arvore.configure(yscrollcommand=rolagem.set)
        self.arvore.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")

    def preencher(self, linhas: list[tuple[str, tuple[str, ...]]]) -> None:
        """`linhas` = [(id, valores)]; o id volta em `selecionado()`."""
        self.arvore.delete(*self.arvore.get_children())
        for identificador, valores in linhas:
            self.arvore.insert("", "end", iid=identificador, values=valores)

    def selecionado(self) -> str | None:
        selecao = self.arvore.selection()
        return selecao[0] if selecao else None

    def ao_selecionar(self, callback: Any) -> None:
        self.arvore.bind("<<TreeviewSelect>>", lambda _evento: callback())


@dataclass
class Campo:
    nome: str  # nome do campo em Settings
    rotulo: str
    tipo: Tipo = "texto"
    opcoes: list[str] = field(default_factory=list)


def campos_do_adapter(classe: Any) -> list[Campo]:
    """Formulário de um adapter a partir do que ele declara em `campos`."""
    return [
        Campo(nome, rotulo, tipo_do_campo(nome))
        for nome, rotulo in classe.campos.items()
    ]


class Formulario(ctk.CTkFrame):
    """Formulário ligado aos campos de Settings: carrega e devolve os valores tipados."""

    def __init__(self, mestre: Any, campos: list[Campo], **kwargs: Any) -> None:
        super().__init__(mestre, **kwargs)
        self.campos = campos
        self._widgets: dict[str, Any] = {}
        self.grid_columnconfigure(1, weight=1)
        for linha, campo in enumerate(campos):
            ctk.CTkLabel(self, text=campo.rotulo, anchor="w").grid(
                row=linha, column=0, sticky="w", padx=(8, 12), pady=4
            )
            self._widgets[campo.nome] = self._criar(campo)
            self._widgets[campo.nome].grid(
                row=linha, column=1, sticky="ew", padx=(0, 8), pady=4
            )

    def _criar(self, campo: Campo) -> Any:
        if campo.tipo == "booleano":
            return ctk.CTkSwitch(self, text="")
        if campo.tipo == "opcoes":
            return ctk.CTkOptionMenu(self, values=campo.opcoes)
        return ctk.CTkEntry(self, show="•" if campo.tipo == "segredo" else "")

    def carregar(self, configuracao: Settings) -> None:
        for campo in self.campos:
            valor = getattr(configuracao, campo.nome)
            widget = self._widgets[campo.nome]
            if campo.tipo == "booleano":
                widget.select() if valor else widget.deselect()
            elif campo.tipo == "opcoes":
                widget.set(str(valor) if valor else campo.opcoes[0])
            else:
                widget.delete(0, "end")
                widget.insert(0, "" if valor is None else str(valor))

    def valores(self) -> dict[str, Any]:
        """Lê os widgets já convertidos; inteiro inválido vira ValueError legível."""
        valores: dict[str, Any] = {}
        for campo in self.campos:
            widget = self._widgets[campo.nome]
            if campo.tipo == "booleano":
                valores[campo.nome] = bool(widget.get())
            elif campo.tipo == "inteiro":
                texto = widget.get().strip()
                try:
                    valores[campo.nome] = int(texto)
                except ValueError:
                    raise ValueError(
                        f"'{campo.rotulo}' precisa ser um número inteiro."
                    ) from None
            else:
                valores[campo.nome] = widget.get().strip()
        return valores
