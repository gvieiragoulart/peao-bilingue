"""Configuration: config.json + the system keyring, with `.env` as a fallback.

The window writes to `data/config.json` (whatever isn't secret) and to the system
keyring (Credential Manager on Windows, Secret Service on Linux). Both beat `.env`;
otherwise a change made on screen would be silently ignored. The CLI and scheduled
collection read the same things.
"""

import json
import os
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal

import keyring
from keyring.errors import NoKeyringError, PasswordDeleteError
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from peao_bilingue.i18n import _


def is_frozen() -> bool:
    """Running from the .exe (PyInstaller), not from the project with `uv run`."""
    return bool(getattr(sys, "frozen", False))


def base_dir() -> Path:
    """Where `data/`, `.env`, `profile_notes.md` and `artifacts/` live.

    In the project, the folder it runs from (the project's). In the .exe, a folder in
    the user's profile that survives reinstalls and doesn't depend on where the .exe
    was opened from.
    """
    if is_frozen():
        if sys.platform.startswith("linux"):
            data_home = os.environ.get("XDG_DATA_HOME") or str(
                Path.home() / ".local" / "share"
            )
            return Path(data_home) / "peao-bilingue"
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "PeaoBilingue"
    return Path.cwd()


BASE_DIR = base_dir()
# PEAO_DATA_DIR wins: it keeps the tests away from the real configuration.
# PEAO_DADOS is its name from before the code was in English.
DATA_DIR = Path(
    os.environ.get("PEAO_DATA_DIR") or os.environ.get("PEAO_DADOS") or BASE_DIR / "data"
)
CONFIG_PATH = DATA_DIR / "config.json"
# What the app saw on a page: evidence of a failed reading and the screenshots asked for
# in a collection.
ARTIFACTS_DIR = BASE_DIR / "artifacts"
ENV_PATH = BASE_DIR / ".env"

KEYRING_SERVICE = "peao-bilingue"
# The download site: CloudFormation's SiteUrl output (infra/site.yaml), no trailing slash.
# Every installed version checks for updates here, so it never changes: a custom domain is
# added to the same CloudFront distribution, and this address keeps working.
SITE_URL = "https://REPLACE-WITH-CLOUDFRONT-DOMAIN.cloudfront.net"
# These fields go to the vault, never to config.json.
SECRETS = frozenset(
    {
        "anthropic_api_key",
        "openai_api_key",
        "gemini_api_key",
        "smtp_pass",
        "twilio_token",
    }
)

# Settings names from before the code was in English (config.json and .env).
LEGACY_NAMES = {
    "fontes_habilitadas": "enabled_sources",
    "llm_analise": "analysis_llm",
    "notificadores": "notifiers",
    "remotive_categoria": "remotive_category",
    "himalayas_pais": "himalayas_country",
    "horario_coleta": "collection_time",
    "anthropic_modelo": "anthropic_model",
    "ollama_modelo": "ollama_model",
    "ollama_contexto": "ollama_context",
    "openai_modelo": "openai_model",
    "gemini_modelo": "gemini_model",
}


