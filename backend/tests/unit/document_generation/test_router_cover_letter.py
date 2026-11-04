"""Routes de lettres (sans base) : validation des entrées et erreurs normalisées."""

import uuid

import httpx
import pytest

from app.core.api.dependencies import get_owner_id, get_session
from app.main import create_app


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c


@pytest.fixture
async def client_sans_base():  # type: ignore[no-untyped-def]
    """Dépendances de base neutralisées : seule la validation des entrées est exercée."""
    application = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        yield None

    application.dependency_overrides[get_session] = _session
    application.dependency_overrides[get_owner_id] = lambda: uuid.uuid4()
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c


async def test_generation_sans_base_renvoie_503(client: httpx.AsyncClient) -> None:
    reponse = await client.post(
        "/api/v1/cover-letters/generate", json={"offer_id": str(uuid.uuid4()), "language": "fr"}
    )
    assert reponse.status_code == 503


async def test_consultation_sans_base_renvoie_503(client: httpx.AsyncClient) -> None:
    reponse = await client.get(f"/api/v1/cover-letters/{uuid.uuid4()}")
    assert reponse.status_code == 503


@pytest.mark.parametrize(
    "corps",
    [
        {"offer_id": str(uuid.uuid4()), "language": "de"},  # langue non gérée
        {"offer_id": str(uuid.uuid4()), "country_code": "FRA"},
        {"offer_id": str(uuid.uuid4()), "motivation": "x" * 1501},
        {"language": "fr"},  # offre obligatoire
        {"offer_id": "pas-un-uuid"},
    ],
)
async def test_entrees_invalides_rejetees_avant_tout_traitement(
    client_sans_base: httpx.AsyncClient, corps: dict[str, str]
) -> None:
    reponse = await client_sans_base.post("/api/v1/cover-letters/generate", json=corps)

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "validation_error"
