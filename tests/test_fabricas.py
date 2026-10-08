import pytest

from peao_bilingue import fabricas
from peao_bilingue.adaptadores.fontes.vanhack.fonte import VanHack
from peao_bilingue.adaptadores.llm.anthropic import Anthropic
from peao_bilingue.dominio.coleta import FonteDeVagas
from peao_bilingue.dominio.erros import NomeDesconhecido
from peao_bilingue.dominio.vagas import Vaga, VagaResumo


def test_adapters_reais_estao_registrados() -> None:
    assert "vanhack" in fabricas.fontes.disponiveis()
    assert "anthropic" in fabricas.llms.disponiveis()
    assert {"email", "whatsapp"} <= set(fabricas.notificadores.disponiveis())


def test_cria_pelo_nome_com_configuracao() -> None:
    fonte = fabricas.fontes.criar("vanhack", headless=False)
    assert isinstance(fonte, VanHack) and fonte.headless is False

    provedor = fabricas.llms.criar(
        "anthropic", modelo="claude-haiku-4-5", api_key="teste"
    )
    assert isinstance(provedor, Anthropic) and provedor.modelo == "claude-haiku-4-5"


def test_nome_desconhecido_lista_os_disponiveis() -> None:
    with pytest.raises(NomeDesconhecido, match="vanhack"):
        fabricas.fontes.criar("linkedn")


def test_registro_novo_aparece_e_cria() -> None:
    registro = fabricas.Registro[FonteDeVagas]("Fonte de teste")

    @registro.registrar("minha")
    class Minha(FonteDeVagas):
        nome = rotulo = "minha"

        async def buscar(self, termo: str) -> list[VagaResumo]:
            return []

        async def detalhar(self, resumo: VagaResumo) -> Vaga:
            raise NotImplementedError

    assert "minha" in registro.disponiveis()
    assert isinstance(registro.criar("minha"), Minha)


def test_nome_repetido_e_recusado() -> None:
    registro = fabricas.Registro[object]("Teste")
    registro.registrar("x")(type("A", (), {}))
    with pytest.raises(ValueError, match="duas vezes"):
        registro.registrar("x")(type("B", (), {}))


def test_porta_incompleta_nem_instancia() -> None:
    # é isso que faz da ABC uma interface de verdade
    class SemDetalhar(FonteDeVagas):
        nome = rotulo = "incompleta"

        async def buscar(self, termo: str) -> list[VagaResumo]:
            return []

    with pytest.raises(TypeError, match="detalhar"):
        SemDetalhar()  # type: ignore[abstract]  # é o que o teste prova
