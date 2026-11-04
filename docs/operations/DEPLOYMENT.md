# Déploiement

## Périmètre actuel : local uniquement

Happly AI est conçue pour tourner **sur la machine de son utilisateur**, sans authentification (ADR-0008). Le seul mode de déploiement supporté est Docker Compose en local (`docs/INSTALL.md`) :

- ports publiés sur `127.0.0.1` uniquement (vérifié par `tests/architecture/test_local_mode.py`) ;
- CORS limité à `http://127.0.0.1:3000` ;
- secrets dans `.env` (non versionné) ;
- données dans les volumes Docker `postgres_data` et `documents_data`.

## Ce qui est interdit tant que l'authentification n'existe pas

Exposer l'application sur un réseau partagé, un tunnel public, un hébergeur ou un serveur distant. Les tâches **018-35** (authentification) et **018-36** (multi-utilisateur) sont des prérequis, avec HTTPS, un reverse proxy et des limites de débit partagées.

## Configuration (variables d'environnement)

| Variable | Rôle | Défaut |
|---|---|---|
| `HAPPLY_ENVIRONMENT` | `development`, `test`, `production` | `development` |
| `HAPPLY_DATABASE_URL` | PostgreSQL (obligatoire en production, mot de passe d'exemple refusé) | — |
| `HAPPLY_CORS_ALLOWED_ORIGINS` | Origines autorisées (`*` interdit) | `["http://127.0.0.1:3000"]` |
| `HAPPLY_LOG_LEVEL` | Niveau des logs JSON | `INFO` |
| `HAPPLY_STORAGE_DIR` | Dossier des PDF générés | `storage` |
| `HAPPLY_PDFLATEX_PATH` | Chemin de `pdflatex` si absent du `PATH` | recherche automatique |
| `HAPPLY_RATE_LIMIT_PER_MINUTE` / `HAPPLY_RATE_LIMIT_EXPENSIVE_PER_MINUTE` | Limites de débit | 600 / 30 |
| `HAPPLY_MAX_REQUEST_BODY_MB` | Taille maximale annoncée d'une requête | 12 |
| `HAPPLY_GEMINI_API_KEY`, `HAPPLY_GEMINI_TIER` | IA en ligne (facultative) | absent, `free` |
| `HAPPLY_OLLAMA_ENABLED`, `HAPPLY_OLLAMA_URL` | IA locale (boucle locale obligatoire) | `false` |
| `HAPPLY_FRANCE_TRAVAIL_CLIENT_ID` / `_SECRET` | API France Travail (accès actuellement bloqué par le fournisseur) | absent |

La configuration est validée au démarrage : une valeur incohérente empêche le démarrage plutôt que de dégrader la sécurité.

## Exploitation

Santé et mesures : `docs/operations/OBSERVABILITY.md`. Sauvegarde : `BACKUP_RESTORE.md`. Incidents : `RECOVERY.md`. Rotation des clés : `docs/security/SECRETS.md`. Checklist de livraison : `docs/engineering/RELEASE_CHECKLIST.md`.
