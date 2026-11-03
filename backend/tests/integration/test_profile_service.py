import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.value_objects import SkillLevel
from app.modules.candidate_profile.application.profile_service import ProfileService
from app.modules.candidate_profile.domain.enums import (
    DataOrigin,
    ProfileStatus,
)
from app.modules.candidate_profile.domain.profile import (
    CertificationDoc,
    DocDate,
    EducationDoc,
    ExperienceDoc,
    Identity,
    LanguageDoc,
    Preferences,
    ProfileDocument,
    SkillDoc,
)
from app.modules.candidate_profile.domain.repository import (
    DraftExistsError,
    NoDraftError,
    ProfileIncompleteError,
    ProfileNotFoundError,
    UnknownItemError,
)
from app.modules.candidate_profile.infrastructure.models import (
    CandidateModel,
    ExperienceModel,
)
from app.modules.candidate_profile.infrastructure.profile_repository import SqlProfileRepository
from app.modules.platform.infrastructure.models import UserModel

T0 = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)


class Horloge:
    """Horloge contrôlée : chaque appel avance d'une minute (journal déterministe)."""

    def __init__(self) -> None:
        self.courant = T0

    def __call__(self) -> datetime:
        self.courant += timedelta(minutes=1)
        return self.courant


@pytest.fixture
def service(session: AsyncSession) -> ProfileService:
    return ProfileService(SqlProfileRepository(session), clock=Horloge())


def _complet(**surcharge: object) -> ProfileDocument:
    valeurs: dict[str, object] = {
        "identity": Identity(first_name="Marie", last_name="Dupont", email="m@exemple.test"),
        "experiences": (
            ExperienceDoc(
                title="Dev", company="Acme", start=DocDate(year=2020, month=3), validated=True
            ),
        ),
        "skills": (SkillDoc(name="Python", validated=True),),
    }
    valeurs.update(surcharge)
    return ProfileDocument(**valeurs)


