# Audit de l'environnement et du dépôt (TASK-001-01)

Date du relevé : 2026-11-03

## État du dépôt

- Branche courante : `dev` (branche principale : `master`).
- Aucun code applicatif : pas de frontend, pas de backend, pas de base de données, pas de scripts, pas de CI.
- Contenu : `README.md`, `CLAUDE.md` et `docs/` (spécification, backlog, règles, deux prompts documentaires).
- Aucun `.gitignore` : à créer avant tout code (TASK-002-01), notamment pour `.env`, `storage/`, `documents/generated/`.

## Outils disponibles sur la machine de développement

| Outil | Version / état |
|---|---|
| macOS | Apple Silicon (arm64), 16 Go de RAM |
| Python | 3.14.7 (Homebrew) |
| uv | présent |
| Node.js | 24.16.0 (nvm) |
| pnpm | présent |
| Docker | présent, démon actif (29.8.1) |
| PostgreSQL client (`psql`) | présent (libpq) ; serveur prévu via Docker Compose |
| pdflatex | présent (`/Library/TeX/texbin`) |
| Ollama | absent (IA locale non prioritaire) |

## Constats et risques

1. **Python 3.14 est très récent** : la compatibilité de certaines dépendances (SQLAlchemy, Pydantic, pilotes PostgreSQL, bibliothèques PDF) n'est pas garantie. Recommandation : épingler une version stable (3.12 ou 3.13) via `uv` pour le backend, à valider dans l'ADR du backend.
2. **pdflatex local** : utile pour le développement, mais la compilation en production doit rester dans un conteneur isolé (spec §17.4).
3. **Docker disponible** : compatible avec le plan PostgreSQL + Docker Compose.
4. **Aucune protection Git en place** : pas de `.gitignore`, pas de détection de secrets.

## Décisions déjà prises (hors code)

- Sources d'offres gratuites et publiques uniquement pour l'instant.
- API IA payante comme fournisseur principal, avec plafond obligatoire.
- Aucun contournement des protections des sites.
