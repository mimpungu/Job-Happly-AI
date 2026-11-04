# Contribuer à Happly AI

Lire d'abord `CLAUDE.md` (règles du propriétaire), `docs/AI_DEVELOPMENT_RULES.md` et `docs/architecture/ARCHITECTURE.md`.

## Principes

- **Clean Architecture** : `domain` → `application` → `infrastructure` / `presentation`. Le domaine ne dépend d'aucun framework. Pas de logique métier dans les routes ni les composants React.
- **Aucun fait inventé** (CV, lettres, entretiens, IA) ; **aucune action externe automatique** (envoi de candidature, message) ; **aucun secret** dans le code ou Git.
- Commentaires, docstrings, commits et documentation en **français** ; identifiants de code en **anglais**.
- Un changement cohérent par commit, tests et documentation dans le même changement.

## Environnement

`docs/INSTALL.md`. PostgreSQL de test : `HAPPLY_TEST_DATABASE_URL` (le nom de la base doit finir par `_test`).

## Avant de proposer un changement

Backend (`backend/`) :

```bash
uv run ruff format --check . && uv run ruff check . && uv run mypy
HAPPLY_TEST_DATABASE_URL=postgresql://… HAPPLY_REQUIRE_PDFLATEX=1 uv run pytest
```

Frontend (`frontend/`) :

```bash
pnpm format:check && pnpm lint && pnpm typecheck && pnpm test && pnpm build
pnpm e2e              # accessibilité (API simulée)
pnpm e2e:fullstack    # parcours complets (vraie pile), avant une release
```

## Tests

- Un bug corrigé commence par un test qui le reproduit. Ne jamais supprimer, désactiver ou affaiblir un test pour faire passer un build.
- Pas de réseau réel dans les tests ; les appels IA passent par de faux fournisseurs identifiés comme tels.
- Structure Arrange / Act / Assert, tests déterministes et indépendants.
- Les garde-fous d'architecture (`backend/tests/architecture`, `tests/unit/core`, `tests/unit/privacy`) échouent si vous ajoutez une connexion sortante, un processus, un SQL assemblé, une table de données sans catégorie RGPD, un appel IA non documenté ou une entrée non bornée : mettez à jour le catalogue concerné **après revue**, avec une justification.

## Base de données

Migrations Alembic versionnées, additives et réversibles quand c'est possible (`uv run alembic revision --autogenerate`, puis relire). Jamais de modification manuelle du schéma. Les contraintes `CHECK` ne sont pas détectées par l'autogénération : les écrire à la main.

## Design

Design system sombre et clair par **tokens** (aucune couleur ou espacement en dur dans un composant) ; pas de dégradé hors la dérogation du graphique d'entonnoir (ADR-0017). Accessibilité vérifiée par axe (deux thèmes, trois tailles).

## Documentation et décisions

Toute décision structurante : un ADR dans `docs/architecture/ADR/` (modèle `TEMPLATE.md`, index à jour). Backlog : `[✅]` seulement si les tests ont réellement été exécutés et ont réussi.

## Commits

Conventional Commits en français (`feat(portée): description à l'impératif`), corps expliquant le **pourquoi**. Changement cassant : `!` et paragraphe `BREAKING CHANGE:`.
