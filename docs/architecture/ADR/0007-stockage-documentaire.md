# ADR-0007 — Stockage documentaire

- **Statut :** Accepté
- **Date :** 2026-11-03

## Décision

- Les fichiers (CV importés, PDF et LaTeX générés) sont stockés sur le **système de fichiers local**, dans `storage/`, hors du dossier versionné (`.gitignore`). Les métadonnées (nom d'origine, type MIME, empreinte, taille, version, offre associée) sont en base.
- Noms de fichiers **générés** (UUID), jamais le nom fourni par l'utilisateur. Protection contre la traversée de chemin, limites de taille, contrôle MIME réel.
- Accès aux fichiers via une interface `DocumentStorage` : un stockage objet (S3 compatible) pourra remplacer le disque sans toucher au métier.
- Compilation LaTeX dans un conteneur isolé, réseau désactivé, limites CPU/mémoire/temps, dossier temporaire dédié.
- Le CV maître n'est jamais écrasé par une version adaptée ; les versions sont immuables.

## Conséquences

- Sauvegarde : base et `storage/` doivent être sauvegardés ensemble.
- Politique de rétention et suppression à définir (RGPD, EPIC 018).
