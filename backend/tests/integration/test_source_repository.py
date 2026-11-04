import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_discovery.domain.connector import (
    ConnectorCapabilities,
    HealthState,
    HealthStatus,
)
from app.modules.job_discovery.infrastructure.source_repository import SqlJobSourceRepository
from tests.unit.job_discovery.fakes import FakeConnector

MAINTENANT = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


async def test_cree_la_source_desactivee_avec_ses_capacites(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    connecteur = FakeConnector(
        "fr",
        capabilities=ConnectorCapabilities(countries=frozenset({"FR"}), requires_credentials=True),
    )

    modele = await SqlJobSourceRepository(session).sync_from_connector(user_id, connecteur)

    assert modele.enabled is False
    assert modele.countries == ["FR"]
    assert modele.requires_api_key is True
    assert modele.kind == "official_api"


async def test_la_synchronisation_ne_reactive_pas_une_source_desactivee_ni_ne_desactive_une_active(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    depot = SqlJobSourceRepository(session)
    connecteur = FakeConnector("a")
    await depot.sync_from_connector(user_id, connecteur)
    await depot.set_enabled(user_id, "a", True)

    modele = await depot.sync_from_connector(user_id, connecteur)

    assert modele.enabled is True


async def test_enregistre_la_sante_et_la_derniere_erreur(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    depot = SqlJobSourceRepository(session)
    modele = await depot.sync_from_connector(user_id, FakeConnector("a"))

    await depot.record_health(
        user_id, "a", HealthStatus(HealthState.UNAVAILABLE, MAINTENANT, "503")
    )
    assert modele.last_error == "unavailable: 503"
    assert modele.last_success_at is None

    await depot.record_health(user_id, "a", HealthStatus(HealthState.OK, MAINTENANT))
    assert modele.last_error is None
    assert modele.last_success_at == MAINTENANT
    assert await depot.last_checked_at(user_id, "a") == MAINTENANT


async def test_une_source_inconnue_est_signalee(session: AsyncSession, user_id: uuid.UUID) -> None:
    with pytest.raises(LookupError):
        await SqlJobSourceRepository(session).set_enabled(user_id, "absente", True)
