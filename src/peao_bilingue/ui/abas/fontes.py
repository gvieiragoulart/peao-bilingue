from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import configuracao, fabricas
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.portas import FonteDePerfil, SessaoManual

if TYPE_CHECKING:
    from peao_bilingue.ui.app import Aplicativo

SITUACAO_SESSAO = {
    0: "Sessão válida",
    1: "Sem sessão: faça o login",
    2: "Bloqueado por verificação humana",
}


class AbaFontes(ctk.CTkScrollableFrame):
    def __init__(self, mestre: Any, app: "Aplicativo") -> None:
        super().__init__(mestre, fg_color="transparent")
        self.app = app
        self.chaves: dict[str, ctk.CTkSwitch] = {}

        ctk.CTkLabel(
            self,
            text="Fontes ligadas entram na coleta. As que exigem conta usam login manual: "
            "o robô nunca preenche o login nem resolve verificação humana.",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        for nome in fabricas.fontes.disponiveis():
            self._linha(nome)

    def _linha(self, nome: str) -> None:
        classe = fabricas.fontes.classe(nome)
        cartao = ctk.CTkFrame(self)
        cartao.pack(fill="x", pady=4)

        chave = ctk.CTkSwitch(cartao, text=classe.rotulo, command=self._salvar)
        chave.pack(side="left", padx=12, pady=12)
        self.chaves[nome] = chave

        recursos = []
        if classe.precisa_navegador:
            recursos.append("navegador")
        if issubclass(classe, FonteDePerfil):
            recursos.append("lê o seu perfil")
        if recursos:
            ctk.CTkLabel(cartao, text=" · ".join(recursos), text_color="gray55").pack(
                side="left"
            )

        if issubclass(classe, SessaoManual):
            situacao = ctk.CTkLabel(cartao, text="")
            situacao.pack(side="right", padx=12)
            ctk.CTkButton(
                cartao,
                text="Verificar sessão",
                width=130,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._verificar(classe, situacao),
            ).pack(side="right")
            ctk.CTkButton(
                cartao,
                text="Fazer login",
                width=110,
                command=lambda: self._login(classe, situacao),
            ).pack(side="right", padx=6)

    def atualizar(self) -> None:
        for nome, chave in self.chaves.items():
            chave.select() if nome in settings.fontes_habilitadas else chave.deselect()

    def _salvar(self) -> None:
        ligadas = [nome for nome, chave in self.chaves.items() if chave.get()]
        configuracao.salvar({"fontes_habilitadas": ligadas})

    def _login(self, classe: type[SessaoManual], situacao: ctk.CTkLabel) -> None:
        situacao.configure(
            text="Janela de login aberta: siga as instruções no registro"
        )

        def falhar(falha: BaseException) -> None:
            situacao.configure(text="Login não concluído")
            self.app.mostrar_erro(falha)

        self.app.rodar(
            classe.login_manual(self.app.registrar),
            ao_terminar=lambda _r: situacao.configure(text="Login concluído"),
            ao_falhar=falhar,
        )

    def _verificar(self, classe: type[SessaoManual], situacao: ctk.CTkLabel) -> None:
        situacao.configure(text="Verificando…")
        self.app.rodar(
            classe.verificar_sessao(self.app.registrar),
            ao_terminar=lambda codigo: situacao.configure(
                text=SITUACAO_SESSAO.get(codigo, "?")
            ),
            ao_falhar=self.app.mostrar_erro,
        )
