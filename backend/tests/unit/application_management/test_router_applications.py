"""Routes du CRM sans base : refus propre, validation des entrées, erreurs normalisées."""

import uuid

import httpx
import pytest
from fastapi import FastAPI

from app.core.api.dependencies import get_owner_id, get_session
from app.core.api.errors import register_error_handlers
from app.main import create_app
from app.modules.application_management.domain import exceptions as exc
from app.modules.application_management.presentation.errors import register_application_errors

APP_ID = str(uuid.uuid4())
JSON_VIDE: dict[str, object] = {}


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


@pytest.mark.parametrize(
    ("methode", "chemin"),
    [
        ("GET", "/api/v1/applications"),
        ("GET", "/api/v1/applications/kanban"),
        ("GET", "/api/v1/applications/stats"),
        ("GET", "/api/v1/dashboard"),
        ("GET", f"/api/v1/applications/{APP_ID}"),
        ("GET", f"/api/v1/applications/{APP_ID}/dossier"),
        ("GET", f"/api/v1/applications/{APP_ID}/open-url"),
    ],
)
async def test_sans_base_chaque_route_repond_503(
    client: httpx.AsyncClient, methode: str, chemin: str
) -> None:
    """Un 503 net, jamais « 200 ou 503 » : l'absence de base est une erreur d'environnement."""
    reponse = await client.request(methode, chemin)
    assert reponse.status_code == 503


@pytest.mark.parametrize(
    ("methode", "chemin", "corps"),
    [
        ("POST", "/api/v1/applications", {"offer_id": "pas-un-uuid"}),
        ("POST", "/api/v1/applications", {"offer_id": APP_ID, "initial_status": "inconnu"}),
        ("PATCH", f"/api/v1/applications/{APP_ID}/status", {"target_status": "inconnu"}),
        ("PATCH", f"/api/v1/applications/{APP_ID}/status", {"target_status": "sent", "reason": ""}),
        ("POST", f"/api/v1/applications/{APP_ID}/notes", {"body": ""}),
        ("POST", f"/api/v1/applications/{APP_ID}/notes", {"body": "    "}),
        ("POST", f"/api/v1/applications/{APP_ID}/notes", {"body": "x" * 5001}),
        (
            "POST",
            f"/api/v1/applications/{APP_ID}/interviews",
            {"description": "RH", "interview_time": "2026-11-10T14:00:00"},  # sans fuseau
        ),
        (
            "POST",
            f"/api/v1/applications/{APP_ID}/confirm-submission",
            {"applied_at": "2026-11-03T09:00:00"},  # sans fuseau
        ),
        (
            "PATCH",
            f"/api/v1/applications/{APP_ID}/follow-up",
            {"follow_up_at": "2026-12-01T09:00:00"},  # sans fuseau
        ),
        ("POST", f"/api/v1/applications/{APP_ID}/contacts", {"name": ""}),
        ("POST", f"/api/v1/applications/{APP_ID}/contacts", {"name": "A", "email": "pas-un-mail"}),
        ("POST", f"/api/v1/applications/{APP_ID}/contacts", {"name": "A", "phone": "abc<script>"}),
        ("PUT", f"/api/v1/applications/{APP_ID}/documents", {"cv_version_id": "x"}),
    ],
)
async def test_entrees_invalides_rejetees_en_422(
    client_sans_base: httpx.AsyncClient, methode: str, chemin: str, corps: dict[str, object]
) -> None:
    reponse = await client_sans_base.request(methode, chemin, json=corps)

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "requete",
    [
        "limit=0",
        "limit=101",
        "offset=-1",
        "status=inconnu",
        "company=" + "x" * 201,
        "follow_up_due=peut-etre",
    ],
)
async def test_parametres_de_liste_invalides(
    client_sans_base: httpx.AsyncClient, requete: str
) -> None:
    reponse = await client_sans_base.get(f"/api/v1/applications?{requete}")
    assert reponse.status_code == 422


@pytest.mark.parametrize("requete", ["per_column_limit=0", "per_column_limit=51"])
async def test_limite_du_kanban_invalide(client_sans_base: httpx.AsyncClient, requete: str) -> None:
    assert (await client_sans_base.get(f"/api/v1/applications/kanban?{requete}")).status_code == 422


CAS: list[tuple[Exception, int, str]] = [
    (exc.ApplicationNotFoundError("x"), 404, "application_not_found"),
    (exc.OfferNotFoundError("x"), 404, "offer_not_found"),
    (exc.DocumentVersionNotFoundError("x"), 404, "document_version_not_found"),
    (exc.DuplicateApplicationError("x"), 409, "duplicate_application"),
    (exc.InvalidStatusTransitionError("x"), 409, "invalid_status_transition"),
    (exc.IncompleteDossierError("x"), 409, "incomplete_dossier"),
    (exc.AlreadySubmittedError("x"), 409, "already_submitted"),
    (exc.DocumentLockedError("x"), 409, "document_locked"),
    (exc.DocumentKindMismatchError("x"), 422, "document_kind_mismatch"),
    (exc.NothingToAttachError("x"), 422, "nothing_to_attach"),
    (exc.InvalidDateError("x"), 422, "invalid_date"),
    (exc.ExternalOfferLinkMissingError("x"), 422, "application_url_unavailable"),
]


@pytest.mark.parametrize(("erreur", "statut", "code"), CAS, ids=[c[2] for c in CAS])
async def test_erreur_metier_vers_http(erreur: Exception, statut: int, code: str) -> None:
    application = FastAPI()
    register_error_handlers(application)
    register_application_errors(application)

    @application.get("/boom")
    async def boom() -> None:
        raise erreur

    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as c:
        reponse = await c.get("/boom")

    assert reponse.status_code == statut
    assert reponse.json()["error"]["code"] == code
    assert "Traceback" not in reponse.text


def test_toutes_les_exceptions_metier_sont_traduites() -> None:
    """Une exception ajoutée au domaine sans traduction HTTP produirait un 500."""
    couvertes = {type(c[0]) for c in CAS} | {exc.ApplicationTrackingError}
    definies = {
        v
        for v in vars(exc).values()
        if isinstance(v, type) and issubclass(v, exc.ApplicationTrackingError)
    }
    assert definies <= couvertes
