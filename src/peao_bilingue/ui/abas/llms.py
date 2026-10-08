from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import configuracao, fabricas
from peao_bilingue.configuracao import settings
from peao_bilingue.ui.componentes import Campo, Formulario, campos_do_adapter

if TYPE_CHECKING:
    from peao_bilingue.ui.app import Aplicativo


class AbaLLMs(ctk.CTkScrollableFrame):
    def __init__(self, mestre: Any, app: "Aplicativo") -> None:
        super().__init__(mestre, fg_color="transparent")
        self.app = app
        provedores = fabricas.llms.disponiveis()

        self._titulo("Quem analisa")
        ctk.CTkLabel(
            self,
            text="A coleta não chama LLM nenhum: a análise é pedida vaga a vaga, na aba "
            "Vagas, com o LLM escolhido lá. O padrão abaixo é o que já vem selecionado.",
            wraplength=900,
            justify="left",
            text_color="gray55",
        ).pack(anchor="w")
        self.geral = Formulario(
            self,
            [Campo("llm_analise", "LLM padrão", "opcoes", opcoes=provedores)],
        )
        self.geral.pack(fill="x", pady=(6, 16))

        self.formularios = [self.geral]
        for nome in provedores:
            classe = fabricas.llms.classe(nome)
            self._titulo(classe.rotulo)
            formulario = Formulario(self, campos_do_adapter(classe))
            formulario.pack(fill="x", pady=(6, 16))
            self.formularios.append(formulario)

        ctk.CTkLabel(
            self,
            text="As chaves ficam no Cofre de Credenciais do Windows, não em arquivo.",
            text_color="gray55",
        ).pack(anchor="w")
        ctk.CTkButton(self, text="Salvar", width=120, command=self._salvar).pack(
            anchor="w", pady=12
        )

    def _titulo(self, texto: str) -> None:
        ctk.CTkLabel(self, text=texto, font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w"
        )

    def atualizar(self) -> None:
        for formulario in self.formularios:
            formulario.carregar(settings)

    def _salvar(self) -> None:
        try:
            alteracoes = {}
            for formulario in self.formularios:
                alteracoes.update(formulario.valores())
        except ValueError as falha:
            self.app.mostrar_erro(falha)
            return
        configuracao.salvar(alteracoes)
        # A aba Vagas mostra o LLM padrão no seletor.
        self.app.ao_mudar_dados()
        self.app.informar("Configuração dos LLMs salva.")
