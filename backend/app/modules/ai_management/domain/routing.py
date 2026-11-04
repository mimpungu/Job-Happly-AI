"""Choix du fournisseur et du modèle (TASK-010-04, 010-05). Fonction pure."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.ai_management.domain.models import (
    AIMode,
    AIRequest,
    BackendPreference,
    ProviderKind,
)
from app.modules.ai_management.domain.provider import AIProvider


@dataclass(frozen=True, slots=True)
class Route:
    provider: AIProvider
    model: str


def plan_routes(
    providers: Sequence[AIProvider],
    request: AIRequest,
    *,
    mode: AIMode,
    preference: BackendPreference,
) -> list[Route]:
    """Routes à essayer dans l'ordre. Le local passe toujours avant l'API payante.

    En mode hybride, l'API n'est retenue que si elle est configurée : si le local échoue, la
    route suivante est tentée (toujours soumise au plafond et au consentement).
    """
    if mode is AIMode.DISABLED:
        return []
    voulus: list[ProviderKind] = {
        BackendPreference.LOCAL_ONLY: [ProviderKind.LOCAL],
        BackendPreference.API_ONLY: [ProviderKind.API],
        BackendPreference.HYBRID: [ProviderKind.LOCAL, ProviderKind.API],
    }[preference]
    routes: list[Route] = []
    for genre in voulus:
        if request.allowed_kinds is not None and genre not in request.allowed_kinds:
            continue
        for fournisseur in providers:
            if fournisseur.kind is not genre or not fournisseur.supports(request):
                continue
            if request.contains_personal_data and fournisseur.uses_data_for_training:
                continue  # jamais de données personnelles vers un palier qui les réutilise
            modele = fournisseur.model_for(request.level, mode.value)
            if modele is not None and modele in fournisseur.pricing:
                routes.append(Route(fournisseur, modele))
    return routes
