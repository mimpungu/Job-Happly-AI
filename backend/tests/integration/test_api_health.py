"""Santé, mesures et en-têtes de sécurité sur PostgreSQL réel (EPIC 018)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.job_discovery.infrastructure.models import JobSourceModel
from app.modules.notifications.infrastructure.models import ScheduledTaskModel
from app.modules.platform.infrastructure import health_checks
from app.modules.platform.infrastructure.models import JobModel, JobStatus


@pytest.fixture(autouse=True)
def _stockage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HAPPLY_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()


def _par_nom(corps: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["name"]: c for c in corps["components"]}


async def test_pret_quand_base_et_stockage_repondent(client: httpx.AsyncClient) -> None:
    reponse = await client.get("/api/v1/health/ready")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["status"] == "ok"
    base = _par_nom(corps)["database"]
    assert base["data"]["latency_ms"] >= 0
    assert base["data"]["migration_revision"]


async def test_tableau_de_sante_sans_ia_ni_source_n_est_pas_une_panne(
    client: httpx.AsyncClient,
) -> None:
    corps = (await client.get("/api/v1/health/details")).json()

    composants = _par_nom(corps)
    assert set(composants) == {"database", "storage", "latex", "ai", "sources", "tasks"}
    assert composants["ai"]["status"] == "not_configured"
    assert composants["sources"]["status"] == "not_configured"
    assert corps["status"] in {"ok", "degraded"}  # degraded seulement si pdfLaTeX est absent


async def test_en_tetes_de_securite_et_correlation_sur_l_api_reelle(
    client: httpx.AsyncClient,
) -> None:
    reponse = await client.get("/api/v1/health", headers={"X-Request-ID": "corr-0123456789"})

    assert reponse.headers["x-request-id"] == "corr-0123456789"
    assert reponse.headers["x-content-type-options"] == "nosniff"
    assert reponse.headers["x-frame-options"] == "DENY"


async def test_mesures_par_modele_de_route(client: httpx.AsyncClient) -> None:
    await client.get("/api/v1/health")
    await client.get("/api/v1/health")

    routes = (await client.get("/api/v1/health/metrics")).json()["routes"]

    assert routes["GET /api/v1/health"]["count"] == 2
    assert {"p50_ms", "p95_ms", "avg_ms", "errors"} <= set(routes["GET /api/v1/health"])


async def test_cors_refuse_une_origine_inconnue(client: httpx.AsyncClient) -> None:
    reponse = await client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in reponse.headers


async def test_cors_accepte_le_frontend_local(client: httpx.AsyncClient) -> None:
    reponse = await client.options(
        "/api/v1/health",
        headers={"Origin": "http://127.0.0.1:3000", "Access-Control-Request-Method": "GET"},
    )

    assert reponse.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


async def test_taches_en_retard_et_abandonnees_sont_signalees(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    maintenant = datetime.now(UTC)
    session.add(
        ScheduledTaskModel(
            owner_id=user_id,
            task_type="daily_digest",
            frequency="daily",
            next_run_at=maintenant - timedelta(hours=2),
        )
    )
    session.add(JobModel(kind="x", idempotency_key="k1", status=JobStatus.DEAD.value))
    session.add(
        JobModel(
            kind="x",
            idempotency_key="k2",
            status=JobStatus.RUNNING.value,
            locked_at=maintenant - timedelta(hours=2),
        )
    )
    await session.flush()

    sante = await health_checks.check_tasks(session, now=maintenant)

    assert sante.status.value == "degraded"
    assert "en retard" in (sante.detail or "")
    assert "bloquée" in (sante.detail or "")
    assert "abandonnée" in (sante.detail or "")
    assert sante.data["jobs"]["dead"] == 1


async def test_source_en_erreur_degrade_sans_fuiter_de_secret(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    session.add(
        JobSourceModel(
            owner_id=user_id,
            key="demo",
            name="Demo",
            kind="official_api",
            enabled=True,
            last_error="échec GET https://api.test/offers?key=AIzaSyA1234567890abcdefghij",
        )
    )
    await session.flush()

    sante = await health_checks.check_sources(session)

    assert sante.status.value == "degraded"
    assert "AIzaSyA1234567890" not in str(sante.data)
