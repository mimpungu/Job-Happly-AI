"""Vocabulaire fermé de technologies courantes, repérées par nom exact dans le texte.

Choix : une liste connue plutôt qu'une devinette sur la prose — précision élevée, au prix d'une
limite assumée : une technologie absente de cette liste n'est pas relevée comme technologie
(elle peut l'être comme compétence par l'extraction des exigences).

Les noms qui sont aussi des mots courants (Go, R, REST, Swift, Spring, Express, Vault, Rails…) ne
figurent que sous une forme non ambiguë (Golang, Spring Boot, REST API, SwiftUI…).
"""

from __future__ import annotations

import re

from app.modules.job_intelligence.domain.matching.skills import SkillMatcher

TECHNOLOGIES: tuple[str, ...] = (
    # Langages
    "Python", "Java", "JavaScript", "TypeScript", "Golang", "Rust", "C++", "C#", "Kotlin",
    "SwiftUI",
    "Scala", "Ruby", "PHP", "SQL", "Julia", "Bash", "PowerShell", "Dart", "Elixir", "Haskell",
    "Objective-C", "Perl", "Lua", "COBOL",
    # Web et frameworks
    "React", "Vue", "Angular", "Svelte", "Next.js", "Node.js", "Django", "Flask", "FastAPI",
    "Spring Boot", "Ruby on Rails", "Laravel", "Symfony", ".NET", "ASP.NET", "Express.js",
    "GraphQL", "REST API", "RESTful", "gRPC", "Tailwind", "HTML", "CSS", "Flutter", "React Native",
    # Données
    "PostgreSQL", "MySQL", "MariaDB", "SQLite", "SQL Server", "Oracle", "MongoDB", "Redis",
    "Elasticsearch", "OpenSearch", "Cassandra", "DynamoDB", "Snowflake", "BigQuery", "Redshift",
    "ClickHouse", "Kafka", "RabbitMQ", "Spark", "Hadoop", "Flink", "Airflow", "dbt", "Pandas",
    "NumPy", "Polars", "Databricks", "Power BI", "Tableau", "Looker", "Metabase",
    # Cloud et infrastructure
    "AWS", "Azure", "Google Cloud", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible",
    "Helm", "Jenkins", "GitLab", "GitHub Actions", "CircleCI", "ArgoCD", "Prometheus", "Grafana",
    "Linux", "Nginx", "OpenTelemetry", "Istio", "Envoy", "HashiCorp Vault",
    # IA et machine learning
    "TensorFlow", "PyTorch", "Keras", "scikit-learn", "Hugging Face", "LangChain", "LLM",
    "MLflow", "CUDA", "OpenAI",
    # Pratiques et concepts techniques courants
    "Machine Learning", "Deep Learning", "Data Engineering", "Data Science", "NLP",
    "Computer Vision", "CI/CD", "DevOps", "Microservices", "Agile", "Scrum",
    # Outils
    "Git", "Jira", "Confluence", "Figma", "Postman", "Swagger", "OpenAPI", "Selenium", "Cypress",
    "Playwright", "Jest", "Pytest", "JUnit", "Sentry", "Snyk",
)  # fmt: skip

_REPERER = SkillMatcher(TECHNOLOGIES)
_CONNUES = {t.casefold() for t in TECHNOLOGIES}
_HEURE = re.compile(r"\d{1,2}(am|pm|h)\b", re.IGNORECASE)
# Fuseaux horaires et sigles de lieu : en majuscules, mais pas des compétences.
_SIGLES_NON_TECHNIQUES = {"cet", "cest", "pst", "pdt", "est", "edt", "utc", "gmt", "bst", "ist"}


def looks_like_skill(terme: str) -> bool:
    """Vrai si un terme extrait d'une rubrique d'exigences ressemble à une compétence technique.

    Les exigences d'une annonce réelle mêlent compétences et prose (« Applicant », « About
    Datadog », « am-12pm »). On n'affiche comme compétence que : une technologie connue, un sigle
    (SQL, AWS) ou un jeton technique (Node.js, C++). Le reste n'est pas jeté du score, seulement
    de cette liste d'affichage.
    """
    if terme.casefold() in _CONNUES:
        return True
    if _HEURE.search(terme) or terme.casefold() in _SIGLES_NON_TECHNIQUES:
        return False
    if " " not in terme and terme.isalpha() and terme.isupper() and 2 <= len(terme) <= 6:
        return True
    return " " not in terme and any(c in terme for c in "+#.") and terme[0].isalpha()


def find_technologies(texte: str) -> list[str]:
    """Technologies du vocabulaire citées dans le texte (mot entier), dans l'ordre de la liste."""
    return _REPERER.find(texte)
