"""Configuration centralisée, validée au démarrage."""

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
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
    # Limites de requêtes (TASK-018-06) : généreuses pour un usage local, utiles contre une boucle
    # folle d'interface ou un script ; plus basses pour les routes coûteuses (IA, génération).
    rate_limit_per_minute: int = Field(default=600, ge=1)
    rate_limit_expensive_per_minute: int = Field(default=30, ge=1)
    # Moteur d'automatisation embarqué : exécute les tâches que l'utilisateur a planifiées ou
    # déclenchées (EPIC 015). Sans tâche planifiée, il ne fait rien.
    worker_enabled: bool = True
    worker_tick_seconds: float = Field(default=30.0, ge=1.0)
    # Taille maximale annoncée d'une requête (l'import de CV est borné plus finement par sa route).
    max_request_body_mb: int = Field(default=12, ge=1, le=100)
    # URL de connexion PostgreSQL (ADR-0004), ex. postgresql://user:motdepasse@127.0.0.1:5432/happly
    database_url: SecretStr | None = None
    # API France Travail (OAuth2). Identifiants absents = source « non configurée ».
    france_travail_client_id: SecretStr | None = None
    france_travail_client_secret: SecretStr | None = None
    # Gemini (Google AI Studio). Clé absente = fournisseur non configuré. Le palier est « free »
    # par défaut : on suppose le pire (contenus réutilisables) tant que l'utilisateur n'a pas
    # déclaré un compte de facturation.
    gemini_api_key: SecretStr | None = None
    gemini_tier: Literal["free", "paid"] = "free"
    gemini_model_level1: str = "gemini-3.1-flash-lite"
    gemini_model_level2: str = "gemini-3-flash-preview"
    # Niveau de réflexion demandé. « minimal » : sans cela, ces modèles dépensent le budget de
    # tokens en réflexion et renvoient une réponse vide ou coupée (constaté le 2026-11-04).
    gemini_thinking_level: str = "minimal"
    # Modèle local (Ollama). Désactivé par défaut ; l'adresse doit rester sur la boucle locale.
    ollama_enabled: bool = False
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model_level1: str = "gemma4:e4b"
    ollama_model_level2: str = "gemma4:12b"
    # Stockage documentaire et compilation LaTeX (EPIC 012 / ADR-0007)
    storage_dir: str = "storage"
    # None : recherche automatique (PATH puis emplacements usuels TeX Live / MacTeX).
    pdflatex_path: str | None = None
    latex_timeout_seconds: float = 15.0
    latex_memory_limit_mb: int = 1024

    @field_validator(
        "gemini_api_key",
        "france_travail_client_id",
        "france_travail_client_secret",
        mode="before",
    )
    @classmethod
    def _vide_vaut_absent(cls, valeur: object) -> object:
        """Une variable présente mais vide (docker compose) signifie « non configuré »."""
        if isinstance(valeur, str) and not valeur.strip():
            return None
        return valeur

    @model_validator(mode="after")
    def _verifier_coherence(self) -> Self:
        hote = urlsplit(self.ollama_url).hostname
        # `host.docker.internal` : la machine hôte, vue depuis le conteneur de l'API.
        if hote not in {"127.0.0.1", "localhost", "::1", "host.docker.internal"}:
            raise ValueError(
                "HAPPLY_OLLAMA_URL doit pointer vers la boucle locale : un modèle « local » "
                "ne doit jamais être distant."
            )
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
