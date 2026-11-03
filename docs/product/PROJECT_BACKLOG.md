# PROJECT_BACKLOG — registre vivant des statuts

Généré à partir de `docs/HAPPLY_AI_MASTER_BACKLOG.md` (référence de périmètre). **En cas d'écart, le backlog maître fait foi** ; régénérer ce registre après tout changement de périmètre.

Légende : [✅] réalisé et validé, [➖] non réalisé. L'état fin (`BACKLOG`, `READY`, `IN_PROGRESS`, `IN_REVIEW`, `TESTING`, `BLOCKED`) est suivi dans la colonne *État*.

**Estimation :** non fixée ici. Elle est posée lorsque la tâche devient `READY` (Definition of Ready, backlog Partie 5.1), une fois ses dépendances et ses risques connus. Une estimation donnée trop tôt serait inventée.

**Tests requis :** déterminés au passage `READY` selon `docs/engineering/DEVELOPMENT_GUIDELINES.md` et les critères d'acceptation de l'EPIC.

**Dépendances :** niveau EPIC (graphe du backlog, Partie 4). Les dépendances entre tâches sont précisées au passage `READY`.

---

## Synthèse

| Statut | EPIC | Priorité | Features | Tasks | Tasks [✅] | Dépendances |
|---|---|---|---|---|---|---|
| [➖] | 001 — PRODUCT DISCOVERY & SOFTWARE ARCHITECTURE | P0 | 4 | 11 | 11 | — |
| [➖] | 002 — PROJECT FOUNDATION & DEVELOPER EXPERIENCE | P0 | 3 | 11 | 6 | EPIC 001 |
| [➖] | 003 — DESIGN SYSTEM & APPLICATION SHELL | P0 | 3 | 18 | 18 | EPIC 002 |
| [➖] | 004 — DATABASE & DOMAIN FOUNDATION | P0 | 3 | 13 | 12 | EPIC 002 |
| [✅] | 005 — CANDIDATE PROFILE & MASTER CV | P0 | 4 | 18 | 18 | EPIC 003, EPIC 004 |
| [➖] | 006 — JOB SOURCE CONNECTOR FRAMEWORK | P0 | 6 | 28 | 18 | EPIC 002 |
| [✅] | 007 — JOB INGESTION, NORMALIZATION & DEDUPLICATION | P0 | 4 | 19 | 19 | EPIC 004, EPIC 006 |
| [➖] | 008 — JOB SEARCH ENGINE & SEARCH EXPERIENCE | P0 | 5 | 28 | 19 | EPIC 003, EPIC 007 |
| [✅] | 009 — JOB MATCHING & SCORING ENGINE | P0 | 3 | 17 | 17 | EPIC 005, EPIC 007, EPIC 008 |
| [➖] | 010 — AI PLATFORM & COST MANAGEMENT | P0 | 6 | 35 | 24 | EPIC 002, EPIC 004 |
| [➖] | 011 — JOB INTELLIGENCE & OFFER ANALYSIS | P1 | 3 | 15 | 0 | EPIC 009, EPIC 010 |
| [➖] | 012 — LATEX RESUME GENERATOR | P1 | 5 | 27 | 0 | EPIC 005, EPIC 010, EPIC 011 |
| [➖] | 013 — COVER LETTER GENERATOR | P1 | 3 | 18 | 0 | EPIC 005, EPIC 010, EPIC 011, EPIC 012 |
| [➖] | 014 — APPLICATION TRACKING & CANDIDATE CRM | P1 | 5 | 22 | 0 | EPIC 004, EPIC 008, EPIC 012, EPIC 013 |
| [➖] | 015 — SCHEDULER, AUTOMATION & NOTIFICATIONS | P1 | 4 | 19 | 0 | EPIC 008, EPIC 009, EPIC 010 |
| [➖] | 016 — INTERVIEW PREPARATION & CAREER ASSISTANT | P2 | 3 | 14 | 0 | EPIC 014 |
| [➖] | 017 — INTERNATIONALIZATION & GLOBAL JOB SEARCH | P1 | 5 | 24 | 0 | EPIC 006, EPIC 007, EPIC 008 |
| [➖] | 018 — SECURITY, PRIVACY & OPERATIONAL EXCELLENCE | P0 | 6 | 37 | 0 | EPIC 002 |
| [➖] | 019 — QA, RELEASE & PRODUCTION READINESS | P0 | 5 | 30 | 0 | EPIC 002 |

Total : 404 tâches.

---

## [➖] EPIC 001 — PRODUCT DISCOVERY & SOFTWARE ARCHITECTURE

- **Priorité :** P0
- **Objectif :** établir une architecture cohérente avant de développer les fonctionnalités métier.
- **Dépendances :** —

### [✅] FEATURE 001.1 — Analyse de l'environnement

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-001-01 | Inspecter le dépôt | P0 | DONE | à estimer |
| [✅] | TASK-001-02 | Identifier les contraintes | P0 | DONE | à estimer |
| [✅] | TASK-001-03 | Définir les objectifs, le périmètre et les critères de réussite | P0 | DONE | à estimer |

### [✅] FEATURE 001.2 — Architecture logicielle

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-001-04 | Concevoir l'architecture globale | P0 | DONE | à estimer |
| [✅] | TASK-001-05 | Définir les bounded contexts | P0 | DONE | à estimer |
| [✅] | TASK-001-06 | Définir les contrats intermodules | P0 | DONE | à estimer |
| [✅] | TASK-001-07 | Définir les conventions de développement | P0 | DONE | à estimer |

### [✅] FEATURE 001.3 — Architecture documentaire

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-001-08 | Créer ARCHITECTURE.md | P0 | DONE | à estimer |
| [✅] | TASK-001-09 | Créer les premiers ADR | P0 | DONE | à estimer |

### [✅] FEATURE 001.4 — Pilotage documentaire

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-001-10 | Produire `PROJECT_BACKLOG.md` détaillé | P0 | DONE | à estimer |
| [✅] | TASK-001-11 | Créer l'arborescence `docs/` | P0 | DONE | à estimer |

**Critères d'acceptation de l'EPIC**

- [✅] Architecture documentée.
- [✅] Dépendances définies.
- [✅] Responsabilités des modules identifiées.
- [✅] Choix technologiques justifiés.
- [➖] Périmètre produit validé par le propriétaire (voir docs/product/PRODUCT_REQUIREMENTS.md).
- [✅] Aucun développement métier majeur commencé sans fondations architecturales.

