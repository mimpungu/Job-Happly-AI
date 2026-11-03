"""Fournisseurs IA disponibles.

Aucun fournisseur n'est encore branché : le choix de l'API payante exige un ADR (ADR-0005) et le
modèle local est une option ultérieure. Tant que cette liste est vide, aucun appel IA n'est
possible et l'application fonctionne entièrement sans IA (niveau 0).
"""

from __future__ import annotations

from app.modules.ai_management.domain.provider import AIProvider


def get_providers() -> list[AIProvider]:
    """Dépendance FastAPI, remplaçable dans les tests. Liste vide : rien n'est configuré."""
    return []
