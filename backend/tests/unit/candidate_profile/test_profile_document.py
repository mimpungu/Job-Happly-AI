import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.candidate_profile.domain.enums import DataOrigin, LanguageProficiency
from app.modules.candidate_profile.domain.extraction.extractor import extract_profile
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
    diff_documents,
    item_issues,
    validation_issues,
)
from app.modules.candidate_profile.domain.proposal import proposal_to_document

from .extraction.cv_samples import CV_FR


class TestDocDate:
    def test_annee_seule_garde_sa_precision(self) -> None:
        d = DocDate(year=2020)

        assert (d.precision, d.label()) == ("year", "2020")
        assert (
            DocDate.from_storage(d.as_date(), d.precision) == d
        )  # aller-retour sans « janvier » inventé

    def test_mois_connu(self) -> None:
        d = DocDate(year=2020, month=3)

        assert (d.precision, d.label()) == ("month", "2020-03")
        assert DocDate.from_storage(d.as_date(), "month") == d

    @pytest.mark.parametrize("kwargs", [{"year": 1800}, {"year": 2020, "month": 13}])
    def test_dates_invalides(self, kwargs: dict[str, int]) -> None:
        with pytest.raises(ValidationError):
            DocDate(**kwargs)


class TestValidationDuBrouillon:
    def test_un_brouillon_peut_etre_tres_incomplet(self) -> None:
        ProfileDocument(experiences=(ExperienceDoc(),), educations=(EducationDoc(),))

    def test_periode_inversee_refusee(self) -> None:
        with pytest.raises(ValidationError, match="précède"):
            ExperienceDoc(start=DocDate(year=2022), end=DocDate(year=2020))

    def test_meme_annee_avec_mois_inverses_refusee_mais_annee_seule_acceptee(self) -> None:
        ExperienceDoc(start=DocDate(year=2020), end=DocDate(year=2020))
        with pytest.raises(ValidationError):
            ExperienceDoc(start=DocDate(year=2020, month=6), end=DocDate(year=2020, month=2))

    def test_une_experience_en_cours_n_a_pas_de_fin(self) -> None:
        with pytest.raises(ValidationError, match="en cours"):
            ExperienceDoc(is_current=True, end=DocDate(year=2022))

    @pytest.mark.parametrize("email", ["pas-un-email", "a@b", "a b@c.fr"])
    def test_email_invalide(self, email: str) -> None:
        with pytest.raises(ValidationError, match="e-mail"):
            Identity(email=email)

    def test_textes_nettoyes_et_vides_deviennent_absents(self) -> None:
        identite = Identity(first_name="  Marie   ", last_name="   ", city="")

        assert identite.first_name == "Marie"
        assert identite.last_name is None
        assert identite.city is None

    def test_doublons_de_competences_et_de_langues_refuses(self) -> None:
        with pytest.raises(ValidationError, match="compétences"):
            ProfileDocument(skills=(SkillDoc(name="Python"), SkillDoc(name="python")))
        with pytest.raises(ValidationError, match="langues"):
            ProfileDocument(
                languages=(LanguageDoc(language_code="fr"), LanguageDoc(language_code="fr"))
            )

    def test_champ_inconnu_refuse(self) -> None:
        with pytest.raises(ValidationError):
            ProfileDocument.model_validate({"identity": {}, "owner_id": "x"})

    def test_url_de_certification_http_seulement(self) -> None:
        with pytest.raises(ValidationError, match="http"):
            CertificationDoc(name="X", credential_url="javascript:alert(1)")


class TestPreferences:
    def test_salaire_exige_une_devise(self) -> None:
        with pytest.raises(ValidationError, match="devise"):
            Preferences(salary_min=Decimal(45000))
        assert (
            Preferences(salary_min=Decimal(45000), salary_currency="eur").salary_currency == "EUR"
        )

    def test_normalisation_et_dedoublonnage(self) -> None:
        p = Preferences(
            job_titles=("Data Analyst", " data analyst", "Data Analyst"),
            country_codes=("fr", "FR", "be"),
            application_languages=("fr", "en", "fr"),
        )

        assert p.job_titles == ("Data Analyst", "data analyst")  # la casse distingue deux saisies
        assert p.country_codes == ("FR", "BE")
        assert p.application_languages == ("fr", "en")

    def test_pays_et_langue_invalides(self) -> None:
        with pytest.raises(ValidationError):
            Preferences(country_codes=("France",))
        with pytest.raises(ValidationError):
            Preferences(application_languages=("fr-",))


