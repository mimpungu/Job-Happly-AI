# Mode local sans authentification

Tant que l'authentification n'est pas intégrée (ADR-0008) :

- Lier l'API et le frontend à `127.0.0.1` uniquement.
- Ne jamais exposer l'application sur Internet, un réseau partagé, un tunnel public ou un hébergement distant.
- CORS limité à l'origine du frontend local.
- Ports Docker publiés sur `127.0.0.1`.
- Toute personne ayant accès à la machine accède aux données (CV, candidatures, clés).

Avant tout partage ou hébergement : implémenter l'authentification complète (EPIC 018, TASK-018-35 à 018-36).
