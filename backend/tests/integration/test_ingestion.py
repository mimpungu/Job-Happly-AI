import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database.session import UnitOfWork
from app.modules.job_discovery.application.ingestion import (
    IngestionReport,
    IngestionService,
)
from app.modules.job_discovery.domain.connector import (
    ConnectorOffer,
    SourceUnavailableError,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SearchRunStatus
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.infrastructure.models import (
    JobOfferModel,
    JobOfferSourceModel,
    JobSourceModel,
)
from tests.unit.job_discovery.fakes import PagedFakeConnector

DESCRIPTION = (
    "Vous rejoignez l'équipe data pour analyser les données clients avec SQL et Python, "
    "construire des tableaux de bord et fiabiliser les indicateurs de pilotage de l'activité."
)
CRITERES = SearchCriteria(title="Data")
T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


class _SessionPartagee(UnitOfWork):
    """Unité de travail de TEST : réutilise la session du test (annulée à la fin du test)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(async_sessionmaker())
        self._session = session

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        async with self._session.begin_nested():
            yield self._session


class Horloge:
    def __init__(self) -> None:
        self.maintenant = T0

    def __call__(self) -> datetime:
        return self.maintenant


def _offre(identifiant: str, titre: str = "Data Analyst", **champs: object) -> ConnectorOffer:
    valeurs: dict[str, Any] = {
        "title": titre,
        "description": DESCRIPTION,
        "application_url": f"https://a.test/{identifiant}",
        "content_hash": (identifiant * 64)[:64]
        if len(identifiant) == 1
        else f"{identifiant:0<64}"[:64],
        "company_name": f"Entreprise {identifiant}",
        "location": "Paris, France",
    }
    valeurs.update(champs)
    return ConnectorOffer(
        external_id=identifiant, offer=NormalizedOffer(**valeurs), raw_payload={"id": identifiant}
    )


async def _preparer(session: AsyncSession, user_id: uuid.UUID, *cles: str) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    for cle in cles:
        source = JobSourceModel(owner_id=user_id, key=cle, name=cle, kind="official_api")
        session.add(source)
        await session.flush()
        ids[cle] = source.id
    return ids


async def _offres(session: AsyncSession) -> list[JobOfferModel]:
    return list(
        (await session.execute(select(JobOfferModel).order_by(JobOfferModel.title))).scalars()
    )


async def _ingerer(
    session: AsyncSession,
    user_id: uuid.UUID,
    connecteurs: list[PagedFakeConnector],
    ids: dict[str, uuid.UUID],
    horloge: Horloge | None = None,
    **options: Any,
) -> IngestionReport:
    service = IngestionService(_SessionPartagee(session), clock=horloge or Horloge())
    return await service.ingest(
        owner_id=user_id, connectors=connecteurs, source_ids=ids, criteria=CRITERES, **options
    )


class TestIngestion:
    async def test_ingere_toutes_les_pages_et_normalise(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "a")
        connecteur = PagedFakeConnector(
            "a",
            [
                [_offre("1", "Data Analyst (H/F)", location="Lyon, France", country_code=None)],
                [_offre("2", "Data Engineer"), _offre("3", "Data Scientist")],
            ],
        )

        rapport = await _ingerer(session, user_id, [connecteur], ids)

        bilan = rapport.outcomes[0]
        assert (bilan.pages, bilan.fetched, bilan.created) == (2, 3, 3)
        assert bilan.succeeded and bilan.complete
        assert rapport.status is SearchRunStatus.SUCCEEDED
        offres = {o.title: o for o in await _offres(session)}
        assert set(offres) == {"Data Analyst", "Data Engineer", "Data Scientist"}  # (H/F) retiré
        assert offres["Data Analyst"].country_code == "FR"  # déduit du lieu explicite

    async def test_relancer_l_ingestion_ne_cree_aucun_doublon(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "a")
        pages = [[_offre("1"), _offre("2")]]

        premiere = await _ingerer(session, user_id, [PagedFakeConnector("a", pages)], ids)
        seconde = await _ingerer(session, user_id, [PagedFakeConnector("a", pages)], ids)

        assert premiere.outcomes[0].created == 2
        assert (seconde.outcomes[0].created, seconde.outcomes[0].unchanged) == (0, 2)
        assert len(await _offres(session)) == 2
        observations = (await session.execute(select(JobOfferSourceModel))).scalars().all()
        assert len(observations) == 2

    async def test_signale_les_offres_modifiees(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "a")
        await _ingerer(session, user_id, [PagedFakeConnector("a", [[_offre("1")]])], ids)

        rapport = await _ingerer(
            session,
            user_id,
            [
                PagedFakeConnector(
                    "a",
                    [[_offre("1", description=DESCRIPTION + " Nouveau.", content_hash="e" * 64)]],
                )
            ],
            ids,
        )

        assert rapport.outcomes[0].changed == 1

    async def test_une_offre_deja_vue_sur_une_autre_source_est_fusionnee(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "a", "b")
        commun = {"company_name": "Exemple SA"}

        rapport = await _ingerer(
            session,
            user_id,
            [
                PagedFakeConnector("a", [[_offre("1", **commun)]]),
                PagedFakeConnector("b", [[_offre("9", **commun)]]),
            ],
            ids,
            concurrency=1,
        )

        assert sum(o.created for o in rapport.outcomes) == 1
        assert sum(o.merged for o in rapport.outcomes) == 1
        assert len(await _offres(session)) == 1


class TestErreursPartielles:
    async def test_une_source_en_echec_n_arrete_pas_les_autres(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "ok", "panne")
        panne = PagedFakeConnector(
            "panne", [[_offre("7")]], fail_on_page=0, error=SourceUnavailableError("500")
        )

        rapport = await _ingerer(
            session, user_id, [PagedFakeConnector("ok", [[_offre("1")]]), panne], ids
        )

        par_cle = {o.source_key: o for o in rapport.outcomes}
        assert par_cle["ok"].succeeded and par_cle["ok"].created == 1
        assert not par_cle["panne"].succeeded
        assert par_cle["panne"].error_type == "SourceUnavailableError"
        assert rapport.status is SearchRunStatus.PARTIAL

    async def test_les_pages_deja_enregistrees_sont_conservees_apres_un_echec(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "a")
        connecteur = PagedFakeConnector(
            "a",
            [[_offre("1")], [_offre("2")]],
            fail_on_page=1,
            error=SourceUnavailableError("500"),
        )

        rapport = await _ingerer(session, user_id, [connecteur], ids)

        bilan = rapport.outcomes[0]
        assert not bilan.succeeded and not bilan.complete
        assert (bilan.pages, bilan.created) == (1, 1)
        assert len(await _offres(session)) == 1
        assert rapport.status is SearchRunStatus.FAILED

    async def test_une_offre_invalide_est_ecartee_sans_perdre_la_page(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "a")
        mauvaise = _offre("1", content_hash="trop-court")

        rapport = await _ingerer(
            session, user_id, [PagedFakeConnector("a", [[mauvaise, _offre("2")]])], ids
        )

        bilan = rapport.outcomes[0]
        assert (bilan.rejected, bilan.created) == (1, 1)
        assert bilan.succeeded
        assert len(await _offres(session)) == 1

    async def test_aucune_source_donne_un_rapport_en_echec(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        rapport = await _ingerer(session, user_id, [], {})

        assert rapport.status is SearchRunStatus.FAILED

    async def test_parametres_invalides(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        with pytest.raises(ValueError):
            await _ingerer(session, user_id, [], {}, max_pages=0)
        with pytest.raises(ValueError):
            await _ingerer(session, user_id, [], {}, concurrency=0)


class TestCycleDeVieIngestion:
    async def test_limite_de_pages_atteinte_n_est_pas_un_parcours_complet(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "a")
        connecteur = PagedFakeConnector("a", [[_offre("1")], [_offre("2")], [_offre("3")]])

        rapport = await _ingerer(session, user_id, [connecteur], ids, max_pages=2)

        bilan = rapport.outcomes[0]
        assert bilan.pages == 2
        assert bilan.succeeded and not bilan.complete

    async def test_catalogue_complet_declare_les_offres_absentes_comme_expirees(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "a")
        horloge = Horloge()
        await _ingerer(
            session, user_id, [PagedFakeConnector("a", [[_offre("1"), _offre("2")]])], ids, horloge
        )
        horloge.maintenant = T0 + timedelta(days=1)

        rapport = await _ingerer(
            session,
            user_id,
            [PagedFakeConnector("a", [[_offre("1")]])],  # l'offre 2 a disparu
            ids,
            horloge,
            full_catalogue=True,
        )

        assert rapport.outcomes[0].expired == 1
        statuts = {o.application_url[-1]: o.status for o in await _offres(session)}
        assert statuts == {"1": "active", "2": "expired"}

    async def test_une_recherche_filtree_n_expire_jamais_les_offres_absentes(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "a")
        horloge = Horloge()
        await _ingerer(
            session, user_id, [PagedFakeConnector("a", [[_offre("1"), _offre("2")]])], ids, horloge
        )
        horloge.maintenant = T0 + timedelta(days=1)

        await _ingerer(session, user_id, [PagedFakeConnector("a", [[_offre("1")]])], ids, horloge)

        assert {o.status for o in await _offres(session)} == {"active"}

    async def test_un_parcours_incomplet_n_expire_rien_meme_en_mode_catalogue(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        ids = await _preparer(session, user_id, "a")
        horloge = Horloge()
        await _ingerer(
            session, user_id, [PagedFakeConnector("a", [[_offre("1"), _offre("2")]])], ids, horloge
        )
        horloge.maintenant = T0 + timedelta(days=1)
        en_panne = PagedFakeConnector(
            "a", [[_offre("1")], [_offre("2")]], fail_on_page=1, error=SourceUnavailableError("500")
        )

        await _ingerer(session, user_id, [en_panne], ids, horloge, full_catalogue=True)

        assert {o.status for o in await _offres(session)} == {"active"}