def migrate_legacy_names(config_path: Path, env_path: Path) -> None:
    """Renames old setting names in config.json and .env, in place.

    Without this, a renamed setting would quietly fall back to its default (e.g. every
    source turned off). An existing new name always wins over an old one.
    """
    if config_path.exists():
        current = json.loads(config_path.read_text(encoding="utf-8"))
        if current.keys() & LEGACY_NAMES.keys():
            migrated = {
                LEGACY_NAMES.get(name, name): value
                for name, value in current.items()
                if name not in LEGACY_NAMES or LEGACY_NAMES[name] not in current
            }
            config_path.write_text(
                json.dumps(migrated, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        legacy = {old.upper(): new.upper() for old, new in LEGACY_NAMES.items()}
        renamed = []
        for line in lines:
            name, separator, value = line.partition("=")
            if separator and name.strip() in legacy:
                renamed.append(f"{legacy[name.strip()]}={value}")
            else:
                renamed.append(line)
        if renamed != lines:
            env_path.write_text("\n".join(renamed) + "\n", encoding="utf-8")


class _Vault(PydanticBaseSettingsSource):
    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        if field_name not in SECRETS:
            return None, field_name, False
        return _get_secret(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        values = {}
        for name in SECRETS:
            value = _get_secret(name)
            if value:
                values[name] = value
        return values


def _get_secret(name: str) -> str | None:
    """Read a saved key when this session has a configured OS keyring."""
    try:
        return keyring.get_password(KEYRING_SERVICE, name)
    except NoKeyringError:
        # Headless Linux sessions and minimal desktops may not have Secret Service.
        # The rest of the app should still be usable; saving a key reports the issue.
        return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
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
            _Vault(settings_cls),
            env_settings,
            dotenv_settings,
        )

    # Which adapters to use, by the name registered in the factories.
    enabled_sources: list[str] = ["vanhack"]
    # The LLM preselected on the jobs screen; analysis is requested job by job.
    analysis_llm: str = "anthropic"
    # Notices after the scheduled collection. The native notification needs no setup,
    # so it starts on; email and WhatsApp start off: turned on before being filled in,
    # they would record a failed notice on every collection.
    notifiers: list[str] = ["linux" if sys.platform.startswith("linux") else "windows"]

    # VanHack
    # Login is passwordless (magic link / Google / LinkedIn) and guarded by
    # Cloudflare Turnstile, so there are no credentials here: the session always
    # comes from a manual login saved in data/state.json.
    vanhack_login_url: str = "https://auth.vanhack.com"
    vanhack_jobs_url: str = "https://app.vanhack.com/jobs"
    vanhack_profile_url: str = "https://app.vanhack.com/profile"
    headless: bool = True
    browser_channel: str = "chrome"
    max_listing_scrolls: int = 15
    max_details_per_run: int = 15

    # Remotive (public API): one category per call; "software-dev" covers development.
    remotive_category: str = "software-dev"
    # Himalayas (public API): only jobs open to candidates from this country (ISO code)
    # or worldwide; empty = no filter, including US-only jobs.
    himalayas_country: str = "BR"
    # Jobicy (public API): its `geo` filter; "brazil" includes LATAM and anywhere jobs.
    jobicy_geo: str = "brazil"
    # Hacker News "Who is hiring?": only posts naming one of these (without accents).
    # Not "visa": posts say they can't sponsor one as often as they offer it.
    hackernews_places: list[str] = [
        "brazil",
        "brasil",
        "latam",
        "latin america",
        "south america",
        "americas",
        "worldwide",
        "anywhere",
    ]
    # GitHub job repositories (public API): "owner/repo" of each community's board.
    github_job_repositories: list[str] = [
        "backend-br/vagas",
        "phpdevbr/vagas",
        "nodejsdevbr/vagas",
        "frontendbr/vagas",
    ]
    # Company job boards (public ATS APIs): "ats:board[=Company]", the board's name as
    # in its URL; "=Company" names it (Lever and Ashby don't, Greenhouse sometimes oddly).
    company_boards: list[str] = [
        "ashby:nubank=Nubank",
        "greenhouse:stone=Stone",
        "greenhouse:quintoandar=QuintoAndar",
        "greenhouse:gympass=Wellhub",
        "greenhouse:vtex",
        "greenhouse:ebanx",
        "greenhouse:clara=Clara",
        "greenhouse:canonical",
        "lever:toptal=Toptal",
        "lever:dlocal=dLocal",
    ]
    # Only jobs whose location names one of these (without accents); empty = all.
    company_boards_places: list[str] = [
        "brazil",
        "brasil",
        "sao paulo",
        "rio de janeiro",
        "belo horizonte",
        "curitiba",
        "porto alegre",
        "florianopolis",
        "campinas",
        "recife",
        "osasco",
        "barueri",
        "remoto",
        "latam",
        "latin america",
        "south america",
        "americas",
        "worldwide",
        "anywhere",
    ]

    timezone: str = "America/Sao_Paulo"
    collection_time: str = "08:00"

    # LLM providers. OpenAI and Gemini have no default model on purpose: their
    # catalogs change, and a made-up name would only fail at run time.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_context: int = 8192
    openai_api_key: str = ""
    openai_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = ""

    # Analysis: notes that complement the profile in every analysis.
    profile_notes_path: str = "profile_notes.md"

    # The first-run guide: shown until finished or skipped (see ui/onboarding.py).
    onboarding_done: bool = False

    # The window: follow Windows' light/dark mode, or force one.
    appearance: Literal["system", "light", "dark"] = "system"

    # Updates: when the app opens, ask the download site whether there's a newer version
    # ({site_url}/latest.json). The site is also the project page.
    check_for_updates: bool = True
    site_url: str = SITE_URL

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


migrate_legacy_names(CONFIG_PATH, ENV_PATH)
settings = Settings()


def save(changes: dict[str, Any]) -> None:
    """Saves what came from the window: secrets in the vault, the rest in config.json."""
    unknown = changes.keys() - Settings.model_fields.keys()
    if unknown:
        raise KeyError(
            _("Unknown setting: {names}").format(names=", ".join(sorted(unknown)))
        )

    for name in SECRETS & changes.keys():
        if changes[name]:
            keyring.set_password(KEYRING_SERVICE, name, changes[name])
        else:
            with suppress(PasswordDeleteError):
                keyring.delete_password(KEYRING_SERVICE, name)

    public = {name: value for name, value in changes.items() if name not in SECRETS}
    if public:
        current = (
            json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if CONFIG_PATH.exists()
            else {}
        )
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps({**current, **public}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    reload()


def reload() -> None:
    """Reads every source again and updates `settings` in place.

    Several modules do `from peao_bilingue.config import settings`; swapping the object
    wouldn't reach them, so the new values are copied into the same instance.
    """
    new = Settings()
    for name in Settings.model_fields:
        setattr(settings, name, getattr(new, name))
