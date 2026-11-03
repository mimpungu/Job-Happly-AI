# ADR-0008 — Authentification différée, exécution locale

- **Statut :** Accepté
- **Date :** 2026-11-03

## Contexte

Pour l'instant l'application est utilisée uniquement en local par son propriétaire. Un partage ou un hébergement distant est prévu plus tard.

## Décision

1. **Pas d'authentification au départ.** Application mono-utilisateur, exécutée en local.
2. **Compensations obligatoires** tant qu'il n'y a pas d'authentification :
   - API et frontend liés à `127.0.0.1` uniquement, jamais exposés sur le réseau (`0.0.0.0` interdit en configuration par défaut).
   - CORS restrictif (origine du frontend local uniquement).
   - Docker Compose : ports publiés sur `127.0.0.1`.
   - Documentation claire : ne pas exposer l'application sur Internet ni sur un réseau partagé sans authentification.
3. **Préparer l'arrivée de l'authentification sans réécriture** :
   - Toutes les entités appartenant à l'utilisateur portent un `owner_id`, relié à un utilisateur local unique créé au démarrage.
   - Les accès aux données passent par des use cases qui reçoivent un contexte utilisateur (même s'il est unique pour l'instant).
   - Les secrets (clés API IA) sont rattachés à ce contexte, pas codés globalement.
4. **Authentification complète planifiée** dans l'EPIC 018 : comptes, sessions sécurisées, autorisations par ressource, protection CSRF, limitation des tentatives, avant tout accès distant.

## Conséquences

- Le passage au multi-utilisateur est une migration, pas une refonte.
- Le coût : `owner_id` partout dès maintenant, et un contexte utilisateur dans les use cases.
- Risque accepté et documenté : toute personne ayant accès à la machine accède aux données.
