"""Offres fictives du mode démonstration (TASK-002-10).

Tout est manifestement fictif : entreprises inventées, adresses en `demo.invalid` (domaine réservé,
jamais résolu), intitulés préfixés. Ce catalogue ne contient aucune donnée réelle ni aucune offre
copiée d'un site.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.value_objects import EmploymentType, RemoteType

DEMO_SOURCE_KEY = "demo"
DEMO_SOURCE_NAME = "Mode démonstration (données fictives)"
CONFIRMATION_DEMO = "Données fictives : aucune de ces offres n'existe."


@dataclass(frozen=True)
class DemoOffer:
    title: str
    company: str
    location: str
    country_code: str
    employment_type: EmploymentType
    remote_type: RemoteType
    description: str


def _texte(mission: str, competences: str) -> str:
    return (
        f"[DÉMO — offre fictive] {mission}\n\n"
        f"Compétences requises : {competences}.\n\n"
        "Cette offre est générée par le mode démonstration de Happly AI : elle n'existe pas."
    )


DEMO_OFFERS: tuple[DemoOffer, ...] = (
    DemoOffer(
        "[DÉMO] Développeur·se Python backend",
        "Atelier Démo",
        "Lyon, France",
        "FR",
        EmploymentType.PERMANENT,
        RemoteType.HYBRID,
        _texte(
            "Concevoir des API REST pour une plateforme fictive.",
            "Python, FastAPI, PostgreSQL, Docker",
        ),
    ),
    DemoOffer(
        "[DÉMO] Data engineer",
        "Données Imaginaires SAS",
        "Paris, France",
        "FR",
        EmploymentType.PERMANENT,
        RemoteType.REMOTE,
        _texte("Construire des pipelines de données fictifs.", "Python, SQL, Airflow, Spark"),
    ),
    DemoOffer(
        "[DÉMO] Ingénieur·e DevOps",
        "Studio Imaginaire",
        "Nantes, France",
        "FR",
        EmploymentType.PERMANENT,
        RemoteType.HYBRID,
        _texte("Automatiser des déploiements fictifs.", "Docker, Kubernetes, Terraform, Linux"),
    ),
    DemoOffer(
        "[DÉMO] Développeur·se front-end React",
        "Pixel Fictif",
        "Lille, France",
        "FR",
        EmploymentType.FIXED_TERM,
        RemoteType.ON_SITE,
        _texte(
            "Construire des interfaces pour un produit fictif.", "TypeScript, React, CSS, tests"
        ),
    ),
    DemoOffer(
        "[DÉMO] Analyste BI",
        "Chiffres Fictifs",
        "Bordeaux, France",
        "FR",
        EmploymentType.PERMANENT,
        RemoteType.HYBRID,
        _texte("Produire des tableaux de bord fictifs.", "SQL, Power BI, Excel"),
    ),
    DemoOffer(
        "[DÉMO] Software engineer (remote)",
        "Demo Labs",
        "Remote",
        "BE",
        EmploymentType.PERMANENT,
        RemoteType.REMOTE,
        _texte("Build features for a made-up product.", "Python, TypeScript, PostgreSQL, Git"),
    ),
    DemoOffer(
        "[DÉMO] Chef·fe de projet technique",
        "Projets Imaginaires",
        "Toulouse, France",
        "FR",
        EmploymentType.PERMANENT,
        RemoteType.ON_SITE,
        _texte("Piloter un projet fictif.", "Gestion de projet, Jira, communication"),
    ),
    DemoOffer(
        "[DÉMO] Stage — ingénieur·e logiciel",
        "Atelier Démo",
        "Lyon, France",
        "FR",
        EmploymentType.INTERNSHIP,
        RemoteType.HYBRID,
        _texte("Participer à un projet fictif.", "Python, Git, curiosité"),
    ),
)
