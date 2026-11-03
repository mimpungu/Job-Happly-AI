"""Configuration centralisée, validée au démarrage."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres de l'application, lus depuis l'environnement (préfixe HAPPLY_)."""

    model_config = SettingsConfigDict(env_prefix="HAPPLY_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    # ADR-0008 : sans authentification, l'API n'écoute que sur la boucle locale.
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1, le=65535)
    # ADR-0008 : CORS restreint à l'origine du frontend local.
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:3000"])
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
