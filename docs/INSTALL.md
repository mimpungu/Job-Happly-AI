# Installation

Application **locale** : tout reste sur `127.0.0.1`. Deux voies : Docker (recommandée) ou développement.

## Prérequis

| Outil | Pour | Remarque |
|---|---|---|
| Docker Desktop | Voie Docker | PostgreSQL, API et interface tournent en conteneurs |
| Python 3.13 et [uv](https://docs.astral.sh/uv/) | Voie développement | |
| Node.js 24 et pnpm | Voie développement | |
| PostgreSQL 17 | Voie développement | Docker suffit (`docker compose up -d postgres`) |
| TeX Live (`pdflatex`) | Génération de CV et lettres hors Docker | L'image Docker de l'API l'embarque |
| Ollama (facultatif) | IA locale | ~9 Go de mémoire pour `gemma4:e4b` |

## Voie Docker (première installation)

Depuis la racine du dépôt, Docker Desktop lancé :

```bash
cp .env.example .env
```

Éditer `.env` : remplacer le mot de passe d'exemple `change-me` (dans `POSTGRES_PASSWORD` **et** dans `HAPPLY_DATABASE_URL`). `.env` n'est jamais versionné.

```bash
./infrastructure/scripts/start.sh      # construit les images (quelques minutes la première fois)
./infrastructure/scripts/migrate.sh    # crée le schéma de la base
```

Vérifier : http://127.0.0.1:8000/api/v1/health répond `{"status":"ok"}`, http://127.0.0.1:8000/api/v1/health/details décrit l'état (base, stockage, LaTeX), puis ouvrir http://127.0.0.1:3000.

Arrêt : `./infrastructure/scripts/stop.sh` (les données sont conservées dans les volumes Docker).

## Mise à jour

```bash
git pull
./infrastructure/scripts/backup.sh     # sauvegarde AVANT toute migration
./infrastructure/scripts/start.sh      # reconstruit les images
./infrastructure/scripts/migrate.sh    # applique les nouvelles migrations
```

Les migrations sont versionnées (Alembic) et additives ; elles ne suppriment pas de données. Retour en arrière : `docs/operations/BACKUP_RESTORE.md`.

## Voie développement

```bash
docker compose up -d postgres          # ou un PostgreSQL local
cd backend && uv sync
export HAPPLY_DATABASE_URL=postgresql://happly:<mot-de-passe>@127.0.0.1:5432/happly
uv run alembic upgrade head
uv run uvicorn app.main:app            # 127.0.0.1:8000
cd ../frontend && pnpm install && pnpm dev   # 127.0.0.1:3000
```

## IA (facultative)

- **Local** : `./infrastructure/scripts/ia-start.sh` et `HAPPLY_OLLAMA_ENABLED=true` dans `.env`.
- **API Gemini** : `HAPPLY_GEMINI_API_KEY` dans `.env` (jamais ailleurs). Palier gratuit : textes d'offres publiques seulement. Aucun appel payant sans plafonds et consentement (Centre IA).

Détail : `docs/operations/DEMARRAGE_ET_ARRET.md`, `docs/AI_COSTS.md`.

## Vérifier l'installation

```bash
./infrastructure/scripts/test.sh       # tests backend et frontend (base de test dédiée)
```

Parcours complets (vraie API, vraie base, vrai navigateur) : `cd frontend && pnpm e2e:fullstack` (requiert `psql`, `uv`, un navigateur Playwright, et pdflatex).

## Dépannage

`docs/operations/DEMARRAGE_ET_ARRET.md` (tableau de dépannage) et `docs/operations/RECOVERY.md`.
