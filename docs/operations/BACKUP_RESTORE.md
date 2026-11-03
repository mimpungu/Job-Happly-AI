# Sauvegarde et restauration

## Ce qui est sauvegardé

| Élément | Contenu | Où |
|---|---|---|
| Base PostgreSQL | Toutes les données | `backups/happly-AAAAMMJJ-HHMMSS.dump` (format custom) + `.sha256` |
| Fichiers | CV importés, PDF et LaTeX générés | `backups/storage-AAAAMMJJ-HHMMSS.tar.gz` |

Base et fichiers doivent être sauvegardés **ensemble** et restaurés ensemble (ADR-0007). Le dossier `backups/` est ignoré par Git.

## Sauvegarder

```bash
./infrastructure/scripts/backup.sh                 # dans backups/
./infrastructure/scripts/backup.sh /autre/dossier
```

Le script lit `.env`, vérifie que la sauvegarde n'est pas vide et écrit une somme de contrôle. Il ne modifie jamais les données.

## Restaurer

```bash
./infrastructure/scripts/restore.sh backups/happly-XXXX.dump <base-cible> --yes
```

- La **base cible est toujours explicite** et **remplacée** : aucune cible implicite, et `--yes` est obligatoire.
- La somme de contrôle est vérifiée avant toute écriture ; un fichier altéré annule la restauration.
- Pour valider une sauvegarde sans risque, restaurer vers une base temporaire (ex. `happly_verification`), puis comparer.
- Restaurer ensuite `storage/` : `tar -xzf backups/storage-XXXX.tar.gz`.
- Après restauration, appliquer d'éventuelles migrations : `./infrastructure/scripts/migrate.sh`.

## Rétention des sauvegardes

```bash
./infrastructure/scripts/prune-backups.sh backups 14   # conserve les 14 plus récentes
```

Recommandation initiale : une sauvegarde avant toute migration et au moins une par semaine. Garder aussi une copie **hors de la machine** : une sauvegarde sur le même disque ne protège pas d'une panne du disque.

## Vérifié

Test manuel de bout en bout sur la base de test : sauvegarde, refus sans `--yes`, restauration dans une base distincte (26 tables et la donnée de test retrouvées), refus d'un fichier altéré, rétention. Une restauration planifiée régulière reste à instaurer (EPIC 018, TASK-018-30).

## Limites connues

- Pas de sauvegarde automatique planifiée (EPIC 015).
- Pas de chiffrement des sauvegardes : elles contiennent des données personnelles, les stocker sur un support protégé.
