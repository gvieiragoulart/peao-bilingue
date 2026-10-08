from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import fabricas
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.perfil import FonteDePerfil
from peao_bilingue.ui.componentes import Tabela

if TYPE_CHECKING:
    from peao_bilingue.ui.app import Aplicativo

NENHUMA = "(nenhuma)"


def fontes_que_leem_perfil() -> list[str]:
    """Fontes ligadas que sabem ler o perfil cadastrado nelas."""
    return [
        nome
        for nome in settings.fontes_habilitadas
        if issubclass(fabricas.fontes.classe(nome), FonteDePerfil)
    ]


class AbaPerfil(ctk.CTkFrame):
    """Um perfil por fonte: o cadastrado na VanHack não é o do LinkedIn."""

    def __init__(self, mestre: Any, app: "Aplicativo") -> None:
        super().__init__(mestre, fg_color="transparent")
        self.app = app

        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(topo, text="Fonte").pack(side="left", padx=(0, 4))
        self.fonte = ctk.CTkOptionMenu(
            topo, values=[NENHUMA], width=140, command=lambda _: self.atualizar()
        )
        self.fonte.pack(side="left", padx=(0, 12))
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
        repositorio = self.app.repositorio
        # As que leem perfil hoje e as que já têm um salvo (mesmo se desligadas).
        fontes = sorted(
            set(fontes_que_leem_perfil()) | set(repositorio.fontes_com_perfil())
        )
        self.fonte.configure(values=fontes or [NENHUMA])
        if self.fonte.get() not in fontes:
            self.fonte.set(fontes[0] if fontes else NENHUMA)
        nome = self.fonte.get()

        salvo = repositorio.ultimo_perfil(nome) if fontes else None
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        if not fontes:
            self.situacao.configure(text="Nenhuma fonte ligada lê perfil.")
        elif salvo is None:
            self.situacao.configure(text=f"Nenhum perfil da fonte {nome} lido ainda.")
            self.texto.insert("1.0", "Clique em Ler perfil agora.")
        else:
            self.situacao.configure(
                text=f"Perfil da fonte {nome}, usado nas análises das vagas dela "
                "(sem dados pessoais):"
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
                for item in (repositorio.historico_perfil(nome) if fontes else [])
            ]
        )

    def _ler(self) -> None:
        nome = self.fonte.get()
        if nome not in fontes_que_leem_perfil():
            self.app.mostrar_erro(
                ValueError(f"A fonte {nome} não está ligada ou não lê perfil.")
            )
            return
        self.botao.configure(state="disabled", text="Lendo…")
        repositorio = self.app.repositorio

        async def ler() -> bool:
            fonte = fabricas.fontes.criar(nome)
            if not isinstance(fonte, FonteDePerfil):  # já filtrado acima
                raise TypeError(f"A fonte {nome} não lê perfil.")
            async with fonte:
                perfil = await fonte.ler_perfil()
            _, mudou = repositorio.salvar_perfil(perfil)
            return mudou

        def terminar(mudou: bool) -> None:
            self.botao.configure(state="normal", text="Ler perfil agora")
            self.app.ao_mudar_dados()
            self.app.informar(
                f"Perfil da fonte {nome} atualizado."
                if mudou
                else "Perfil sem mudanças."
            )

        def falhar(falha: BaseException) -> None:
            self.botao.configure(state="normal", text="Ler perfil agora")
            self.app.mostrar_erro(falha)

        self.app.rodar(ler(), ao_terminar=terminar, ao_falhar=falhar)
