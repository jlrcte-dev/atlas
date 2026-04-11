from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Atlas AI Assistant"
    app_env: str = "development"
    app_host: str = "0.0.0.0"  # noqa: S104  # nosec B104 — bind-all intentional for Docker
    app_port: int = 8000
    database_url: str = "sqlite:///./atlas_assistant.db"
    telegram_bot_token: str = ""
    telegram_allowed_user_id: str = ""
    claude_provider: str = "anthropic"
    claude_model: str = "claude-sonnet-4-5"
    google_mcp_base_url: str = ""
    google_mcp_api_key: str = ""
    rss_default_feeds: str = ""
    timezone: str = "America/Sao_Paulo"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
