"""Environment-driven settings for the ml-crop service.

Loaded once at startup. Values come from process environment (and optionally a
local ``.env`` file at the repo root in development). Production environments
inject configuration via the runtime, not files.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the ml-crop service."""

    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="development", description="Deployment environment.")
    log_level: str = Field(default="INFO", description="Root logger level.")
    port: int = Field(default=8010, ge=1, le=65535, description="HTTP listen port.")

    # Model paths are wired in later commits. Declared here so the Settings
    # surface is forward-compatible with apps/ml-crop/AGENTS.md.
    crop_model_path: str = Field(default="models/crop_model.pkl")
    yield_model_path: str = Field(default="models/yield_model.pkl")
    fertilizer_model_path: str = Field(default="models/fertilizer_model.pkl")
    hmac_secret: str = Field(default="")
    ml_allow_stub_mode: bool = Field(default=False)


def get_settings() -> Settings:
    """Return a fresh Settings instance.

    Kept as a function (not a module-level singleton) so tests can monkeypatch
    the environment and re-construct cleanly.
    """

    return Settings()
