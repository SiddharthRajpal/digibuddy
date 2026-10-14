"""Application settings, loaded from environment variables (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DigiBuddy"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://digibuddy:digibuddy@localhost:5432/digibuddy"

    jwt_secret: str = Field(default="change-me-in-production-please-32b", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    cors_origins: list[str] = ["http://localhost:3000"]

    auth_rate_limit_per_minute: int = 10
    refresh_rate_limit_per_minute: int = 120
    # Only enable when the API is reachable solely through a trusted proxy (the frontend).
    trust_forwarded_for: bool = True

    model_artifact_dir: Path = Path("./model_artifacts")

    # ML
    recency_half_life_days: float = 60.0
    baseline_half_life_days: float = 3.0
    backtest_max_days: int = 30
    backtest_fraction: float = 0.25
    interval_coverage: float = 0.8
    promotion_min_improvement: float = 0.02
    gap_revert_days: int = 3
    use_lightgbm: bool = True

    enable_scheduler: bool = True
    nightly_hour_local: int = 3

    default_support_region: str = "INTL"


@lru_cache
def get_settings() -> Settings:
    return Settings()
