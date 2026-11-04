import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.value_objects import EmploymentType
from app.modules.candidate_profile.application.profile_service import ProfileService
from app.modules.candidate_profile.domain.profile import (
    DocDate,
    EducationDoc,
    ExperienceDoc,
    Identity,
    Preferences,
    ProfileDocument,
    SkillDoc,
)
from app.modules.candidate_profile.infrastructure.profile_repository import SqlProfileRepository
from app.modules.job_discovery.domain.search import (
    OfferFilter,
    OfferSort,
    ScoreContext,
    ScoringUnavailableError,
)
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.job_discovery.infrastructure.offer_queries import SqlOfferQueryRepository
from app.modules.job_intelligence.application.matching_service import MatchingService
from app.modules.job_intelligence.application.ports import NoValidatedProfileError
from app.modules.job_intelligence.domain.matching.models import Criterion
from app.modules.job_intelligence.domain.matching.weights import InvalidWeightsError
from app.modules.job_intelligence.infrastructure.composition import build_matching_service
from app.modules.job_intelligence.infrastructure.models import JobMatchScoreModel
from app.modules.platform.infrastructure.models import UserModel

from ..unit.job_intelligence.offers import OFFRE_FR

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _profil() -> ProfileDocument:
    return ProfileDocument(
        identity=Identity(first_name="Marie", last_name="Dupont"),
        experiences=(
            ExperienceDoc(
                title="Data Analyst",
                company="Acme",
                start=DocDate(year=2019, month=1),
                is_current=True,
                validated=True,
            ),
        ),
        educations=(EducationDoc(degree="Master Informatique", institution="UL", validated=True),),
        skills=(
            SkillDoc(name="SQL", validated=True),
            SkillDoc(name="Python", validated=True),
        ),
        preferences=Preferences(
            job_titles=("Data Analyst",),
            country_codes=("FR",),
            cities=("Lyon",),
            employment_types=(EmploymentType.PERMANENT,),
        ),
    )


async def _valider_profil(session: AsyncSession, owner_id: uuid.UUID) -> uuid.UUID:
    service = ProfileService(SqlProfileRepository(session))
    await service.save_draft(owner_id=owner_id, document=_profil())
    return (await service.validate(owner_id=owner_id)).meta.id


async def _offre(session: AsyncSession, owner_id: uuid.UUID, **champs: object) -> JobOfferModel:
    valeurs: dict[str, object] = {
        "owner_id": owner_id,
        "title": "Data Analyst",
        "description": OFFRE_FR,
        "application_url": "https://a.test/" + uuid.uuid4().hex,
        "content_hash": uuid.uuid4().hex * 2,
        "location": "Lyon, France",
        "country_code": "FR",
        "employment_type": "permanent",
        "published_at": T0 - timedelta(days=2),
    }
    valeurs.update(champs)
    offre = JobOfferModel(**valeurs)
    session.add(offre)
    await session.flush()
    return offre


def _service(session: AsyncSession) -> MatchingService:
    base = build_matching_service(session)
    return MatchingService(
        base._profiles,
        base._offers,
        base._store,
        clock=lambda: T0,
    )


