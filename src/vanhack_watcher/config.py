from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # VanHack
    vanhack_email: str = ""
    vanhack_password: str = ""
    vanhack_login_url: str = "https://app.vanhack.com/login"
    vanhack_jobs_url: str = "https://app.vanhack.com/jobs"
    vanhack_profile_url: str = "https://app.vanhack.com/profile"
    headless: bool = True
    max_listing_scrolls: int = 15
    max_details_per_run: int = 15

    # Agendamento
    schedule_cron: str = "0 8 * * *"
    timezone: str = "America/Sao_Paulo"

    # Análise
    anthropic_api_key: str = ""
    analysis_model: str = "claude-sonnet-5-5"
    profile_notes_path: str = "profile_notes.md"
    reanalyze_on_profile_change: bool = True
    max_reanalyses_on_change: int = 10
    max_analyses_per_run: int = 10

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_pass: str = ""
    email_to: str = ""

    # WhatsApp (Twilio)
    whatsapp_enabled: bool = True
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    whatsapp_to: str = ""

    dry_run: bool = False


settings = Settings()
