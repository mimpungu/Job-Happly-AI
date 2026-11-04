# Politique de sécurité

La politique complète, le modèle de menaces et les contrôles automatiques sont dans [`docs/security/SECURITY.md`](docs/security/SECURITY.md).

## Signaler une vulnérabilité

Ouvrez un signalement **privé** sur le dépôt GitHub (onglet *Security* → *Report a vulnerability*) ou contactez directement le propriétaire. Ne publiez jamais de détail exploitable dans une issue publique, ni de secret réel.

## Périmètre

Application **locale, sans authentification** (ADR-0008) : ne pas l'exposer sur un réseau. Les versions prises en charge sont celles de la branche `dev` / `master` courantes.