class TestScoreSurProfilValide:
    async def test_sans_profil_valide_le_score_est_refuse_meme_avec_un_brouillon(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        offre = await _offre(session, user_id)
        await ProfileService(SqlProfileRepository(session)).save_draft(
            owner_id=user_id, document=_profil()
        )  # brouillon non validé

        with pytest.raises(NoValidatedProfileError, match="Validez votre profil"):
            await _service(session).match_offer(owner_id=user_id, offer_id=offre.id)

    async def test_score_detaille_et_memorise(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        profil_id = await _valider_profil(session, user_id)
        offre = await _offre(session, user_id)

        sortie = await _service(session).match_offer(owner_id=user_id, offer_id=offre.id)

        assert sortie.result.score is not None and sortie.result.score > Decimal(60)
        assert sortie.profile_version == 1
        stocke = await session.scalar(
            select(JobMatchScoreModel).where(JobMatchScoreModel.offer_id == offre.id)
        )
        assert stocke is not None
        assert stocke.profile_id == profil_id
        assert stocke.score == sortie.result.score
        assert stocke.breakdown["reliability"] in {"high", "medium", "low"}
        assert stocke.breakdown["profile_version"] == 1
        assert {c["criterion"] for c in stocke.breakdown["criteria"]} >= {"skills", "job_title"}

    async def test_recalculer_remplace_sans_doublon(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await _valider_profil(session, user_id)
        offre = await _offre(session, user_id)
        service = _service(session)

        await service.match_offer(owner_id=user_id, offer_id=offre.id)
        await service.match_offer(owner_id=user_id, offer_id=offre.id)

        assert await session.scalar(select(func.count()).select_from(JobMatchScoreModel)) == 1

    async def test_le_score_d_une_offre_d_un_autre_proprietaire_est_refuse(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        from app.modules.job_discovery.domain.search import OfferNotFoundError

        await _valider_profil(session, user_id)
        autre = UserModel(display_name="Autre")
        session.add(autre)
        await session.flush()
        offre = await _offre(session, autre.id)

        with pytest.raises(OfferNotFoundError):
            await _service(session).match_offer(owner_id=user_id, offer_id=offre.id)


class TestRecalcul:
    async def test_recalcule_toutes_les_offres_actives_par_lots(
        self, session: AsyncSession, user_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.modules.job_intelligence.application import matching_service

        monkeypatch.setattr(matching_service, "BATCH_SIZE", 3)  # force plusieurs lots
        await _valider_profil(session, user_id)
        for _ in range(7):
            await _offre(session, user_id)
        await _offre(session, user_id, status="expired")  # exclue

        rapport = await _service(session).recompute(owner_id=user_id)

        assert rapport.computed == 7
        assert rapport.not_computable == 0
        assert await session.scalar(select(func.count()).select_from(JobMatchScoreModel)) == 7

    async def test_changer_les_ponderations_remplace_les_anciens_scores(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await _valider_profil(session, user_id)
        await _offre(session, user_id)
        service = _service(session)
        premier = await service.recompute(owner_id=user_id)

        await service.set_weights(owner_id=user_id, brutes={"skills": 60})
        second = await service.recompute(owner_id=user_id)

        assert premier.weights_version != second.weights_version
        versions = set(await session.scalars(select(JobMatchScoreModel.weights_version)))
        assert versions == {second.weights_version}  # l'ancien jeu de scores est purgé

    async def test_sans_profil_valide_le_recalcul_est_refuse(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        with pytest.raises(NoValidatedProfileError):
            await _service(session).recompute(owner_id=user_id)


class TestPonderations:
    async def test_defaut_puis_personnalisation_puis_reinitialisation(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        service = _service(session)
        assert (await service.weights(owner_id=user_id)).is_default is True

        perso = await service.set_weights(owner_id=user_id, brutes={"salary": 0, "skills": 40})
        assert perso.is_default is False
        assert (
            perso.weights.values[next(c for c in perso.weights.values if c.value == "salary")] == 0
        )

        relu = await service.weights(owner_id=user_id)
        assert relu.version == perso.version
        reinit = await service.reset_weights(owner_id=user_id)
        assert reinit.is_default is True

    async def test_ponderations_invalides_refusees_sans_rien_enregistrer(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        service = _service(session)

        with pytest.raises(InvalidWeightsError):
            await service.set_weights(owner_id=user_id, brutes={"skills": -5})

        assert (await service.weights(owner_id=user_id)).is_default is True

    async def test_chaque_proprietaire_a_ses_ponderations(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        autre = UserModel(display_name="Autre")
        session.add(autre)
        await session.flush()
        service = _service(session)

        await service.set_weights(owner_id=user_id, brutes={"skills": 50})

        assert (await service.weights(owner_id=autre.id)).is_default is True

    async def test_ponderations_stockees_devenues_invalides_retombent_sur_le_defaut(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        from app.modules.job_intelligence.infrastructure.models import MatchingSettingsModel

        session.add(MatchingSettingsModel(owner_id=user_id, weights={"critere_disparu": 3}))
        await session.flush()

        assert (await _service(session).weights(owner_id=user_id)).is_default is True


class TestRechercheParScore:
    async def test_tri_et_filtre_par_score_dans_la_recherche(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await _valider_profil(session, user_id)
        bonne = await _offre(session, user_id, title="Data Analyst")
        mediocre = await _offre(
            session,
            user_id,
            title="Cuisinier",
            description="Cuisine",
            location="Brest",
            employment_type="fixed_term",
        )
        non_notee = await _offre(session, user_id, title="Data Analyst junior")
        service = _service(session)
        await service.match_offer(owner_id=user_id, offer_id=bonne.id)
        await service.match_offer(owner_id=user_id, offer_id=mediocre.id)
        contexte = await service.score_context(owner_id=user_id)
        depot = SqlOfferQueryRepository(session)

        tri = await depot.search(
            owner_id=user_id,
            offer_filter=OfferFilter(sort=OfferSort.SCORE_DESC),
            score_context=contexte,
        )
        filtre = await depot.search(
            owner_id=user_id,
            offer_filter=OfferFilter(min_score=Decimal(50)),
            score_context=contexte,
        )

        assert [o.id for o in tri.items] == [
            bonne.id,
            mediocre.id,
            non_notee.id,
        ]  # non notée en dernier
        assert tri.items[0].match_score is not None and tri.items[0].match_reliability is not None
        assert tri.items[2].match_score is None
        assert [o.id for o in filtre.items] == [
            bonne.id
        ]  # une offre non évaluée n'est pas « mauvaise » : exclue

    async def test_trier_par_score_sans_profil_valide_est_explicitement_refuse(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await _offre(session, user_id)

        with pytest.raises(ScoringUnavailableError):
            await SqlOfferQueryRepository(session).search(
                owner_id=user_id, offer_filter=OfferFilter(sort=OfferSort.SCORE_DESC)
            )
        with pytest.raises(ScoringUnavailableError):
            await SqlOfferQueryRepository(session).search(
                owner_id=user_id, offer_filter=OfferFilter(min_score=Decimal(10))
            )

    async def test_les_scores_d_un_autre_profil_ou_jeu_de_poids_ne_sont_pas_lus(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await _valider_profil(session, user_id)
        offre = await _offre(session, user_id)
        service = _service(session)
        await service.match_offer(owner_id=user_id, offer_id=offre.id)
        ancien = await service.score_context(owner_id=user_id)
        await service.set_weights(owner_id=user_id, brutes={"skills": 70})  # nouveau jeu de poids
        nouveau = await service.score_context(owner_id=user_id)
        assert (
            ancien is not None
            and nouveau is not None
            and ancien.weights_version != nouveau.weights_version
        )

        page = await SqlOfferQueryRepository(session).search(
            owner_id=user_id, offer_filter=OfferFilter(), score_context=nouveau
        )

        assert page.items[0].match_score is None  # le score calculé avec d'autres poids est ignoré

    async def test_une_recherche_sans_contexte_n_affiche_pas_de_score(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await _offre(session, user_id)

        page = await SqlOfferQueryRepository(session).search(
            owner_id=user_id, offer_filter=OfferFilter(), score_context=None
        )

        assert page.items[0].match_score is None
        assert isinstance(ScoreContext(uuid.uuid4(), "x"), ScoreContext)


async def _profil_valide_via_api(client: httpx.AsyncClient) -> None:
    doc = _profil().model_dump(mode="json")
    for cle in ("experiences", "educations", "skills", "languages", "certifications"):
        for element in doc[cle]:
            element["validated"] = True
    assert (await client.put("/api/v1/profile/draft", json=doc)).status_code == 200
    assert (await client.post("/api/v1/profile/validate")).status_code == 200


async def _offre_via_session(client: httpx.AsyncClient, session: AsyncSession) -> uuid.UUID:
    from app.modules.platform.infrastructure.models import UserModel as U

    owner = await session.scalar(select(U.id).order_by(U.created_at).limit(1))
    assert owner is not None
    return (await _offre(session, owner)).id


_TOUS_LES_CRITERES = tuple(c.value for c in Criterion)


class TestApi:
    async def test_score_d_offre_sans_profil_valide_donne_409_explicite(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        await client.get("/api/v1/offers")  # crée l'utilisateur local
        offre_id = await _offre_via_session(client, session)

        reponse = await client.get(f"/api/v1/offers/{offre_id}/match")

        assert (reponse.status_code, reponse.json()["error"]["code"]) == (
            409,
            "no_validated_profile",
        )
        assert "Validez votre profil" in reponse.json()["error"]["message"]

    async def test_parcours_complet(self, client: httpx.AsyncClient, session: AsyncSession) -> None:
        await client.get("/api/v1/offers")
        offre_id = await _offre_via_session(client, session)
        await _profil_valide_via_api(client)

        match = await client.get(f"/api/v1/offers/{offre_id}/match")
        assert match.status_code == 200
        corps = match.json()
        assert Decimal(corps["result"]["score"]) > 60
        assert corps["result"]["reliability"] in {"high", "medium"}
        assert corps["result"]["disclaimer"].startswith("Score indicatif")
        criteres = {c["criterion"]: c for c in corps["result"]["criteria"]}
        assert criteres["skills"]["status"] == "evaluated"
        assert {i["kind"] for i in criteres["skills"]["items"]} >= {
            "present",
            "absent",
            "unverifiable",
        }
        assert corps["profile_version"] == 1

        recalcul = await client.post("/api/v1/matching/recompute")
        assert recalcul.json()["computed"] == 1

        liste = await client.get("/api/v1/offers", params={"sort": "score_desc", "min_score": 50})
        assert [o["id"] for o in liste.json()["items"]] == [str(offre_id)]
        assert Decimal(liste.json()["items"][0]["match_score"]) > 60

    async def test_trier_par_score_sans_profil_valide_409(self, client: httpx.AsyncClient) -> None:
        reponse = await client.get("/api/v1/offers", params={"sort": "score_desc"})

        assert (reponse.status_code, reponse.json()["error"]["code"]) == (
            409,
            "scoring_unavailable",
        )

    async def test_ponderations_lecture_modification_reinitialisation(
        self, client: httpx.AsyncClient
    ) -> None:
        defaut = (await client.get("/api/v1/matching/weights")).json()
        assert defaut["is_default"] is True
        assert [c["key"] for c in defaut["criteria"]][:3] == ["job_title", "skills", "experience"]
        assert defaut["criteria"][0]["label"] == "Métier"

        perso = await client.put(
            "/api/v1/matching/weights", json={"weights": {"skills": 40, "salary": 0}}
        )
        assert perso.status_code == 200
        assert perso.json()["is_default"] is False
        poids = {c["key"]: Decimal(c["weight"]) for c in perso.json()["criteria"]}
        assert poids["skills"] == 40 and poids["salary"] == 0
        assert (
            Decimal(
                next(c for c in perso.json()["criteria"] if c["key"] == "skills")["default_weight"]
            )
            == 25
        )

        reinit = await client.delete("/api/v1/matching/weights")
        assert reinit.json()["is_default"] is True

    @pytest.mark.parametrize(
        "corps",
        [
            {"weights": {"inconnu": 5}},
            {"weights": {"skills": -1}},
            {"weights": {"skills": 1000}},
            {"weights": {"skills": "beaucoup"}},
            {"weights": {"skills": True}},
            {"weights": dict.fromkeys(_TOUS_LES_CRITERES, 0)},  # plus aucun critère actif
            {"poids": {}},
        ],
    )
    async def test_ponderations_invalides_422(self, client: httpx.AsyncClient, corps: dict) -> None:  # type: ignore[type-arg]
        reponse = await client.put("/api/v1/matching/weights", json=corps)

        assert reponse.status_code == 422
        assert (await client.get("/api/v1/matching/weights")).json()["is_default"] is True

    async def test_offre_inconnue_404(self, client: httpx.AsyncClient) -> None:
        await client.get("/api/v1/offers")
        await _profil_valide_via_api(client)

        reponse = await client.get(f"/api/v1/offers/{uuid.uuid4()}/match")

        assert (reponse.status_code, reponse.json()["error"]["code"]) == (404, "offer_not_found")
