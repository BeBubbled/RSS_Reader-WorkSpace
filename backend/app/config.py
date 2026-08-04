from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets are intentionally never logged."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_environment: str = "development"
    app_allowed_origins: str = ""
    admin_username: str = "admin"
    admin_password: str = "change-this-before-deploying"
    app_session_secret: str = Field(
        default="replace-with-a-long-random-secret-at-least-32-characters"
    )
    app_encryption_key: str = "replace-with-a-fernet-key-generated-for-this-deployment"
    session_cookie_secure: bool = False
    session_cookie_max_age_seconds: int = 60 * 60 * 24 * 7
    database_url: str = "postgresql+asyncpg://rss_ai:change-this-postgres-password@postgres:5432/rss_ai"
    redis_url: str = "redis://redis:6379/0"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.app_allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def reject_default_production_secrets(self) -> "Settings":
        if self.app_environment.lower() == "production":
            if self.admin_password == "change-this-before-deploying":
                raise ValueError("ADMIN_PASSWORD must be changed in production")
            if self.app_session_secret == "replace-with-a-long-random-secret-at-least-32-characters":
                raise ValueError("APP_SESSION_SECRET must be changed in production")
            if self.app_encryption_key == "replace-with-a-fernet-key-generated-for-this-deployment":
                raise ValueError("APP_ENCRYPTION_KEY must be changed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
