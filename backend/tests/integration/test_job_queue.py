import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.database.session import UnitOfWork, create_session_factory, to_driver_url
from app.modules.platform.application.worker import JobWorker, NonRetryableJobError, backoff
from app.modules.platform.infrastructure.job_queue import PostgresJobQueue, ReservedJob
from app.modules.platform.infrastructure.models import JobModel, JobStatus

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


class Horloge:
    def __init__(self) -> None:
        self.maintenant = T0

    def __call__(self) -> datetime:
        return self.maintenant


@pytest.fixture
async def engine(schema_migre: str) -> AsyncIterator[AsyncEngine]:
    moteur = create_async_engine(to_driver_url(schema_migre))
    # Les opérations de la file valident réellement : on repart d'une table vide, avant et après.
    async with moteur.begin() as connexion:
        await connexion.execute(delete(JobModel))
    yield moteur
    async with moteur.begin() as connexion:
        await connexion.execute(delete(JobModel))
    await moteur.dispose()


@pytest.fixture
def horloge() -> Horloge:
    return Horloge()


@pytest.fixture
def uow(engine: AsyncEngine) -> UnitOfWork:
    return UnitOfWork(create_session_factory(engine))


@pytest.fixture
def file(uow: UnitOfWork, horloge: Horloge) -> PostgresJobQueue:
    return PostgresJobQueue(uow, clock=horloge)


async def _etat(uow: UnitOfWork, job_id: uuid.UUID) -> JobModel:
    async with uow.begin() as session:
        job = await session.get(JobModel, job_id)
        assert job is not None
        session.expunge(job)
        return job


class TestIdempotence:
    async def test_deux_tâches_actives_identiques_n_en_font_qu_une(
        self, file: PostgresJobQueue
    ) -> None:
        premiere = await file.enqueue(kind="ingestion", idempotency_key="recherche-1")
        seconde = await file.enqueue(kind="ingestion", idempotency_key="recherche-1")

        assert premiere.created and not seconde.created
        assert seconde.job_id == premiere.job_id

    async def test_des_cles_ou_types_differents_sont_independants(
        self, file: PostgresJobQueue
    ) -> None:
        a = await file.enqueue(kind="ingestion", idempotency_key="k")
        b = await file.enqueue(kind="ingestion", idempotency_key="autre")
        c = await file.enqueue(kind="documents", idempotency_key="k")

        assert len({a.job_id, b.job_id, c.job_id}) == 3

    async def test_une_tache_terminee_peut_etre_replanifiee(self, file: PostgresJobQueue) -> None:
        premiere = await file.enqueue(kind="ingestion", idempotency_key="k")
        job = await file.reserve(worker_id="w1")
        assert job is not None
        await file.complete(job.id)

        seconde = await file.enqueue(kind="ingestion", idempotency_key="k")

        assert seconde.created
        assert seconde.job_id != premiere.job_id

    async def test_refuse_un_nombre_de_tentatives_invalide(self, file: PostgresJobQueue) -> None:
        with pytest.raises(ValueError):
            await file.enqueue(kind="k", idempotency_key="k", max_attempts=0)


class TestReservation:
    async def test_reserve_dans_l_ordre_et_ignore_les_taches_futures(
        self, file: PostgresJobQueue, horloge: Horloge
    ) -> None:
        futur = await file.enqueue(
            kind="k", idempotency_key="futur", run_at=T0 + timedelta(hours=1)
        )
        ancienne = await file.enqueue(
            kind="k", idempotency_key="ancienne", run_at=T0 - timedelta(minutes=5)
        )
        recente = await file.enqueue(kind="k", idempotency_key="recente", run_at=T0)

        premiere = await file.reserve(worker_id="w1")
        seconde = await file.reserve(worker_id="w1")
        aucune = await file.reserve(worker_id="w1")

        assert premiere is not None and premiere.id == ancienne.job_id
        assert seconde is not None and seconde.id == recente.job_id
        assert aucune is None  # la tâche future n'est pas encore prête
        horloge.maintenant = T0 + timedelta(hours=2)
        tardive = await file.reserve(worker_id="w1")
        assert tardive is not None and tardive.id == futur.job_id

    async def test_deux_workers_concurrents_ne_prennent_jamais_la_meme_tache(
        self, file: PostgresJobQueue
    ) -> None:
        for numero in range(6):
            await file.enqueue(kind="k", idempotency_key=f"t{numero}")

        reservations = await asyncio.gather(*(file.reserve(worker_id=f"w{i}") for i in range(6)))

        ids = [r.id for r in reservations if r is not None]
        assert len(ids) == 6
        assert len(set(ids)) == 6  # aucune tâche attribuée deux fois

    async def test_la_tache_reservee_est_en_cours_avec_son_verrou(
        self, file: PostgresJobQueue, uow: UnitOfWork
    ) -> None:
        await file.enqueue(kind="k", idempotency_key="k", payload={"critere": "data"})

        job = await file.reserve(worker_id="w1")

        assert job is not None
        assert (job.attempts, job.payload) == (1, {"critere": "data"})
        etat = await _etat(uow, job.id)
        assert (etat.status, etat.locked_by) == ("running", "w1")