## [➖] EPIC 002 — PROJECT FOUNDATION & DEVELOPER EXPERIENCE

- **Priorité :** P0
- **Objectif :** mettre en place un environnement de développement propre, reproductible et maintenable.
- **Dépendances :** EPIC 001

### [➖] FEATURE 002.1 — Initialisation du projet

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-002-01 | Initialiser le repository | P0 | DONE | à estimer |
| [✅] | TASK-002-02 | Initialiser le frontend | P0 | DONE | à estimer |
| [✅] | TASK-002-03 | Initialiser le backend | P0 | DONE | à estimer |
| [➖] | TASK-002-04 | Configurer les outils qualité | P0 | BACKLOG | à estimer |

### [➖] FEATURE 002.2 — Configuration et environnements

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-002-05 | Gestion des variables d'environnement | P0 | DONE | à estimer |
| [✅] | TASK-002-06 | Docker Compose | P0 | DONE | à estimer |
| [➖] | TASK-002-07 | Scripts de développement | P0 | BACKLOG | à estimer |
| [➖] | TASK-002-10 | Mode démonstration | P0 | BACKLOG | à estimer |
| [✅] | TASK-002-11 | Outillage de tests de base | P0 | DONE | à estimer |

### [➖] FEATURE 002.3 — CI/CD

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-002-08 | Pipeline CI | P0 | BACKLOG | à estimer |
| [➖] | TASK-002-09 | Protection Git | P0 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Le projet démarre depuis une installation propre.
- [➖] Frontend et backend communiquent.
- [➖] Les migrations fonctionnent.
- [➖] Les contrôles qualité passent.
- [➖] La CI détecte les régressions.
- [➖] Aucun secret réel n'est versionné.

## [➖] EPIC 003 — DESIGN SYSTEM & APPLICATION SHELL

- **Priorité :** P0
- **Objectif :** créer une interface premium cohérente, inspirée de la philosophie de design Apple.
- **Dépendances :** EPIC 002

### [✅] FEATURE 003.1 — Design tokens

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-003-01 | Définir la palette sombre | P0 | DONE | à estimer |
| [✅] | TASK-003-02 | Définir les tokens typographiques | P0 | DONE | à estimer |
| [✅] | TASK-003-03 | Définir les espacements et dimensions | P0 | DONE | à estimer |
| [✅] | TASK-003-04 | Définir les états visuels | P0 | DONE | à estimer |

### [✅] FEATURE 003.2 — Composants fondamentaux

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-003-05 | Développer Button | P0 | DONE | à estimer |
| [✅] | TASK-003-06 | Développer Input et SearchInput | P0 | DONE | à estimer |
| [✅] | TASK-003-07 | Développer Select et Dropdown | P0 | DONE | à estimer |
| [✅] | TASK-003-08 | Développer Badge et StatusBadge | P0 | DONE | à estimer |
| [✅] | TASK-003-09 | Développer Card et Panel | P0 | DONE | à estimer |
| [✅] | TASK-003-10 | Développer Modal et Dialog | P0 | DONE | à estimer |
| [✅] | TASK-003-11 | Développer Table et Pagination | P0 | DONE | à estimer |
| [✅] | TASK-003-12 | Développer Toast, Tooltip et Skeleton | P0 | DONE | à estimer |
| [✅] | TASK-003-18 | Développer IconButton, Tabs, FilterPanel et EmptyState | P0 | DONE | à estimer |

### [✅] FEATURE 003.3 — Application Shell

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-003-13 | Créer la Sidebar | P0 | DONE | à estimer |
| [✅] | TASK-003-14 | Créer le Header | P0 | DONE | à estimer |
| [✅] | TASK-003-15 | Créer le système de navigation | P0 | DONE | à estimer |
| [✅] | TASK-003-16 | Créer les pages Empty State | P0 | DONE | à estimer |
| [✅] | TASK-003-17 | Développer le responsive design | P0 | DONE | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Design sombre cohérent.
- [✅] Aucun dégradé sur les textes ou boutons.
- [✅] Couleurs centralisées.
- [✅] Composants réutilisables.
- [✅] Navigation fonctionnelle.
- [✅] Responsive desktop/tablette/mobile.
- [✅] Accessibilité clavier.
- [✅] Contrastes lisibles.

## [➖] EPIC 004 — DATABASE & DOMAIN FOUNDATION

- **Priorité :** P0
- **Objectif :** construire une base de données fiable et un modèle métier extensible.
- **Dépendances :** EPIC 002

### [✅] FEATURE 004.1 — Modèle de données

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-004-01 | Définir les entités principales | P0 | DONE | à estimer |
| [✅] | TASK-004-02 | Définir les Value Objects | P0 | DONE | à estimer |
| [✅] | TASK-004-03 | Définir les relations | P0 | DONE | à estimer |
| [✅] | TASK-004-04 | Définir les contraintes métier | P0 | DONE | à estimer |

### [➖] FEATURE 004.2 — Persistence Layer

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-004-05 | Configurer SQLAlchemy | P0 | DONE | à estimer |
| [✅] | TASK-004-06 | Créer les migrations Alembic | P0 | DONE | à estimer |
| [➖] | TASK-004-07 | Créer les repositories | P0 | BACKLOG | à estimer |
| [✅] | TASK-004-08 | Ajouter les index | P0 | DONE | à estimer |
| [✅] | TASK-004-09 | Définir les transactions | P0 | DONE | à estimer |

### [✅] FEATURE 004.3 — Infrastructure de données

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-004-10 | Créer les mécanismes de sauvegarde | P0 | DONE | à estimer |
| [✅] | TASK-004-11 | Créer la stratégie de restauration | P0 | DONE | à estimer |
| [✅] | TASK-004-12 | Définir les règles de rétention | P0 | DONE | à estimer |
| [✅] | TASK-004-13 | Définir la stratégie d'archivage | P0 | DONE | à estimer |

**Critères d'acceptation de l'EPIC**

- [✅] Modèle cohérent.
- [✅] Migrations reproductibles.
- [➖] Repositories testés.
- [✅] Contraintes SQL fonctionnelles.
- [✅] Sauvegarde et restauration documentées.
- [➖] Aucun accès direct à la base depuis la logique métier.

## [✅] EPIC 005 — CANDIDATE PROFILE & MASTER CV

