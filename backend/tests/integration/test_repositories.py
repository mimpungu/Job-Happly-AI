import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.session import UnitOfWork, create_session_factory, to_driver_url
from app.core.domain.value_objects import CountryCode, EmploymentType
from app.modules.ai_management.infrastructure.models import AIUsageModel
from app.modules.ai_management.infrastructure.repositories import SqlAIUsageRepository
from app.modules.job_discovery.domain.offers import NormalizedOffer, UpsertResult
from app.modules.job_discovery.infrastructure.models import (
    JobOfferModel,
    JobOfferSourceModel,
    JobSourceModel,
)
from app.modules.job_discovery.infrastructure.repositories import SqlJobOfferRepository
from app.modules.platform.infrastructure.models import UserModel

MAINTENANT = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def _offre(hash_: str = "a" * 64, titre: str = "Data Analyst") -> NormalizedOffer:
    return NormalizedOffer(
        title=titre,
        description="Description",
        application_url="https://exemple.test/1",
        content_hash=hash_,
        country_code=CountryCode("fr"),
        employment_type=EmploymentType.PERMANENT,
    )


async def _source(session: AsyncSession, user_id: uuid.UUID) -> JobSourceModel:
    source = JobSourceModel(owner_id=user_id, key="src", name="Source", kind="official_api")
    session.add(source)
    await session.flush()
    return source


async def _observer(
    session: AsyncSession,
    user_id: uuid.UUID,
    source: JobSourceModel,
    offre: NormalizedOffer,
    instant: datetime,
    external_id: str = "E1",
    raw_payload: dict[str, Any] | None = None,
) -> UpsertResult:
    return await SqlJobOfferRepository(session).upsert_observation(
        owner_id=user_id,
        source_id=source.id,
        external_id=external_id,
        offer=offre,
        raw_payload=raw_payload or {},
        observed_at=instant,
    )


async def _compter(session: AsyncSession, modele: type) -> int:
    return int(await session.scalar(select(func.count()).select_from(modele)) or 0)


