"""Les contraintes SQL protègent l'intégrité même si le code applicatif se trompe."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.infrastructure.models import AIBudgetModel, AIUsageModel
from app.modules.application_management.infrastructure.models import ApplicationModel
from app.modules.candidate_profile.infrastructure.models import (
    CandidateModel,
    CandidateProfileModel,
    ExperienceModel,
    SkillModel,
)
from app.modules.document_generation.infrastructure.models import (
    DocumentVersionModel,
    GeneratedDocumentModel,
)
from app.modules.job_discovery.infrastructure.models import (
    JobOfferModel,
    JobOfferSourceModel,
    JobSourceModel,
)
from app.modules.platform.infrastructure.models import UserModel

HASH = "a" * 64


async def _doit_etre_refuse(session: AsyncSession, *objets: object) -> None:
    # La base refuse la donnée : contrainte (IntegrityError) ou type/longueur (DataError).
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            session.add_all(objets)
            await session.flush()


def _offre(user_id: uuid.UUID, **champs: object) -> JobOfferModel:
    valeurs: dict[str, object] = {
        "owner_id": user_id,
        "title": "Data Analyst",
        "description": "Description",
        "application_url": "https://exemple.test/offre/1",
        "content_hash": HASH,
    }
    valeurs.update(champs)
    return JobOfferModel(**valeurs)


async def _source(session: AsyncSession, user_id: uuid.UUID, key: str = "src") -> JobSourceModel:
    source = JobSourceModel(owner_id=user_id, key=key, name=key, kind="official_api")
    session.add(source)
    await session.flush()
    return source


class TestOffres:
    async def test_offre_valide_avec_valeurs_par_defaut(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        offre = _offre(user_id)
        session.add(offre)
        await session.flush()

        assert offre.status == "active"
        assert offre.salary_min is None  # absence d'information ≠ zéro

    @pytest.mark.parametrize(
        "champs",
        [
            {
                "salary_min": Decimal("50000"),
                "salary_max": Decimal("40000"),
                "salary_currency": "EUR",
            },
            {"salary_min": Decimal("40000")},  # salaire sans devise
            {"salary_min": Decimal("-1"), "salary_currency": "EUR"},
            {"salary_currency": "euro"},
            {"country_code": "fr"},
            {"employment_type": "inconnu"},
            {"remote_type": "partout"},
            {"status": "supprimee"},
            {"content_hash": "court"},
        ],
    )
    async def test_refuse_les_valeurs_incoherentes(
        self, session: AsyncSession, user_id: uuid.UUID, champs: dict[str, object]
    ) -> None:
        await _doit_etre_refuse(session, _offre(user_id, **champs))

    async def test_refuse_deux_offres_avec_la_meme_url_canonique(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        session.add(_offre(user_id, canonical_url="https://exemple.test/a"))
        await session.flush()

        await _doit_etre_refuse(session, _offre(user_id, canonical_url="https://exemple.test/a"))

    async def test_autorise_plusieurs_offres_sans_url_canonique(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        session.add_all([_offre(user_id), _offre(user_id)])
        await session.flush()

    async def test_la_meme_offre_externe_ne_peut_etre_enregistree_deux_fois(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        source = await _source(session, user_id)
        offre = _offre(user_id)
        session.add(offre)
        await session.flush()
        session.add(
            JobOfferSourceModel(
                owner_id=user_id,
                offer_id=offre.id,
                source_id=source.id,
                external_id="X1",
                raw_payload={"brut": True},
            )
        )
        await session.flush()

        await _doit_etre_refuse(
            session,
            JobOfferSourceModel(
                owner_id=user_id,
                offer_id=offre.id,
                source_id=source.id,
                external_id="X1",
                raw_payload={},
            ),
        )

    async def test_une_source_utilisee_ne_peut_pas_etre_supprimee(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        source = await _source(session, user_id)
        offre = _offre(user_id)
        session.add(offre)
        await session.flush()
        session.add(
            JobOfferSourceModel(
                owner_id=user_id,
                offer_id=offre.id,
                source_id=source.id,
                external_id="X1",
                raw_payload={},
            )
        )
        await session.flush()

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.delete(source)
                await session.flush()


class TestProprietaire:
    async def test_refuse_un_proprietaire_inexistant(self, session: AsyncSession) -> None:
        await _doit_etre_refuse(session, _offre(uuid.uuid4()))

    async def test_supprimer_l_utilisateur_supprime_ses_donnees(
        self, session: AsyncSession
    ) -> None:
        utilisateur = UserModel()
        session.add(utilisateur)
        await session.flush()
        session.add_all([_offre(utilisateur.id), _offre(utilisateur.id)])
        await session.flush()

        await session.delete(utilisateur)
        await session.flush()

        restantes = await session.scalar(
            select(func.count())
            .select_from(JobOfferModel)
            .where(JobOfferModel.owner_id == utilisateur.id)
        )
        assert restantes == 0


class TestProfil:
    async def _profil(self, session: AsyncSession, user_id: uuid.UUID) -> CandidateProfileModel:
        candidat = CandidateModel(owner_id=user_id, first_name="A", last_name="B")
        session.add(candidat)
        await session.flush()
        profil = CandidateProfileModel(owner_id=user_id, candidate_id=candidat.id, version=1)
        session.add(profil)
        await session.flush()
        return profil

    async def test_un_seul_candidat_par_proprietaire(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        session.add(CandidateModel(owner_id=user_id, first_name="A", last_name="B"))
        await session.flush()

        await _doit_etre_refuse(
            session, CandidateModel(owner_id=user_id, first_name="C", last_name="D")
        )

    async def test_version_de_profil_unique_et_positive(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        profil = await self._profil(session, user_id)

        await _doit_etre_refuse(
            session,
            CandidateProfileModel(owner_id=user_id, candidate_id=profil.candidate_id, version=1),
        )
        await _doit_etre_refuse(
            session,
            CandidateProfileModel(owner_id=user_id, candidate_id=profil.candidate_id, version=0),
        )

    async def test_experience_ne_peut_pas_finir_avant_de_commencer(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        profil = await self._profil(session, user_id)

        await _doit_etre_refuse(
            session,
            ExperienceModel(
                owner_id=user_id,
                profile_id=profil.id,
                company="X",
                title="Y",
                start_date=date(2024, 5, 1),
                end_date=date(2024, 4, 1),
            ),
        )

    async def test_competence_unique_sans_tenir_compte_de_la_casse(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        profil = await self._profil(session, user_id)
        session.add(SkillModel(owner_id=user_id, profile_id=profil.id, name="Python"))
        await session.flush()

        await _doit_etre_refuse(
            session, SkillModel(owner_id=user_id, profile_id=profil.id, name="python")
        )

    async def test_niveau_de_competence_non_renseigne_est_autorise(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        profil = await self._profil(session, user_id)
        competence = SkillModel(owner_id=user_id, profile_id=profil.id, name="SQL")
        session.add(competence)
        await session.flush()

        assert competence.level is None


class TestCandidatures:
    async def _offre_persistee(self, session: AsyncSession, user_id: uuid.UUID) -> JobOfferModel:
        offre = _offre(user_id)
        session.add(offre)
        await session.flush()
        return offre

    async def test_statut_par_defaut_et_valeurs_autorisees(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        offre = await self._offre_persistee(session, user_id)
        candidature = ApplicationModel(owner_id=user_id, offer_id=offre.id)
        session.add(candidature)
        await session.flush()

        assert candidature.status == "new_offer"

    async def test_refuse_un_statut_inconnu(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        offre = await self._offre_persistee(session, user_id)

        await _doit_etre_refuse(
            session, ApplicationModel(owner_id=user_id, offer_id=offre.id, status="gagnee")
        )

    async def test_une_seule_candidature_par_offre(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        offre = await self._offre_persistee(session, user_id)
        session.add(ApplicationModel(owner_id=user_id, offer_id=offre.id))
        await session.flush()

        await _doit_etre_refuse(session, ApplicationModel(owner_id=user_id, offer_id=offre.id))

    async def test_une_offre_avec_candidature_ne_peut_pas_etre_supprimee(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        offre = await self._offre_persistee(session, user_id)
        session.add(ApplicationModel(owner_id=user_id, offer_id=offre.id))
        await session.flush()

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.delete(offre)
                await session.flush()


class TestDocuments:
    async def test_numero_de_version_unique_par_document(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        document = GeneratedDocumentModel(
            owner_id=user_id, kind="cv", language="fr", title="CV Data Analyst"
        )
        session.add(document)
        await session.flush()

        def version(numero: int) -> DocumentVersionModel:
            return DocumentVersionModel(
                owner_id=user_id,
                document_id=document.id,
                version=numero,
                storage_key=f"cv/{numero}.pdf",
                sha256=HASH,
                size_bytes=10,
            )

        session.add(version(1))
        await session.flush()

        await _doit_etre_refuse(session, version(1))

    async def test_refuse_un_type_de_document_inconnu(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await _doit_etre_refuse(
            session,
            GeneratedDocumentModel(owner_id=user_id, kind="affiche", language="fr", title="x"),
        )


class TestBudgetIA:
    async def test_un_seul_plafond_global_par_periode(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        session.add(
            AIBudgetModel(owner_id=user_id, period="monthly", amount=Decimal("10"), currency="EUR")
        )
        await session.flush()

        await _doit_etre_refuse(
            session,
            AIBudgetModel(owner_id=user_id, period="monthly", amount=Decimal("20"), currency="EUR"),
        )

    async def test_plafonds_distincts_par_fournisseur_autorises(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        session.add_all(
            [
                AIBudgetModel(
                    owner_id=user_id, period="monthly", amount=Decimal("10"), currency="EUR"
                ),
                AIBudgetModel(
                    owner_id=user_id,
                    period="monthly",
                    provider="a",
                    amount=Decimal("5"),
                    currency="EUR",
                ),
            ]
        )
        await session.flush()

    @pytest.mark.parametrize("montant", [Decimal("0"), Decimal("-5")])
    async def test_refuse_un_plafond_nul_ou_negatif(
        self, session: AsyncSession, user_id: uuid.UUID, montant: Decimal
    ) -> None:
        await _doit_etre_refuse(
            session,
            AIBudgetModel(owner_id=user_id, period="daily", amount=montant, currency="EUR"),
        )

    async def test_refuse_un_usage_avec_des_valeurs_incoherentes(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        def usage(**champs: object) -> AIUsageModel:
            valeurs: dict[str, object] = {
                "owner_id": user_id,
                "provider": "p",
                "model": "m",
                "task_type": "t",
                "level": 1,
                "currency": "EUR",
                "operation_id": uuid.uuid4(),
                "outcome": "success",
            }
            valeurs.update(champs)
            return AIUsageModel(**valeurs)

        session.add(usage())
        await session.flush()

        await _doit_etre_refuse(session, usage(level=3))
        await _doit_etre_refuse(session, usage(input_tokens=-1))
        await _doit_etre_refuse(session, usage(estimated_cost=Decimal("-0.01")))
        await _doit_etre_refuse(session, usage(outcome="inconnu"))