- **Priorité :** P0
- **Objectif :** créer le référentiel central du candidat.
- **Dépendances :** EPIC 003, EPIC 004

### [✅] FEATURE 005.1 — Import des documents

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-005-01 | Développer l'upload sécurisé | P0 | DONE | à estimer |
| [✅] | TASK-005-02 | Développer l'extraction PDF | P0 | DONE | à estimer |
| [✅] | TASK-005-03 | Développer l'extraction DOCX | P0 | DONE | à estimer |
| [✅] | TASK-005-04 | Normaliser le texte extrait | P0 | DONE | à estimer |
| [✅] | TASK-005-05 | Détecter les documents malformés | P0 | DONE | à estimer |

### [✅] FEATURE 005.2 — Extraction du profil

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-005-06 | Extraire les coordonnées | P0 | DONE | à estimer |
| [✅] | TASK-005-07 | Extraire les expériences | P0 | DONE | à estimer |
| [✅] | TASK-005-08 | Extraire les formations | P0 | DONE | à estimer |
| [✅] | TASK-005-09 | Extraire les compétences | P0 | DONE | à estimer |
| [✅] | TASK-005-10 | Extraire les langues et certifications | P0 | DONE | à estimer |

### [✅] FEATURE 005.3 — Validation du CV maître

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-005-11 | Créer le formulaire de profil | P0 | DONE | à estimer |
| [✅] | TASK-005-12 | Créer l'éditeur des expériences | P0 | DONE | à estimer |
| [✅] | TASK-005-13 | Créer l'éditeur des compétences | P0 | DONE | à estimer |
| [✅] | TASK-005-14 | Créer la gestion des formations | P0 | DONE | à estimer |
| [✅] | TASK-005-15 | Ajouter la validation des informations extraites | P0 | DONE | à estimer |
| [✅] | TASK-005-16 | Ajouter l'historique des modifications | P0 | DONE | à estimer |

### [✅] FEATURE 005.4 — Profil professionnel

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-005-17 | Créer le profil maître versionné | P0 | DONE | à estimer |
| [✅] | TASK-005-18 | Créer la gestion des préférences professionnelles | P0 | DONE | à estimer |

**Critères d'acceptation de l'EPIC**

- [✅] Import de CV fonctionnel.
- [✅] Extraction testée.
- [✅] Modifications possibles.
- [✅] Validation humaine disponible.
- [✅] Profil maître conservé indépendamment des CV ciblés.
- [✅] Traçabilité des informations.
- [✅] Aucune donnée professionnelle inventée.

## [➖] EPIC 006 — JOB SOURCE CONNECTOR FRAMEWORK

- **Priorité :** P0
- **Objectif :** créer une architecture de connecteurs indépendante des fournisseurs.
- **Dépendances :** EPIC 002

### [✅] FEATURE 006.1 — Contrat des connecteurs

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-006-01 | Définir JobSourceConnector | P0 | DONE | à estimer |
| [✅] | TASK-006-02 | Définir les modèles de requête | P0 | DONE | à estimer |
| [✅] | TASK-006-03 | Définir les modèles de réponse | P0 | DONE | à estimer |
| [✅] | TASK-006-04 | Définir les exceptions spécifiques | P0 | DONE | à estimer |

### [✅] FEATURE 006.2 — Registre des sources

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-006-05 | Développer ConnectorRegistry | P0 | DONE | à estimer |
| [✅] | TASK-006-06 | Ajouter la configuration des sources | P0 | DONE | à estimer |
| [✅] | TASK-006-07 | Ajouter l'activation et la désactivation | P0 | DONE | à estimer |
| [✅] | TASK-006-08 | Ajouter le statut de santé | P0 | DONE | à estimer |

### [✅] FEATURE 006.3 — Résilience

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-006-09 | Implémenter les timeouts | P0 | DONE | à estimer |
| [✅] | TASK-006-10 | Implémenter les retries | P0 | DONE | à estimer |
| [✅] | TASK-006-11 | Implémenter le rate limiting | P0 | DONE | à estimer |
| [✅] | TASK-006-12 | Ajouter le circuit breaker si nécessaire | P0 | DONE | à estimer |
| [✅] | TASK-006-13 | Journaliser les erreurs | P0 | DONE | à estimer |

### [➖] FEATURE 006.4 — Premier connecteur réel

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-006-14 | Étudier les API officielles disponibles | P0 | BACKLOG | à estimer |
| [➖] | TASK-006-15 | Sélectionner une première source française | P0 | BACKLOG | à estimer |
| [➖] | TASK-006-16 | Obtenir et configurer les accès nécessaires | P0 | BACKLOG | à estimer |
| [➖] | TASK-006-17 | Implémenter la recherche réelle | P0 | BACKLOG | à estimer |
| [➖] | TASK-006-18 | Implémenter la récupération des détails | P0 | BACKLOG | à estimer |
| [➖] | TASK-006-19 | Écrire les tests avec fixtures et réponses anonymisées | P0 | BACKLOG | à estimer |

### [➖] FEATURE 006.5 — Page Sources de données

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-006-20 | Créer la page Sources de données | P0 | BACKLOG | à estimer |

### [➖] FEATURE 006.6 — Sites carrières des entreprises (sources publiques uniquement)

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-006-21 | Gérer la liste des entreprises ciblées | P0 | BACKLOG | à estimer |
| [✅] | TASK-006-22 | Détecter la source publique d'une entreprise | P0 | DONE | à estimer |
| [➖] | TASK-006-23 | Connecteurs d'API publiques d'ATS | P0 | BACKLOG | à estimer |
| [✅] | TASK-006-24 | Extraction des données structurées `JobPosting` (schema.org) | P0 | DONE | à estimer |
| [➖] | TASK-006-25 | Lecture de pages publiques conditionnée à l'autorisation | P0 | BACKLOG | à estimer |
| [✅] | TASK-006-26 | Filtrer les offres d'entreprise par intitulé de poste | P0 | DONE | à estimer |
| [✅] | TASK-006-27 | Sécuriser les requêtes sortantes (SSRF) | P0 | DONE | à estimer |
| [✅] | TASK-006-28 | Tests avec fixtures anonymisées | P0 | DONE | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Connecteur interchangeable.
- [➖] Premier fournisseur réellement fonctionnel.
- [➖] Gestion des erreurs.
- [➖] Respect des quotas et conditions d'utilisation.
- [➖] Aucune source simulée présentée comme réelle.
- [➖] Un connecteur indisponible ne bloque pas les autres.

