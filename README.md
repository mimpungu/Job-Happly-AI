# Happly AI

Assistant personnel de recherche d'emploi, **local et sans compte** : trouver des offres sur des sources autorisées, les comparer à son CV maître, générer CV et lettres sur mesure (LaTeX, compatibles ATS), suivre ses candidatures, préparer ses entretiens et rester maître de ses données.

> **État : version de préparation (voir `CHANGELOG.md`), pas une version stable.** Application locale, sans authentification : ne jamais l'exposer sur un réseau (`docs/security/LOCAL_NO_AUTH_NOTICE.md`). Limites restantes : `docs/engineering/QUALITY_REPORT.md`.

## Ce que l'application fait

| Parcours | Où |
|---|---|
| Importer son CV (PDF, DOCX, TXT), relire, valider le profil maître | Espace CV → Profil maître |
| Trouver des offres (entreprises suivies, saisie manuelle), filtrer, voir le score de compatibilité | Recherche d'emploi |
| Générer un CV ciblé, contrôlé (aucun fait inventé) et audité ATS ; PDF et LaTeX | Espace CV → CV générés |
| Générer une lettre de motivation adaptée, auditée, à relire avant envoi | Lettres de motivation |
| Suivre ses candidatures (Kanban, historique, relances) ; l'envoi reste **manuel** | Candidatures |
| Préparer et simuler un entretien, suivre les entretiens | Préparation d'entretien |
| Régler l'IA (facultative), les plafonds de coût et le consentement | Centre IA |
| Voir, exporter, supprimer ses données ; santé de l'application | Paramètres |

L'application fonctionne **entièrement sans IA**. L'IA (modèle local ou API plafonnée) n'intervient qu'à la demande.

## Démarrer

Guide pas à pas : [`docs/INSTALL.md`](docs/INSTALL.md). En bref (Docker Desktop lancé, depuis la racine) :

```bash
cp .env.example .env                    # puis remplacer le mot de passe d'exemple
./infrastructure/scripts/start.sh       # PostgreSQL, API et interface
./infrastructure/scripts/migrate.sh     # première installation et après chaque mise à jour
```

Interface : http://127.0.0.1:3000 · API : http://127.0.0.1:8000/api/v1/health

## Documentation

| Document | Contenu |
|---|---|
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | Guide utilisateur |
| [`docs/INSTALL.md`](docs/INSTALL.md) | Installation et mise à jour |
| [`docs/operations/BACKUP_RESTORE.md`](docs/operations/BACKUP_RESTORE.md) | Sauvegarde et restauration |
| [`docs/operations/DEPLOYMENT.md`](docs/operations/DEPLOYMENT.md) | Déploiement (local uniquement) |
| [`docs/security/SECURITY.md`](docs/security/SECURITY.md) | Sécurité, confidentialité, menaces |
| [`docs/API.md`](docs/API.md) | API REST |
| [`docs/AI_COSTS.md`](docs/AI_COSTS.md), [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | Coûts IA, sources d'offres |
| [`docs/engineering/QUALITY_REPORT.md`](docs/engineering/QUALITY_REPORT.md) | Rapport de qualité chiffré |
| [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CHANGELOG.md`](CHANGELOG.md) | Contribuer, historique |
| [`docs/architecture/ADR/`](docs/architecture/ADR/README.md) | Décisions d'architecture |

## Structure du dépôt

| Dossier | Contenu |
|---|---|
| `frontend/` | Interface Next.js / React / TypeScript strict |
| `backend/` | API FastAPI (Python 3.13, uv), monolithe modulaire en Clean Architecture |
| `docs/` | Spécification, backlog, architecture, ADR, exploitation, sécurité |
| `infrastructure/scripts/` | Démarrage, arrêt, migration, tests, sauvegarde, restauration |

## Développer

Backend (depuis `backend/`) :

```bash
uv sync
uv run uvicorn app.main:app           # API sur 127.0.0.1:8000
uv run pytest                          # HAPPLY_TEST_DATABASE_URL requis pour l'intégration
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Frontend (depuis `frontend/`) :

```bash
pnpm install
pnpm dev
pnpm lint && pnpm typecheck && pnpm format:check && pnpm test && pnpm build
pnpm e2e                               # accessibilité, API simulée
pnpm e2e:fullstack                     # parcours complets : vraie API, base et pdfLaTeX
```

Détails et conventions : [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Branches

`master` : branche stable. `dev` : intégration. Travail en branches `feat/…`, `fix/…`, `chore/…`, `docs/…`. Commits en français, Conventional Commits.
