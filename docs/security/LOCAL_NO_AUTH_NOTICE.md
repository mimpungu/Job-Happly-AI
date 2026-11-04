# Mode local sans authentification

Tant que l'authentification n'est pas intégrée (ADR-0008) :

- Lier l'API et le frontend à `127.0.0.1` uniquement.
- Ne jamais exposer l'application sur Internet, un réseau partagé, un tunnel public ou un hébergement distant.
- CORS limité à l'origine du frontend local.
- Ports Docker publiés sur `127.0.0.1`.
- Toute personne ayant accès à la machine accède aux données (CV, candidatures, clés).

Avant tout partage ou hébergement : implémenter l'authentification complète (EPIC 018, TASK-018-35 à 018-36).

## Ce qui est vérifié (et non seulement recommandé)

Les tests `tests/architecture/test_local_mode.py` échouent si :

- un port Docker est publié ailleurs que sur `127.0.0.1` ;
- l'API n'écoute plus par défaut sur `127.0.0.1` ou si le CORS par défaut s'élargit ; l'origine
  générique `*` est refusée à la configuration ;
- un modèle « local » (Ollama) pointe vers une adresse non locale ;
- la production démarre sans base ou avec le mot de passe d'exemple ;
- un fichier `.env`, une clé ou un certificat est suivi par Git.

Autorisations par ressource : chaque donnée porte un `owner_id` et l'isolation est testée
(`test_owner_isolation.py`) ; elle prépare le passage au multi-utilisateur mais ne remplace pas
l'authentification.

## Pourquoi l'authentification reste différée

TASK-018-35 (comptes, sessions, mots de passe hachés, limitation des tentatives, CSRF) et
TASK-018-36 (multi-utilisateur) sont volontairement **non réalisées** : l'application est locale et
mono-utilisateur (ADR-0008). Elles deviennent bloquantes dès qu'un accès distant, un partage ou un
hébergement est envisagé.
