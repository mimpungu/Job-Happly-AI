"""Profil et offre d'exemple partagés par les tests de la lettre de motivation."""

from datetime import date

from app.modules.candidate_profile.domain.profile import (
    DocDate,
    EducationDoc,
    ExperienceDoc,
    Identity,
    ProfileDocument,
    SkillDoc,
)
from app.modules.document_generation.domain.cover_letter_generator import (
    extract_company_offer_context,
)
from app.modules.document_generation.domain.cover_letter_models import CompanyOfferContext

AUJOURDHUI = date(2026, 11, 4)

DESCRIPTION_OFFRE = """Nous construisons une plateforme de santé numérique.

Vos missions
- Concevoir des API FastAPI robustes
- Écrire des requêtes SQL sur PostgreSQL
- Participer aux revues de code

Compétences requises : Python, FastAPI, Rust
"""


def profil_alice() -> ProfileDocument:
    return ProfileDocument(
        identity=Identity(
            first_name="Alice",
            last_name="Mercier",
            city="Paris",
            email="alice.mercier@example.com",
            phone="+33 6 00 00 00 00",
        ),
        experiences=(
            ExperienceDoc(
                title="Lead Tech Python",
                company="DataCorp",
                start=DocDate(year=2021),
                is_current=True,
                description="Architecture de microservices Python et FastAPI.",
                achievements=(
                    "Latence réduite de 40 %",
                    "Migration vers PostgreSQL",
                    "Mentorat de 3 développeurs",
                ),
            ),
            ExperienceDoc(
                title="Développeuse Backend",
                company="WebAgency",
                start=DocDate(year=2018),
                end=DocDate(year=2021),
                description="API REST en Python.",
                achievements=("Mise en place de la CI",),
            ),
        ),
        educations=(EducationDoc(degree="Master Informatique", institution="Université de Lyon"),),
        skills=(
            SkillDoc(name="Python"),
            SkillDoc(name="FastAPI"),
            SkillDoc(name="PostgreSQL"),
            SkillDoc(name="Docker"),
        ),
    )


def contexte_offre(**surcharges: object) -> CompanyOfferContext:
    valeurs: dict[str, object] = {
        "job_title": "Développeur Python Backend",
        "company_name": "Doctolib",
        "offer_description": DESCRIPTION_OFFRE,
        "company_location": "Paris",
        "required_skills": ("Python", "FastAPI", "Rust"),
    }
    valeurs.update(surcharges)
    return extract_company_offer_context(**valeurs)  # type: ignore[arg-type]
