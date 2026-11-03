"""Configuration centralisée, validée au démarrage."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valeur d'exemple publiée dans .env.example : interdite en production.
_EXEMPLE_MOT_DE_PASSE = "change-me"


class Settings(BaseSettings):
    """Paramètres de l'application, lus depuis l'environnement (préfixe HAPPLY_).

    Environnements : `development`, `test`, `production`. Les secrets sont des `SecretStr`
    pour ne jamais apparaître dans les logs ni dans `repr()`.
    """

    model_config = SettingsConfigDict(env_prefix="HAPPLY_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    # ADR-0008 : sans authentification, l'API n'écoute que sur la boucle locale.
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1, le=65535)
    # ADR-0008 : CORS restreint à l'origine du frontend local.
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:3000"])
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    # URL de connexion PostgreSQL (ADR-0004), ex. postgresql://user:motdepasse@127.0.0.1:5432/happly
    database_url: SecretStr | None = None
    # API France Travail (OAuth2). Identifiants absents = source « non configurée ».
    france_travail_client_id: SecretStr | None = None
    france_travail_client_secret: SecretStr | None = None

    @model_validator(mode="after")
    def _verifier_coherence(self) -> Self:
        if "*" in self.cors_allowed_origins:
            raise ValueError("CORS : l'origine générique '*' est interdite (ADR-0008).")
        if self.environment == "production":
            if self.database_url is None:
                raise ValueError("HAPPLY_DATABASE_URL est obligatoire en production.")
            if _EXEMPLE_MOT_DE_PASSE in self.database_url.get_secret_value():
                raise ValueError("Le mot de passe d'exemple est interdit en production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
