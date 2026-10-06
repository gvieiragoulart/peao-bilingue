from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import fabricas
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.portas import FonteDePerfil
from peao_bilingue.ui.componentes import Tabela

if TYPE_CHECKING:
    from peao_bilingue.ui.app import Aplicativo


def fonte_de_perfil() -> str | None:
    """Primeira fonte ligada que sabe ler o perfil do candidato."""
    for nome in settings.fontes_habilitadas:
        if issubclass(fabricas.fontes.classe(nome), FonteDePerfil):
            return nome
    return None


class AbaPerfil(ctk.CTkFrame):
    def __init__(self, mestre: Any, app: "Aplicativo") -> None:
        super().__init__(mestre, fg_color="transparent")
        self.app = app

        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", pady=(0, 8))
        self.situacao = ctk.CTkLabel(topo, text="")
        self.situacao.pack(side="left")
        self.botao = ctk.CTkButton(
            topo, text="Ler perfil agora", width=140, command=self._ler
        )
        self.botao.pack(side="right")

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True)
        corpo.grid_columnconfigure(0, weight=3)
        corpo.grid_columnconfigure(1, weight=2)
        corpo.grid_rowconfigure(0, weight=1)

        self.texto = ctk.CTkTextbox(corpo, wrap="word")
        self.texto.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.historico = Tabela(
            corpo, [("lido_em", "Lido em", 120), ("campos", "O que mudou", 260)]
        )
        self.historico.grid(row=0, column=1, sticky="nsew")

    def atualizar(self) -> None:
        salvo = self.app.repositorio.ultimo_perfil()
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        if salvo is None:
            self.situacao.configure(text="Nenhum perfil lido ainda.")
            self.texto.insert(
                "1.0", "O perfil é lido da fonte com perfil (hoje, a VanHack)."
            )
        else:
            self.situacao.configure(
                text="Perfil usado nas análises (sem dados pessoais):"
            )
            self.texto.insert("1.0", salvo[1].texto)
        self.texto.configure(state="disabled")

        self.historico.preencher(
            [
                (
                    str(item["id"]),
                    (
                        f"{item['lido_em']:%d/%m/%Y %H:%M}",
                        ", ".join(item["campos_alterados"]),
                    ),
                )
                for item in self.app.repositorio.historico_perfil()
            ]
        )

    def _ler(self) -> None:
        nome = fonte_de_perfil()
        if nome is None:
            self.app.mostrar_erro(ValueError("Nenhuma fonte ligada sabe ler o perfil."))
            return
        self.botao.configure(state="disabled", text="Lendo…")
        repositorio = self.app.repositorio

        async def ler() -> bool:
            fonte = fabricas.fontes.criar(nome)
            async with fonte:
                perfil = await fonte.ler_perfil()
            _, mudou = repositorio.salvar_perfil(perfil)
            return mudou

        def terminar(mudou: bool) -> None:
            self.botao.configure(state="normal", text="Ler perfil agora")
            self.atualizar()
            self.app.informar("Perfil atualizado." if mudou else "Perfil sem mudanças.")

        def falhar(falha: BaseException) -> None:
            self.botao.configure(state="normal", text="Ler perfil agora")
            self.app.mostrar_erro(falha)

        self.app.rodar(ler(), ao_terminar=terminar, ao_falhar=falhar)