class TestEchecsEtReprises:
    async def test_un_echec_remet_en_attente_avec_delai_puis_epuise_les_tentatives(
        self, file: PostgresJobQueue, uow: UnitOfWork, horloge: Horloge
    ) -> None:
        enfile = await file.enqueue(kind="k", idempotency_key="k", max_attempts=2)

        premiere = await file.reserve(worker_id="w1")
        assert premiere is not None
        etat1 = await file.fail(premiere.id, error="réseau", retry_delay=timedelta(minutes=5))
        assert etat1 is JobStatus.QUEUED
        assert await file.reserve(worker_id="w1") is None  # délai non écoulé

        horloge.maintenant += timedelta(minutes=6)
        seconde = await file.reserve(worker_id="w1")
        assert seconde is not None and seconde.attempts == 2
        etat2 = await file.fail(seconde.id, error="réseau", retry_delay=timedelta(minutes=5))

        assert etat2 is JobStatus.DEAD
        job = await _etat(uow, enfile.job_id)
        assert job.status == "dead"
        assert job.last_error == "réseau"
        assert job.finished_at is not None  # conservée et consultable, jamais supprimée

    async def test_un_echec_definitif_n_est_pas_rejoue(self, file: PostgresJobQueue) -> None:
        await file.enqueue(kind="k", idempotency_key="k", max_attempts=5)
        job = await file.reserve(worker_id="w1")
        assert job is not None

        etat = await file.fail(job.id, error="invalide", retry_delay=None)

        assert etat is JobStatus.FAILED
        assert await file.reserve(worker_id="w1") is None

    async def test_le_message_d_erreur_est_borne(
        self, file: PostgresJobQueue, uow: UnitOfWork
    ) -> None:
        await file.enqueue(kind="k", idempotency_key="k")
        job = await file.reserve(worker_id="w1")
        assert job is not None

        await file.fail(job.id, error="x" * 5000, retry_delay=None)

        assert len((await _etat(uow, job.id)).last_error or "") == 500

    async def test_une_tache_interrompue_est_reprise_apres_expiration_du_verrou(
        self, file: PostgresJobQueue, horloge: Horloge
    ) -> None:
        await file.enqueue(kind="k", idempotency_key="k")
        job = await file.reserve(worker_id="mort")
        assert job is not None
        horloge.maintenant += timedelta(minutes=10)

        assert await file.recover_stale(lock_timeout=timedelta(minutes=15)) == 0  # verrou valide
        horloge.maintenant += timedelta(minutes=10)
        assert await file.recover_stale(lock_timeout=timedelta(minutes=15)) == 1

        reprise = await file.reserve(worker_id="vivant")
        assert reprise is not None and reprise.id == job.id and reprise.attempts == 2

    async def test_une_tache_interrompue_au_dernier_essai_devient_morte(
        self, file: PostgresJobQueue, uow: UnitOfWork, horloge: Horloge
    ) -> None:
        enfile = await file.enqueue(kind="k", idempotency_key="k", max_attempts=1)
        await file.reserve(worker_id="mort")
        horloge.maintenant += timedelta(hours=1)

        await file.recover_stale(lock_timeout=timedelta(minutes=15))

        assert (await _etat(uow, enfile.job_id)).status == "dead"

    async def test_completer_une_tache_non_en_cours_ne_change_rien(
        self, file: PostgresJobQueue, uow: UnitOfWork
    ) -> None:
        enfile = await file.enqueue(kind="k", idempotency_key="k")

        await file.complete(enfile.job_id)

        assert (await _etat(uow, enfile.job_id)).status == "queued"


