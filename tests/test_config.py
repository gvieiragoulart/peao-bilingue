import json
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path

import keyring
import pytest

from peao_bilingue import config
from peao_bilingue.config import KEYRING_SERVICE, Settings, settings


@pytest.fixture(autouse=True)
def clean_config() -> Iterator[None]:
    """Each test starts with no config.json and an empty vault."""
    config.CONFIG_PATH.unlink(missing_ok=True)
    for name in config.SECRETS:
        with suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(KEYRING_SERVICE, name)
    yield
    config.CONFIG_PATH.unlink(missing_ok=True)
    config.reload()


def test_tests_do_not_use_real_data_dir() -> None:
    assert config.DATA_DIR.name != "data"
    assert "peao-tests-" in str(config.DATA_DIR)


def test_defaults() -> None:
    default = Settings(_env_file=None)
    assert default.vanhack_login_url == "https://auth.vanhack.com"
    assert default.timezone == "America/Sao_Paulo"
    # Windows needs no setup; email and WhatsApp are turned on by hand, filled in
    assert default.notifiers == ["windows"]


def test_save_puts_public_in_json_and_secrets_in_vault() -> None:
    config.save({"analysis_llm": "ollama", "openai_api_key": "sk-test"})

    recorded = json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))
    assert recorded == {"analysis_llm": "ollama"}  # the key stays out of the file
    assert keyring.get_password(KEYRING_SERVICE, "openai_api_key") == "sk-test"


def test_save_updates_already_imported_settings() -> None:
    # several modules do `from peao_bilingue.config import settings`
    config.save({"max_details_per_run": 7, "gemini_api_key": "g-test"})
    assert settings.max_details_per_run == 7
    assert settings.gemini_api_key == "g-test"


def test_config_json_beats_env(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("ANALYSIS_LLM=openai\nMAX_DETAILS_PER_RUN=3\n", encoding="utf-8")
    config.CONFIG_PATH.write_text(
        json.dumps({"analysis_llm": "gemini"}), encoding="utf-8"
    )

    read = Settings(_env_file=env)

    assert read.analysis_llm == "gemini"  # a change made on screen isn't ignored
    assert read.max_details_per_run == 3  # what the screen didn't touch comes from .env


def test_vault_beats_env_but_empty_falls_back(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "ANTHROPIC_API_KEY=from-env\nOPENAI_API_KEY=from-env\n", encoding="utf-8"
    )
    keyring.set_password(KEYRING_SERVICE, "anthropic_api_key", "from-vault")

    read = Settings(_env_file=env)

    assert read.anthropic_api_key == "from-vault"
    assert read.openai_api_key == "from-env"


def test_clearing_secret_removes_it_from_vault() -> None:
    config.save({"smtp_pass": "password"})
    config.save({"smtp_pass": ""})
    assert keyring.get_password(KEYRING_SERVICE, "smtp_pass") is None


def test_save_preserves_existing_json() -> None:
    config.save({"analysis_llm": "ollama"})
    config.save({"max_details_per_run": 7})
    recorded = json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))
    assert recorded == {"analysis_llm": "ollama", "max_details_per_run": 7}


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(KeyError, match="does_not_exist"):
        config.save({"does_not_exist": 1})


def test_project_base_dir_is_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)
    assert config.base_dir() == Path.cwd()


def test_frozen_base_dir_is_user_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the .exe can be opened from any folder: the data can't depend on it
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert config.base_dir() == tmp_path / "PeaoBilingue"


# --- names from before the code was in English ---------------------------------------


def test_legacy_config_names_are_renamed_in_place(tmp_path: Path) -> None:
    # Without this, the user's enabled sources would quietly fall back to the default.
    saved = tmp_path / "config.json"
    saved.write_text(
        json.dumps(
            {"fontes_habilitadas": ["remotive", "vanhack"], "llm_analise": "anthropic"}
        ),
        encoding="utf-8",
    )

    config.migrate_legacy_names(saved, tmp_path / "missing.env")

    assert json.loads(saved.read_text(encoding="utf-8")) == {
        "enabled_sources": ["remotive", "vanhack"],
        "analysis_llm": "anthropic",
    }


def test_a_new_name_already_there_wins_over_the_old_one(tmp_path: Path) -> None:
    saved = tmp_path / "config.json"
    saved.write_text(
        json.dumps({"llm_analise": "openai", "analysis_llm": "ollama"}),
        encoding="utf-8",
    )
    config.migrate_legacy_names(saved, tmp_path / "missing.env")
    assert json.loads(saved.read_text(encoding="utf-8")) == {"analysis_llm": "ollama"}


def test_legacy_env_names_are_renamed_and_the_rest_is_kept(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\nHIMALAYAS_PAIS=PT\nTIMEZONE=America/Sao_Paulo\n", encoding="utf-8"
    )

    config.migrate_legacy_names(tmp_path / "missing.json", env)

    assert env.read_text(encoding="utf-8") == (
        "# comment\nHIMALAYAS_COUNTRY=PT\nTIMEZONE=America/Sao_Paulo\n"
    )
