"""Sources de recherche (API officielles) branchées sur la recherche multi-sources.

Seules les sources **configurées** sont interrogées : une source sans identifiants est signalée
« non configurée » dans l'interface, jamais appelée ni simulée.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from app.core.config import Settings
from app.modules.job_discovery.domain.connector import JobSourceConnector
from app.modules.job_discovery.infrastructure.france_travail import FranceTravailConnector


def france_travail_configured(settings: Settings) -> bool:
    return (
        settings.france_travail_client_id is not None
        and settings.france_travail_client_secret is not None
    )


def build_search_connectors(
    settings: Settings, client: httpx.AsyncClient
) -> Sequence[JobSourceConnector]:
    connecteurs: list[JobSourceConnector] = []
    if france_travail_configured(settings):
        connecteurs.append(
            FranceTravailConnector(
                client=client,
                client_id=settings.france_travail_client_id,
                client_secret=settings.france_travail_client_secret,
            )
        )
    return connecteurs
