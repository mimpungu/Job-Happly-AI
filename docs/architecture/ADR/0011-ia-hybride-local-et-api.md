# ADR-0011 — IA hybride : modèle local et API payante derrière la même interface

- **Statut :** Accepté (aucun fournisseur concret choisi)
- **Date :** 2026-11-04
- **Complète :** ADR-0005

## Contexte

L'utilisateur veut les deux versions : une IA locale (gratuite, données sur sa machine) et une API payante (plus performante), utilisables ensemble.

## Décision

1. Un seul contrat `AIProvider` couvre les deux. Chaque fournisseur déclare son genre (`api` ou `local`), ses modèles avec leur tarif (nul en local), les tâches qu'il sait traiter (`supports`) et son modèle par niveau et par mode.
2. Une préférence utilisateur choisit : `local_only`, `api_only` ou `hybrid`. En hybride, **le local passe toujours avant l'API** ; si le local ne sait pas faire la tâche ou échoue, l'API prend le relais.
3. Les garde-fous de l'ADR-0005 (plafonds définis, contrôle du coût estimé avant l'appel, consentement) s'appliquent **à toute route payante, y compris en repli**. Une route locale ne coûte rien et ne fait rien sortir de la machine : ni plafond ni consentement requis.
4. Toute entrée passe par `AIGateway` : cache, contrôle, appel avec délai maximal, validation stricte de la sortie, journal de chaque tentative (réussie, refusée, en échec, servie par le cache).
5. Aucun fournisseur réel n'est branché par cette décision. L'API payante exige son propre ADR ; le moteur local (quel runtime, quels modèles) aussi.

## Conséquences

- Tant qu'aucun fournisseur n'est enregistré, l'application fonctionne entièrement sans IA (niveau 0).
- Le verrou qui empêche deux appels simultanés de dépasser ensemble le plafond est interne au processus : suffisant en local mono-processus, à remplacer par un verrou en base si le déploiement change.
- Un appel interrompu par un délai dépassé n'est pas compté comme dépensé, alors que le fournisseur peut l'avoir facturé : limite documentée.
