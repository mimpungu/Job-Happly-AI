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


def test_experiences_restituees_en_ordre_antechronologique() -> None:
    """Un ATS et un recruteur attendent le plus récent d'abord, quel que soit le score."""
    profil = _profil_multi_experiences()
    adapted = adapt_resume_content(
        build_generation_context(profil, required_skills=("Kubernetes",)), max_experiences=3
    )

    assert [e.company for e in adapted.adapted_profile.experiences] == [
        "FinTech SaaS",  # en cours
        "Cloud Solutions",  # 2020-2022
        "Web Agency",  # 2018-2020
    ]


def test_la_limite_garde_les_plus_pertinentes_puis_les_remet_dans_l_ordre() -> None:
    """Kubernetes (titre + texte) et Django (titre + texte) battent le seul bonus « en cours »."""
    profil = _profil_multi_experiences()
    adapted = adapt_resume_content(
        build_generation_context(profil, required_skills=("Kubernetes", "Django")),
        max_experiences=2,
    )

    assert [e.company for e in adapted.adapted_profile.experiences] == [
        "Cloud Solutions",  # 2020-2022, restitué avant…
        "Web Agency",  # …2018-2020, malgré un score égal
    ]


def test_un_terme_court_ne_correspond_pas_a_une_sous_chaine() -> None:
    """« Go » ne doit pas faire remonter une expérience qui parle de « Google »."""
    profil = ProfileDocument(
        experiences=(
            ExperienceDoc(
                title="Dev",
                company="A",
                start=DocDate(year=2010),
                end=DocDate(year=2011),
                description="Intégration de Google Analytics.",
            ),
            ExperienceDoc(
                title="Dev",
                company="B",
                start=DocDate(year=2012),
                end=DocDate(year=2013),
                description="Services en Go.",
            ),
        ),
        skills=(SkillDoc(name="Go"),),
    )
    adapted = adapt_resume_content(
        build_generation_context(profil, required_skills=("Go",)), max_experiences=1
    )
    assert adapted.adapted_profile.experiences[0].company == "B"


def test_realisations_pertinentes_en_tete_sans_reecriture() -> None:
    exp = ExperienceDoc(
        title="Dev",
        company="A",
        achievements=("Organisation d'ateliers", "Migration vers PostgreSQL", "Revue de code"),
    )
    profil = ProfileDocument(experiences=(exp,), skills=(SkillDoc(name="PostgreSQL"),))
    adapted = adapt_resume_content(
        build_generation_context(profil, required_skills=("PostgreSQL",)), max_achievements=2
    )
    realisations = adapted.adapted_profile.experiences[0].achievements

    assert realisations == ("Migration vers PostgreSQL", "Organisation d'ateliers")
    assert set(realisations) <= set(exp.achievements)  # jamais de texte nouveau


def test_synonymes_de_competences_reconnus() -> None:
    """« JavaScript » demandé par l'offre, « JS » dans le profil : même compétence."""
    profil = ProfileDocument(skills=(SkillDoc(name="JS"), SkillDoc(name="Python")))
    adapted = adapt_resume_content(
        build_generation_context(profil, required_skills=("JavaScript", "Rust"))
    )

    assert adapted.matched_keywords == ("JS",)
    assert adapted.missing_keywords == ("Rust",)
    assert adapted.offer_terms == ("JavaScript", "Rust")


def test_sans_termes_explicites_seules_les_competences_du_candidat_citees_comptent() -> None:
    """Plus de « mots les plus fréquents de l'annonce » : uniquement du vérifié."""
    profil = ProfileDocument(skills=(SkillDoc(name="Python"), SkillDoc(name="Docker")))
    adapted = adapt_resume_content(
        build_generation_context(
            profil,
            offer_description="Nous cherchons un expert Python, avec de solides notions de Rust "
            "et une culture agile pour rejoindre notre équipe.",
        )
    )
    assert adapted.matched_keywords == ("Python",)
    assert "Rust" not in adapted.offer_terms
    assert "équipe" not in adapted.offer_terms


def test_accroche_factuelle_sans_chiffre_ni_qualificatif_invente() -> None:
    """Régression : l'ancienne accroche inventait « plus de 6 ans » et « passionné »."""
    profil = ProfileDocument(
        identity=Identity(headline="Dév"),
        experiences=tuple(ExperienceDoc(title="Dev", company=f"E{i}") for i in range(3)),
        skills=(SkillDoc(name="Python"),),
    )
    adapted = adapt_resume_content(build_generation_context(profil, required_skills=("Python",)))
    resume = adapted.adapted_summary or ""

    assert adapted.summary_is_generated is True
    assert "Python" in resume
    assert not any(c.isdigit() for c in resume)
    for invente in ("ans", "passionné", "Rigoureux", "orienté résultats"):
        assert invente not in resume


def test_pas_d_accroche_quand_rien_de_verifiable() -> None:
    profil = ProfileDocument(skills=(SkillDoc(name="Python"),))
    adapted = adapt_resume_content(build_generation_context(profil))

    assert adapted.adapted_summary is None
    assert adapted.summary_is_generated is False


def test_accroche_du_profil_maitre_conservee_telle_quelle() -> None:
    profil = ProfileDocument(summary="Mon résumé.", skills=(SkillDoc(name="Python"),))
    adapted = adapt_resume_content(build_generation_context(profil, required_skills=("Python",)))

    assert adapted.adapted_summary == "Mon résumé."
    assert adapted.summary_is_generated is False


def test_accroche_en_anglais() -> None:
    profil = ProfileDocument(skills=(SkillDoc(name="Python"),))
    adapted = adapt_resume_content(
        build_generation_context(profil, required_skills=("Python",), language="en")
    )
    assert adapted.adapted_summary == "Key skills for this role: Python."
