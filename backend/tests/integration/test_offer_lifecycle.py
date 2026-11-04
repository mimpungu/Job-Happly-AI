import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.application_management.infrastructure.models import ApplicationModel
from app.modules.job_discovery.domain.offers import NormalizedOffer, UpsertResult
from app.modules.job_discovery.infrastructure.models import (
    JobOfferModel,
    JobOfferRevisionModel,
    JobOfferSourceModel,
    JobOfferStateModel,
    JobSourceModel,
)
from app.modules.job_discovery.infrastructure.repositories import SqlJobOfferRepository

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
DESCRIPTION = (
    "Vous rejoignez l'équipe data pour analyser les données clients avec SQL et Python, "
    "construire des tableaux de bord et fiabiliser les indicateurs de pilotage de l'activité."
)


def _offre(**champs: object) -> NormalizedOffer:
    valeurs: dict[str, object] = {
        "title": "Data Analyst",
        "description": DESCRIPTION,
        "application_url": "https://a.test/1",
        "content_hash": "a" * 64,
        "company_name": "Exemple SA",
        "location": "Paris, France",
    }
    valeurs.update(champs)
    return NormalizedOffer(**valeurs)  # type: ignore[arg-type]


async def _source(session: AsyncSession, user_id: uuid.UUID, key: str) -> JobSourceModel:
    source = JobSourceModel(owner_id=user_id, key=key, name=key, kind="official_api")
    session.add(source)
    await session.flush()
    return source


async def _observer(
    session: AsyncSession,
    user_id: uuid.UUID,
    source: JobSourceModel,
    offre: NormalizedOffer,
    *,
    externe: str = "E1",
    quand: datetime = T0,
) -> UpsertResult:
    return await SqlJobOfferRepository(session).upsert_observation(
        owner_id=user_id,
        source_id=source.id,
        external_id=externe,
        offer=offre,
        raw_payload={"id": externe},
        observed_at=quand,
    )


async def _compter(session: AsyncSession, modele: type) -> int:
    return int(await session.scalar(select(func.count()).select_from(modele)) or 0)


