"""Configuração: config.json + cofre do Windows, com o .env como fallback.

A interface grava em `data/config.json` (o que não é segredo) e no keyring (no
Windows, o Cofre de Credenciais). Os dois vencem o `.env`: senão uma alteração
feita na tela seria ignorada em silêncio. CLI e tarefa agendada leem o mesmo.
"""

import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Any

import keyring
from keyring.errors import PasswordDeleteError
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# PEAO_DADOS isola os testes da configuração real e servirá ao .exe (Fase 8).
DIRETORIO_DADOS = Path(os.environ.get("PEAO_DADOS", "data"))
CONFIG_PATH = DIRETORIO_DADOS / "config.json"

SERVICO_KEYRING = "peao-bilingue"
# Estes campos vão para o cofre, nunca para o config.json.
SEGREDOS = frozenset(
    {
        "anthropic_api_key",
        "openai_api_key",
        "gemini_api_key",
        "smtp_pass",
        "twilio_token",
    }
)


class _Cofre(PydanticBaseSettingsSource):
    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        if field_name not in SEGREDOS:
            return None, field_name, False
        return keyring.get_password(SERVICO_KEYRING, field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        valores = {}
        for nome in SEGREDOS:
            valor = keyring.get_password(SERVICO_KEYRING, nome)
            if valor:
                valores[nome] = valor
        return valores


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        json_file=CONFIG_PATH,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            JsonConfigSettingsSource(settings_cls),
            _Cofre(settings_cls),
            env_settings,
            dotenv_settings,
        )

    # Quais adapters usar, pelo nome registrado nas fábricas.
    fontes_habilitadas: list[str] = ["vanhack"]
    # O LLM que já vem escolhido na tela de vagas; a análise é pedida vaga a vaga.
    llm_analise: str = "anthropic"
    # Avisos de vagas novas após a coleta agendada. Começam desligados: ligar um
    # canal sem preenchê-lo faria toda coleta registrar a falha do aviso.
    notificadores: list[str] = []

    # VanHack
    # O login é passwordless (magic link / Google / LinkedIn) e protegido por
    # Cloudflare Turnstile, então não há credenciais aqui: a sessão vem sempre
    # de um login manual salvo em data/state.json.
    vanhack_login_url: str = "https://auth.vanhack.com"
    vanhack_jobs_url: str = "https://app.vanhack.com/jobs"
    vanhack_profile_url: str = "https://app.vanhack.com/profile"
    headless: bool = True
    browser_channel: str = "chrome"
    max_listing_scrolls: int = 15
    max_details_per_run: int = 15

    timezone: str = "America/Sao_Paulo"
    horario_coleta: str = "08:00"

    # Provedores de LLM. OpenAI e Gemini não têm modelo padrão de propósito:
    # o catálogo deles muda, e um nome inventado falharia só na hora de rodar.
    anthropic_api_key: str = ""
    anthropic_modelo: str = "claude-sonnet-5-5"
    ollama_host: str = "http://localhost:11434"
    ollama_modelo: str = "qwen3:8b"
    ollama_contexto: int = 8192
    openai_api_key: str = ""
    openai_modelo: str = ""
    gemini_api_key: str = ""
    gemini_modelo: str = ""

    # Análise: notas que complementam o perfil em toda análise.
    profile_notes_path: str = "profile_notes.md"

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_pass: str = ""
    email_to: str = ""

    # WhatsApp (Twilio)
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    whatsapp_to: str = ""


settings = Settings()


def salvar(alteracoes: dict[str, Any]) -> None:
    """Grava o que veio da interface: segredos no cofre, o resto no config.json."""
    desconhecidos = alteracoes.keys() - Settings.model_fields.keys()
    if desconhecidos:
        raise KeyError(f"Configuração desconhecida: {', '.join(sorted(desconhecidos))}")

    for nome in SEGREDOS & alteracoes.keys():
        if alteracoes[nome]:
            keyring.set_password(SERVICO_KEYRING, nome, alteracoes[nome])
        else:
            with suppress(PasswordDeleteError):
                keyring.delete_password(SERVICO_KEYRING, nome)

    publicos = {
        nome: valor for nome, valor in alteracoes.items() if nome not in SEGREDOS
    }
    if publicos:
        atual = (
            json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if CONFIG_PATH.exists()
            else {}
        )
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps({**atual, **publicos}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    recarregar()


def recarregar() -> None:
    """Relê todas as fontes e atualiza `settings` no lugar.

    Vários módulos fazem `from configuracao import settings`; trocar o objeto não
    chegaria a eles, então os valores novos são copiados para a mesma instância.
    """
    novo = Settings()
    for nome in Settings.model_fields:
        setattr(settings, nome, getattr(novo, nome))
