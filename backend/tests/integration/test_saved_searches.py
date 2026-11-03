import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.value_objects import RemoteType
from app.modules.job_discovery.application.saved_searches import SearchService
from app.modules.job_discovery.domain.saved_search import (
    DuplicateSavedSearchError,
    InvalidSavedSearchError,
    SavedSearchNotFoundError,
)
from app.modules.job_discovery.domain.search import OfferFilter, OfferSort
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.job_discovery.infrastructure.offer_queries import SqlOfferQueryRepository
from app.modules.job_discovery.infrastructure.saved_search_repository import (
    SqlSavedSearchRepository,
)
from app.modules.platform.infrastructure.models import UserModel

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


async def _offre(session: AsyncSession, owner_id: uuid.UUID, titre: str) -> None:
    session.add(
        JobOfferModel(
            owner_id=owner_id,
            title=titre,
            description="d",
            application_url="https://a.test/" + uuid.uuid4().hex,
            content_hash=uuid.uuid4().hex * 2,
        )
    )
    await session.flush()


async def test_les_criteres_sont_restitues_a_l_identique(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    repo = SqlSavedSearchRepository(session)
    criteres = OfferFilter(
        text="python",
        country_codes=("FR", "BE"),
        remote_types=(RemoteType.REMOTE,),
        salary_min=Decimal(45000),
        salary_currency="EUR",
        sort=OfferSort.TITLE_ASC,
        page=4,
    )

    creee = await repo.create(owner_id=user_id, name="  Python   remote ", offer_filter=criteres)
    relue = await repo.get(owner_id=user_id, search_id=creee.id)

    assert relue.name == "Python remote"
    assert relue.offer_filter == criteres.model_copy(
        update={"page": 1}
    )  # la page n'est pas mémorisée


async def test_deux_recherches_ne_partagent_pas_un_nom_meme_en_changeant_la_casse(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    repo = SqlSavedSearchRepository(session)
    await repo.create(owner_id=user_id, name="Data", offer_filter=OfferFilter())

    with pytest.raises(DuplicateSavedSearchError):
        await repo.create(owner_id=user_id, name="DATA", offer_filter=OfferFilter())
    # La transaction reste utilisable après le refus.
    assert len(await repo.list(owner_id=user_id)) == 1


async def test_nom_vide_refuse(session: AsyncSession, user_id: uuid.UUID) -> None:
    with pytest.raises(InvalidSavedSearchError):
        await SqlSavedSearchRepository(session).create(
            owner_id=user_id, name="   ", offer_filter=OfferFilter()
        )


async def test_modification_partielle(session: AsyncSession, user_id: uuid.UUID) -> None:
    repo = SqlSavedSearchRepository(session)
    creee = await repo.create(owner_id=user_id, name="A", offer_filter=OfferFilter(text="x"))

    modifiee = await repo.update(owner_id=user_id, search_id=creee.id, active=False)
    assert (modifiee.name, modifiee.active, modifiee.offer_filter.text) == ("A", False, "x")

    renommee = await repo.update(
        owner_id=user_id, search_id=creee.id, name="B", offer_filter=OfferFilter(text="y")
    )
    assert (renommee.name, renommee.offer_filter.text) == ("B", "y")


async def test_renommer_vers_un_nom_pris_est_refuse(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    repo = SqlSavedSearchRepository(session)
    await repo.create(owner_id=user_id, name="A", offer_filter=OfferFilter())
    seconde = await repo.create(owner_id=user_id, name="B", offer_filter=OfferFilter())

    with pytest.raises(DuplicateSavedSearchError):
        await repo.update(owner_id=user_id, search_id=seconde.id, name="a")


async def test_isolation_entre_proprietaires(session: AsyncSession, user_id: uuid.UUID) -> None:
    autre = UserModel(display_name="Autre")
    session.add(autre)
    await session.flush()
    repo = SqlSavedSearchRepository(session)
    creee = await repo.create(owner_id=autre.id, name="Privée", offer_filter=OfferFilter())

    assert await repo.list(owner_id=user_id) == ()
    with pytest.raises(SavedSearchNotFoundError):
        await repo.get(owner_id=user_id, search_id=creee.id)
    with pytest.raises(SavedSearchNotFoundError):
        await repo.delete(owner_id=user_id, search_id=creee.id)


async def test_relancer_reexecute_les_criteres_et_alimente_l_historique(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _offre(session, user_id, "Data Analyst")
    await _offre(session, user_id, "Comptable")
    saved = SqlSavedSearchRepository(session)
    service = SearchService(SqlOfferQueryRepository(session), saved)
    creee = await saved.create(
        owner_id=user_id, name="Data", offer_filter=OfferFilter(text="data", page=3)
    )

    page, execution = await service.rerun(owner_id=user_id, saved_search_id=creee.id)
    await _offre(session, user_id, "Data Engineer")
    page2, _ = await service.rerun(owner_id=user_id, saved_search_id=creee.id)

    assert (page.total, page.page) == (1, 1)  # repart de la première page
    assert execution.saved_search_id == creee.id
    assert page2.total == 2  # reproductible, et reflète les nouvelles offres
    historique = await saved.history(owner_id=user_id)
    assert [h.result_count for h in historique] == [2, 1]  # le plus récent d'abord


async def test_supprimer_une_recherche_conserve_son_historique(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    saved = SqlSavedSearchRepository(session)
    service = SearchService(SqlOfferQueryRepository(session), saved)
    creee = await saved.create(owner_id=user_id, name="Temp", offer_filter=OfferFilter())
    await service.rerun(owner_id=user_id, saved_search_id=creee.id)

    await saved.delete(owner_id=user_id, search_id=creee.id)

    historique = await saved.history(owner_id=user_id)
    assert len(historique) == 1
    assert historique[0].saved_search_id is None
