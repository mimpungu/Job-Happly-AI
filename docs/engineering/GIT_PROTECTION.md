# Protection Git (TASK-002-09)

| Contrôle | Où | État |
|---|---|---|
| Secrets : analyse de l'historique et des commits | CI (job `secrets`, gitleaks) et hook pre-commit | **En place** |
| Dépendances vulnérables | CI : `pip-audit` (Python, versions verrouillées) et `pnpm audit --prod` ; Dependabot hebdomadaire (`.github/dependabot.yml`) | **En place** |
| Protection des branches principales | Réglage GitHub du dépôt | **À faire par le propriétaire** (non vérifiable depuis le code) |

## Réglage à effectuer sur GitHub (une fois)

*Settings → Branches → Add branch ruleset* pour `master` (et `dev` si souhaité) :

1. Exiger une *pull request* avant fusion (au moins 0 approbation si vous travaillez seul).
2. Exiger que les vérifications **`backend`**, **`frontend`** et **`secrets`** (workflow CI) passent.
3. Interdire le *force push* et la suppression de la branche.
4. Exiger que la branche soit à jour avant fusion.

*Settings → Code security* : activer **Dependabot alerts** et **Dependabot security updates**, ainsi que **Secret scanning** et **Push protection**.

## Vulnérabilités connues

- `minimatch` < 11.0.1 (déni de service, gravité modérée) : présent **uniquement** via ESLint (outillage de développement, jamais livré). Suivi par Dependabot ; sans effet sur l'application en production.