class TestBrouillon:
    async def test_premiere_sauvegarde_cree_la_version_1_en_brouillon(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        assert await service.current(owner_id=user_id) is None

        stocke = await service.save_draft(owner_id=user_id, document=_complet())

        assert (stocke.meta.version, stocke.meta.status) == (1, ProfileStatus.DRAFT)
        assert stocke.document.identity.first_name == "Marie"
        assert stocke.document.experiences[0].id is not None
        assert (await service.current(owner_id=user_id)) == stocke

    async def test_les_dates_partielles_survivent_a_l_enregistrement(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        document = ProfileDocument(
            experiences=(ExperienceDoc(start=DocDate(year=2020), end=DocDate(year=2022)),),
            educations=(EducationDoc(start=None, end=DocDate(year=2019)),),
            certifications=(CertificationDoc(name="AWS", issued_on=DocDate(year=2022)),),
        )

        relu = (await service.save_draft(owner_id=user_id, document=document)).document

        assert relu.experiences[0].start == DocDate(year=2020)  # pas « 2020-01 »
        assert relu.experiences[0].start is not None and relu.experiences[0].start.month is None
        assert relu.educations[0].start is None
        assert relu.educations[0].end == DocDate(year=2019)
        assert relu.certifications[0].issued_on == DocDate(year=2022)

    async def test_un_brouillon_incomplet_est_accepte_avec_champs_inconnus_a_none(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        document = ProfileDocument(
            experiences=(ExperienceDoc(title="Consultant"),),
            languages=(LanguageDoc(language_code="en", level_text="courant"),),
        )

        relu = (await service.save_draft(owner_id=user_id, document=document)).document

        assert relu.experiences[0].company is None
        assert relu.experiences[0].start is None
        assert relu.languages[0].proficiency is None
        assert relu.languages[0].level_text == "courant"

    async def test_confirmer_un_element_incomplet_est_refuse(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        document = ProfileDocument(experiences=(ExperienceDoc(title="Dev", validated=True),))

        with pytest.raises(ProfileIncompleteError) as erreur:
            await service.save_draft(owner_id=user_id, document=document)

        assert {i.path for i in erreur.value.issues} == {
            "experiences[0].company",
            "experiences[0].start",
        }
        assert await service.current(owner_id=user_id) is None  # rien n'a été écrit

    async def test_la_base_refuse_aussi_un_element_valide_incomplet(
        self, session: AsyncSession, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        await service.save_draft(
            owner_id=user_id, document=ProfileDocument(experiences=(ExperienceDoc(title="Dev"),))
        )

        with pytest.raises(IntegrityError, match="validated_is_complete"):
            async with session.begin_nested():
                await session.execute(
                    update(ExperienceModel).values(validated_at=T0)  # company/start manquants
                )

    async def test_mise_a_jour_ajout_suppression_et_ordre(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        v1 = await service.save_draft(
            owner_id=user_id,
            document=ProfileDocument(
                experiences=(ExperienceDoc(title="A"), ExperienceDoc(title="B")),
                skills=(SkillDoc(name="Python"), SkillDoc(name="SQL")),
            ),
        )
        a, b = v1.document.experiences
        python, _sql = v1.document.skills

        v2 = await service.save_draft(
            owner_id=user_id,
            document=ProfileDocument(
                experiences=(
                    ExperienceDoc(title="C"),  # nouvelle, placée en tête
                    b.model_copy(update={"title": "B modifiée"}),
                ),
                skills=(python,),  # SQL supprimée
            ),
        )

        assert [e.title for e in v2.document.experiences] == ["C", "B modifiée"]
        assert v2.document.experiences[1].id == b.id  # même ligne mise à jour
        assert a.id not in {e.id for e in v2.document.experiences}  # A supprimée
        assert [s.name for s in v2.document.skills] == ["Python"]

    async def test_l_ordre_saisi_est_conserve_pour_tous_les_types_d_elements(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        # Insérés dans la même transaction, ces éléments partagent le même `created_at` : seul
        # l'ordre explicite (position) garantit qu'on les relit comme saisis.
        noms = ["Zèbre", "Alpha", "Mike", "Bravo", "Yankee", "Charlie", "X-ray", "Delta"]
        langues = ["fr", "en", "es", "de", "it", "pt", "nl", "ar"]
        document = ProfileDocument(
            skills=tuple(SkillDoc(name=n) for n in noms),
            languages=tuple(LanguageDoc(language_code=c) for c in langues),
            educations=tuple(EducationDoc(degree=n) for n in noms),
            certifications=tuple(CertificationDoc(name=n) for n in noms),
        )

        relu = (await service.save_draft(owner_id=user_id, document=document)).document

        assert [s.name for s in relu.skills] == noms
        assert [lg.language_code for lg in relu.languages] == langues
        assert [e.degree for e in relu.educations] == noms
        assert [c.name for c in relu.certifications] == noms

        # Réordonner puis réenregistrer doit être pris en compte.
        inverse = relu.model_copy(update={"skills": tuple(reversed(relu.skills))})
        apres = (await service.save_draft(owner_id=user_id, document=inverse)).document
        assert [s.name for s in apres.skills] == list(reversed(noms))

    async def test_identifiant_inconnu_refuse_et_rien_n_est_modifie(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        v1 = await service.save_draft(
            owner_id=user_id, document=ProfileDocument(skills=(SkillDoc(name="Python"),))
        )

        with pytest.raises(UnknownItemError):
            await service.save_draft(
                owner_id=user_id,
                document=ProfileDocument(skills=(SkillDoc(id=uuid.uuid4(), name="Autre"),)),
            )

        assert (await service.current(owner_id=user_id)) == v1

    async def test_la_date_de_confirmation_est_conservee_au_resauvegarde(
        self, session: AsyncSession, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        v1 = await service.save_draft(owner_id=user_id, document=_complet())
        premiere = await session.scalar(select(ExperienceModel.validated_at))

        await service.save_draft(owner_id=user_id, document=v1.document)

        assert await session.scalar(select(ExperienceModel.validated_at)) == premiere

    async def test_deconfirmer_un_element_efface_sa_validation(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        v1 = await service.save_draft(owner_id=user_id, document=_complet())
        competence = v1.document.skills[0].model_copy(update={"validated": False})

        v2 = await service.save_draft(
            owner_id=user_id, document=v1.document.model_copy(update={"skills": (competence,)})
        )

        assert v2.document.skills[0].validated is False


class TestValidationEtVersions:
    async def test_valider_un_profil_incomplet_liste_les_problemes(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        await service.save_draft(
            owner_id=user_id, document=ProfileDocument(skills=(SkillDoc(name="Python"),))
        )

        with pytest.raises(ProfileIncompleteError) as erreur:
            await service.validate(owner_id=user_id)

        assert {i.path for i in erreur.value.issues} == {
            "identity.first_name",
            "identity.last_name",
            "skills[0]",
        }

    async def test_valider_sans_profil(self, service: ProfileService, user_id: uuid.UUID) -> None:
        with pytest.raises(ProfileNotFoundError):
            await service.validate(owner_id=user_id)

    async def test_validation_fige_la_version_et_met_a_jour_le_candidat(
        self, session: AsyncSession, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        await service.save_draft(owner_id=user_id, document=_complet())

        valide = await service.validate(owner_id=user_id)

        assert valide.meta.status is ProfileStatus.VALIDATED
        assert valide.meta.validated_at is not None
        candidat = await session.scalar(select(CandidateModel))
        assert candidat is not None
        assert (candidat.first_name, candidat.last_name) == ("Marie", "Dupont")
        with pytest.raises(NoDraftError):
            await service.save_draft(owner_id=user_id, document=_complet())
        with pytest.raises(NoDraftError):
            await service.validate(owner_id=user_id)

    async def test_nouvelle_version_copie_sans_toucher_a_la_precedente(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        await service.save_draft(owner_id=user_id, document=_complet())
        v1 = await service.validate(owner_id=user_id)

        v2 = await service.start_new_version(owner_id=user_id)
        modifie = v2.document.model_copy(
            update={
                "summary": "Nouveau résumé",
                "identity": Identity(first_name="Marie", last_name="Martin"),
            }
        )
        await service.save_draft(owner_id=user_id, document=modifie)

        assert v2.meta.version == 2
        assert v2.meta.status is ProfileStatus.DRAFT
        # Les éléments sont recopiés avec de nouveaux identifiants.
        assert v2.document.skills[0].id != v1.document.skills[0].id
        relue_v1 = await service.version(owner_id=user_id, version=1)
        assert relue_v1.document == v1.document  # v1 inchangée, identité comprise
        assert relue_v1.document.identity.last_name == "Dupont"
        assert (await service.current(owner_id=user_id)).document.identity.last_name == "Martin"  # type: ignore[union-attr]

    async def test_pas_de_seconde_version_tant_qu_un_brouillon_existe(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        with pytest.raises(ProfileNotFoundError):
            await service.start_new_version(owner_id=user_id)
        await service.save_draft(owner_id=user_id, document=_complet())

        with pytest.raises(DraftExistsError):
            await service.start_new_version(owner_id=user_id)

    async def test_liste_des_versions_et_version_inconnue(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        await service.save_draft(owner_id=user_id, document=_complet())
        await service.validate(owner_id=user_id)
        await service.start_new_version(owner_id=user_id)

        versions = await service.versions(owner_id=user_id)

        assert [(v.version, v.status) for v in versions] == [
            (2, ProfileStatus.DRAFT),
            (1, ProfileStatus.VALIDATED),
        ]
        with pytest.raises(ProfileNotFoundError):
            await service.version(owner_id=user_id, version=9)

    async def test_les_preferences_sont_versionnees(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        prefs = Preferences(
            job_titles=("Analyste",), country_codes=("FR",), application_languages=("fr", "en")
        )
        await service.save_draft(owner_id=user_id, document=_complet(preferences=prefs))
        await service.validate(owner_id=user_id)

        v2 = await service.start_new_version(owner_id=user_id)

        assert v2.document.preferences == prefs


class TestJournal:
    async def test_import_validation_et_modifications_sont_tracees(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        importe = ProfileDocument(
            identity=Identity(first_name="Marie", last_name="Dupont"),
            skills=(SkillDoc(name="Python", origin=DataOrigin.IMPORTED, source_text="Python"),),
        )
        v1 = await service.save_draft(owner_id=user_id, document=importe)
        competence = v1.document.skills[0].model_copy(
            update={"validated": True, "level": SkillLevel.EXPERT}
        )
        await service.save_draft(
            owner_id=user_id, document=v1.document.model_copy(update={"skills": (competence,)})
        )
        await service.validate(owner_id=user_id)

        historique = await service.history(owner_id=user_id)

        assert [(h.entity_type, h.action) for h in historique] == [
            ("profile", "validate"),
            ("skill", "update"),
            ("profile", "import"),
        ]
        maj = historique[1]
        assert maj.label == "Python"
        assert maj.changes == {"validated": [False, True], "level": [None, "expert"]}
        assert historique[2].label == "Brouillon créé à partir d'un CV importé"

    async def test_un_enregistrement_sans_changement_n_ajoute_rien(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        v1 = await service.save_draft(owner_id=user_id, document=_complet())
        avant = len(await service.history(owner_id=user_id))

        await service.save_draft(owner_id=user_id, document=v1.document)

        assert len(await service.history(owner_id=user_id)) == avant

    async def test_la_suppression_d_un_element_garde_ce_qui_a_ete_supprime(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        v1 = await service.save_draft(
            owner_id=user_id, document=ProfileDocument(skills=(SkillDoc(name="COBOL"),))
        )
        await service.save_draft(owner_id=user_id, document=ProfileDocument())

        suppression = (await service.history(owner_id=user_id))[0]

        assert (suppression.action, suppression.label) == ("delete", "COBOL")
        assert suppression.changes["name"] == ["COBOL", None]
        assert suppression.entity_id == v1.document.skills[0].id

    async def test_la_nouvelle_version_est_tracee(
        self, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        await service.save_draft(owner_id=user_id, document=_complet())
        await service.validate(owner_id=user_id)
        await service.start_new_version(owner_id=user_id)

        derniere = (await service.history(owner_id=user_id))[0]

        assert derniere.label == "Version 2 créée à partir de la version 1"
        assert derniere.profile_version == 2


class TestIsolation:
    async def test_un_autre_proprietaire_ne_voit_rien(
        self, session: AsyncSession, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        autre = UserModel(display_name="Autre")
        session.add(autre)
        await session.flush()
        await service.save_draft(owner_id=user_id, document=_complet())

        assert await service.current(owner_id=autre.id) is None
        assert await service.versions(owner_id=autre.id) == ()
        assert await service.history(owner_id=autre.id) == ()
        with pytest.raises(ProfileNotFoundError):
            await service.version(owner_id=autre.id, version=1)

    async def test_deux_proprietaires_ont_chacun_leur_version_1(
        self, session: AsyncSession, service: ProfileService, user_id: uuid.UUID
    ) -> None:
        autre = UserModel(display_name="Autre")
        session.add(autre)
        await session.flush()

        a = await service.save_draft(owner_id=user_id, document=_complet())
        b = await service.save_draft(owner_id=autre.id, document=_complet())

        assert a.meta.version == b.meta.version == 1
        assert a.meta.id != b.meta.id
