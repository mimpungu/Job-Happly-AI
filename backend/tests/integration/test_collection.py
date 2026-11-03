"""Collecte des offres des entreprises suivies (réseau simulé, base PostgreSQL réelle)."""

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_discovery.application.collection import (
    CollectionService,
    NoEnabledCompanyError,
)
from app.modules.job_discovery.domain.enums import SearchRunStatus
from app.modules.job_discovery.infrastructure.http import create_http_client
from app.modules.job_discovery.infrastructure.models import (
    JobOfferModel,
    JobSourceModel,
    TargetCompanyModel,
)
from app.modules.job_discovery.infrastructure.resilience import ResilientConnector, RetryPolicy
from app.modules.job_discovery.infrastructure.target_company_repository import (
    SqlTargetCompanyRepository,
)
from tests.integration.conftest import SessionPartagee

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ats" / "greenhouse_jobs.json"
MAINTENANT = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def _service(
    session: AsyncSession, handler: Callable[[httpx.Request], httpx.Response]
) -> CollectionService:
    return CollectionService(
        SessionPartagee(session),
        lambda: create_http_client(transport=httpx.MockTransport(handler)),
        clock=lambda: MAINTENANT,
        # Pas de nouvelle tentative : les tests n'attendent jamais un backoff.
        resilient=lambda c: ResilientConnector(c, retry=RetryPolicy(max_attempts=1)),
    )


async def _suivre(
    session: AsyncSession, owner: uuid.UUID, nom: str, url: str, *, active: bool = True
) -> TargetCompanyModel:
    depot = SqlTargetCompanyRepository(session)
    entreprise = await depot.add(owner, name=nom, careers_url=url, now=MAINTENANT)
    if active:
        await depot.set_enabled(entreprise, True)
    return entreprise


async def test_sans_entreprise_activee_il_n_y_a_rien_a_collecter(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _suivre(
        session, user_id, "Inactive", "https://boards.greenhouse.io/inactive", active=False
    )

    with pytest.raises(NoEnabledCompanyError):
        await _service(session, lambda _: httpx.Response(500)).run(owner_id=user_id)


async def test_collecte_les_offres_et_isole_les_sources_en_echec(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _suivre(session, user_id, "Bonne", "https://boards.greenhouse.io/bonne")
    await _suivre(session, user_id, "Panne", "https://boards.greenhouse.io/panne")
    refus = await _suivre(session, user_id, "Refus", "https://boards.greenhouse.io/refus")

    def handler(requete: httpx.Request) -> httpx.Response:
        if "/bonne/" in requete.url.path:
            return httpx.Response(200, json=json.loads(FIXTURE.read_text(encoding="utf-8")))
        if "/panne/" in requete.url.path:
            return httpx.Response(503)
        return httpx.Response(403)

    rapport = await _service(session, handler).run(owner_id=user_id)

    assert rapport.status is SearchRunStatus.PARTIAL
    par_nom = {c.company_name: c.outcome for c in rapport.companies}
    assert par_nom["Bonne"].succeeded and par_nom["Bonne"].created == 3
    assert par_nom["Panne"].error_type == "SourceUnavailableError"
    assert par_nom["Refus"].error_type == "AccessDeniedError"
    assert await session.scalar(select(func.count()).select_from(JobOfferModel)) == 3

    sources = {s.key: s for s in (await session.execute(select(JobSourceModel))).scalars()}
    assert sources["greenhouse:bonne"].last_error is None
    assert sources["greenhouse:bonne"].last_success_at == MAINTENANT
    assert sources["greenhouse:panne"].last_error.startswith("unavailable")  # type: ignore[union-attr]
    # Un refus d'accès n'est jamais contourné : la source devient non supportée et désactivée.
    assert refus.detection_status == "unsupported"
    assert refus.enabled is False


async def test_relancer_la_collecte_ne_cree_aucun_doublon(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _suivre(session, user_id, "Bonne", "https://boards.greenhouse.io/bonne")
    contenu = json.loads(FIXTURE.read_text(encoding="utf-8"))
    service = _service(session, lambda _: httpx.Response(200, json=contenu))

    premiere = await service.run(owner_id=user_id)
    seconde = await service.run(owner_id=user_id)

    assert premiere.companies[0].outcome.created == 3
    assert seconde.companies[0].outcome.created == 0
    assert seconde.companies[0].outcome.unchanged == 3
    assert await session.scalar(select(func.count()).select_from(JobOfferModel)) == 3
