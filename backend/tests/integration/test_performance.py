"""Volumes, pagination, requêtes SQL et concurrence (EPIC 019 : TASK-019-18 à 019-22).

Les seuils de durée sont volontairement larges (machines de CI lentes) : ils détectent une
régression d'ordre de grandeur (balayage complet, N+1), pas une variation de quelques millisecondes.
Les mesures réelles sont rapportées dans `docs/engineering/QUALITY_REPORT.md`.
"""

import asyncio
import math
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, event, insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.database.session import UnitOfWork, create_session_factory, to_driver_url
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.platform.application.worker import JobWorker
from app.modules.platform.infrastructure.job_queue import PostgresJobQueue
from app.modules.platform.infrastructure.models import JobModel

VOLUME = 20_000
SEUIL_LISTE_S = 1.5
SEUIL_RECHERCHE_S = 2.0
REQUETES_MAX_PAR_LISTE = 8  # indépendant de la taille de page : sinon c'est un N+1


@pytest.fixture
async def catalogue(session: AsyncSession, user_id: uuid.UUID) -> int:
    """20 000 offres d'un même propriétaire, dates étalées, 1 % mentionnent Kubernetes."""
    maintenant = datetime.now(UTC)
    lignes: list[dict[str, Any]] = [
        {
            "owner_id": user_id,
            "title": f"Développeur {('Python', 'Java', 'Go', 'Rust')[i % 4]} #{i}",
            "company_name": f"Entreprise {i % 500}",
            "description": "Plateforme de données. "
            + ("Kubernetes, Docker. " if i % 100 == 0 else "Python, PostgreSQL. ")
            + "Équipe produit.",
            "location": ("Paris", "Lyon", "Lille", "Nantes")[i % 4],
            "country_code": "FR",
            "employment_type": "permanent",
            "remote_type": ("on_site", "hybrid", "remote")[i % 3],
            "status": "active",
            "application_url": f"https://exemple.test/offre/{i}",
            "content_hash": f"{i:064d}",
            "published_at": maintenant - timedelta(minutes=i),
        }
        for i in range(VOLUME)
    ]
    for debut in range(0, VOLUME, 5000):
        await session.execute(insert(JobOfferModel), lignes[debut : debut + 5000])
    await session.flush()
    return VOLUME


async def _mesure(client: httpx.AsyncClient, url: str) -> tuple[httpx.Response, float]:
    debut = time.perf_counter()
    reponse = await client.get(url)
    return reponse, time.perf_counter() - debut


@pytest.fixture
def requetes_sql(session: AsyncSession) -> Iterator[list[tuple[str, Any]]]:
    """Instructions SQL et paramètres exécutés pendant le test (N+1, puis EXPLAIN réel)."""
    vues: list[tuple[str, Any]] = []
    moteur = session.sync_session.get_bind()

    def _noter(_c: Any, _cur: Any, statement: str, parameters: Any, *_: Any) -> None:
        vues.append((statement, parameters))

    event.listen(moteur, "before_cursor_execute", _noter)
    yield vues
    event.remove(moteur, "before_cursor_execute", _noter)


async def test_la_liste_reste_rapide_avec_vingt_mille_offres(
    client: httpx.AsyncClient, catalogue: int
) -> None:
    reponse, duree = await _mesure(client, "/api/v1/offers?page_size=25")

    corps = reponse.json()
    assert reponse.status_code == 200
    assert corps["total"] == catalogue and len(corps["items"]) == 25
    assert duree < SEUIL_LISTE_S, f"liste : {duree:.2f}s pour {catalogue} offres"


async def test_la_pagination_est_complete_stable_et_sans_doublon(
    client: httpx.AsyncClient, catalogue: int
) -> None:
    taille = 100
    pages_a_lire = [1, 2, 3, math.ceil(catalogue / taille)]
    vus: set[str] = set()
    for numero in pages_a_lire:
        reponse = await client.get(f"/api/v1/offers?page={numero}&page_size={taille}")
        corps = reponse.json()
        ids = [o["id"] for o in corps["items"]]
        assert reponse.status_code == 200
        assert corps["page_count"] == math.ceil(catalogue / taille)
        assert not (vus & set(ids)), f"page {numero} : offres déjà vues"
        vus |= set(ids)
    derniere = (
        await client.get(f"/api/v1/offers?page={pages_a_lire[-1]}&page_size={taille}")
    ).json()
    assert len(derniere["items"]) == catalogue - taille * (pages_a_lire[-1] - 1)
    # l'ordre est celui du tri demandé : plus récentes d'abord
    premiere = (await client.get(f"/api/v1/offers?page=1&page_size={taille}")).json()["items"]
    dates = [o["published_at"] for o in premiere]
    assert dates == sorted(dates, reverse=True)


async def test_une_page_hors_limites_est_vide_et_la_taille_de_page_est_bornee(
    client: httpx.AsyncClient, catalogue: int
) -> None:
    hors = await client.get("/api/v1/offers?page=9999&page_size=25")
    enorme = await client.get("/api/v1/offers?page_size=100000")

    assert hors.status_code == 200 and hors.json()["items"] == []
    assert enorme.status_code in (200, 422)
    if enorme.status_code == 200:
        assert len(enorme.json()["items"]) <= 100  # jamais tout le catalogue en une réponse


