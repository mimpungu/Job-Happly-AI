# Definition of Done

Une tâche passe à `[✅]` (état `DONE`) uniquement si **tout** est vrai :

- Le code est implémenté et respecte l'architecture (`docs/architecture/ARCHITECTURE.md`) et les conventions (`DEVELOPMENT_GUIDELINES.md`).
- Les critères d'acceptation sont vérifiés.
- Les tests pertinents existent **et ont été exécutés avec succès**.
- Lint, formatage et typage passent ; le build passe.
- Les erreurs et cas limites sont gérés ; aucune exception avalée.
- Aucune régression connue ; aucun test supprimé ou affaibli.
- Contrôle de sécurité effectué pour les fonctionnalités sensibles.
- La documentation et le backlog sont à jour (registre `docs/product/PROJECT_BACKLOG.md` régénéré).
- Les limites restantes sont signalées.

Sinon la tâche reste `[➖]` avec l'état adapté : `IN_PROGRESS`, `IN_REVIEW`, `TESTING` ou `BLOCKED` (avec la dépendance qui bloque).

## Definition of Ready

Objectif clair, périmètre défini, dépendances satisfaites, critères d'acceptation écrits, contrats nécessaires existants, fichiers concernés identifiés, risques connus, stratégie de test définie, **estimation posée**.
