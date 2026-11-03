# Happly AI

Assistant personnel de recherche d'emploi : trouver des offres sur des sources autorisées, les comparer à son CV maître, générer CV et lettres sur mesure, suivre ses candidatures et préparer ses entretiens.

> Projet en construction (EPIC 002 en cours). Application locale, sans authentification pour l'instant : ne pas l'exposer sur un réseau. Voir `docs/security/LOCAL_NO_AUTH_NOTICE.md`.

## Structure du dépôt

| Dossier | Contenu |
|---|---|
| `frontend/` | Interface Next.js / React / TypeScript strict |
| `backend/` | API FastAPI (Python 3.13, uv) |
| `docs/` | Spécification, backlog, architecture, ADR, conventions |

Le frontend et le backend sont deux projets distincts, avec chacun ses dépendances et ses outils.

## Prérequis

Python 3.13 et [uv](https://docs.astral.sh/uv/), Node.js et pnpm, Docker (à venir avec la base de données).

## Commandes

Backend (depuis `backend/`) :

```bash
uv sync                      # installer les dépendances
uv run uvicorn app.main:app  # lancer l'API sur 127.0.0.1:8000
uv run pytest                # tests
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Frontend (depuis `frontend/`) :

```bash
pnpm install
pnpm dev                     # lancer l'interface
pnpm lint && pnpm typecheck && pnpm format:check && pnpm build
```

Variables d'environnement : copier `.env.example` vers `.env` (jamais versionné).

Docker Compose (PostgreSQL, API, frontend ; ports liés à `127.0.0.1`) et scripts, depuis la racine :

```bash
./infrastructure/scripts/start.sh       # démarrer les services
./infrastructure/scripts/stop.sh        # arrêter (données conservées)
./infrastructure/scripts/test.sh        # tests backend et frontend
./infrastructure/scripts/lint.sh        # formatage, lint, typage
./infrastructure/scripts/build.sh       # images Docker
./infrastructure/scripts/reset-test.sh  # base de TEST uniquement (projet Docker dédié)
./infrastructure/scripts/migrate.sh     # disponible avec Alembic (EPIC 004)
```

## Branches

`master` : branche stable. `dev` : intégration. Travail en branches `feat/…`, `fix/…`, `chore/…`, `docs/…`. Commits en français, Conventional Commits.

## Documentation

Point d'entrée : [docs/README.md](docs/README.md).