async def test_une_page_profonde_n_est_pas_sensiblement_plus_lente(
    client: httpx.AsyncClient, catalogue: int
) -> None:
    _, premiere = await _mesure(client, "/api/v1/offers?page=1&page_size=25")
    reponse, profonde = await _mesure(client, f"/api/v1/offers?page={catalogue // 25}&page_size=25")

    assert reponse.status_code == 200 and reponse.json()["items"]
    assert profonde < SEUIL_LISTE_S, f"page profonde : {profonde:.2f}s (1re page {premiere:.2f}s)"


async def test_la_recherche_texte_retrouve_exactement_les_offres_concernees_et_reste_rapide(
    client: httpx.AsyncClient, catalogue: int
) -> None:
    reponse, duree = await _mesure(client, "/api/v1/offers?text=kubernetes&page_size=100")

    assert reponse.status_code == 200
    assert reponse.json()["total"] == catalogue // 100
    assert duree < SEUIL_RECHERCHE_S, f"recherche : {duree:.2f}s pour {catalogue} offres"


async def test_le_nombre_de_requetes_sql_ne_depend_pas_de_la_taille_de_page(
    client: httpx.AsyncClient, catalogue: int, requetes_sql: list[tuple[str, Any]]
) -> None:
    """Pas de N+1 : 5 ou 100 offres par page coûtent le même nombre de requêtes."""
    await client.get("/api/v1/offers?page_size=5")
    petite = len(requetes_sql)
    requetes_sql.clear()
    await client.get("/api/v1/offers?page_size=100")
    grande = len(requetes_sql)

    assert petite == grande
    assert grande <= REQUETES_MAX_PAR_LISTE


async def test_le_plan_d_execution_reel_de_la_liste_reste_sous_un_budget_de_temps(
    session: AsyncSession,
    client: httpx.AsyncClient,
    catalogue: int,
    requetes_sql: list[tuple[str, Any]],
) -> None:
    """EXPLAIN ANALYZE rejoué sur la requête RÉELLE de la liste, avec ses vrais paramètres."""
    await client.get("/api/v1/offers?page_size=25")
    candidates = [
        (sql, params)
        for sql, params in requetes_sql
        if "FROM job_offers" in sql
        and sql.lstrip().upper().startswith("SELECT")
        and "count(" not in sql.lower()
    ]
    assert candidates, "requête principale de liste introuvable"
    sql, params = max(candidates, key=lambda c: len(c[0]))

    connexion = await session.connection()
    resultat = await connexion.exec_driver_sql(f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}", params)
    plan = resultat.scalar_one()[0]

    assert plan["Execution Time"] < 500, f"plan : {plan['Execution Time']:.0f} ms"
    assert plan["Plan"]["Actual Rows"] <= 25  # la pagination est faite par la base, pas en mémoire


@pytest.fixture
async def moteur(schema_migre: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(to_driver_url(schema_migre))
    async with engine.begin() as c:
        await c.execute(delete(JobModel))
    yield engine
    async with engine.begin() as c:
        await c.execute(delete(JobModel))
    await engine.dispose()


async def test_dix_workers_concurrents_traitent_cent_taches_chacune_exactement_une_fois(
    moteur: AsyncEngine,
) -> None:
    """TASK-019-22 : sur PostgreSQL réel, sans session partagée, aucune tâche n'est perdue ni
    exécutée deux fois, même sous forte concurrence."""
    uow = UnitOfWork(create_session_factory(moteur))
    file = PostgresJobQueue(uow)
    for numero in range(100):
        await file.enqueue(kind="stress", idempotency_key=f"t{numero}")
    executions: list[uuid.UUID] = []

    async def gestionnaire(job: Any) -> None:
        executions.append(job.id)
        await asyncio.sleep(0)  # cède la main : favorise l'entrelacement

    workers = [JobWorker(file, {"stress": gestionnaire}, worker_id=f"w{i}") for i in range(10)]

    async def vider(worker: JobWorker) -> None:
        while await worker.run_once():
            pass

    await asyncio.wait_for(asyncio.gather(*(vider(w) for w in workers)), timeout=60)

    assert len(executions) == 100
    assert len(set(executions)) == 100


async def test_les_requetes_api_concurrentes_ne_se_melangent_pas(schema_migre: str) -> None:
    """Quarante requêtes simultanées, chacune avec sa propre transaction : toutes réussissent."""
    from app.main import create_app

    application = create_app()
    moteur = create_async_engine(to_driver_url(schema_migre))
    application.state.session_factory = create_session_factory(moteur)
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
            debut = time.perf_counter()
            reponses = await asyncio.gather(*(c.get("/api/v1/health/ready") for _ in range(40)))
            duree = time.perf_counter() - debut
    finally:
        await moteur.dispose()

    assert [r.status_code for r in reponses] == [200] * 40
    assert duree < 10
