"""Fournisseurs IA disponibles, construits depuis la configuration.

Un fournisseur n'est présent que s'il est configuré : clé Gemini renseignée, Ollama activé. Sans
rien de tout cela la liste est vide, aucun appel IA n'est possible et l'application fonctionne
entièrement sans IA (niveau 0).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.modules.ai_management.domain.provider import AIProvider
from app.modules.ai_management.infrastructure.gemini import GeminiProvider
from app.modules.ai_management.infrastructure.ollama import OllamaProvider


def build_providers(settings: Settings) -> list[AIProvider]:
    fournisseurs: list[AIProvider] = []
    if settings.ollama_enabled:
        fournisseurs.append(
            OllamaProvider(
                base_url=settings.ollama_url,
                model_level1=settings.ollama_model_level1,
                model_level2=settings.ollama_model_level2,
            )
        )
    if settings.gemini_api_key is not None:
        fournisseurs.append(
            GeminiProvider(
                api_key=settings.gemini_api_key,
                tier=settings.gemini_tier,
                model_level1=settings.gemini_model_level1,
                model_level2=settings.gemini_model_level2,
                thinking_level=settings.gemini_thinking_level,
            )
        )
    return fournisseurs


def get_providers(settings: Annotated[Settings, Depends(get_settings)]) -> list[AIProvider]:
    """Dépendance FastAPI, remplaçable dans les tests."""
    return build_providers(settings)
