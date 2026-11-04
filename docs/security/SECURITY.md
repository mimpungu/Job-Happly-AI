# Sécurité — Happly AI

Documents : [modèle de menaces](THREAT_MODEL.md) · [secrets](SECRETS.md) ·
[confidentialité et RGPD](PRIVACY.md) · [mode local sans authentification](LOCAL_NO_AUTH_NOTICE.md) ·
[observabilité](../operations/OBSERVABILITY.md) · [récupération](../operations/RECOVERY.md).

## Signaler une faille

Projet personnel : ouvrir un signalement privé sur le dépôt GitHub (« Security » → « Report a
vulnerability ») ou contacter le propriétaire. Ne jamais publier de détail exploitable dans une
issue publique, ni de secret réel.

## Principes

1. **Local d'abord** : liaison `127.0.0.1`, CORS restreint, aucune exposition distante tant que
   l'authentification n'est pas intégrée.
2. **Toute entrée est une donnée non fiable** : schémas bornés, fichiers contrôlés, annonces et
   documents jamais traités comme des instructions.
3. **Moindre donnée vers l'extérieur** : aucun appel IA ou réseau implicite ; chaque transfert est
   documenté, plafonné, journalisé, et soumis à la politique de confidentialité de l'utilisateur.
4. **Pas de secret en clair** : `SecretStr`, logs masqués, indice partiel en interface.
5. **Surface contrôlée par la CI** : une nouvelle connexion sortante, un nouveau processus, un SQL
   assemblé, un appel IA non documenté ou une table de données sans catégorie RGPD font échouer
   les tests.

## Ce qui est contrôlé automatiquement

| Contrôle | Test |
|---|---|
| Entrées bornées (schéma OpenAPI réel) | `tests/unit/core/test_input_validation.py` |
| Surface sortante, processus, SQL, secrets | `tests/architecture/test_security_surface.py` |
| Mode local (ports, CORS, `.env`) | `tests/architecture/test_local_mode.py` |
| Isolation entre propriétaires | `tests/integration/test_owner_isolation.py` |
| Frontière de confiance IA, politique de confidentialité | `test_framing.py`, `test_ai_gateway.py` |
| Export, effacement, conservation | `tests/integration/test_api_privacy.py` |
| Catalogue RGPD et transferts IA | `tests/unit/privacy/test_catalogues.py` |
| Logs structurés, masquage, limites, en-têtes | `tests/unit/core/test_observability.py` |
| Restauration, base injoignable | `tests/integration/test_resilience.py` |
| LaTeX isolé, fichiers importés | `test_latex_safety.py`, `test_latex_compiler.py`, tests du profil |

## Limites connues

Voir « Risques résiduels » du [modèle de menaces](THREAT_MODEL.md). La principale : **pas
d'authentification** (TASK-018-35 et 018-36 différées par ADR-0008), donc interdiction d'exposer
l'application sur un réseau.