## [✅] EPIC 007 — JOB INGESTION, NORMALIZATION & DEDUPLICATION

- **Priorité :** P0
- **Objectif :** centraliser et fiabiliser les offres issues de différentes sources.
- **Dépendances :** EPIC 004, EPIC 006

### [✅] FEATURE 007.1 — Ingestion

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-007-01 | Créer le Job Ingestion Service | P0 | DONE | à estimer |
| [✅] | TASK-007-02 | Ajouter les tâches asynchrones | P0 | DONE | à estimer |
| [✅] | TASK-007-03 | Gérer les résultats paginés | P0 | DONE | à estimer |
| [✅] | TASK-007-04 | Gérer les erreurs partielles | P0 | DONE | à estimer |

### [✅] FEATURE 007.2 — Normalisation

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-007-05 | Normaliser les intitulés | P0 | DONE | à estimer |
| [✅] | TASK-007-06 | Normaliser les pays et villes | P0 | DONE | à estimer |
| [✅] | TASK-007-07 | Normaliser les contrats | P0 | DONE | à estimer |
| [✅] | TASK-007-08 | Normaliser les devises | P0 | DONE | à estimer |
| [✅] | TASK-007-09 | Normaliser les dates et fuseaux horaires | P0 | DONE | à estimer |
| [✅] | TASK-007-10 | Préserver les données originales | P0 | DONE | à estimer |

### [✅] FEATURE 007.3 — Déduplication

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-007-11 | Détection par identifiant externe | P0 | DONE | à estimer |
| [✅] | TASK-007-12 | Détection par URL canonique | P0 | DONE | à estimer |
| [✅] | TASK-007-13 | Détection multicritère | P0 | DONE | à estimer |
| [✅] | TASK-007-14 | Calcul de similarité textuelle | P0 | DONE | à estimer |
| [✅] | TASK-007-15 | Gestion des offres multi-sources | P0 | DONE | à estimer |

### [✅] FEATURE 007.4 — Cycle de vie des annonces

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-007-16 | Détection des annonces expirées | P0 | DONE | à estimer |
| [✅] | TASK-007-17 | Gestion des annonces modifiées | P0 | DONE | à estimer |
| [✅] | TASK-007-18 | Historisation des changements | P0 | DONE | à estimer |
| [✅] | TASK-007-19 | Nettoyage des annonces obsolètes selon politique de rétention | P0 | DONE | à estimer |

**Critères d'acceptation de l'EPIC**

- [✅] Données normalisées.
- [✅] Doublons contrôlés.
- [✅] Historique conservé.
- [✅] Offres correctement reliées à leurs sources.
- [✅] Ingestion résiliente.
- [✅] Aucun doublon créé lors de la relance d'une tâche.

## [➖] EPIC 008 — JOB SEARCH ENGINE & SEARCH EXPERIENCE

- **Priorité :** P0
- **Objectif :** permettre à l'utilisateur de rechercher des emplois avec des critères avancés.
- **Dépendances :** EPIC 003, EPIC 007

### [➖] FEATURE 008.1 — Formulaire de recherche

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-008-01 | Recherche par intitulé | P0 | DONE | à estimer |
| [✅] | TASK-008-02 | Recherche par mots-clés | P0 | DONE | à estimer |
| [✅] | TASK-008-03 | Recherche par ville et pays | P0 | DONE | à estimer |
| [➖] | TASK-008-04 | Recherche par rayon | P0 | BACKLOG | à estimer |
| [✅] | TASK-008-05 | Recherche par contrat | P0 | DONE | à estimer |
| [✅] | TASK-008-06 | Recherche par salaire | P0 | DONE | à estimer |
| [✅] | TASK-008-07 | Recherche par télétravail | P0 | DONE | à estimer |
| [➖] | TASK-008-08 | Recherche par expérience | P0 | BACKLOG | à estimer |
| [✅] | TASK-008-09 | Recherche par date de publication | P0 | DONE | à estimer |
| [➖] | TASK-008-10 | Recherche multilingue | P0 | BACKLOG | à estimer |

### [➖] FEATURE 008.2 — Orchestration multi-sources

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-008-11 | Sélectionner les connecteurs compatibles | P0 | BACKLOG | à estimer |
| [➖] | TASK-008-12 | Lancer les recherches en parallèle | P0 | BACKLOG | à estimer |
| [➖] | TASK-008-13 | Agréger les résultats | P0 | BACKLOG | à estimer |
| [➖] | TASK-008-14 | Gérer les erreurs partielles | P0 | BACKLOG | à estimer |
| [➖] | TASK-008-15 | Afficher les sources interrogées | P0 | BACKLOG | à estimer |

### [✅] FEATURE 008.3 — Résultats

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-008-16 | Développer Job Results Table | P0 | DONE | à estimer |
| [✅] | TASK-008-17 | Développer les filtres dynamiques | P0 | DONE | à estimer |
| [✅] | TASK-008-18 | Développer le tri | P0 | DONE | à estimer |
| [✅] | TASK-008-19 | Développer la pagination | P0 | DONE | à estimer |
| [✅] | TASK-008-20 | Développer la vue détaillée | P0 | DONE | à estimer |
| [✅] | TASK-008-21 | Ajouter la sauvegarde d'une offre | P0 | DONE | à estimer |

### [✅] FEATURE 008.4 — Recherches sauvegardées

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-008-22 | Créer SavedSearch | P0 | DONE | à estimer |
| [✅] | TASK-008-23 | Enregistrer les critères | P0 | DONE | à estimer |
| [✅] | TASK-008-24 | Modifier les recherches | P0 | DONE | à estimer |
| [✅] | TASK-008-25 | Relancer une recherche | P0 | DONE | à estimer |
| [✅] | TASK-008-26 | Afficher l'historique | P0 | DONE | à estimer |

### [➖] FEATURE 008.5 — Compléments de recherche et d'offre

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-008-27 | Ignorer une offre | P0 | DONE | à estimer |
| [➖] | TASK-008-28 | Recherche par entreprise, secteur et langue de l'annonce | P0 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Recherche fonctionnelle.
- [➖] Filtres opérationnels.
- [✅] Résultats paginés.
- [➖] Sources visibles.
- [✅] Erreurs clairement affichées.
- [✅] Recherche sauvegardable et reproductible.

