"""Construit le connecteur d'une entreprise suivie à partir de sa source détectée."""

from __future__ import annotations

from typing import Literal, cast

import httpx

from app.modules.job_discovery.domain.connector import JobSourceConnector
from app.modules.job_discovery.domain.target_company import AtsKind
from app.modules.job_discovery.infrastructure.ats.ashby import AshbyConnector
from app.modules.job_discovery.infrastructure.ats.greenhouse import GreenhouseConnector
from app.modules.job_discovery.infrastructure.ats.lever import LeverConnector
from app.modules.job_discovery.infrastructure.ats.workable import WorkableConnector
from app.modules.job_discovery.infrastructure.models import TargetCompanyModel


def connector_for(
    entreprise: TargetCompanyModel, client: httpx.AsyncClient
) -> JobSourceConnector | None:
    """Connecteur prêt à l'emploi, ou `None` si la source n'est pas (encore) supportée."""
    if entreprise.detection_status != "supported" or entreprise.ats_token is None:
        return None
    if entreprise.ats_kind == AtsKind.GREENHOUSE.value:
        return GreenhouseConnector(
            board_token=entreprise.ats_token, company_name=entreprise.name, client=client
        )
    if entreprise.ats_kind == AtsKind.LEVER.value:
        region = cast(Literal["global", "eu"], entreprise.ats_region or "global")
        return LeverConnector(
            company_token=entreprise.ats_token,
            company_name=entreprise.name,
            client=client,
            region=region,
        )
    if entreprise.ats_kind == AtsKind.ASHBY.value:
        return AshbyConnector(
            board_name=entreprise.ats_token, company_name=entreprise.name, client=client
        )
    if entreprise.ats_kind == AtsKind.WORKABLE.value:
        return WorkableConnector(
            subdomain=entreprise.ats_token, company_name=entreprise.name, client=client
        )
    return None
