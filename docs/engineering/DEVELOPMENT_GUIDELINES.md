# Conventions de développement (TASK-001-07)

Complète `CLAUDE.md` et `docs/AI_DEVELOPMENT_RULES.md` (qui prévalent en cas de conflit).

## Nommage

| Élément | Convention |
|---|---|
| Code (variables, fonctions, classes, fichiers, routes, tables) | Anglais |
| Commentaires, docstrings, documentation, commits | Français |
| Python | `snake_case` fonctions/variables/modules, `PascalCase` classes, `UPPER_SNAKE` constantes |
| TypeScript | `camelCase` variables/fonctions, `PascalCase` composants/types, fichiers de composants en `PascalCase.tsx`, autres en `kebab-case.ts` |
| Tables SQL | `snake_case` pluriel (`job_offers`), clés `id`, clés étrangères `<table_singulier>_id`, horodatages `created_at`/`updated_at` |
| Routes API | `/api/v1/<ressource-pluriel>` en `kebab-case`, verbes HTTP standards |
| Branches | `feat/…`, `fix/…`, `chore/…`, `docs/…` |
| Commits | Conventional Commits en français (voir `CLAUDE.md`) |

## Typage

- Python : annotations complètes, mypy/pyright strict, pas de `Any` sans justification.
- TypeScript : `strict`, `noUncheckedIndexedAccess`, pas de `any`, pas de `@ts-ignore` sans commentaire expliquant pourquoi.
- Schémas Pydantic aux frontières (API, connecteurs, sorties IA) ; types de domaine à l'intérieur.
- Montants : type décimal (jamais de flottant pour l'argent) ; dates en UTC avec fuseau explicite.

## Gestion des erreurs

- Hiérarchie d'exceptions métier (`DomainError` → `NotFoundError`, `ValidationError`, `ConflictError`, `BudgetExceededError`, `SourceUnavailableError`, …) dans le domaine.
- Les erreurs d'infrastructure sont **traduites** à la frontière en erreurs métier, avec la cause d'origine conservée.
- Une seule couche convertit les exceptions en réponses HTTP, au format `application/problem+json` : `type`, `title`, `status`, `detail`, `code` stable, `correlation_id`. Aucun détail interne ni stack trace.
- Jamais d'`except` nu ni d'exception avalée sans log. Erreurs récupérables (retry) distinguées des erreurs fatales.
- Résultats partiels explicites (ex. une source en échec) plutôt que des exceptions globales.

## Validation

- Toute entrée externe (HTTP, annonce, fichier, sortie IA) est validée par un schéma strict avant usage.
- Listes blanches plutôt que listes noires ; tailles et longueurs bornées.
- La validation côté client (Zod) est un confort, jamais une protection.

## Logs

- JSON structuré : `timestamp`, `level`, `message`, `module`, `correlation_id`, `duration_ms` quand pertinent.
- Niveaux : `DEBUG` (dev), `INFO` (événements métier), `WARNING` (dégradation récupérable), `ERROR` (échec), `CRITICAL`.
- Interdit dans les logs : clés API, mots de passe, contenu de CV, données personnelles inutiles, contenu complet des annonces ou des prompts.
- Identifiant de corrélation créé à l'entrée de l'API ou du job et propagé partout.

## Structure et nommage des tests

```text
backend/tests/{unit,integration,api,security,architecture}/
frontend/src/**/*.test.ts(x)   # à côté du code testé
e2e/                           # Playwright
```

- Backend : `test_<comportement>_<condition>` ; schéma Arrange / Act / Assert.
- Tests déterministes, indépendants, sans réseau réel (fixtures anonymisées, `Clock` injectable).
- Intégration sur PostgreSQL réel (conteneur), pas de SQLite de substitution.
- Un bug corrigé commence par un test qui le reproduit.
- Tests d'architecture : dépendances entre couches et modules conformes à `MODULE_CONTRACTS.md`.

## Formatage et qualité

- Python : Ruff (lint + format), mypy/pyright. TypeScript : ESLint, Prettier, `tsc --noEmit`.
- Hooks pre-commit : formatage, lint, détection de secrets. La CI exécute les mêmes contrôles.
- Pas de code mort, pas de TODO sans ticket, fonctions courtes, fichiers de taille raisonnable.

## Configuration

- Une seule classe de configuration typée par application, lue depuis l'environnement, validée au démarrage (échec explicite si invalide).
- `.env.example` documente chaque variable sans valeur réelle ; secrets jamais versionnés.
