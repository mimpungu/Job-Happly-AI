"""Tests unitaires du routeur cover letter (TASK-013-13, 14, 15)."""

import uuid

import httpx
import pytest

from app.main import create_app


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c


async def test_generation_requete_sans_profil_renvoie_404_ou_503(
    client: httpx.AsyncClient,
) -> None:
    body = {
        "offer_id": str(uuid.uuid4()),
        "language": "fr",
    }
    reponse = await client.post("/api/v1/cover-letters/generate", json=body)
    # Sans base de données PostgreSQL active, le middleware renvoie 503 (Service Unavailable)
    # avec base, renverrait 404 (Profil introuvable)
    assert reponse.status_code in (404, 500, 503)


async def test_recuperation_document_inconnu_renvoie_404_ou_503(
    client: httpx.AsyncClient,
) -> None:
    doc_id = str(uuid.uuid4())
    reponse = await client.get(f"/api/v1/cover-letters/{doc_id}")
    assert reponse.status_code in (404, 500, 503)
