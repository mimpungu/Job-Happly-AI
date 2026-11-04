"""Tests unitaires du contrôleur strict des faits (TASK-012-10)."""

import pytest

from app.modules.candidate_profile.domain.profile import (
    CertificationDoc,
    DocDate,
    EducationDoc,
    ExperienceDoc,
    Identity,
    LanguageDoc,
    ProfileDocument,
    SkillDoc,
)
from app.modules.document_generation.domain.fact_checker import (
    UnverifiedFactError,
    assert_facts_verified,
    verify_facts,
)


def _profil_maitre() -> ProfileDocument:
    return ProfileDocument(
        identity=Identity(first_name="Bob", last_name="Dupont"),
        experiences=(
            ExperienceDoc(
                title="Développeur Python",
                company="Real Company SAS",
                description="Développement backend.",
            ),
        ),
        skills=(
            SkillDoc(name="Python"),
            SkillDoc(name="Docker"),
        ),
        educations=(
            EducationDoc(
                degree="Licence Informatique",
                institution="Université de Lyon",
            ),
        ),
    )


def test_profil_conforme_passe_sans_erreur() -> None:
    maitre = _profil_maitre()
    # Le profil généré reprend les mêmes faits
    genere = maitre.model_copy()

    rapport = verify_facts(maitre, genere)
    assert rapport.is_valid is True
    assert len(rapport.issues) == 0
    assert_facts_verified(maitre, genere)


def test_entreprise_inventee_est_rejetee() -> None:
    maitre = _profil_maitre()
    # Tentative d'ajouter une fausse expérience chez Google
    fausse_exp = ExperienceDoc(
        title="Senior Architect",
        company="Fake Google Corp",
    )
    genere = maitre.model_copy(update={"experiences": (fausse_exp,)})

    rapport = verify_facts(maitre, genere)
    assert rapport.is_valid is False
    assert "Fake Google Corp" in rapport.unverified_companies
    with pytest.raises(UnverifiedFactError, match="Fake Google Corp"):
        assert_facts_verified(maitre, genere)


def test_diplome_ou_etablissement_invente_est_rejete() -> None:
    maitre = _profil_maitre()
    faux_diplome = EducationDoc(
        degree="Doctorat en IA",
        institution="MIT",
    )
    genere = maitre.model_copy(update={"educations": (faux_diplome,)})

    rapport = verify_facts(maitre, genere)
    assert rapport.is_valid is False
    assert "MIT" in rapport.unverified_institutions
    with pytest.raises(UnverifiedFactError, match="MIT"):
        assert_facts_verified(maitre, genere)


def test_competence_inventee_est_rejetee() -> None:
    maitre = _profil_maitre()
    fausses_skills = (SkillDoc(name="Python"), SkillDoc(name="C++ (Inventé)"))
    genere = maitre.model_copy(update={"skills": fausses_skills})

    rapport = verify_facts(maitre, genere)
    assert rapport.is_valid is False
    assert "C++ (Inventé)" in rapport.unverified_skills
    with pytest.raises(UnverifiedFactError, match="C\\+\\+ \\(Inventé\\)"):
        assert_facts_verified(maitre, genere)


def _profil_detaille() -> ProfileDocument:
    return ProfileDocument(
        identity=Identity(first_name="Bob", last_name="Dupont"),
        experiences=(
            ExperienceDoc(
                title="Développeur",
                company="Acme",
                start=DocDate(year=2019),
                end=DocDate(year=2022),
                description="Services web.",
                achievements=("Latence réduite de 30 %", "Migration vers PostgreSQL"),
            ),
        ),
        certifications=(CertificationDoc(name="AWS SAA", issuer="Amazon"),),
        languages=(LanguageDoc(language_code="fr", level_text="natif"),),
    )


def test_selection_de_realisations_existantes_reste_valide() -> None:
    maitre = _profil_detaille()
    exp = maitre.experiences[0].model_copy(update={"achievements": ("Migration vers PostgreSQL",)})
    assert verify_facts(maitre, maitre.model_copy(update={"experiences": (exp,)})).is_valid


def test_realisation_inventee_est_rejetee() -> None:
    maitre = _profil_detaille()
    exp = maitre.experiences[0].model_copy(
        update={"achievements": (*maitre.experiences[0].achievements, "Équipe de 50 personnes")}
    )
    rapport = verify_facts(maitre, maitre.model_copy(update={"experiences": (exp,)}))

    assert rapport.is_valid is False
    assert any("Équipe de 50 personnes" in i for i in rapport.issues)


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("start", DocDate(year=2010)),  # ancienneté gonflée
        ("end", DocDate(year=2025)),
        ("is_current", True),
        ("description", "Direction de l'ingénierie."),
        ("location", "Silicon Valley"),
    ],
)
def test_champ_d_experience_modifie_est_rejete(champ: str, valeur: object) -> None:
    maitre = _profil_detaille()
    exp = maitre.experiences[0].model_copy(update={champ: valeur})
    rapport = verify_facts(maitre, maitre.model_copy(update={"experiences": (exp,)}))

    assert rapport.is_valid is False
    assert any(f"'{champ}'" in i for i in rapport.issues)


def test_formation_modifiee_est_rejetee() -> None:
    maitre = _profil_maitre()
    edu = maitre.educations[0].model_copy(update={"end": DocDate(year=1999)})
    rapport = verify_facts(maitre, maitre.model_copy(update={"educations": (edu,)}))
    assert rapport.is_valid is False


def test_certification_ou_langue_modifiee_est_rejetee() -> None:
    maitre = _profil_detaille()
    certif = CertificationDoc(name="AWS SAA", issuer="Google")
    langue = LanguageDoc(language_code="fr", level_text="bilingue")

    assert not verify_facts(
        maitre, maitre.model_copy(update={"certifications": (certif,)})
    ).is_valid
    assert not verify_facts(maitre, maitre.model_copy(update={"languages": (langue,)})).is_valid


def test_identite_modifiee_est_rejetee() -> None:
    maitre = _profil_detaille()
    genere = maitre.model_copy(update={"identity": Identity(first_name="Bob", last_name="Martin")})
    assert verify_facts(maitre, genere).is_valid is False


def test_accroche_generee_avec_chiffre_sans_source_est_rejetee() -> None:
    maitre = _profil_detaille()
    rapport = verify_facts(maitre, maitre, generated_summary="Plus de 12 ans d'expérience.")

    assert rapport.is_valid is False
    assert any("'12'" in i for i in rapport.issues)


def test_accroche_generee_avec_chiffre_du_profil_est_acceptee() -> None:
    maitre = _profil_detaille()
    assert verify_facts(
        maitre, maitre, generated_summary="Réduction de 30 % de la latence."
    ).is_valid
    assert verify_facts(maitre, maitre, generated_summary="Compétences clés : Python.").is_valid
