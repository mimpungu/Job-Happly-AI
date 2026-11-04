"""Notifications, préférences et planificateur sur PostgreSQL réel (EPIC 015).

Complète les tests unitaires du module : ici les routes, les dépôts SQL et les transactions sont
exercés pour de bon (les anciens tests de routes acceptaient « 200 ou 503 »).
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.api.dependencies import get_session, get_unit_of_work
from app.core.database.session import create_session_factory, to_driver_url
from app.main import create_app
from app.modules.notifications.infrastructure.models import NotificationModel
from app.modules.platform.infrastructure.models import JobModel, UserModel
from tests.integration.conftest import SessionPartagee

NOTIFS = "/api/v1/notifications"
PLANIF = "/api/v1/scheduler"


@pytest.fixture
async def api(
    session: AsyncSession, user_id: uuid.UUID, schema_migre: str
) -> AsyncIterator[httpx.AsyncClient]:
    """Client sur la session de test ; la file de tâches utilise sa propre fabrique (comme en
    production) : les tâches qu'elle valide sont supprimées à la fin du test."""
    application = create_app()
    application.dependency_overrides[get_unit_of_work] = lambda: SessionPartagee(session)

    async def _session() -> AsyncIterator[AsyncSession]:
        yield session

    application.dependency_overrides[get_session] = _session
    moteur = create_async_engine(to_driver_url(schema_migre))
    application.state.session_factory = create_session_factory(moteur)
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c
    async with moteur.begin() as connexion:
        await connexion.execute(delete(JobModel))
    await moteur.dispose()


async def _notifier(
    session: AsyncSession, owner: uuid.UUID, titre: str, *, lue: bool = False
) -> uuid.UUID:
    notification = NotificationModel(
        owner_id=owner,
        kind="new_offers",
        title=titre,
        read_at=datetime.now(UTC) if lue else None,
    )
    session.add(notification)
    await session.flush()
    return notification.id


@pytest.fixture
async def api_reel(schema_migre: str) -> AsyncIterator[httpx.AsyncClient]:
    """Sans surcharge ni session partagée : chaque requête valide sa propre transaction, comme en
    production. Indispensable quand la file de tâches (autre connexion) référence l'utilisateur.
    Tout est supprimé à la fin (la suppression de l'utilisateur emporte ses données)."""
    application = create_app()
    moteur = create_async_engine(to_driver_url(schema_migre))
    application.state.session_factory = create_session_factory(moteur)
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c
    async with moteur.begin() as connexion:
        await connexion.execute(delete(JobModel))
        await connexion.execute(delete(UserModel))
    await moteur.dispose()