## [✅] EPIC 009 — JOB MATCHING & SCORING ENGINE

- **Priorité :** P0
- **Objectif :** classer les offres selon leur correspondance avec le profil candidat.
- **Dépendances :** EPIC 005, EPIC 007, EPIC 008

### [✅] FEATURE 009.1 — Matching déterministe

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-009-01 | Définir les critères de correspondance | P0 | DONE | à estimer |
| [✅] | TASK-009-02 | Créer le moteur de correspondance métier | P0 | DONE | à estimer |
| [✅] | TASK-009-03 | Comparer les compétences | P0 | DONE | à estimer |
| [✅] | TASK-009-04 | Comparer l'expérience | P0 | DONE | à estimer |
| [✅] | TASK-009-05 | Comparer la formation | P0 | DONE | à estimer |
| [✅] | TASK-009-06 | Comparer les préférences géographiques | P0 | DONE | à estimer |
| [✅] | TASK-009-07 | Comparer les conditions contractuelles | P0 | DONE | à estimer |

### [✅] FEATURE 009.2 — Scoring

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-009-08 | Définir les pondérations | P0 | DONE | à estimer |
| [✅] | TASK-009-09 | Calculer le score sur 100 | P0 | DONE | à estimer |
| [✅] | TASK-009-10 | Identifier les correspondances | P0 | DONE | à estimer |
| [✅] | TASK-009-11 | Identifier les écarts | P0 | DONE | à estimer |
| [✅] | TASK-009-12 | Expliquer chaque score | P0 | DONE | à estimer |
| [✅] | TASK-009-13 | Permettre la personnalisation des pondérations | P0 | DONE | à estimer |

### [✅] FEATURE 009.3 — Interface de compatibilité

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-009-14 | Créer ScoreIndicator | P0 | DONE | à estimer |
| [✅] | TASK-009-15 | Créer SkillMatchPanel | P0 | DONE | à estimer |
| [✅] | TASK-009-16 | Créer le détail des critères | P0 | DONE | à estimer |
| [✅] | TASK-009-17 | Créer les filtres par compatibilité | P0 | DONE | à estimer |

**Critères d'acceptation de l'EPIC**

- [✅] Score reproductible.
- [✅] Pondérations configurables.
- [✅] Justification visible.
- [✅] Aucun score présenté comme une probabilité réelle d'embauche.
- [✅] Données manquantes distinguées des compétences absentes.

## [➖] EPIC 010 — AI PLATFORM & COST MANAGEMENT

- **Priorité :** P0
- **Objectif :** centraliser les fournisseurs IA et contrôler rigoureusement les coûts.
- **Dépendances :** EPIC 002, EPIC 004

### [➖] FEATURE 010.1 — Abstraction IA

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-010-01 | Définir AIProvider | P0 | DONE | à estimer |
| [➖] | TASK-010-02 | Implémenter le premier fournisseur IA | P0 | BACKLOG | à estimer |
| [✅] | TASK-010-03 | Ajouter le système de configuration | P0 | DONE | à estimer |
| [✅] | TASK-010-04 | Ajouter le routage des modèles | P0 | DONE | à estimer |
| [✅] | TASK-010-05 | Ajouter le mode local lorsque disponible | P0 | DONE | à estimer |

### [➖] FEATURE 010.2 — Gestion des coûts

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-010-06 | Créer AIUsage | P0 | DONE | à estimer |
| [✅] | TASK-010-07 | Enregistrer les tokens | P0 | DONE | à estimer |
| [✅] | TASK-010-08 | Calculer les coûts | P0 | DONE | à estimer |
| [✅] | TASK-010-09 | Ajouter les budgets journaliers | P0 | DONE | à estimer |
| [✅] | TASK-010-10 | Ajouter les budgets mensuels | P0 | DONE | à estimer |
| [➖] | TASK-010-11 | Ajouter les alertes | P0 | BACKLOG | à estimer |
| [➖] | TASK-010-12 | Ajouter les plafonds par tâche | P0 | BACKLOG | à estimer |

### [➖] FEATURE 010.3 — Cache et optimisation

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-010-13 | Développer le cache des analyses | P0 | DONE | à estimer |
| [✅] | TASK-010-14 | Définir les clés de cache | P0 | DONE | à estimer |
| [✅] | TASK-010-15 | Gérer l'expiration | P0 | DONE | à estimer |
| [➖] | TASK-010-16 | Versionner les prompts | P0 | BACKLOG | à estimer |
| [➖] | TASK-010-17 | Regrouper les tâches compatibles | P0 | BACKLOG | à estimer |
| [➖] | TASK-010-18 | Limiter les contextes envoyés | P0 | BACKLOG | à estimer |

### [✅] FEATURE 010.4 — Interface de gestion IA

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-010-19 | Créer AI Settings | P0 | DONE | à estimer |
| [✅] | TASK-010-20 | Créer AI Usage Dashboard | P0 | DONE | à estimer |
| [✅] | TASK-010-21 | Créer AI Budget Manager | P0 | DONE | à estimer |
| [✅] | TASK-010-22 | Ajouter les modes économique, équilibré et qualité | P0 | DONE | à estimer |
| [✅] | TASK-010-23 | Ajouter le mode IA désactivée | P0 | DONE | à estimer |

### [➖] FEATURE 010.5 — Fiabilité des traitements IA

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [✅] | TASK-010-24 | Valider les sorties structurées | P0 | DONE | à estimer |
| [✅] | TASK-010-25 | Gérer les réponses incomplètes | P0 | DONE | à estimer |
| [✅] | TASK-010-26 | Gérer les erreurs fournisseurs | P0 | DONE | à estimer |
| [✅] | TASK-010-27 | Tester le cache et les plafonds | P0 | DONE | à estimer |
| [➖] | TASK-010-28 | Afficher le coût estimé avant les opérations IA importantes | P0 | BACKLOG | à estimer |

