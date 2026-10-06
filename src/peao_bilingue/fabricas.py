"""Fábricas de adapters, baseadas em registro.

Cada adapter se registra com um decorator; quem cria só conhece o nome.
A interface lista o que está disponível sem importar nenhuma classe concreta.
"""

import importlib
from collections.abc import Callable
from functools import cache

from peao_bilingue.dominio.erros import NomeDesconhecido
from peao_bilingue.dominio.portas import FonteDeVagas, Notificador, ProvedorLLM


@cache
def carregar_adaptadores() -> None:
    """Importa o pacote de adapters, o que dispara os registros."""
    importlib.import_module("peao_bilingue.adaptadores")


class Registro[T]:
    def __init__(self, tipo: str) -> None:
        self.tipo = tipo
        self._classes: dict[str, type[T]] = {}

    def registrar(self, nome: str) -> Callable[[type[T]], type[T]]:
        def decorador(classe: type[T]) -> type[T]:
            if nome in self._classes:
                raise ValueError(f"{self.tipo} {nome!r} registrado duas vezes")
            self._classes[nome] = classe
            return classe

        return decorador

    def classe(self, nome: str) -> type[T]:
        carregar_adaptadores()
        try:
            return self._classes[nome]
        except KeyError:
            disponiveis = ", ".join(self.disponiveis()) or "nenhum"
            raise NomeDesconhecido(
                f"{self.tipo} desconhecido: {nome!r}. Disponíveis: {disponiveis}."
            ) from None

    def criar(self, nome: str, **config: object) -> T:
        return self.classe(nome)(**config)

    def disponiveis(self) -> list[str]:
        carregar_adaptadores()
        return sorted(self._classes)


fontes: Registro[FonteDeVagas] = Registro("Fonte de vagas")
llms: Registro[ProvedorLLM] = Registro("Provedor de LLM")
notificadores: Registro[Notificador] = Registro("Notificador")
