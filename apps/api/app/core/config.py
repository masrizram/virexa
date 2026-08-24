"""Application configuration.

All secrets come from environment (Fly secrets in production).
Never hardcode values; .env.example documents names only.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Environment / safety ---
    env: Literal["local", "staging", "production"] = "local"
    dry_run: bool = Field(default=True, alias="DRY_RUN")
    autonomous_mode: bool = Field(default=False, alias="AUTONOMOUS_MODE")
    service_token: str = Field(default="", alias="SERVICE_TOKEN")
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- Database (Neon) ---
    # Pooled URL for runtime; direct URL for migrations/session-level ops.
    app_database_url: str = Field(default="", alias="APP_DATABASE_URL")
    app_database_direct_url: str = Field(default="", alias="APP_DATABASE_DIRECT_URL")

    # --- S3-compatible object storage ---
    s3_endpoint: str = Field(default="", alias="S3_ENDPOINT")
    s3_region: str = Field(default="auto", alias="S3_REGION")
    s3_bucket: str = Field(default="", alias="S3_BUCKET")
    s3_access_key_id: str = Field(default="", alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(default="", alias="S3_SECRET_ACCESS_KEY")

    # --- AI providers (OpenAI-compatible) ---
    openai_compatible_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_COMPATIBLE_BASE_URL")
    openai_compatible_api_key: str = Field(default="", alias="OPENAI_COMPATIBLE_API_KEY")
    glm_api_key: str = Field(default="", alias="GLM_API_KEY")
    kimi_api_key: str = Field(default="", alias="KIMI_API_KEY")
    # Explicitly opt in the deterministic mock provider — tests/dry-run only, never production.
    ai_allow_mock: bool = Field(default=False, alias="AI_ALLOW_MOCK")

    # --- MoneyPrinterTurbo ---
    mpt_base_url: str = Field(default="http://localhost:8080", alias="MPT_BASE_URL")
    mpt_api_secret: str = Field(default="", alias="MPT_API_SECRET")
    mpt_timeout_seconds: float = 30.0
    mpt_poll_interval_seconds: float = 3.0
    mpt_max_poll_seconds: float = 900.0

    # --- Defaults (configurable at runtime via system_settings) ---
    default_brand_name: str = "default"

    def has_ai(self) -> bool:
        return bool(self.openai_compatible_api_key or self.glm_api_key or self.kimi_api_key or self.ai_allow_mock)


@lru_cache
def get_settings() -> Settings:
    return Settings()
