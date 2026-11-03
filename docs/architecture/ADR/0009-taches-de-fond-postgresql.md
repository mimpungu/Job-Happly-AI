# ADR-0009 — Tâches de fond adossées à PostgreSQL

- **Statut :** Proposé
- **Date :** 2026-11-03

## Contexte

Recherches longues, ingestion, analyses IA, compilations PDF et recherches planifiées doivent être asynchrones, reprenables, dédupliquées et observables. La spec n'autorise Redis/Celery que si leur nécessité est démontrée.

## Décision

- Table de jobs dans PostgreSQL (statut, tentatives, prochaine exécution, clé d'idempotence, erreur, horodatages).
- Un processus `worker` séparé réserve les jobs avec `SELECT … FOR UPDATE SKIP LOCKED`, avec retry et backoff.
- Contrainte d'unicité sur la clé d'idempotence pour empêcher deux exécutions identiques simultanées.
- Planification des recherches récurrentes par le worker (fuseau horaire explicite).
- Reprise après interruption : les jobs « en cours » dont le verrou a expiré sont repris.

## Alternatives étudiées

- Redis + Celery : plus de services à exploiter, cohérence entre deux stockages à gérer.
- Tâches en mémoire dans l'API : perdues au redémarrage, non observables.

## Conséquences

- Un seul stockage à sauvegarder et superviser.
- Débit limité par PostgreSQL : largement suffisant pour l'usage prévu ; migration vers Redis possible derrière une interface `JobQueue`.