### [➖] FEATURE 010.6 — API IA payante avec plafonds budgétaires stricts

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-010-29 | Fournisseur API payante principal | P0 | BACKLOG | à estimer |
| [✅] | TASK-010-30 | Plafond obligatoire avant toute utilisation | P0 | DONE | à estimer |
| [➖] | TASK-010-31 | Plafonds budgétaires stricts | P0 | BACKLOG | à estimer |
| [➖] | TASK-010-32 | Réduction de la consommation | P0 | BACKLOG | à estimer |
| [✅] | TASK-010-33 | Consentement sur les données transmises | P0 | DONE | à estimer |
| [✅] | TASK-010-34 | Tests des plafonds | P0 | DONE | à estimer |
| [➖] | TASK-010-35 | Fournisseur local (optionnel, ultérieur) | P0 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Fournisseurs interchangeables.
- [➖] Coûts tracés.
- [➖] Budget respecté.
- [➖] Cache fonctionnel.
- [➖] Appels inutiles évités.
- [➖] Sorties validées.
- [➖] Aucune clé exposée.

## [➖] EPIC 011 — JOB INTELLIGENCE & OFFER ANALYSIS

- **Priorité :** P1
- **Objectif :** enrichir les offres pertinentes avec une analyse sémantique.
- **Dépendances :** EPIC 009, EPIC 010

### [➖] FEATURE 011.1 — Extraction des exigences

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-011-01 | Extraire les missions | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-02 | Extraire les compétences obligatoires | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-03 | Extraire les compétences souhaitées | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-04 | Extraire les outils et technologies | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-05 | Extraire les années d'expérience | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-06 | Extraire les exigences linguistiques | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-07 | Extraire les contraintes de mobilité et de visa si mentionnées | P1 | BACKLOG | à estimer |

### [➖] FEATURE 011.2 — Analyse de pertinence

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-011-08 | Comparer l'annonce au CV maître | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-09 | Identifier les compétences transférables | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-10 | Identifier les informations manquantes | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-11 | Générer un résumé de l'annonce | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-12 | Expliquer les raisons de compatibilité | P1 | BACKLOG | à estimer |

### [➖] FEATURE 011.3 — Historique des analyses

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-011-13 | Versionner les analyses | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-14 | Réutiliser les analyses en cache | P1 | BACKLOG | à estimer |
| [➖] | TASK-011-15 | Invalider le cache si l'annonce change | P1 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Analyse basée sur des informations réelles.
- [➖] Résultats structurés.
- [➖] Coût IA maîtrisé.
- [➖] Analyse réutilisable.
- [➖] Aucun fait inventé.

## [➖] EPIC 012 — LATEX RESUME GENERATOR

- **Priorité :** P1
- **Objectif :** produire des CV personnalisés, professionnels et compatibles avec les contraintes ATS.
- **Dépendances :** EPIC 005, EPIC 010, EPIC 011

### [➖] FEATURE 012.1 — Templates LaTeX

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-012-01 | Créer le template principal | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-02 | Créer les sections standards | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-03 | Garantir la mise en page mono-colonne | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-04 | Gérer les caractères internationaux | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-05 | Gérer les variations de longueur | P1 | BACKLOG | à estimer |

### [➖] FEATURE 012.2 — Génération du contenu

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-012-06 | Construire le contexte de génération | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-07 | Sélectionner les expériences pertinentes | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-08 | Adapter les formulations | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-09 | Intégrer les mots-clés vérifiés | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-10 | Contrôler les faits | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-11 | Produire le code LaTeX | P1 | BACKLOG | à estimer |

### [➖] FEATURE 012.3 — Compilation

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-012-12 | Installer et configurer pdfLaTeX | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-13 | Développer le service de compilation isolé | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-14 | Gérer les erreurs de compilation | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-15 | Appliquer les limites de ressources | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-16 | Désactiver l'accès réseau pendant la compilation | P1 | BACKLOG | à estimer |

### [➖] FEATURE 012.4 — Contrôle ATS

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-012-17 | Extraire le texte PDF | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-18 | Vérifier l'ordre de lecture | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-19 | Vérifier les caractères accentués | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-20 | Vérifier les rubriques | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-21 | Détecter les problèmes de mise en page | P1 | BACKLOG | à estimer |

### [➖] FEATURE 012.5 — Versions et exports

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-012-22 | Sauvegarder les versions | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-23 | Associer chaque version à une offre | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-24 | Télécharger le PDF | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-25 | Télécharger le LaTeX | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-26 | Comparer les versions | P1 | BACKLOG | à estimer |
| [➖] | TASK-012-27 | Intégrer `docs/HAPPLY_AI_CV_GENERATION_PROMPT.md` comme prompt versionné | P1 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] PDF réellement compilé.
- [➖] Texte sélectionnable.
- [➖] Extraction vérifiée.
- [➖] Une seule colonne.
- [➖] Documents modifiables.
- [➖] CV maître préservé.
- [➖] Aucune information inventée.

## [➖] EPIC 013 — COVER LETTER GENERATOR

- **Priorité :** P1
- **Objectif :** créer une lettre de motivation adaptée à chaque entreprise.
- **Dépendances :** EPIC 005, EPIC 010, EPIC 011, EPIC 012

### [➖] FEATURE 013.1 — Analyse entreprise et offre

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-013-01 | Extraire les informations de l'entreprise | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-02 | Analyser les responsabilités | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-03 | Identifier les attentes du recruteur | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-04 | Sélectionner les expériences pertinentes | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-05 | Vérifier les informations externes | P1 | BACKLOG | à estimer |

### [➖] FEATURE 013.2 — Génération

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-013-06 | Créer le prompt versionné | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-07 | Construire le contexte minimal | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-08 | Générer la lettre | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-09 | Contrôler la cohérence avec le CV | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-10 | Contrôler les informations inventées | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-11 | Contrôler la longueur et la qualité | P1 | BACKLOG | à estimer |

### [➖] FEATURE 013.3 — Documents

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-013-12 | Créer le template de lettre | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-13 | Générer le PDF | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-14 | Ajouter l'édition manuelle | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-15 | Gérer les versions | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-16 | Ajouter les langues de candidature | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-17 | Intégrer `docs/HAPPLY_AI_COVER_LETTER_PROMPT.md` comme prompt versionné | P1 | BACKLOG | à estimer |
| [➖] | TASK-013-18 | Contrôler l'orthographe et adapter le ton au pays | P1 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Lettre personnalisée.
- [➖] Cohérence avec le CV.
- [➖] Coordonnées exactes.
- [➖] Informations vérifiées.
- [➖] PDF téléchargeable.
- [➖] Modification manuelle possible.

## [➖] EPIC 014 — APPLICATION TRACKING & CANDIDATE CRM

