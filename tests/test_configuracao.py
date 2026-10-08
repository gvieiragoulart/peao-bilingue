import json

import keyring
import pytest

from peao_bilingue import configuracao
from peao_bilingue.configuracao import SERVICO_KEYRING, Settings, settings


@pytest.fixture(autouse=True)
def configuracao_limpa():
    """Cada teste começa sem config.json e com o cofre vazio."""
    configuracao.CONFIG_PATH.unlink(missing_ok=True)
    for nome in configuracao.SEGREDOS:
        try:
            keyring.delete_password(SERVICO_KEYRING, nome)
        except keyring.errors.PasswordDeleteError:
            pass
    yield
    configuracao.CONFIG_PATH.unlink(missing_ok=True)
    configuracao.recarregar()


def test_testes_nao_usam_a_pasta_de_dados_real():
    assert configuracao.DIRETORIO_DADOS.name != "data"
    assert "peao-testes-" in str(configuracao.DIRETORIO_DADOS)


def test_padroes():
    padrao = Settings(_env_file=None)
    assert padrao.vanhack_login_url == "https://auth.vanhack.com"
    assert padrao.timezone == "America/Sao_Paulo"
    assert padrao.notificadores == []  # cada canal é ligado à mão, já preenchido


def test_salvar_grava_publico_no_json_e_segredo_no_cofre():
    configuracao.salvar({"llm_analise": "ollama", "openai_api_key": "sk-teste"})

    gravado = json.loads(configuracao.CONFIG_PATH.read_text(encoding="utf-8"))
    assert gravado == {"llm_analise": "ollama"}  # a chave não vai para o arquivo
    assert keyring.get_password(SERVICO_KEYRING, "openai_api_key") == "sk-teste"


def test_salvar_atualiza_o_settings_que_os_modulos_ja_importaram():
    # vários módulos fazem `from configuracao import settings`
    configuracao.salvar({"max_details_per_run": 7, "gemini_api_key": "g-teste"})
    assert settings.max_details_per_run == 7
    assert settings.gemini_api_key == "g-teste"


def test_config_json_vence_o_env(tmp_path):
    env = tmp_path / ".env"
    env.write_text("LLM_ANALISE=openai\nMAX_DETAILS_PER_RUN=3\n", encoding="utf-8")
    configuracao.CONFIG_PATH.write_text(
        json.dumps({"llm_analise": "gemini"}), encoding="utf-8"
    )

    lido = Settings(_env_file=env)

    assert lido.llm_analise == "gemini"  # alteração feita na tela não é ignorada
    assert lido.max_details_per_run == 3  # o que a tela não mexeu ainda vem do .env


def test_cofre_vence_o_env_mas_vazio_cai_no_env(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "ANTHROPIC_API_KEY=do-env\nOPENAI_API_KEY=do-env\n", encoding="utf-8"
    )
    keyring.set_password(SERVICO_KEYRING, "anthropic_api_key", "do-cofre")

    lido = Settings(_env_file=env)

    assert lido.anthropic_api_key == "do-cofre"
    assert lido.openai_api_key == "do-env"


def test_apagar_segredo_remove_do_cofre():
    configuracao.salvar({"smtp_pass": "senha"})
    configuracao.salvar({"smtp_pass": ""})
    assert keyring.get_password(SERVICO_KEYRING, "smtp_pass") is None


def test_salvar_preserva_o_que_ja_estava_no_json():
    configuracao.salvar({"llm_analise": "ollama"})
    configuracao.salvar({"max_details_per_run": 7})
    gravado = json.loads(configuracao.CONFIG_PATH.read_text(encoding="utf-8"))
    assert gravado == {"llm_analise": "ollama", "max_details_per_run": 7}


def test_campo_desconhecido_e_recusado():
    with pytest.raises(KeyError, match="nao_existe"):
        configuracao.salvar({"nao_existe": 1})
