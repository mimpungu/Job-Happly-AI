# Procédures de récupération

Chaque procédure indique le test qui garantit le comportement décrit.

| Situation | Symptôme | Action | Vérifié par |
|---|---|---|---|
| Base injoignable | `/health/ready` → 503, routes métier en erreur normalisée | Vérifier `docker compose ps`, relancer `postgres` ; l'API n'a pas à être redémarrée (`/health` reste 200) | `test_resilience.py` |
| Tâche de fond interrompue (arrêt brutal) | Tâche « bloquée » dans la santé | Redémarrer le worker : les tâches orphelines sont reprises après expiration du verrou, la dernière tentative les déclare « abandonnées » | `test_job_queue.py` |
| Source d'offres en panne | Source « en erreur » (état dégradé) | Aucune action requise : les autres sources continuent ; la source est réessayée avec backoff | `test_collection.py`, `tests/unit/job_discovery/test_resilience.py` |
| Fournisseur d'IA en panne / plafond atteint | Statut « IA indisponible » dans l'interface | Aucune : le résultat de base (niveau 0) est livré ; vérifier le Centre IA | `test_ai_gateway.py`, `test_resume_rewrite.py` |
| pdfLaTeX absent | Composant `latex` dégradé | Installer TeX Live ou définir `HAPPLY_PDFLATEX_PATH` | `test_api_health.py` |
| Disque presque plein | Stockage dégradé (< 200 Mo) | Purger (Paramètres → Conservation), supprimer d'anciens documents, élargir le disque | `test_api_health.py` |
| Corruption ou perte de la base | Données absentes | Restaurer la dernière sauvegarde (ci-dessous) | `test_resilience.py` |
| Mauvaise manipulation | Données supprimées par erreur | Restaurer la sauvegarde ; l'effacement dans l'application est **irréversible** | — |

## Restaurer une sauvegarde

Voir `BACKUP_RESTORE.md`. Principe : toujours restaurer dans une base **explicite** (jamais
implicite), après vérification de la somme de contrôle, puis restaurer `storage/` avec la base,
puis appliquer les migrations.

Test automatisé (`test_une_sauvegarde_se_restaure_dans_une_base_distincte_avec_ses_donnees`) :
migrations, insertion de données, `pg_dump`, `pg_restore` vers une autre base, comparaison des
données et de la révision de schéma, détection d'un fichier altéré. Il est exécuté à chaque CI.

## À faire régulièrement

- Une sauvegarde avant chaque migration et au moins hebdomadaire, **copiée hors de la machine**.
- Une restauration d'essai vers une base temporaire après un changement de version majeure de
  PostgreSQL.
