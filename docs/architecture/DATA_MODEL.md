# Modèle de données (PostgreSQL)

Source de vérité : les migrations Alembic (`backend/migrations/versions/`), vérifiées contre les modèles par un test (`test_le_schema_migre_correspond_exactement_aux_modeles`). Relations : voir [DOMAIN_MODEL.md](DOMAIN_MODEL.md).

## Conventions

- Tables en `snake_case` pluriel ; clés primaires `id` (UUID, `gen_random_uuid()`) ; horodatages `created_at`/`updated_at` (`timestamptz`).
- Noms de contraintes et d'index déterministes (convention SQLAlchemy) : `pk_`, `fk_`, `uq_`, `ix_`, `ck_`.
- Énumérations : colonnes texte + contrainte `CHECK` (ajouter une valeur ne demande pas de migration de type).
- Montants en `NUMERIC`, jamais en flottant. Données semi-structurées (préférences, critères, résultats d'analyse, charge brute d'une source) en `JSONB`, validées par le domaine avant écriture.
- Pays, langues et devises : formats contrôlés par `CHECK`, sans liste fermée.

## Tables (31)

`users` · `candidates` · `candidate_profiles` · `experiences` · `educations` · `certifications` · `skills` · `profile_languages` · `profile_changes` · `matching_settings` · `ai_settings` · `job_sources` · `target_companies` · `job_offers` · `job_offer_revisions` · `job_offer_sources` · `job_offer_states` · `saved_searches` · `search_runs` · `job_analyses` · `job_match_scores` · `ai_usages` · `ai_budgets` · `ai_cache_entries` · `generated_documents` · `document_versions` · `applications` · `application_events` · `application_contacts` · `application_documents` · `notifications` · `jobs`

À venir avec leur EPIC : préférences de notification (EPIC 015), préparation d'entretien (EPIC 016).

## Profil maître (EPIC 005, migration 0004)

- **Versions** : une ligne de `candidate_profiles` par version (`version` croissante par candidat). Une version `validated` n'est jamais réécrite ; modifier ouvre un nouveau brouillon copié.
- **Identité figée par version** (`candidate_profiles.identity`, JSONB) : modifier l'identité d'un brouillon ne change pas les versions validées. `candidates` reflète la dernière version validée.
- **Brouillon libre, élément validé complet** : `company`, `title`, `start_date`, `institution`, `degree`, `proficiency` sont nullables ; les contraintes `validated_is_complete` interdisent de confirmer (`validated_at`) un élément incomplet.
- **Dates partielles** : une date `date` est accompagnée d'une précision (`*_precision` = `year` ou `month`). « 2020 » est stocké au 1er janvier avec la précision `year` : la base ne prétend pas connaître le mois.
- **Niveau de langue inconnu** : `proficiency` NULL ; le texte d'origine (« courant ») est gardé dans `level_text`, jamais converti en niveau CECR.
- **Traçabilité** : `source` (importé/manuel), `source_text` (extrait du CV d'origine) et `validated_at` sur chaque élément.
- **Journal** `profile_changes` : une ligne par modification (`entity_type`, `action`, `changes` = `{champ: [avant, après]}`), supprimée avec le profil. Le CV importé n'est jamais conservé, seul l'extrait source de chaque élément l'est.

## Scoring (EPIC 009, migration 0005)

- `job_match_scores` : une ligne par (offre, version de profil, version de poids) ; `score` 0-100, `breakdown` JSONB (critères, correspondances, écarts, fiabilité). Les scores d'une autre version de profil ou de poids sont purgés au recalcul. Voir `MATCHING.md`.
- `matching_settings` : pondérations personnalisées (JSONB), une ligne par propriétaire ; aucune ligne = pondérations par défaut. Distinctes du profil maître.

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
| Offres expirées | Passent à `expired` quand toutes leurs observations ont disparu d'un parcours **complet** de leur source, ou à la date d'expiration annoncée ; passent à `archived` après 90 jours sans candidature ni sauvegarde. Jamais supprimées si une candidature y est liée |
| Historique des modifications d'offres (`job_offer_revisions`) | Conservé tant que l'offre existe |
| Tâches de fond terminées (`jobs`) | À purger après 30 jours ; les tâches mortes restent consultables jusqu'à purge manuelle |
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
