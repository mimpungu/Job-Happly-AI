# Contrats intermodules (TASK-001-06)

Les contrats sont des interfaces Python (`Protocol` ou classe abstraite) déclarées dans la couche `application`/`domain` du module fournisseur, implémentées dans `infrastructure`. Les signatures ci-dessous sont **indicatives** et seront figées lors de l'implémentation de chaque EPIC.

## Contrats vers l'extérieur (ports)

| Port | Fournisseur | Rôle | Implémentations |
|---|---|---|---|
| `JobSourceConnector` | job_discovery | `search`, `get_details`, `health_check`, `get_capabilities` | Une par source réelle ; faux uniquement en test |
| `AIProvider` | ai_management | `generate`, `health_check` | Fournisseur payant (à décider), local plus tard |
| `DocumentStorage` | document_generation | `save`, `open`, `delete` | Disque local ; objet plus tard |
| `LatexCompiler` | document_generation | `compile(source) → pdf` dans un environnement isolé | Conteneur sans réseau |
| `Notifier` | notifications | `send` | In-app ; e-mail si configuré |
| `JobQueue` | jobs | `enqueue`, `reserve`, `complete`, `fail` | PostgreSQL |
| `Clock` | core | Heure courante injectable (tests déterministes) | Système / fixe en test |

## Contrats entre modules

| Interface | Fournisseur → consommateurs | Contenu |
|---|---|---|
| `AIGateway` | ai_management → job_intelligence, document_generation, interview_preparation | `run(task, inputs, user_context) → résultat validé` ; applique cache, plafond, journal ; refuse si plafond dépassé |
| `CandidateFactsReader` | candidate_profile → job_intelligence, document_generation | Lecture des faits validés du CV maître, par champs demandés (minimisation) |
| `JobOfferReader` | job_discovery → job_intelligence, document_generation, application_management | Lecture d'une offre normalisée par identifiant |
| *(exception de lecture)* | job_intelligence → job_discovery | La recherche d'offres joint `job_match_scores` en lecture seule (tri/filtre par score côté base). Jointure assumée, sans écriture croisée |
| `DocumentVersionReader` | document_generation → application_management | Versions de CV/lettre associées à une offre |
| `BudgetStatusReader` | ai_management → notifications, Dashboard | État de consommation et seuils |

## Événements de domaine

Publiés en mémoire dans le processus, avec persistance pour ceux qui déclenchent des jobs (outbox dans PostgreSQL).

| Événement | Émetteur | Consommateurs |
|---|---|---|
| `JobOffersIngested` | job_discovery | job_intelligence (scoring), notifications |
| `JobOfferChanged` / `JobOfferExpired` | job_discovery | job_intelligence (invalidation du cache d'analyse) |
| `JobScored` | job_intelligence | notifications (offres pertinentes) |
| `BudgetThresholdReached` | ai_management | notifications |
| `DocumentGenerated` | document_generation | application_management |
| `ApplicationStatusChanged` | application_management | notifications, historique |
| `ReminderDue` | application_management | notifications |

## Règles de contrat

- Entrées et sorties typées (Pydantic/dataclasses), sans objet ORM.
- Toute opération reçoit un `UserContext` (utilisateur, identifiant de corrélation).
- Les erreurs traversent les frontières sous forme d'exceptions métier typées, jamais d'exceptions d'infrastructure brutes.
- Un contrat modifié exige la mise à jour de ce document et des tests de contrat.
- Les contrats externes (API HTTP) sont décrits par OpenAPI, versionnés sous `/api/v1`.

## Matrice de dépendances autorisées

Lecture : la ligne peut dépendre de la colonne (via son interface publique).

| | core | candidate_profile | job_discovery | job_intelligence | ai_management | document_generation | application_management | interview_prep | notifications |
|---|---|---|---|---|---|---|---|---|---|
| candidate_profile | ✔ | | | | | | | | |
| job_discovery | ✔ | | | | | | | | |
| job_intelligence | ✔ | ✔ | ✔ | | ✔ | | | | |
| ai_management | ✔ | | | | | | | | |
| document_generation | ✔ | ✔ | ✔ | | ✔ | | | | |
| application_management | ✔ | | ✔ | | | ✔ | | | |
| interview_preparation | ✔ | ✔ | ✔ | | ✔ | | ✔ | | |
| notifications | ✔ | | | | | | | | |

Les notifications reçoivent des événements ; elles ne dépendent d'aucun autre module. Cette matrice sera vérifiée automatiquement (test d'architecture, TASK-002-04).
