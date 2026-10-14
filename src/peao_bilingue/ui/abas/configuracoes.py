from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import configuracao, fabricas
from peao_bilingue.configuracao import settings
from peao_bilingue.ui.componentes import Campo, Formulario, campos_do_adapter

if TYPE_CHECKING:
    from peao_bilingue.ui.app import Aplicativo

LIMITES = [
    Campo("max_details_per_run", "Vagas detalhadas por fonte, por execução", "inteiro"),
    Campo("max_listing_scrolls", "Rolagens máximas da listagem", "inteiro"),
    Campo("headless", "Navegador escondido durante a coleta", "booleano"),
    Campo("profile_notes_path", "Arquivo de notas do perfil"),
]


class AbaConfiguracoes(ctk.CTkScrollableFrame):
    def __init__(self, mestre: Any, app: "Aplicativo") -> None:
        super().__init__(mestre, fg_color="transparent")
        self.app = app

        self._titulo("Limites da coleta")
        self.limites = Formulario(self, LIMITES)
        self.limites.pack(fill="x", pady=(6, 16))

        self._titulo("Avisos")
        ctk.CTkLabel(
            self,
            text="Depois da coleta agendada, um resumo das vagas novas (título, fonte e "
            "link) pelos canais ligados — e um aviso se algo falhar, como a sessão de "
            "uma fonte vencida. Ligue só os que já estiverem preenchidos.",
            wraplength=900,
            justify="left",
            text_color="gray55",
        ).pack(anchor="w")
        self.ligados: dict[str, ctk.CTkSwitch] = {}
        self.formularios = [self.limites]
        for nome in fabricas.notificadores.disponiveis():
            classe = fabricas.notificadores.classe(nome)
            chave = ctk.CTkSwitch(self, text=classe.rotulo)
            chave.pack(anchor="w", pady=(8, 2))
            self.ligados[nome] = chave
            formulario = Formulario(self, campos_do_adapter(classe))
            formulario.pack(fill="x", pady=(0, 8))
            self.formularios.append(formulario)

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
        for nome, chave in self.ligados.items():
            chave.select() if nome in settings.notificadores else chave.deselect()

    def _salvar(self) -> None:
        try:
            alteracoes = {}
            for formulario in self.formularios:
                alteracoes.update(formulario.valores())
        except ValueError as falha:
            self.app.mostrar_erro(falha)
            return
        alteracoes["notificadores"] = [
            n for n, chave in self.ligados.items() if chave.get()
        ]
        configuracao.salvar(alteracoes)
        self.app.informar("Configurações salvas.")
