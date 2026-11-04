"""Tests unitaires des endpoints HTTP de notifications et planification (EPIC 015)."""

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from app.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c


async def test_endpoint_notifications_liste_repond_200_ou_503(client: httpx.AsyncClient) -> None:
    reponse = await client.get("/api/v1/notifications")
    assert reponse.status_code in (200, 503)


async def test_endpoint_notifications_unread_count_repond_200_ou_503(
    client: httpx.AsyncClient,
) -> None:
    reponse = await client.get("/api/v1/notifications/unread-count")
    assert reponse.status_code in (200, 503)


async def test_endpoint_notifications_preferences_repond_200_ou_503(
    client: httpx.AsyncClient,
) -> None:
    reponse = await client.get("/api/v1/notifications/preferences")
    assert reponse.status_code in (200, 503)


async def test_endpoint_scheduler_tasks_liste_repond_200_ou_503(
    client: httpx.AsyncClient,
) -> None:
    reponse = await client.get("/api/v1/scheduler/tasks")
    assert reponse.status_code in (200, 503)


async def test_endpoint_scheduler_jobs_history_repond_200_ou_503(
    client: httpx.AsyncClient,
) -> None:
    reponse = await client.get("/api/v1/scheduler/jobs/history")
    assert reponse.status_code in (200, 503)


async def test_endpoint_notification_inconnue_repond_404_ou_503(
    client: httpx.AsyncClient,
) -> None:
    notif_id = str(uuid.uuid4())
    reponse = await client.patch(f"/api/v1/notifications/{notif_id}/read")
    assert reponse.status_code in (404, 503)


async def test_endpoint_task_inconnue_repond_404_ou_503(
    client: httpx.AsyncClient,
) -> None:
    task_id = str(uuid.uuid4())
    reponse = await client.get(f"/api/v1/scheduler/tasks/{task_id}")
    assert reponse.status_code in (404, 503)
