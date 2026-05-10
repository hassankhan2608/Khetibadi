"""Environment-driven settings for the ml-vision service."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the ml-vision service."""

    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    port: int = Field(default=8011, ge=1, le=65535)

    # Forward-compatible with apps/ml-vision/AGENTS.md. Wired in later commits.
    vision_model_path: str = Field(default="models/resnet34_plantvillage.pth")
    redis_url: str = Field(default="redis://redis:6379/0")
    confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    hmac_secret: str = Field(default="")
    ml_allow_stub_mode: bool = Field(default=False)


def get_settings() -> Settings:
    return Settings()
