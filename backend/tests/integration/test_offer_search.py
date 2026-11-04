import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.value_objects import EmploymentType, RemoteType
from app.modules.job_discovery.domain.enums import OfferState, OfferStatus
from app.modules.job_discovery.domain.search import (
    OfferFilter,
    OfferNotFoundError,
    OfferSort,
    StateFilter,
)
from app.modules.job_discovery.infrastructure.models import (
    JobOfferModel,
    JobOfferSourceModel,
    JobSourceModel,
)
from app.modules.job_discovery.infrastructure.offer_queries import SqlOfferQueryRepository
from app.modules.platform.infrastructure.models import UserModel

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


async def _offre(session: AsyncSession, owner_id: uuid.UUID, **champs: object) -> JobOfferModel:
    valeurs: dict[str, object] = {
        "owner_id": owner_id,
        "title": "Data Analyst",
        "description": "Analyse de données avec SQL.",
        "application_url": "https://a.test/" + uuid.uuid4().hex,
        "content_hash": uuid.uuid4().hex * 2,
        "company_name": "Exemple SA",
        "location": "Paris, France",
        "country_code": "FR",
        "published_at": T0,
    }
    valeurs.update(champs)
    offre = JobOfferModel(**valeurs)
    session.add(offre)
    await session.flush()
    return offre


async def _ids(
    repo: SqlOfferQueryRepository, owner_id: uuid.UUID, **filtres: object
) -> list[uuid.UUID]:
    page = await repo.search(owner_id=owner_id, offer_filter=OfferFilter(**filtres))
    return [item.id for item in page.items]


@pytest.fixture
def repo(session: AsyncSession) -> SqlOfferQueryRepository:
    return SqlOfferQueryRepository(session)


