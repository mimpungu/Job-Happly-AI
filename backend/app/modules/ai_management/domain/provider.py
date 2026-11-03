"""Contrat commun des fournisseurs IA (payants ou locaux). Le métier ne connaît que ceci."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from app.modules.ai_management.domain.models import (
    AIRequest,
    ModelPricing,
    ProviderKind,
    ProviderResult,
)


class AIProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def kind(self) -> ProviderKind: ...

    @property
    def pricing(self) -> Mapping[str, ModelPricing]:
        """Modèles proposés et leur tarif (un modèle local a un tarif nul)."""
        ...

    def supports(self, request: AIRequest) -> bool:
        """Vrai si ce fournisseur sait traiter cette demande (niveau, taille de contexte…)."""
        ...

    def model_for(self, level: int, mode: str) -> str | None:
        """Modèle à utiliser pour un niveau et un mode (économique/équilibré/qualité)."""
        ...

    async def generate(self, request: AIRequest, model: str) -> ProviderResult:
        """Appelle le modèle. Lève `ProviderFailureError` en cas d'échec."""
        ...
