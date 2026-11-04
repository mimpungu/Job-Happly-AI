"""Tests unitaires des endpoints HTTP de suivi des candidatures et dashboard (EPIC 014)."""

import uuid

import httpx
import pytest

from app.main import create_app


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c


async def test_endpoint_applications_liste_repond_200_ou_503(client: httpx.AsyncClient) -> None:
    reponse = await client.get("/api/v1/applications")
    assert reponse.status_code in (200, 503)


async def test_endpoint_applications_kanban_repond_200_ou_503(client: httpx.AsyncClient) -> None:
    reponse = await client.get("/api/v1/applications/kanban")
    assert reponse.status_code in (200, 503)


async def test_endpoint_applications_stats_repond_200_ou_503(client: httpx.AsyncClient) -> None:
    reponse = await client.get("/api/v1/applications/stats")
    assert reponse.status_code in (200, 503)


async def test_endpoint_dashboard_repond_200_ou_503(client: httpx.AsyncClient) -> None:
    reponse = await client.get("/api/v1/dashboard")
    assert reponse.status_code in (200, 503)


async def test_endpoint_candidature_inconnue_repond_404_ou_503(client: httpx.AsyncClient) -> None:
    app_id = str(uuid.uuid4())
    reponse = await client.get(f"/api/v1/applications/{app_id}")
    assert reponse.status_code in (404, 503)

