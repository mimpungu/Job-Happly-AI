"""Tests unitaires du contrôleur strict des faits (TASK-012-10)."""

import pytest

from app.modules.candidate_profile.domain.profile import (
    EducationDoc,
    ExperienceDoc,
    Identity,
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