class TestDeduplicationMultiSources:
    async def test_meme_url_canonique_sur_deux_sources_donne_une_offre_deux_observations(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        b = await _source(session, user_id, "b")
        premiere = await _observer(
            session, user_id, a, _offre(canonical_url="https://www.exemple.test/o/1?utm_source=x")
        )

        seconde = await _observer(
            session, user_id, b, _offre(canonical_url="https://exemple.test/o/1/"), externe="Z9"
        )

        assert seconde.merged and not seconde.created
        assert seconde.offer_id == premiere.offer_id
        assert await _compter(session, JobOfferModel) == 1
        assert await _compter(session, JobOfferSourceModel) == 2

    async def test_la_canonicalisation_est_appliquee_au_stockage(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")

        resultat = await _observer(
            session, user_id, a, _offre(canonical_url="https://WWW.Exemple.test/o/1/?utm_x=1#top")
        )

        offre = await session.get(JobOfferModel, resultat.offer_id)
        assert offre is not None
        assert offre.canonical_url == "https://exemple.test/o/1"

    async def test_meme_poste_decrit_par_deux_sources_est_fusionne_par_criteres(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        b = await _source(session, user_id, "b")
        premiere = await _observer(session, user_id, a, _offre())

        seconde = await _observer(
            session,
            user_id,
            b,
            _offre(
                title="Data Analyst (H/F)", location="Paris", application_url="https://b.test/9"
            ),
            externe="B7",
        )

        assert seconde.merged
        assert seconde.offer_id == premiere.offer_id
        assert await _compter(session, JobOfferModel) == 1

    async def test_meme_poste_dans_une_autre_ville_reste_une_offre_distincte(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        b = await _source(session, user_id, "b")
        await _observer(session, user_id, a, _offre())

        seconde = await _observer(session, user_id, b, _offre(location="Marseille"), externe="B7")

        assert seconde.created and not seconde.merged
        assert await _compter(session, JobOfferModel) == 2

    async def test_la_fusion_ne_traverse_pas_les_proprietaires(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        from app.modules.platform.infrastructure.models import UserModel

        autre = UserModel()
        session.add(autre)
        await session.flush()
        a = await _source(session, user_id, "a")
        b = await _source(session, autre.id, "a")
        await _observer(session, user_id, a, _offre(canonical_url="https://exemple.test/o/1"))

        seconde = await _observer(
            session, autre.id, b, _offre(canonical_url="https://exemple.test/o/1")
        )

        assert seconde.created
        assert await _compter(session, JobOfferModel) == 2

    async def test_rejouer_la_collecte_complete_ne_cree_aucun_doublon(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        b = await _source(session, user_id, "b")
        for _ in range(3):
            await _observer(session, user_id, a, _offre(), externe="E1")
            await _observer(session, user_id, b, _offre(), externe="B7")

        assert await _compter(session, JobOfferModel) == 1
        assert await _compter(session, JobOfferSourceModel) == 2


class TestHistoriqueDesModifications:
    async def test_un_changement_conserve_l_etat_precedent(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        premiere = await _observer(session, user_id, a, _offre())

        modifiee = await _observer(
            session,
            user_id,
            a,
            _offre(title="Senior Data Analyst", content_hash="b" * 64),
            quand=T0 + timedelta(days=1),
        )

        assert modifiee.changed
        revisions = (await session.execute(select(JobOfferRevisionModel))).scalars().all()
        assert len(revisions) == 1
        assert revisions[0].offer_id == premiere.offer_id
        assert revisions[0].content_hash == "a" * 64
        assert revisions[0].snapshot["title"] == "Data Analyst"
        offre = await session.get(JobOfferModel, premiere.offer_id)
        assert offre is not None
        await session.refresh(offre)
        assert offre.title == "Senior Data Analyst"

    async def test_sans_changement_aucune_revision(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        await _observer(session, user_id, a, _offre())
        await _observer(session, user_id, a, _offre(), quand=T0 + timedelta(days=1))

        assert await _compter(session, JobOfferRevisionModel) == 0

    async def test_une_source_secondaire_differente_ne_reecrit_pas_la_fiche(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        b = await _source(session, user_id, "b")
        premiere = await _observer(session, user_id, a, _offre())
        await _observer(session, user_id, b, _offre(), externe="B7")

        resultat = await _observer(
            session,
            user_id,
            b,
            _offre(title="Data Analyst", content_hash="c" * 64),
            externe="B7",
            quand=T0 + timedelta(days=1),
        )

        assert not resultat.changed
        offre = await session.get(JobOfferModel, premiere.offer_id)
        assert offre is not None
        await session.refresh(offre)
        assert offre.content_hash == "a" * 64
        assert await _compter(session, JobOfferRevisionModel) == 0


class TestCycleDeVie:
    async def test_une_offre_disparue_de_sa_seule_source_expire(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        resultat = await _observer(session, user_id, a, _offre(), quand=T0)
        depot = SqlJobOfferRepository(session)
        maintenant = T0 + timedelta(days=2)

        disparues = await depot.mark_unseen_observations_gone(
            owner_id=user_id, source_id=a.id, seen_since=T0 + timedelta(days=1), now=maintenant
        )
        expirees = await depot.expire_offers(owner_id=user_id, now=maintenant)

        assert (disparues, expirees) == (1, 1)
        offre = await session.get(JobOfferModel, resultat.offer_id)
        assert offre is not None
        await session.refresh(offre)
        assert offre.status == "expired"

    async def test_une_offre_encore_visible_sur_une_autre_source_reste_active(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        b = await _source(session, user_id, "b")
        resultat = await _observer(session, user_id, a, _offre(), quand=T0)
        await _observer(session, user_id, b, _offre(), externe="B7", quand=T0 + timedelta(days=2))
        depot = SqlJobOfferRepository(session)
        maintenant = T0 + timedelta(days=3)

        await depot.mark_unseen_observations_gone(
            owner_id=user_id, source_id=a.id, seen_since=T0 + timedelta(days=1), now=maintenant
        )
        expirees = await depot.expire_offers(owner_id=user_id, now=maintenant)

        assert expirees == 0
        offre = await session.get(JobOfferModel, resultat.offer_id)
        assert offre is not None
        await session.refresh(offre)
        assert offre.status == "active"

    async def test_une_offre_deja_revue_n_est_pas_marquee_disparue(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        await _observer(session, user_id, a, _offre(), quand=T0 + timedelta(days=2))

        disparues = await SqlJobOfferRepository(session).mark_unseen_observations_gone(
            owner_id=user_id, source_id=a.id, seen_since=T0 + timedelta(days=1), now=T0
        )

        assert disparues == 0

    async def test_une_date_d_expiration_depassee_expire_l_offre(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        resultat = await _observer(
            session, user_id, a, _offre(expires_at=T0 + timedelta(days=5)), quand=T0
        )

        expirees = await SqlJobOfferRepository(session).expire_offers(
            owner_id=user_id, now=T0 + timedelta(days=6)
        )

        assert expirees == 1
        offre = await session.get(JobOfferModel, resultat.offer_id)
        assert offre is not None
        await session.refresh(offre)
        assert offre.status == "expired"

    async def test_la_reapparition_reactive_l_offre(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        resultat = await _observer(session, user_id, a, _offre(), quand=T0)
        depot = SqlJobOfferRepository(session)
        jour2 = T0 + timedelta(days=2)
        await depot.mark_unseen_observations_gone(
            owner_id=user_id, source_id=a.id, seen_since=T0 + timedelta(days=1), now=jour2
        )
        await depot.expire_offers(owner_id=user_id, now=jour2)

        await _observer(session, user_id, a, _offre(), quand=T0 + timedelta(days=3))

        offre = await session.get(JobOfferModel, resultat.offer_id)
        assert offre is not None
        await session.refresh(offre)
        assert offre.status == "active"
        observation = (await session.execute(select(JobOfferSourceModel))).scalar_one()
        assert observation.gone_at is None

    async def test_archive_les_offres_expirees_depuis_longtemps_sauf_suivies_ou_sauvegardees(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        a = await _source(session, user_id, "a")
        ids: dict[str, uuid.UUID] = {}
        for nom in ("simple", "suivie", "sauvegardee", "recente"):
            resultat = await _observer(
                session,
                user_id,
                a,
                _offre(title=f"Poste {nom}", application_url=f"https://a.test/{nom}"),
                externe=nom,
                quand=T0,
            )
            ids[nom] = resultat.offer_id
        await session.execute(
            update(JobOfferModel).where(JobOfferModel.id.in_(ids.values())).values(status="expired")
        )
        await session.execute(
            update(JobOfferModel)
            .where(JobOfferModel.id == ids["recente"])
            .values(last_seen_at=T0 + timedelta(days=100))
        )
        session.add(ApplicationModel(owner_id=user_id, offer_id=ids["suivie"]))
        session.add(
            JobOfferStateModel(owner_id=user_id, offer_id=ids["sauvegardee"], state="saved")
        )
        await session.flush()

        archivees = await SqlJobOfferRepository(session).archive_stale_offers(
            owner_id=user_id, expired_before=T0 + timedelta(days=90)
        )

        assert archivees == 1
        statuts = {
            nom: (await session.get(JobOfferModel, identifiant)) for nom, identifiant in ids.items()
        }
        for modele in statuts.values():
            assert modele is not None
            await session.refresh(modele)
        assert {n: m.status for n, m in statuts.items() if m} == {
            "simple": "archived",
            "suivie": "expired",
            "sauvegardee": "expired",
            "recente": "expired",
        }
