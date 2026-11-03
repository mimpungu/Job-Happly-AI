# Modèle de données (PostgreSQL)

Source de vérité : les migrations Alembic (`backend/migrations/versions/`), vérifiées contre les modèles par un test (`test_le_schema_migre_correspond_exactement_aux_modeles`). Relations : voir [DOMAIN_MODEL.md](DOMAIN_MODEL.md).

## Conventions

- Tables en `snake_case` pluriel ; clés primaires `id` (UUID, `gen_random_uuid()`) ; horodatages `created_at`/`updated_at` (`timestamptz`).
- Noms de contraintes et d'index déterministes (convention SQLAlchemy) : `pk_`, `fk_`, `uq_`, `ix_`, `ck_`.
- Énumérations : colonnes texte + contrainte `CHECK` (ajouter une valeur ne demande pas de migration de type).
- Montants en `NUMERIC`, jamais en flottant. Données semi-structurées (préférences, critères, résultats d'analyse, charge brute d'une source) en `JSONB`, validées par le domaine avant écriture.
- Pays, langues et devises : formats contrôlés par `CHECK`, sans liste fermée.

## Tables (27)

`users` · `candidates` · `candidate_profiles` · `experiences` · `educations` · `certifications` · `skills` · `profile_languages` · `job_sources` · `target_companies` · `job_offers` · `job_offer_sources` · `job_offer_states` · `saved_searches` · `search_runs` · `job_analyses` · `job_match_scores` · `ai_usages` · `ai_budgets` · `ai_cache_entries` · `generated_documents` · `document_versions` · `applications` · `application_events` · `application_contacts` · `application_documents` · `notifications`

À venir avec leur EPIC : file de tâches (`jobs`, ADR-0009, EPIC 007/015), préférences de notification (EPIC 015), préparation d'entretien (EPIC 016).

## Index (TASK-004-08)

| Table | Index | Requête servie |
|---|---|---|
| job_offer_sources | unique (owner, source, identifiant externe) | Déduplication par identifiant externe, idempotence de l'ingestion |
| job_offers | (owner, pays) · (owner, date de publication décroissante) · (owner, `lower(titre)`) · (owner, `lower(entreprise)`) · (owner, statut) · (owner, empreinte) · unique partiel (owner, URL canonique) | Filtres de recherche, tri, doublons par URL ou contenu |
| applications | unique (owner, offre) · (owner, statut) · partiel (owner, relance) | Kanban, filtres, rappels |
| search_runs | (owner, début décroissant) | Historique des recherches |
| ai_usages | (owner, date) · (owner, fournisseur, date) · (opération) | Calcul des budgets journalier et mensuel |
| job_analyses | unique (owner, offre, type, prompt, modèle, empreinte) | Réutilisation des analyses (aucun appel IA inutile) |

Chaque table de données a aussi un index sur `owner_id` et sur ses clés étrangères. Les index restent à valider par `EXPLAIN` sur volumes réalistes (TASK-019-19).

## Transactions (TASK-004-09)

- L'unité de travail (`UnitOfWork`) délimite une transaction : validation en cas de succès, annulation en cas d'exception.
- Les repositories ne valident jamais ; seul le use case le fait.
- L'ingestion est idempotente : `upsert_observation` s'appuie sur la contrainte d'unicité et `ON CONFLICT DO NOTHING`, donc relancer une collecte ne crée aucun doublon.

## Historisation et rétention (TASK-004-12)

| Donnée | Règle |
|---|---|
| Observations d'offres et données brutes | Conservées tant que l'offre existe (audit, traçabilité) |
| Offres expirées | Passent à `expired` ; passent à `archived` après 90 jours sans candidature ni sauvegarde. Jamais supprimées si une candidature y est liée |
| Historique des candidatures | Conservé (utile à l'utilisateur) |
| `ai_usages` | 24 mois, puis agrégation mensuelle conservée |
| `ai_cache_entries` | Suppression à `expires_at` |
| `search_runs` | 12 mois |
| Versions de documents | Conservées ; immuables |
| Sauvegardes | Voir [BACKUP_RESTORE.md](../operations/BACKUP_RESTORE.md) |
| Données de l'utilisateur | Export et suppression complète à sa demande (EPIC 018) |

Ces durées sont des valeurs initiales, rendues configurables et appliquées par des tâches planifiées (EPIC 007 et 015).

## Archivage (TASK-004-13)

- L'archivage change le **statut** (`archived`), sans déplacer ni supprimer de ligne : l'historique utile reste intact.
- Les listes excluent par défaut les offres archivées ; elles restent consultables.
- Toutes les listes sont paginées côté base (jamais de chargement complet en mémoire).
- Si le volume l'exige un jour : partitionnement par date ou table d'archive, décidé par ADR sur mesures réelles.
