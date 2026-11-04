# Secrets : protection et rotation

## Règles

- Aucun secret dans le code, l'historique Git ni les journaux. Les clés vivent dans `.env`
  (ignoré par Git, vérifié par `test_local_mode.py`) ou dans les variables d'environnement.
- `.env.example` ne contient aucune vraie valeur (vérifié par test).
- Tous les secrets de configuration sont des `SecretStr` : ils n'apparaissent ni dans `repr()` ni
  dans `model_dump()` (vérifié par `test_security_surface.py`).
- Les journaux masquent clés d'API, jetons, mots de passe, identifiants d'URL et adresses e-mail
  (`app/core/observability/redaction.py`).
- L'interface ne reçoit **jamais** une clé : elle reçoit seulement un indice masqué (`…ghij`, les
  quatre derniers caractères, uniquement pour une clé d'au moins 12 caractères).
- Les clés ne sont pas stockées en base : exporter ses données n'exporte aucun secret.

## Rotation d'une clé (ex. Gemini)

1. Créer une nouvelle clé chez le fournisseur ; **ne pas** supprimer l'ancienne tout de suite.
2. Remplacer `HAPPLY_GEMINI_API_KEY` dans `.env`.
3. Redémarrer l'API : `docker compose up -d api` (ou `./infrastructure/scripts/start.sh`).
4. Ouvrir le **Centre IA** : l'indice affiché (`clé …xxxx`) doit correspondre à la nouvelle clé.
5. Lancer le test du fournisseur (bouton de test du Centre IA) pour valider l'accès.
6. Révoquer l'ancienne clé chez le fournisseur.

Fréquence recommandée : à chaque suspicion de fuite, et au moins une fois par an.

## En cas de fuite suspectée

Révoquer immédiatement la clé chez le fournisseur, puis suivre la rotation ci-dessus. Si la clé a
pu être commitée : la considérer comme compromise même après suppression du commit (l'historique
reste consultable) ; ne jamais se contenter de réécrire l'historique.
