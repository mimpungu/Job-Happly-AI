# Observabilité

Sans dépendance externe, adaptée à une application locale mono-processus.

## Logs structurés (TASK-018-23)

Une ligne JSON par événement sur la sortie standard : `ts` (UTC), `level`, `logger`, `message`,
`request_id` et champs utiles. Le niveau se règle par `HAPPLY_LOG_LEVEL`.

- Message, champs texte et exceptions sont **masqués** (clés, jetons, mots de passe, identifiants
  d'URL, e-mails). Les exceptions ne journalisent que leur type et leur message masqué.
- Le journal d'accès n'enregistre ni corps de requête, ni query string, ni CV : seulement
  méthode, **modèle de route**, statut et durée.

## Corrélation (TASK-018-24)

Chaque requête reçoit un `X-Request-ID` (repris du client s'il est sûr, sinon généré) renvoyé dans
la réponse et présent dans tous les logs de la requête. Pour suivre un incident : demander
l'identifiant affiché par le navigateur (en-tête de réponse) puis filtrer les logs dessus.

## Santé (TASK-018-25, 018-27)

| Route | Usage |
|---|---|
| `GET /api/v1/health` | Vivacité : le processus répond (sans base) |
| `GET /api/v1/health/ready` | Prêt : base et stockage ; **503** sinon |
| `GET /api/v1/health/details` | Tableau de santé : base, stockage, LaTeX, IA, sources, tâches |
| `GET /api/v1/health/metrics` | Durées et volumes par route |

États : `ok`, `degraded`, `down`, `not_configured`. Un composant facultatif absent (IA, source) est
`not_configured` et **ne dégrade jamais** l'ensemble ; une panne de base ou de stockage donne
`down`. Les messages ne contiennent aucun détail technique (jamais l'URL de connexion).

Le tableau de santé est affiché dans **Paramètres → Santé de l'application**, actualisé toutes les
30 secondes.

## Performances (TASK-018-26)

Par route (modèle d'URL) : nombre d'appels, erreurs 5xx, durée moyenne, p50 et p95 sur les 500
dernières mesures. Stockées **en mémoire** : elles repartent à zéro au redémarrage (assumé).
Au plus 300 routes distinctes suivies (borne mémoire).

## Monitoring des tâches (TASK-018-28)

Le composant `tasks` signale : tâches planifiées en retard (> 15 min), tâches de fond bloquées
(verrou > 30 min) et tâches abandonnées après échecs répétés. L'historique détaillé reste dans
`GET /api/v1/scheduler/jobs/history` (EPIC 015).

## Limites de requêtes (TASK-018-06)

600 requêtes/minute par client, 30/minute pour les écritures coûteuses (IA, génération, import,
collecte, préparation d'entretien) ; au-delà : `429` + `Retry-After`. Taille annoncée maximale :
12 Mo (`413`). Réglables : `HAPPLY_RATE_LIMIT_PER_MINUTE`,
`HAPPLY_RATE_LIMIT_EXPENSIVE_PER_MINUTE`, `HAPPLY_MAX_REQUEST_BODY_MB`.

## En-têtes de sécurité

Toutes les réponses : `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'; frame-ancestors
'none'` (assouplie pour les PDF affichés), `Cache-Control: no-store`, `Permissions-Policy`,
`Cross-Origin-Resource-Policy: same-site`.
