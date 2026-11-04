# ADR-0016 — Planification, automatisation des recherches et centre de notifications

- **Statut :** Accepté
- **Date :** 2026-11-04

## Contexte

L'EPIC 015 a pour objectif d'automatiser les recherches d'offres récurrentes, d'orchestrer les tâches asynchrones en arrière-plan, de centraliser les notifications et de fournir des résumés synthétiques quotidiens, conformément à la spécification `docs/HAPPLY_AI_MASTER_SPEC.md` §13.
Les exigences majeures sont :
1. **Planification fiable et multi-fuseaux** : Calcul déterministe des prochaines exécutions selon des fréquences prédéfinies (`hourly`, `every_6_hours`, `daily`, `interval_minutes`) avec prise en compte stricte des fuseaux horaires via `zoneinfo.ZoneInfo`.
2. **Prévention absolue des doublons et exécutions concurrentes inutiles** : Exploitation des verrous logiques et des clés d'idempotence uniques adossées à la contrainte `uq_jobs_kind_idempotency_key_active` de la table `jobs` (PostgreSQL / ADR-0009).
3. **Orchestration résiliente et traçable** : Mécanismes de retry avec backoff exponentiel, reprise des tâches orphelines périmées (`recover_stale`), et transition vers l'état `DEAD` sans suppression silencieuse en cas d'épuisement des tentatives.
4. **Notifications maîtrisées** : Centre de notifications in-app (non-lues/lues, suppression, alertes ciblées sur nouvelles offres, offres pertinentes selon seuil, alertes budget IA, erreurs de recherche, rappels de relances).
5. **Protection stricte de la confidentialité et canal e-mail conditionnel** : **Règle absolue : aucun e-mail externe n'est envoyé sans configuration explicite et sans consentement préalable vérifié (`email_consent_given=True`)**.
6. **Résumé quotidien (Daily Digest)** : Consolidation des activités sur 24 heures (nouvelles offres, relances dues, candidatures actives, budget IA).

## Décision

1. **Modèle de Domaine (`notifications.domain`)** :
   - Énumérations strictes : `NotificationKind` (`new_offers`, `relevant_match`, `search_error`, `follow_up_reminder`, `ai_budget_alert`, `daily_digest`), `ScheduleFrequency`, `ScheduledTaskType`.
   - Entités immuables : `Notification`, `NotificationPreferences`, `ScheduledTask`, `DailyDigestSummary`.
   - Logique pure de calcul temporel : `compute_next_run`, validation de fuseau horaire `get_zone_info`, filtrage d'éligibilité `should_notify`, et calcul de clé d'idempotence `build_idempotency_key`.

2. **Couche Applicative (`notifications.application`)** :
   - `NotificationService` : émet les notifications en respectant strictement les filtres et canaux choisis par l'utilisateur (in-app et/ou e-mail).
   - `SchedulerService` : planifie les tâches récurrentes, évalue les tâches échues (`enqueue_due_tasks`), et permet le déclenchement immédiat (`trigger_task_now`).
   - `DailyDigestService` : consolide les métriques sur les 24 dernières heures et génère le résumé quotidien structuré.
   - `AutomationJobHandlers` & `list_job_history` : exécute les tâches réservées (`recurring_search`, `follow_up_check`, `ai_budget_check`, `daily_digest`, `stale_jobs_cleanup`) et expose l'audit d'exécution des jobs.

3. **Infrastructure & Persistance (`notifications.infrastructure`)** :
   - Exploitation de la table existante `notifications` (`NotificationModel`).
   - Table `notification_preferences` pour les réglages utilisateur et table `scheduled_tasks` pour les planifications récurrentes (migration Alembic 0008).
   - Exploitation de la file PostgreSQL transactionnelle `PostgresJobQueue` (ADR-0009) avec `SELECT FOR UPDATE SKIP LOCKED`.
   - Adaptateur sécurisé `SafeEmailSender` bloquant immédiatement toute émission sans consentement ou sans configuration.

4. **API REST (`/api/v1/notifications` & `/api/v1/scheduler`)** :
   - Endpoints pour la consultation des notifications, compteurs de non-lues, marquage comme lue, préférences utilisateur.
   - Endpoints pour les tâches planifiées (CRUD, déclenchement manuel, balayage des échéances, audit historique des jobs, génération de résumé quotidien).

## Alternatives étudiées

- **Planification en mémoire (ex: APScheduler / asyncio.sleep)** : Rejetée car fragile aux redémarrages de l'API et incapable de persister les prochaines exécutions de manière observable et auditable.
- **Envoi systématique d'e-mails sans consentement** : Formellement interdit par les règles de sécurité et RGPD (GEMINI.md). L'envoi requiert obligatoirement une activation et un consentement explicite.

## Conséquences

- Les recherches et surveillances tournent automatiquement et régulièrement sans doublons.
- L'utilisateur est notifié opportunément des nouvelles opportunités et des relances de candidatures sans être spammé.
- L'orchestration repose sur le socle PostgreSQL existant sans dépendance externe superflue (Redis/Celery évités).