class TestWorker:
    def _worker(self, file: PostgresJobQueue, handlers: dict) -> JobWorker:  # type: ignore[type-arg]
        return JobWorker(file, handlers, worker_id="test")

    async def test_execute_la_tache_et_la_marque_terminee(
        self, file: PostgresJobQueue, uow: UnitOfWork
    ) -> None:
        recus: list[ReservedJob] = []

        async def gestionnaire(job: ReservedJob) -> None:
            recus.append(job)

        enfile = await file.enqueue(kind="ingestion", idempotency_key="k", payload={"a": 1})

        assert await self._worker(file, {"ingestion": gestionnaire}).run_once() is True

        assert recus[0].payload == {"a": 1}
        assert (await _etat(uow, enfile.job_id)).status == "succeeded"

    async def test_file_vide(self, file: PostgresJobQueue) -> None:
        assert await self._worker(file, {}).run_once() is False

    async def test_une_exception_est_journalisee_puis_la_tache_est_rejouee(
        self, file: PostgresJobQueue, uow: UnitOfWork, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def casse(job: ReservedJob) -> None:
            raise ConnectionError("réseau coupé")

        enfile = await file.enqueue(kind="k", idempotency_key="k")

        with caplog.at_level("ERROR", logger="happly.worker"):
            await self._worker(file, {"k": casse}).run_once()

        job = await _etat(uow, enfile.job_id)
        assert job.status == "queued"
        assert job.last_error == "ConnectionError: réseau coupé"
        assert "Échec de tâche" in caplog.text  # jamais avalée silencieusement

    async def test_un_echec_non_rejouable_est_definitif(
        self, file: PostgresJobQueue, uow: UnitOfWork
    ) -> None:
        async def refuse(job: ReservedJob) -> None:
            raise NonRetryableJobError("critères invalides")

        enfile = await file.enqueue(kind="k", idempotency_key="k", max_attempts=5)

        await self._worker(file, {"k": refuse}).run_once()

        job = await _etat(uow, enfile.job_id)
        assert (job.status, job.last_error) == ("failed", "critères invalides")

    async def test_un_type_sans_gestionnaire_echoue_explicitement(
        self, file: PostgresJobQueue, uow: UnitOfWork
    ) -> None:
        enfile = await file.enqueue(kind="inconnu", idempotency_key="k")

        await self._worker(file, {}).run_once()

        job = await _etat(uow, enfile.job_id)
        assert job.status == "failed"
        assert "inconnu" in (job.last_error or "")

    async def test_run_forever_traite_la_file_puis_s_arrete(self, file: PostgresJobQueue) -> None:
        traitees: list[str] = []
        arret = asyncio.Event()

        async def gestionnaire(job: ReservedJob) -> None:
            traitees.append(job.kind)
            if len(traitees) == 2:
                arret.set()

        await file.enqueue(kind="k", idempotency_key="1")
        await file.enqueue(kind="k", idempotency_key="2")
        worker = JobWorker(file, {"k": gestionnaire}, worker_id="t", poll_interval=0.01)

        await asyncio.wait_for(worker.run_forever(arret), timeout=5)

        assert traitees == ["k", "k"]


def test_attente_exponentielle_plafonnee() -> None:
    assert backoff(1) == timedelta(seconds=30)
    assert backoff(2) == timedelta(seconds=60)
    assert backoff(3) == timedelta(seconds=120)
    assert backoff(20) == timedelta(seconds=3600)
    assert backoff(0) == timedelta(seconds=30)


async def test_enqueue_reste_fiable_apres_de_nombreuses_executions_sur_la_meme_connexion(
    file: PostgresJobQueue,
) -> None:
    """Régression : au-delà de 5 exécutions d'une même requête préparée, PostgreSQL bascule sur un
    plan générique ; un prédicat d'index partiel passé en paramètres n'était alors plus reconnu
    et l'enqueue échouait (« no unique or exclusion constraint matching ON CONFLICT »)."""
    resultats = [await file.enqueue(kind="regression", idempotency_key=f"k{i}") for i in range(15)]

    assert all(r.created for r in resultats)
    doublon = await file.enqueue(kind="regression", idempotency_key="k0")
    assert doublon.created is False and doublon.job_id == resultats[0].job_id
