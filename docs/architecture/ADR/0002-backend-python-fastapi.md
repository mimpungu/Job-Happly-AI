# ADR-0002 — Backend Python / FastAPI

- **Statut :** Accepté (version de Python à confirmer)
- **Date :** 2026-11-03

## Contexte

Le backend orchestre des I/O (sources d'offres, API IA, base) et du traitement de texte/PDF. L'écosystème Python est le plus riche pour ces usages.

## Décision

- Python, FastAPI, Pydantic v2, SQLAlchemy 2 (style typé), Alembic.
- API REST versionnée (`/api/v1`), async pour les I/O.
- Gestion des dépendances et des environnements avec **uv**.
- Qualité : Ruff, mypy (ou pyright) en mode strict, pytest.
- **Version de Python proposée : 3.13**, épinglée via uv. Le poste de développement a Python 3.14, jugé trop récent pour garantir la compatibilité de toutes les dépendances. À confirmer lors de TASK-002-03 après vérification des dépendances réelles.

## Alternatives étudiées

- Node/NestJS : un seul langage, mais écosystème moins adapté au traitement de documents et à l'IA.
- Django : plus complet, mais moins adapté à une architecture en couches async explicite.

## Conséquences

- Deux langages (Python, TypeScript) : contrats d'API à garder synchronisés (schéma OpenAPI, types partagés générés).