- **Priorité :** P1
- **Objectif :** centraliser et suivre le parcours de chaque candidature.
- **Dépendances :** EPIC 004, EPIC 008, EPIC 012, EPIC 013

### [➖] FEATURE 014.1 — Gestion des candidatures

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-014-01 | Créer Application Entity | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-02 | Associer une candidature à une offre | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-03 | Gérer les statuts | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-04 | Enregistrer la date d'envoi | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-05 | Enregistrer les coordonnées du recruteur lorsqu'elles sont connues | P1 | BACKLOG | à estimer |

### [➖] FEATURE 014.2 — Historique

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-014-06 | Historiser les changements de statut | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-07 | Ajouter des notes | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-08 | Ajouter des événements | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-09 | Associer les documents envoyés | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-10 | Gérer les dates de relance | P1 | BACKLOG | à estimer |

### [➖] FEATURE 014.3 — Interface CRM

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-014-11 | Créer la vue tableau | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-12 | Créer la vue Kanban | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-13 | Créer les filtres | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-14 | Créer la fiche candidature | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-15 | Ajouter les statistiques | P1 | BACKLOG | à estimer |

### [➖] FEATURE 014.4 — Préparation de candidature

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-014-16 | Créer un dossier de candidature | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-17 | Vérifier les documents | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-18 | Ajouter le lien vers l'annonce originale | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-19 | Ajouter l'action d'ouverture du site de candidature | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-20 | Ajouter la confirmation manuelle d'envoi | P1 | BACKLOG | à estimer |

### [➖] FEATURE 014.5 — Dashboard

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-014-21 | Créer le Dashboard | P1 | BACKLOG | à estimer |
| [➖] | TASK-014-22 | Calculer le taux de réponse sur données réelles | P1 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Historique fiable.
- [➖] Statuts modifiables.
- [➖] Documents associés.
- [➖] Candidatures filtrables.
- [➖] Envoi externe toujours contrôlé par l'utilisateur.

## [➖] EPIC 015 — SCHEDULER, AUTOMATION & NOTIFICATIONS

- **Priorité :** P1
- **Objectif :** automatiser les recherches et les rappels.
- **Dépendances :** EPIC 008, EPIC 009, EPIC 010

### [➖] FEATURE 015.1 — Scheduler

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-015-01 | Définir les tâches planifiées | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-02 | Ajouter les recherches récurrentes | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-03 | Ajouter les fuseaux horaires | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-04 | Ajouter les règles de fréquence | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-05 | Empêcher les exécutions concurrentes inutiles | P1 | BACKLOG | à estimer |

### [➖] FEATURE 015.2 — Orchestration

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-015-06 | Gérer les tâches asynchrones | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-07 | Gérer les reprises | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-08 | Gérer les tâches échouées | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-09 | Ajouter une file de tâches | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-10 | Ajouter un historique d'exécution | P1 | BACKLOG | à estimer |

### [➖] FEATURE 015.3 — Notifications

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-015-11 | Créer le centre de notifications | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-12 | Notifier les nouvelles offres | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-13 | Notifier les offres pertinentes | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-14 | Notifier les erreurs de recherche | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-15 | Ajouter les rappels de candidature | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-16 | Ajouter les alertes budget IA | P1 | BACKLOG | à estimer |

### [➖] FEATURE 015.4 — Résumés

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-015-17 | Créer un résumé quotidien | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-18 | Ajouter les préférences de notification | P1 | BACKLOG | à estimer |
| [➖] | TASK-015-19 | Ajouter les notifications e-mail si configurées | P1 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Tâches planifiées fiables.
- [➖] Pas de doublons d'exécution.
- [➖] Erreurs traçables.
- [➖] Notifications contrôlables.
- [➖] Aucun e-mail externe sans configuration et consentement.

## [➖] EPIC 016 — INTERVIEW PREPARATION & CAREER ASSISTANT

- **Priorité :** P2
- **Objectif :** accompagner le candidat après l'envoi de ses candidatures.
- **Dépendances :** EPIC 014

### [➖] FEATURE 016.1 — Préparation personnalisée

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-016-01 | Analyser l'offre et le CV envoyé | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-02 | Générer des questions RH | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-03 | Générer des questions techniques | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-04 | Préparer une présentation personnelle | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-05 | Proposer des réponses structurées | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-06 | Préparer des questions pour le recruteur | P2 | BACKLOG | à estimer |

### [➖] FEATURE 016.2 — Simulation

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-016-07 | Créer le moteur de simulation | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-08 | Ajouter les réponses utilisateur | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-09 | Fournir des retours | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-10 | Sauvegarder les simulations | P2 | BACKLOG | à estimer |

### [➖] FEATURE 016.3 — Suivi des entretiens

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-016-11 | Créer une fiche entretien | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-12 | Enregistrer les dates | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-13 | Enregistrer les retours | P2 | BACKLOG | à estimer |
| [➖] | TASK-016-14 | Préparer les relances post-entretien | P2 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Questions adaptées au poste.
- [➖] Réponses basées sur le vrai parcours.
- [➖] Utilisation IA à la demande.
- [➖] Historique conservé.

## [➖] EPIC 017 — INTERNATIONALIZATION & GLOBAL JOB SEARCH

- **Priorité :** P1
- **Objectif :** permettre des recherches adaptées aux marchés de l'emploi du monde entier.
- **Dépendances :** EPIC 006, EPIC 007, EPIC 008

### [➖] FEATURE 017.1 — Internationalisation de l'application

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-017-01 | Définir les langues de l'interface | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-02 | Ajouter les traductions | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-03 | Gérer les formats de date | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-04 | Gérer les devises | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-05 | Gérer les fuseaux horaires | P1 | BACKLOG | à estimer |

### [➖] FEATURE 017.2 — Référentiel géographique

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-017-06 | Définir Country Entity | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-07 | Gérer les codes ISO | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-08 | Gérer les villes et régions | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-09 | Gérer les langues officielles | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-10 | Gérer les devises | P1 | BACKLOG | à estimer |

### [➖] FEATURE 017.3 — Recherche internationale

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-017-11 | Implémenter les filtres par pays | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-12 | Gérer les intitulés de postes multilingues | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-13 | Gérer les compétences multilingues | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-14 | Gérer les sources par pays | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-15 | Gérer les recherches multi-pays | P1 | BACKLOG | à estimer |

