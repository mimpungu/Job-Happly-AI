"""Requêtes SQL des faits d'automatisation, sur PostgreSQL réel (déplacées hors du métier)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.infrastructure.models import AISettingsModel, AIUsageModel
from app.modules.application_management.infrastructure.models import ApplicationModel
from app.modules.job_discovery.infrastructure.models import JobOfferModel, SavedSearchModel
from app.modules.notifications.infrastructure.automation_facts import SqlAutomationFacts
from app.modules.notifications.infrastructure.job_history import list_job_history
from app.modules.platform.infrastructure.models import JobModel, JobStatus, UserModel

MAINTENANT = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _offre(
    owner: uuid.UUID, titre: str, *, vue: datetime, entreprise: str | None = "Acme"
) -> JobOfferModel:
    return JobOfferModel(
        owner_id=owner,
        title=titre,
        company_name=entreprise,
        description="d",
        application_url=f"https://exemple.test/{uuid.uuid4()}",
        content_hash=uuid.uuid4().hex * 2,
        first_seen_at=vue,
        last_seen_at=vue,
        created_at=vue,
    )


@pytest.fixture
async def faits(session: AsyncSession) -> SqlAutomationFacts:
    return SqlAutomationFacts(session)


async def test_resume_quotidien_compte_uniquement_les_donnees_du_proprietaire(
    session: AsyncSession, user_id: uuid.UUID, faits: SqlAutomationFacts
) -> None:
    autre = UserModel(display_name="Autre")
    session.add(autre)
    await session.flush()
    recente, ancienne = MAINTENANT - timedelta(hours=3), MAINTENANT - timedelta(days=3)
    offres = [
        _offre(user_id, "Récente 1", vue=recente),
        _offre(user_id, "Récente 2", vue=recente, entreprise=None),
        _offre(user_id, "Ancienne", vue=ancienne),
        _offre(autre.id, "D'un autre", vue=recente),
    ]
    session.add_all(offres)
    await session.flush()
    for statut, relance in (
        ("sent", MAINTENANT - timedelta(days=1)),  # relance échue, à compter
        ("sent", MAINTENANT + timedelta(days=2)),  # relance future : non
        ("rejected", MAINTENANT - timedelta(days=1)),  # clos : ni relance ni active
        ("to_apply", None),  # active, sans relance
    ):
        offre = _offre(user_id, f"Cand {statut}", vue=ancienne)
        session.add(offre)
        await session.flush()
        session.add(
            ApplicationModel(
                owner_id=user_id, offer_id=offre.id, status=statut, follow_up_at=relance
            )
        )
    session.add(
        AIUsageModel(
            owner_id=user_id,
            provider="p",
            model="m",
            task_type="t",
            level=1,
            estimated_cost=Decimal("0.25"),
            actual_cost=Decimal("0.20"),
            currency="EUR",
            operation_id=uuid.uuid4(),
            outcome="success",
            created_at=MAINTENANT - timedelta(hours=1),
        )
    )
    await session.flush()

    resultat = await faits.digest_facts(user_id, now=MAINTENANT)

    assert resultat.new_offers_count == 2  # les 2 récentes seulement (pas l'ancienne ni l'autre)
    assert {o["company"] for o in resultat.sample_offers} <= {"Acme", "Entreprise"}
    assert len(resultat.sample_offers) == 2  # une ligne par offre récente (borné à 3)
    assert resultat.follow_ups_due == 1
    assert resultat.active_applications == 3  # tout sauf « rejected »
    assert resultat.ai_spent_today == Decimal("0.200000")  # coût réel prioritaire


async def test_recherche_sauvegardee_inconnue_ou_d_un_autre_est_introuvable(
    session: AsyncSession, user_id: uuid.UUID, faits: SqlAutomationFacts
) -> None:
    recherche = SavedSearchModel(owner_id=user_id, name="Python", criteria={}, active=False)
    session.add(recherche)
    await session.flush()

    trouvee = await faits.saved_search(user_id, recherche.id)

    assert trouvee is not None and trouvee.name == "Python" and trouvee.active is False
    assert await faits.saved_search(user_id, uuid.uuid4()) is None
    assert await faits.saved_search(uuid.uuid4(), recherche.id) is None


async def test_relances_dues_avec_intitule_entreprise_et_valeurs_de_repli(
    session: AsyncSession, user_id: uuid.UUID, faits: SqlAutomationFacts
) -> None:
    offre = _offre(user_id, "Ingénieur", vue=MAINTENANT, entreprise=None)
    session.add(offre)
    await session.flush()
    session.add(
        ApplicationModel(
            owner_id=user_id,
            offer_id=offre.id,
            status="interview",
            follow_up_at=MAINTENANT - timedelta(hours=1),
        )
    )
    await session.flush()

    relances = await faits.due_follow_ups(user_id, MAINTENANT)

    assert len(relances) == 1
    assert (relances[0].title, relances[0].company) == ("Ingénieur", "Entreprise")
    assert relances[0].offer_id == offre.id


async def test_offres_creees_depuis_et_devise(
    session: AsyncSession, user_id: uuid.UUID, faits: SqlAutomationFacts
) -> None:
    session.add(_offre(user_id, "Neuve", vue=MAINTENANT - timedelta(hours=2)))
    session.add(_offre(user_id, "Vieille", vue=MAINTENANT - timedelta(days=5)))
    await faits.ai_currency(user_id)  # sans réglage : repli sur l'euro
    await session.flush()

    assert await faits.offers_created_since(user_id, MAINTENANT - timedelta(days=1)) == 1
    assert await faits.ai_currency(user_id) == "EUR"
    session.add(AISettingsModel(owner_id=user_id, currency="USD"))
    await session.flush()
    assert await faits.ai_currency(user_id) == "USD"
    assert await faits.ai_spent_since(user_id, MAINTENANT) == Decimal("0.0000")


async def test_historique_des_taches_filtre_pagine_et_ordonne(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    for i, (statut, genre) in enumerate(
        [("succeeded", "a"), ("failed", "a"), ("succeeded", "b"), ("dead", "b")]
    ):
        session.add(
            JobModel(
                owner_id=user_id,
                kind=genre,
                idempotency_key=f"k{i}",
                status=statut if statut in {s.value for s in JobStatus} else "failed",
                created_at=MAINTENANT + timedelta(minutes=i),
            )
        )
    await session.flush()

    tous, total = await list_job_history(session, owner_id=user_id)
    reussis, n_reussis = await list_job_history(session, owner_id=user_id, status="succeeded")
    genre_b, n_b = await list_job_history(session, owner_id=user_id, kind="b")
    page, _ = await list_job_history(session, owner_id=user_id, limit=1, offset=1)

    assert total == 4 and [j["idempotency_key"] for j in tous] == ["k3", "k2", "k1", "k0"]
    assert n_reussis == 2 and {j["status"] for j in reussis} == {"succeeded"}
    assert n_b == 2 and {j["kind"] for j in genre_b} == {"b"}
    assert [j["idempotency_key"] for j in page] == ["k2"]
