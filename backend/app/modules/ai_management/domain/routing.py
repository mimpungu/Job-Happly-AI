"""Choix du fournisseur et du modèle (TASK-010-04, 010-05, 010-32). Fonction pure."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.ai_management.domain.cost import estimate_worst_case
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

    En mode économique, les candidats d'un même genre sont triés du moins cher au plus cher.
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
        candidates: list[Route] = []
        if request.allowed_kinds is not None and genre not in request.allowed_kinds:
            continue
        for fournisseur in providers:
            if fournisseur.kind is not genre or not fournisseur.supports(request):
                continue
            if request.contains_personal_data and fournisseur.uses_data_for_training:
                continue  # jamais de données personnelles vers un palier qui les réutilise
            modele = fournisseur.model_for(request.level, mode.value)
            if modele is not None and modele in fournisseur.pricing:
                candidates.append(Route(fournisseur, modele))
        if mode is AIMode.ECONOMY:
            # Modèle le moins cher suffisant (TASK-010-32) : tous ces candidats savent traiter
            # la tâche (niveau géré), on essaie donc le moins coûteux d'abord. Le tri est stable :
            # à coût égal, l'ordre de configuration est conservé.
            candidates.sort(key=lambda r: estimate_worst_case(request, r.provider.pricing[r.model]))
        routes.extend(candidates)
    return routes