### [➖] FEATURE 017.4 — Mobilité internationale

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-017-16 | Ajouter les préférences de mobilité | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-17 | Ajouter les exigences de permis de travail lorsqu'elles sont disponibles | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-18 | Identifier les annonces mentionnant le sponsoring | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-19 | Afficher les limites et informations manquantes | P1 | BACKLOG | à estimer |

### [➖] FEATURE 017.5 — Connecteurs internationaux

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-017-20 | Étudier EURES | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-21 | Intégrer une première source européenne réelle | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-22 | Étudier une source nord-américaine | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-23 | Ajouter progressivement les autres fournisseurs | P1 | BACKLOG | à estimer |
| [➖] | TASK-017-24 | Créer la page Paramètres généraux | P1 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Recherche par pays.
- [➖] Gestion multidevise.
- [➖] Gestion multilingue.
- [➖] Sources documentées.
- [➖] Connecteurs testés.
- [➖] Couverture géographique explicitement affichée.

## [➖] EPIC 018 — SECURITY, PRIVACY & OPERATIONAL EXCELLENCE

- **Priorité :** P0
- **Objectif :** sécuriser l'application dès sa conception et garantir son fonctionnement durable.
- **Dépendances :** EPIC 002

### [➖] FEATURE 018.1 — Sécurité applicative

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-018-01 | Définir le modèle de menaces | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-02 | Sécuriser les API | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-03 | Valider toutes les entrées | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-04 | Configurer les permissions | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-05 | Protéger les secrets | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-06 | Configurer les limites de requêtes | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-07 | Protéger contre SSRF | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-08 | Protéger contre les injections | P0 | BACKLOG | à estimer |

### [➖] FEATURE 018.2 — Sécurité IA

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-018-09 | Définir les frontières de confiance | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-10 | Protéger contre prompt injection | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-11 | Séparer instructions et données externes | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-12 | Limiter les données envoyées aux fournisseurs | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-13 | Valider les réponses structurées | P0 | BACKLOG | à estimer |

### [➖] FEATURE 018.3 — Sécurité documentaire

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-018-14 | Isoler les fichiers importés | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-15 | Sécuriser la compilation LaTeX | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-16 | Contrôler les fichiers générés | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-17 | Définir les limites de ressources | P0 | BACKLOG | à estimer |

### [➖] FEATURE 018.4 — RGPD et confidentialité

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-018-18 | Définir la politique de conservation | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-19 | Ajouter l'export des données | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-20 | Ajouter la suppression des données | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-21 | Documenter les transferts vers les fournisseurs IA | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-22 | Ajouter les paramètres de confidentialité | P0 | BACKLOG | à estimer |

### [➖] FEATURE 018.5 — Observabilité

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-018-23 | Créer les logs structurés | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-24 | Ajouter les identifiants de corrélation | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-25 | Ajouter les health checks | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-26 | Mesurer les performances | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-27 | Ajouter le tableau de santé | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-28 | Ajouter le monitoring des tâches | P0 | BACKLOG | à estimer |

### [➖] FEATURE 018.6 — Résilience

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-018-29 | Tester les interruptions | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-30 | Tester la restauration | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-31 | Tester les défaillances de fournisseurs | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-32 | Documenter les procédures de récupération | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-33 | Protéger l'accès réseau en mode local et configurer un CORS restrictif | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-34 | Gérer la rotation des clés et le masquage des secrets dans l'interface | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-35 | Intégrer l'authentification (différée, ADR-0008) | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-36 | Passer au multi-utilisateur | P0 | BACKLOG | à estimer |
| [➖] | TASK-018-37 | Documenter et vérifier le mode local sans authentification | P0 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Modèle de menaces documenté.
- [➖] Secrets protégés.
- [➖] Documents isolés.
- [➖] Compilation sécurisée.
- [➖] Données personnelles contrôlables.
- [➖] Logs non sensibles.
- [➖] Procédures de restauration testées.

## [➖] EPIC 019 — QA, RELEASE & PRODUCTION READINESS

- **Priorité :** P0
- **Objectif :** garantir que le produit est réellement utilisable, maintenable et livrable.
- **Dépendances :** EPIC 002

### [➖] FEATURE 019.1 — Tests backend

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-019-01 | Tests unitaires du domaine | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-02 | Tests des use cases | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-03 | Tests des repositories | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-04 | Tests des connecteurs | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-05 | Tests des tâches asynchrones | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-06 | Tests de sécurité | P0 | BACKLOG | à estimer |

### [➖] FEATURE 019.2 — Tests frontend

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-019-07 | Tests des composants | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-08 | Tests des formulaires | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-09 | Tests de navigation | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-10 | Tests responsive | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-11 | Tests des états d'erreur | P0 | BACKLOG | à estimer |

### [➖] FEATURE 019.3 — Tests E2E

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-019-12 | Parcours de recherche | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-13 | Parcours d'import du CV | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-14 | Parcours de génération du CV | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-15 | Parcours de génération de lettre | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-16 | Parcours de candidature | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-17 | Parcours de gestion du budget IA | P0 | BACKLOG | à estimer |

### [➖] FEATURE 019.4 — Performance

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-019-18 | Mesurer les temps de réponse | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-19 | Analyser les requêtes SQL | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-20 | Tester la pagination | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-21 | Tester les volumes d'offres | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-22 | Tester les tâches concurrentes | P0 | BACKLOG | à estimer |

### [➖] FEATURE 019.5 — Documentation et livraison

| Statut | ID | Titre | Priorité | État | Estimation |
|---|---|---|---|---|---|
| [➖] | TASK-019-23 | Finaliser README | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-24 | Finaliser le guide utilisateur | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-25 | Finaliser le guide d'installation | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-26 | Finaliser le guide de sauvegarde | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-27 | Finaliser les ADR | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-28 | Créer le rapport de qualité | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-29 | Préparer la version stable | P0 | BACKLOG | à estimer |
| [➖] | TASK-019-30 | Produire les documents obligatoires de la spécification (§22) | P0 | BACKLOG | à estimer |

**Critères d'acceptation de l'EPIC**

- [➖] Tests critiques exécutés.
- [➖] Aucun défaut bloquant connu.
- [➖] Installation reproductible.
- [➖] Documentation à jour.
- [➖] Sauvegarde et restauration testées.
- [➖] Parcours métier principaux opérationnels.
- [➖] Limites restantes clairement documentées.