class TestJobOfferRepository:
    async def test_cree_l_offre_et_son_observation_avec_la_donnee_brute(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        source = await _source(session, user_id)

        resultat = await SqlJobOfferRepository(session).upsert_observation(
            owner_id=user_id,
            source_id=source.id,
            external_id="E1",
            offer=_offre(),
            raw_payload={"id": "E1", "brut": True},
            observed_at=MAINTENANT,
        )

        assert resultat.created and not resultat.changed
        observation = (await session.execute(select(JobOfferSourceModel))).scalar_one()
        assert observation.raw_payload == {"id": "E1", "brut": True}
        offre = await session.get(JobOfferModel, resultat.offer_id)
        assert offre is not None
        assert offre.country_code == "FR"
        assert offre.first_seen_at == MAINTENANT

    async def test_rejouer_la_meme_observation_ne_cree_aucun_doublon(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        source = await _source(session, user_id)
        premier = await _observer(session, user_id, source, _offre(), MAINTENANT)
        second = await _observer(
            session, user_id, source, _offre(), MAINTENANT + timedelta(hours=1)
        )

        assert second.offer_id == premier.offer_id
        assert not second.created and not second.changed
        assert await _compter(session, JobOfferModel) == 1
        assert await _compter(session, JobOfferSourceModel) == 1
        offre = await session.get(JobOfferModel, premier.offer_id)
        assert offre is not None
        await session.refresh(offre)
        assert offre.last_seen_at == MAINTENANT + timedelta(hours=1)
        assert offre.first_seen_at == MAINTENANT

    async def test_un_contenu_modifie_est_signale_et_mis_a_jour(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        source = await _source(session, user_id)
        premier = await _observer(session, user_id, source, _offre(), MAINTENANT)

        modifie = await _observer(
            session, user_id, source, _offre("b" * 64, "Senior Data Analyst"), MAINTENANT
        )

        assert modifie.changed and not modifie.created
        offre = await session.get(JobOfferModel, premier.offer_id)
        assert offre is not None
        await session.refresh(offre)
        assert offre.title == "Senior Data Analyst"
        assert offre.content_hash == "b" * 64

    async def test_la_reobservation_reactive_une_offre_expiree(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        source = await _source(session, user_id)
        premier = await _observer(session, user_id, source, _offre(), MAINTENANT)
        offre = await session.get(JobOfferModel, premier.offer_id)
        assert offre is not None
        offre.status = "expired"
        await session.flush()

        await _observer(session, user_id, source, _offre(), MAINTENANT)
        await session.refresh(offre)

        assert offre.status == "active"

    async def test_une_meme_reference_sur_deux_sources_donne_deux_observations_distinctes(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id)
        b = JobSourceModel(owner_id=user_id, key="autre", name="Autre", kind="public_ats")
        session.add(b)
        await session.flush()
        depot = SqlJobOfferRepository(session)

        await depot.upsert_observation(
            owner_id=user_id,
            source_id=a.id,
            external_id="E1",
            offer=_offre(),
            raw_payload={},
            observed_at=MAINTENANT,
        )
        await depot.upsert_observation(
            owner_id=user_id,
            source_id=b.id,
            external_id="E1",
            offer=_offre(),
            raw_payload={},
            observed_at=MAINTENANT,
        )

        assert await _compter(session, JobOfferSourceModel) == 2


class TestAIUsageRepository:
    async def _usage(
        self, session: AsyncSession, user_id: uuid.UUID, cout: str, **champs: object
    ) -> None:
        valeurs: dict[str, object] = {
            "owner_id": user_id,
            "provider": "p1",
            "model": "m",
            "task_type": "t",
            "level": 1,
            "currency": "EUR",
            "operation_id": uuid.uuid4(),
            "outcome": "success",
            "estimated_cost": Decimal(cout),
            "created_at": MAINTENANT,
        }
        valeurs.update(champs)
        await SqlAIUsageRepository(session).add(AIUsageModel(**valeurs))

    async def test_additionne_le_cout_reel_sinon_estime(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await self._usage(session, user_id, "0.10")
        await self._usage(session, user_id, "0.10", actual_cost=Decimal("0.25"))

        total = await SqlAIUsageRepository(session).total_cost(
            owner_id=user_id,
            since=MAINTENANT - timedelta(days=1),
            until=MAINTENANT + timedelta(days=1),
        )

        assert total == Decimal("0.35")

    async def test_exclut_les_appels_refuses_ou_servis_par_le_cache(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await self._usage(session, user_id, "1.00")
        await self._usage(session, user_id, "5.00", outcome="blocked_budget")
        await self._usage(session, user_id, "5.00", outcome="cache_hit", cache_hit=True)

        total = await SqlAIUsageRepository(session).total_cost(
            owner_id=user_id,
            since=MAINTENANT - timedelta(days=1),
            until=MAINTENANT + timedelta(days=1),
        )

        assert total == Decimal("1.00")

    async def test_respecte_la_periode_le_fournisseur_et_le_proprietaire(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        autre = UserModel()
        session.add(autre)
        await session.flush()
        await self._usage(session, user_id, "1.00")
        await self._usage(session, user_id, "2.00", provider="p2")
        await self._usage(session, user_id, "4.00", created_at=MAINTENANT - timedelta(days=40))
        await self._usage(session, autre.id, "8.00")
        depot = SqlAIUsageRepository(session)
        debut = MAINTENANT - timedelta(days=1)
        fin = MAINTENANT + timedelta(days=1)

        assert await depot.total_cost(owner_id=user_id, since=debut, until=fin) == Decimal("3.00")
        assert await depot.total_cost(
            owner_id=user_id, since=debut, until=fin, provider="p2"
        ) == Decimal("2.00")

    async def test_la_borne_de_fin_est_exclue(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await self._usage(session, user_id, "1.00")

        total = await SqlAIUsageRepository(session).total_cost(
            owner_id=user_id, since=MAINTENANT - timedelta(days=1), until=MAINTENANT
        )

        assert total == Decimal("0")

    async def test_zero_depense_retourne_zero(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        total = await SqlAIUsageRepository(session).total_cost(
            owner_id=user_id, since=MAINTENANT - timedelta(days=1), until=MAINTENANT
        )

        assert total == Decimal("0")


class TestUnitOfWork:
    async def test_valide_en_cas_de_succes_et_annule_en_cas_d_erreur(
        self, schema_migre: str
    ) -> None:
        engine = create_async_engine(to_driver_url(schema_migre))
        factory = create_session_factory(engine)
        uow = UnitOfWork(factory)
        valide = uuid.uuid4()
        annule = uuid.uuid4()
        try:
            async with uow.begin() as s:
                s.add(UserModel(id=valide, display_name="uow-valide"))

            with pytest.raises(RuntimeError):
                async with uow.begin() as s:
                    s.add(UserModel(id=annule, display_name="uow-annule"))
                    await s.flush()
                    raise RuntimeError("échec métier")

            async with factory() as s:
                assert await s.get(UserModel, valide) is not None
                assert await s.get(UserModel, annule) is None
                # nettoyage : cette unité de travail a réellement validé sa donnée
                utilisateur = await s.get(UserModel, valide)
                assert utilisateur is not None
                await s.delete(utilisateur)
                await s.commit()
        finally:
            await engine.dispose()