class TestNotifications:
    async def test_liste_filtre_et_compte_les_non_lues(
        self, api: httpx.AsyncClient, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await _notifier(session, user_id, "Nouvelle offre")
        await _notifier(session, user_id, "Déjà lue", lue=True)

        toutes = (await api.get(NOTIFS)).json()
        non_lues = (await api.get(NOTIFS, params={"unread_only": "true"})).json()
        compte = (await api.get(f"{NOTIFS}/unread-count")).json()

        assert toutes["total"] == 2 and toutes["unread_count"] == 1
        assert [n["title"] for n in non_lues["items"]] == ["Nouvelle offre"]
        assert compte == {"unread_count": 1}

    async def test_filtre_par_type_et_pagination(
        self, api: httpx.AsyncClient, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        for i in range(3):
            await _notifier(session, user_id, f"n{i}")

        page = (await api.get(NOTIFS, params={"limit": 2, "offset": 2})).json()
        autre_type = (await api.get(NOTIFS, params={"kind": "ai_budget_alert"})).json()
        invalide = await api.get(NOTIFS, params={"kind": "inconnu"})

        assert page["total"] == 3 and len(page["items"]) == 1
        assert autre_type["total"] == 0
        assert invalide.status_code == 422

    async def test_marquer_lue_puis_tout_marquer_lu(
        self, api: httpx.AsyncClient, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        premiere = await _notifier(session, user_id, "a")
        await _notifier(session, user_id, "b")

        lue = (await api.patch(f"{NOTIFS}/{premiere}/read")).json()
        reste = (await api.post(f"{NOTIFS}/mark-all-read")).json()

        assert lue["is_read"] is True and lue["read_at"]
        assert reste == {"marked_read": 1}
        assert (await api.get(f"{NOTIFS}/unread-count")).json() == {"unread_count": 0}

    async def test_supprimer_et_notification_inconnue(
        self, api: httpx.AsyncClient, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        identifiant = await _notifier(session, user_id, "à supprimer")

        assert (await api.delete(f"{NOTIFS}/{identifiant}")).status_code == 204
        assert (await api.delete(f"{NOTIFS}/{identifiant}")).status_code == 404
        assert (await api.patch(f"{NOTIFS}/{uuid.uuid4()}/read")).status_code == 404

    async def test_les_notifications_d_un_autre_utilisateur_sont_invisibles(
        self, api: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        autre = UserModel(display_name="Autre", created_at=datetime.now(UTC) + timedelta(hours=1))
        session.add(autre)
        await session.flush()
        secrete = await _notifier(session, autre.id, "secrète")

        assert (await api.get(NOTIFS)).json()["total"] == 0
        assert (await api.patch(f"{NOTIFS}/{secrete}/read")).status_code == 404
        assert (await api.delete(f"{NOTIFS}/{secrete}")).status_code == 404


class TestPreferences:
    async def test_valeurs_par_defaut_puis_mise_a_jour_partielle(
        self, api: httpx.AsyncClient
    ) -> None:
        defaut = (await api.get(f"{NOTIFS}/preferences")).json()
        maj = await api.put(
            f"{NOTIFS}/preferences",
            json={
                "min_relevance_score": 85,
                "daily_digest_time": "07:30",
                "timezone": "Europe/Paris",
            },
        )
        relu = (await api.get(f"{NOTIFS}/preferences")).json()

        assert defaut["in_app_enabled"] is True and defaut["email_enabled"] is False
        assert defaut["email_consent_given"] is False  # aucun envoi d'e-mail sans accord
        assert maj.status_code == 200
        assert relu["min_relevance_score"] == 85 and relu["daily_digest_time"] == "07:30"
        assert relu["in_app_enabled"] is True  # un champ non fourni reste inchangé

    @pytest.mark.parametrize(
        "corps",
        [
            {"min_relevance_score": 101},
            {"daily_digest_time": "25:00"},
            {"daily_digest_time": "7h30"},
            {"email_recipient": "a" * 400},
        ],
    )
    async def test_valeurs_invalides_refusees(
        self, api: httpx.AsyncClient, corps: dict[str, object]
    ) -> None:
        assert (await api.put(f"{NOTIFS}/preferences", json=corps)).status_code == 422


class TestPlanificateur:
    async def _creer(self, api: httpx.AsyncClient, **corps: object) -> httpx.Response:
        base = {
            "task_type": "daily_digest",
            "frequency": "daily",
            "target_hour": 8,
            "target_minute": 0,
        }
        return await api.post(f"{PLANIF}/tasks", json={**base, **corps})

    async def test_cycle_complet_d_une_tache_planifiee(self, api: httpx.AsyncClient) -> None:
        creation = await self._creer(api)
        assert creation.status_code == 201, creation.text
        tache = creation.json()
        assert tache["enabled"] is True and tache["next_run_at"]

        liste = (await api.get(f"{PLANIF}/tasks")).json()
        assert [t["id"] for t in liste] == [tache["id"]]
        assert (await api.get(f"{PLANIF}/tasks/{tache['id']}")).json()[
            "task_type"
        ] == "daily_digest"

        maj = await api.put(
            f"{PLANIF}/tasks/{tache['id']}", json={"enabled": False, "target_hour": 9}
        )
        assert maj.status_code == 200
        assert maj.json()["enabled"] is False and maj.json()["target_hour"] == 9

        assert (await api.delete(f"{PLANIF}/tasks/{tache['id']}")).status_code == 204
        assert (await api.get(f"{PLANIF}/tasks/{tache['id']}")).status_code == 404

    async def test_fuseau_ou_frequence_invalides_refuses(self, api: httpx.AsyncClient) -> None:
        mauvais_fuseau = await self._creer(api, timezone="Mars/Olympus")
        sans_intervalle = await self._creer(api, frequency="interval_minutes", target_hour=None)

        assert mauvais_fuseau.status_code == 422
        assert sans_intervalle.status_code == 422

    async def test_charge_utile_trop_grande_refusee(self, api: httpx.AsyncClient) -> None:
        reponse = await self._creer(api, payload={"x": "a" * 5000})

        assert reponse.status_code == 422

    async def test_declenchement_manuel_met_une_tache_en_file_et_l_historique_la_montre(
        self, api_reel: httpx.AsyncClient
    ) -> None:
        tache = (await self._creer(api_reel)).json()

        declenche = await api_reel.post(f"{PLANIF}/tasks/{tache['id']}/trigger")
        historique = (await api_reel.get(f"{PLANIF}/jobs/history")).json()

        assert declenche.status_code == 200 and declenche.json()["status"] == "queued"
        assert historique["total"] >= 1
        assert any(j["id"] == declenche.json()["job_id"] for j in historique["items"])

    async def test_tache_inconnue_et_declenchement_inconnu(self, api: httpx.AsyncClient) -> None:
        inconnu = uuid.uuid4()

        assert (await api.get(f"{PLANIF}/tasks/{inconnu}")).status_code == 404
        assert (
            await api.put(f"{PLANIF}/tasks/{inconnu}", json={"enabled": False})
        ).status_code == 404
        assert (await api.delete(f"{PLANIF}/tasks/{inconnu}")).status_code == 404
        assert (await api.post(f"{PLANIF}/tasks/{inconnu}/trigger")).status_code == 404

    async def test_enqueue_due_et_resume_quotidien(self, api: httpx.AsyncClient) -> None:
        enfile = await api.post(f"{PLANIF}/enqueue-due")
        resume = await api.post(f"{PLANIF}/daily-digest/generate")

        assert enfile.status_code == 200 and enfile.json()["enqueued"] >= 0
        assert resume.status_code == 200
        corps = resume.json()
        assert {"new_offers_count", "follow_ups_due_count", "ai_spent_today"} <= set(corps)
