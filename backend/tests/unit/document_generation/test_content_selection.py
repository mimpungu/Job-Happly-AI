"""Tests unitaires de la sélection de contenu et de l'adaptation (FEATURE 012.2)."""

from app.modules.candidate_profile.domain.profile import (
    DocDate,
    ExperienceDoc,
    Identity,
    ProfileDocument,
    SkillDoc,
)
from app.modules.document_generation.domain.content_selection import (
    adapt_resume_content,
    build_generation_context,
)


def _profil_multi_experiences() -> ProfileDocument:
    return ProfileDocument(
        identity=Identity(
            first_name="Alice",
            last_name="Martin",
            headline="Développeuse Python & DevOps",
        ),
        experiences=(
            ExperienceDoc(
                title="Développeuse Python Django",
                company="Web Agency",
                start=DocDate(year=2018),
                end=DocDate(year=2020),
                description="Développement de plateformes web en Django et MySQL.",
            ),
            ExperienceDoc(
                title="Ingénieure DevOps Kubernetes",
                company="Cloud Solutions",
                start=DocDate(year=2020),
                end=DocDate(year=2022),
                description="Déploiement de clusters Kubernetes et pipelines CI/CD.",
            ),
            ExperienceDoc(
                title="Lead Backend Python FastAPI",
                company="FinTech SaaS",
                start=DocDate(year=2022),
                is_current=True,
                description="Architecture microservices avec FastAPI, Kafka et PostgreSQL.",
                achievements=("Performance améliorée", "Architecture DDD"),
            ),
        ),
        skills=(
            SkillDoc(name="Python", category="Langages"),
            SkillDoc(name="FastAPI", category="Frameworks"),
            SkillDoc(name="Kubernetes", category="DevOps"),
            SkillDoc(name="Docker", category="DevOps"),
            SkillDoc(name="PostgreSQL", category="Bases"),
        ),
    )


def test_contexte_et_scoring_experiences() -> None:
    """Vérifie la priorité des expériences pertinentes (TASK-012-06 et TASK-012-07)."""
    profil = _profil_multi_experiences()
    context = build_generation_context(
        profile=profil,
        offer_title="Senior Python Backend Engineer (FastAPI / PostgreSQL)",
        offer_description="Développeur senior maîtrisant FastAPI, Python et PostgreSQL.",
        required_skills=("Python", "FastAPI", "PostgreSQL"),
    )

    adapted = adapt_resume_content(context)

    # L'expérience la plus pertinente (FinTech SaaS / FastAPI) doit être en première position
    assert len(adapted.adapted_profile.experiences) == 3
    assert adapted.adapted_profile.experiences[0].company == "FinTech SaaS"
    assert "FastAPI" in (adapted.adapted_profile.experiences[0].title or "")


def test_limite_nombre_experiences() -> None:
    """Vérifie le filtrage au nombre maximal d'expériences (ex: pour 1 page)."""
    profil = _profil_multi_experiences()
    context = build_generation_context(
        profile=profil,
        offer_title="Python Developer",
        required_skills=("Python",),
    )

    adapted = adapt_resume_content(context, max_experiences=2)
    assert len(adapted.adapted_profile.experiences) == 2


def test_mots_cles_verifies_et_manquants() -> None:
    """Vérifie l'identification exacte des mots-clés vérifiés sans bourrage (TASK-012-09)."""
    profil = _profil_multi_experiences()
    context = build_generation_context(
        profile=profil,
        offer_title="Ingénieur Backend",
        required_skills=("Python", "FastAPI", "Rust", "Go"),
    )

    adapted = adapt_resume_content(context)

    # Mots-clés vérifiés (présents chez la candidate)
    assert "Python" in adapted.matched_keywords
    assert "FastAPI" in adapted.matched_keywords
    # Mots-clés manquants (l'IA ne doit JAMAIS les inventer)
    assert "Rust" in adapted.missing_keywords
    assert "Go" in adapted.missing_keywords
    assert "Rust" not in [s.name for s in adapted.adapted_profile.skills]
