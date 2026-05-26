"""Environment-driven settings for the ai-chat service."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the ai-chat service."""

    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    port: int = Field(default=8012, ge=1, le=65535)

    # Forward-compatible with apps/ai-chat/AGENTS.md. Wired in later commits.
    database_url: str = Field(default="postgresql://khetibadi:khetibadi@postgres:5432/khetibadi")
    redis_url: str = Field(default="redis://redis:6379/0")
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    groq_max_tokens: int = Field(default=1024, ge=1)
    chat_rate_limit_per_minute: int = Field(default=30, ge=1)
    chat_retention_days: int = Field(default=90, ge=1)
    hmac_secret: str = Field(default="")
    ai_chat_allow_fake_llm: bool = Field(default=False)
    farm_service_url: str = Field(default="http://farm-service:8001")
    market_service_url: str = Field(default="http://market-service:8002")
    ml_crop_service_url: str = Field(default="http://ml-crop:8010")
    ml_vision_service_url: str = Field(default="http://ml-vision:8011")


def get_settings() -> Settings:
    return Settings()
