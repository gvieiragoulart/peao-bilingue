from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Quais adapters usar, pelo nome registrado nas fábricas.
    fontes_habilitadas: list[str] = ["vanhack"]
    llm_analise: str = "anthropic"
    # Opcional: um LLM barato (ex.: "ollama") dá uma nota rápida a cada vaga nova,
    # e só as que passam do limiar seguem para a análise completa.
    llm_triagem: str | None = None
    limiar_triagem: int = 60
    notificadores: list[str] = ["email", "whatsapp"]

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

    # Análise
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
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    whatsapp_to: str = ""

    dry_run: bool = False


settings = Settings()