class TestCompletude:
    def test_un_element_valide_doit_etre_complet(self) -> None:
        document = ProfileDocument(
            experiences=(ExperienceDoc(title="Dev", validated=True),),
            educations=(EducationDoc(degree="Master"),),  # incomplet mais non validé : toléré
            languages=(LanguageDoc(language_code="en", validated=True),),
        )

        chemins = {i.path for i in item_issues(document, only_validated=True)}

        assert chemins == {
            "experiences[0].company",
            "experiences[0].start",
            "languages[0].proficiency",
        }

    def test_valider_le_profil_exige_identite_et_confirmation_de_chaque_element(self) -> None:
        document = ProfileDocument(
            skills=(SkillDoc(name="Python"),),
            experiences=(
                ExperienceDoc(
                    title="Dev", company="Acme", start=DocDate(year=2020), validated=True
                ),
            ),
        )

        chemins = {i.path for i in validation_issues(document)}

        assert chemins == {"identity.first_name", "identity.last_name", "skills[0]"}

    def test_profil_complet_et_confirme(self) -> None:
        document = ProfileDocument(
            identity=Identity(first_name="Marie", last_name="Dupont"),
            skills=(SkillDoc(name="Python", validated=True),),
        )

        assert validation_issues(document) == []


class TestDiff:
    def test_creation_modification_suppression(self) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()
        avant = ProfileDocument(
            skills=(SkillDoc(id=a, name="Python"), SkillDoc(id=b, name="SQL")),
            summary="Ancien",
        )
        apres = ProfileDocument(
            skills=(SkillDoc(id=a, name="Python", level="expert"), SkillDoc(name="Docker")),
            summary="Nouveau",
        )

        changements = diff_documents(avant, apres)
        resume = {(c.entity_type, c.action, c.label) for c in changements}

        assert resume == {
            ("summary", "update", None),
            ("skill", "update", "Python"),
            ("skill", "create", "Docker"),
            ("skill", "delete", "SQL"),
        }
        maj = next(c for c in changements if c.action == "update" and c.entity_type == "skill")
        assert maj.changes == {"level": [None, "expert"]}
        assert maj.entity_id == a

    def test_aucun_changement_aucune_entree(self) -> None:
        document = ProfileDocument(skills=(SkillDoc(id=uuid.uuid4(), name="Python"),))

        assert diff_documents(document, document) == []

    def test_changement_d_identite_et_de_preferences(self) -> None:
        avant = ProfileDocument()
        apres = ProfileDocument(
            identity=Identity(first_name="Marie"),
            preferences=Preferences(job_titles=("Analyste",)),
        )

        types = {c.entity_type for c in diff_documents(avant, apres)}

        assert types == {"identity", "preferences"}

    def test_la_confirmation_d_un_element_est_journalisee(self) -> None:
        i = uuid.uuid4()
        avant = ProfileDocument(skills=(SkillDoc(id=i, name="Python"),))
        apres = ProfileDocument(skills=(SkillDoc(id=i, name="Python", validated=True),))

        (changement,) = diff_documents(avant, apres)

        assert changement.changes == {"validated": [False, True]}


class TestPropositionVersBrouillon:
    def test_tout_est_importe_et_non_valide(self) -> None:
        document = proposal_to_document(extract_profile(CV_FR))

        elements = (
            *document.experiences,
            *document.educations,
            *document.skills,
            *document.languages,
            *document.certifications,
        )
        assert elements
        assert all(e.origin is DataOrigin.IMPORTED and not e.validated for e in elements)
        assert all(e.source_text for e in elements)

    def test_identite_et_dates_partielles_reprises_sans_completion(self) -> None:
        document = proposal_to_document(extract_profile(CV_FR))

        assert document.identity.first_name == "Marie"
        assert document.identity.last_name == "Dupont"
        assert document.identity.email == "marie.dupont@exemple.test"
        master = document.educations[0]
        assert master.start == DocDate(year=2016)
        assert master.start is not None and master.start.month is None
        assert document.experiences[0].is_current is True
        assert document.experiences[0].end is None

    def test_niveau_de_langue_vague_reste_inconnu(self) -> None:
        document = proposal_to_document(extract_profile(CV_FR))

        niveaux = {lg.language_code: lg.proficiency for lg in document.languages}

        assert niveaux == {
            "fr": LanguageProficiency.NATIVE,
            "en": LanguageProficiency.B2,
            "es": None,
        }
        espagnol = next(lg for lg in document.languages if lg.language_code == "es")
        assert espagnol.level_text == "notions scolaires"

    def test_un_nom_ambigu_n_est_pas_decoupe(self) -> None:
        document = proposal_to_document(extract_profile("Jean Pierre Martin\njp@exemple.test\n"))

        assert (document.identity.first_name, document.identity.last_name) == (None, None)

    def test_une_certification_datee_garde_l_annee_seule(self) -> None:
        document = proposal_to_document(extract_profile(CV_FR))

        aws = next(c for c in document.certifications if c.name.startswith("AWS"))

        assert aws.issued_on == DocDate(year=2022)

    def test_le_brouillon_propose_ne_passe_pas_la_validation(self) -> None:
        document = proposal_to_document(extract_profile(CV_FR))

        assert validation_issues(document)
