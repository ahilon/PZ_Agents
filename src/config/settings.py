"""Application settings and configuration"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

    # API Keys
    OPENAI_API_KEY: str = ""

    # Model Configuration
    DEFAULT_MODEL: str = "gpt-4o"
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 2000

    # Logging
    LOG_LEVEL: str = "INFO"

    # Agent execution
    AGENT_TIMEOUT_SECONDS: float = 120.0

    # Git Bot Identity
    GIT_BOT_NAME: str = "agents-bot"
    GIT_BOT_EMAIL: str = "agents-bot@users.noreply.github.com"
    GIT_BOT_TOKEN: str = ""


settings = Settings()