class TestFiltres:
    async def test_sans_filtre_retourne_les_offres_actives_du_proprietaire(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        active = await _offre(session, user_id)
        await _offre(session, user_id, status=OfferStatus.EXPIRED.value)
        autre = UserModel(display_name="Autre")
        session.add(autre)
        await session.flush()
        await _offre(session, autre.id)

        assert await _ids(repo, user_id) == [active.id]

    async def test_recherche_par_intitule_insensible_a_la_casse(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        voulue = await _offre(session, user_id, title="Ingénieur Python")
        await _offre(session, user_id, title="Comptable")

        assert await _ids(repo, user_id, text="python") == [voulue.id]

    async def test_les_caracteres_joker_saisis_sont_litteraux(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        await _offre(session, user_id, title="Data Analyst")
        voulue = await _offre(session, user_id, title="Remise à 100% garantie")

        assert await _ids(repo, user_id, text="100%") == [voulue.id]
        assert await _ids(repo, user_id, text="%") == [voulue.id]
        assert await _ids(repo, user_id, text="_") == []

    async def test_les_mots_cles_se_cumulent(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        voulue = await _offre(session, user_id, description="SQL et Python")
        await _offre(session, user_id, description="SQL seulement")

        assert await _ids(repo, user_id, keywords=("sql", "python")) == [voulue.id]

    async def test_une_tentative_d_injection_sql_est_traitee_comme_du_texte(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        await _offre(session, user_id)

        assert await _ids(repo, user_id, text="'; DROP TABLE job_offers; --") == []
        assert len(await _ids(repo, user_id)) == 1

    async def test_filtre_ville_pays_contrat_teletravail(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        voulue = await _offre(
            session,
            user_id,
            location="Lyon, France",
            employment_type=EmploymentType.PERMANENT.value,
            remote_type=RemoteType.HYBRID.value,
        )
        await _offre(session, user_id, location="Paris, France", country_code="FR")
        await _offre(session, user_id, location="Lyon", country_code="BE")

        assert await _ids(repo, user_id, city="lyon", country_codes=("FR",)) == [voulue.id]
        assert await _ids(repo, user_id, employment_types=(EmploymentType.PERMANENT,)) == [
            voulue.id
        ]
        assert await _ids(repo, user_id, remote_types=(RemoteType.HYBRID,)) == [voulue.id]

    async def test_filtre_salaire_exige_la_devise_et_exclut_les_salaires_inconnus(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        voulue = await _offre(
            session,
            user_id,
            salary_min=Decimal(40000),
            salary_max=Decimal(55000),
            salary_currency="EUR",
        )
        await _offre(session, user_id, salary_min=Decimal(30000), salary_currency="EUR")
        await _offre(session, user_id, salary_min=Decimal(90000), salary_currency="USD")
        await _offre(session, user_id)  # salaire inconnu : jamais deviné

        assert await _ids(repo, user_id, salary_min=Decimal(50000), salary_currency="EUR") == [
            voulue.id
        ]
        with pytest.raises(ValueError, match="devise"):
            OfferFilter(salary_min=Decimal(50000))

    async def test_filtre_date_de_publication(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        recente = await _offre(session, user_id, published_at=T0)
        await _offre(session, user_id, published_at=T0 - timedelta(days=30))
        await _offre(session, user_id, published_at=None)

        assert await _ids(repo, user_id, published_since=T0 - timedelta(days=7)) == [recente.id]

    async def test_filtre_langue_accepte_les_variantes_regionales(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        voulue = await _offre(session, user_id, language="fr-FR")
        await _offre(session, user_id, language="en")

        assert await _ids(repo, user_id, language="fr") == [voulue.id]


class TestTriEtPagination:
    async def test_pagination_cote_base_sans_doublon_ni_oubli(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        # Même date pour toutes : seul le départage par identifiant garantit des pages stables.
        creees = {(await _offre(session, user_id)).id for _ in range(7)}

        vues: list[uuid.UUID] = []
        for numero in (1, 2, 3):
            page = await repo.search(
                owner_id=user_id, offer_filter=OfferFilter(page=numero, page_size=3)
            )
            assert page.total == 7
            assert page.page_count == 3
            vues.extend(item.id for item in page.items)

        assert len(vues) == 7
        assert set(vues) == creees

    async def test_page_hors_limites_est_vide_sans_erreur(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        await _offre(session, user_id)

        page = await repo.search(owner_id=user_id, offer_filter=OfferFilter(page=5))

        assert page.items == ()
        assert page.total == 1

    async def test_tris(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        a = await _offre(
            session,
            user_id,
            title="b",
            published_at=T0,
            salary_min=Decimal(10),
            salary_currency="EUR",
        )
        b = await _offre(
            session,
            user_id,
            title="A",
            published_at=T0 - timedelta(days=1),
            salary_min=Decimal(99),
            salary_currency="EUR",
        )
        c = await _offre(session, user_id, title="c", published_at=None)

        assert await _ids(repo, user_id, sort=OfferSort.PUBLISHED_DESC) == [a.id, b.id, c.id]
        assert await _ids(repo, user_id, sort=OfferSort.PUBLISHED_ASC) == [b.id, a.id, c.id]
        assert await _ids(repo, user_id, sort=OfferSort.TITLE_ASC) == [b.id, a.id, c.id]
        assert await _ids(repo, user_id, sort=OfferSort.SALARY_DESC) == [b.id, a.id, c.id]


class TestEtatsEtDetail:
    async def test_une_offre_ignoree_est_masquee_par_defaut_mais_retrouvable(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        gardee = await _offre(session, user_id)
        ignoree = await _offre(session, user_id)
        await repo.set_state(owner_id=user_id, offer_id=ignoree.id, state=OfferState.IGNORED)

        assert await _ids(repo, user_id) == [gardee.id]
        assert await _ids(repo, user_id, state=StateFilter.IGNORED) == [ignoree.id]
        assert set(await _ids(repo, user_id, state=StateFilter.ALL)) == {gardee.id, ignoree.id}

    async def test_sauvegarder_est_idempotent_et_reversible(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        offre = await _offre(session, user_id)

        await repo.set_state(owner_id=user_id, offer_id=offre.id, state=OfferState.SAVED)
        await repo.set_state(owner_id=user_id, offer_id=offre.id, state=OfferState.SAVED)
        assert await _ids(repo, user_id, state=StateFilter.SAVED) == [offre.id]

        await repo.set_state(owner_id=user_id, offer_id=offre.id, state=OfferState.IGNORED)
        assert await _ids(repo, user_id, state=StateFilter.SAVED) == []

        await repo.set_state(owner_id=user_id, offer_id=offre.id, state=None)
        assert await _ids(repo, user_id, state=StateFilter.VISIBLE) == [offre.id]

    async def test_poser_un_etat_sur_l_offre_d_un_autre_proprietaire_est_refuse(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        autre = UserModel(display_name="Autre")
        session.add(autre)
        await session.flush()
        offre = await _offre(session, autre.id)

        with pytest.raises(OfferNotFoundError):
            await repo.set_state(owner_id=user_id, offer_id=offre.id, state=OfferState.SAVED)
        with pytest.raises(OfferNotFoundError):
            await repo.get(owner_id=user_id, offer_id=offre.id)

    async def test_le_detail_expose_les_sources_et_le_resume_les_cles(
        self, session: AsyncSession, user_id: uuid.UUID, repo: SqlOfferQueryRepository
    ) -> None:
        offre = await _offre(session, user_id)
        for cle in ("zeta", "alpha"):
            source = JobSourceModel(
                owner_id=user_id, key=cle, name=cle.title(), kind="official_api"
            )
            session.add(source)
            await session.flush()
            session.add(
                JobOfferSourceModel(
                    owner_id=user_id,
                    offer_id=offre.id,
                    source_id=source.id,
                    external_id=cle,
                    source_url=f"https://{cle}.test/1",
                    raw_payload={},
                    gone_at=T0 if cle == "zeta" else None,
                )
            )
        await session.flush()

        detail = await repo.get(owner_id=user_id, offer_id=offre.id)
        page = await repo.search(owner_id=user_id, offer_filter=OfferFilter())

        assert [s.source_key for s in detail.sources] == ["alpha", "zeta"]
        assert [s.still_listed for s in detail.sources] == [True, False]
        assert page.items[0].source_keys == ("alpha", "zeta")
        assert detail.description == offre.description
