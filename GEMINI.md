# GEMINI.md — Happly AI

Ce fichier est lu automatiquement au début de chaque session. Il complète (sans les remplacer) :

- `docs/HAPPLY_AI_MASTER_SPEC.md` — vision, architecture, contraintes.
- `docs/HAPPLY_AI_MASTER_BACKLOG.md` — périmètre, dépendances, statuts.
- `docs/AI_DEVELOPMENT_RULES.md` — règles obligatoires.
- `docs/HAPPLY_AI_CV_GENERATION_PROMPT.md` et `docs/HAPPLY_AI_COVER_LETTER_PROMPT.md` — prompts maîtres documentaires.

En cas de contradiction : signale-la avant toute décision structurante, ne tranche pas en silence.

---

## 1. Règles absolues (consignes du propriétaire)

### Git
- **Ne jamais exécuter `git add`, `git commit` ni `git push`** (ni `git commit --amend`, ni équivalent). EXCEPTÉ SI je te le demande explicitement.
- À la fin de chaque tâche, **fournis uniquement un message de commit**, que l'utilisateur exécutera lui-même.
- Le message est **rédigé en français** et suit la convention **Conventional Commits** :

```text
<type>(<portée optionnelle>): <description courte à l'impératif, minuscule, sans point final>

<corps optionnel : pourquoi, pas seulement quoi>
```

| Type | Usage |
|---|---|
| `feat` | nouvelle fonctionnalité |
| `fix` | correction de bug |
| `docs` | documentation uniquement |
| `refactor` | refonte sans changement de comportement |
| `test` | ajout ou correction de tests |
| `chore` | maintenance, outillage, dépendances |
| `ci` | pipeline d'intégration continue |
| `build` | système de build, Docker |
| `perf` | optimisation de performance |
| `style` | formatage, sans effet logique |
| `revert` | annulation d'un commit |

Exemples :
- `feat(search): ajouter le connecteur France Travail`
- `fix(ai-budget): bloquer les appels non essentiels au dépassement du plafond`
- `chore(deps): mettre à jour Ruff`

Un commit = un changement cohérent. Changement cassant : ajouter `!` après le type (`feat(api)!:`) et un paragraphe `BREAKING CHANGE:`.

### Langue
- **Commentaires de code, docstrings, messages de commit, documentation : en français.**
- **Identifiants de code (variables, fonctions, classes, fichiers, routes) : en anglais**, pour rester cohérent avec l'écosystème.
- Les commentaires expliquent le **pourquoi**, pas le **quoi** que le code dit déjà.

### Exécution locale, sans authentification (pour l'instant)
- Application locale mono-utilisateur, **sans authentification** au départ (ADR-0008), mais l'authentification sera intégrée plus tard.
- Lier API et frontend à `127.0.0.1`, CORS restrictif, ports Docker locaux. Ne jamais exposer l'application à distance.
- Toute entité de l'utilisateur porte un `owner_id` et passe par un contexte utilisateur, pour que le multi-utilisateur reste une migration.
- Le fournisseur d'IA payante n'est **pas encore choisi** : ne dépendre d'aucun fournisseur précis avant l'ADR dédié.
- Le projet n'est pas un MVP jetable : viser une qualité durable dès le départ.

### Suivi du backlog
- `[✅]` = réalisé et validé (Definition of Done satisfaite). `[➖]` = non réalisé.
- Ne passer une tâche à `[✅]` que si les tests ont été **réellement exécutés** et ont réussi.
- Une FEATURE / un EPIC ne passe à `[✅]` que si tous ses éléments le sont.
- Mettre à jour le tableau de pilotage (Backlog, Partie 8.1) à chaque changement.
- Ne jamais déclarer une tâche terminée sur la seule base d'une réponse textuelle.

---

## 2. Méthode de travail

1. **Inspecter** le dépôt réel avant toute chose : ne jamais supposer qu'un fichier, une dépendance ou une fonctionnalité existe.
2. **Lire** la documentation concernée et vérifier les dépendances du backlog.
3. **Planifier** brièvement pour les tâches complexes (fichiers, risques, critères d'acceptation, tests).
4. **Implémenter une seule tâche à la fois**, par petits changements ciblés.
5. **Valider** : tests, lint, typage, build.
6. **Documenter** : doc technique, ADR si décision structurante, backlog.
7. **Rapporter** : ce qui a été fait, fichiers touchés, tests exécutés et résultats, limites, tâche suivante, message de commit.

Demander confirmation avant : opération destructive, migration risquée, dépense, activation d'un service payant, envoi de données personnelles à un tiers, envoi d'une candidature.

---

## 3. Principes d'ingénierie senior

- **Simplicité maîtrisée** : pas de sur-ingénierie, pas d'abstraction sans besoin avéré (YAGNI), pas de microservices prématurés.
- **DRY raisonné** : factoriser la logique métier, tolérer une petite duplication plutôt qu'une mauvaise abstraction.
- **SOLID** appliqué avec pragmatisme ; composition plutôt qu'héritage.
- **Explicite plutôt qu'implicite** : pas de magie, pas d'effets de bord cachés.
- **Fail fast** : valider tôt, échouer clairement, ne jamais avaler une exception.
- **Immutabilité par défaut**, fonctions pures pour la logique métier.
- **Pas de code mort, pas de TODO sans ticket**, pas de hack non documenté.
- **Petites fonctions** (une responsabilité), **petits fichiers**, noms descriptifs.
- **Corriger la cause, pas le symptôme**. Ne jamais contourner un test, un linter ou une erreur de typage.
- Ne pas modifier du code sans rapport avec la tâche. Ne pas réécrire un module fonctionnel sans justification.

---

## 4. Architecture

- **Clean Architecture + DDD pragmatique**, monolithe modulaire.
- Couches : `domain` → `application` → `infrastructure` / `presentation`. **Les dépendances pointent vers le domaine**, jamais l'inverse.
- Le domaine ne dépend d'aucun framework (ni FastAPI, ni SQLAlchemy, ni SDK IA).
- **Aucune logique métier** dans les routes HTTP, ni dans les composants React.
- **Aucun accès direct à la base** depuis les routes : passer par repositories et use cases.
- Intégrations externes (sources d'emploi, IA, stockage) **derrière des interfaces** (ports/adapters).
- Pas de dépendances circulaires entre modules. Contrats intermodules documentés.
- Configuration centralisée ; injection de dépendances ; pas d'état global modifiable.
- Toute décision structurante → **ADR** dans `docs/architecture/ADR/`.

---

## 5. Backend (Python / FastAPI)

- Python typé partout (`mypy` ou `pyright` en mode strict), Pydantic pour les schémas, SQLAlchemy 2 en style typé.
- Routes **minces** : validation → use case → réponse.
- API REST **versionnée** (`/api/v1`), contrats explicites, erreurs normalisées (jamais de stack trace côté client).
- **Async** pour les I/O ; ne jamais bloquer la boucle d'événements (déporter le CPU-bound dans des jobs).
- Gestion d'erreurs centralisée, exceptions métier dédiées, distinction erreurs récupérables / fatales.
- **Idempotence** des tâches de fond ; verrous pour éviter les exécutions concurrentes inutiles.
- Tout service externe est **non fiable** : timeout, retry avec backoff exponentiel et jitter, rate limiting, circuit breaker si pertinent.
- Logs **structurés** (JSON) avec identifiant de corrélation ; jamais de données personnelles ni de secrets.
- Outils : Ruff (lint + format), mypy/pyright, pytest.

## 6. Frontend (Next.js / React / TypeScript)

- TypeScript **strict** (`strict: true`, pas de `any` sans justification, pas de `@ts-ignore` sans commentaire).
- Composants petits, réutilisables, accessibles (clavier, ARIA, contrastes).
- Logique métier **hors** des composants (hooks, services). Données distantes via TanStack Query ; Zustand seulement si nécessaire.
- Formulaires : React Hook Form + Zod. Valider côté client **et** serveur.
- Toujours gérer les états : chargement, vide, succès, erreur.
- Performance : Server Components par défaut, code splitting, images optimisées, éviter les re-rendus inutiles, mémoïser avec discernement.
- Pas de dépendance ajoutée sans justification (poids, maintenance, sécurité).
- Outils : ESLint, Prettier, Vitest + Testing Library, Playwright.

## 7. Design system

- Thème **sombre** inspiré d'Apple : sobre, espacements généreux, hiérarchie claire.
- **Interdits** : dégradés (texte, boutons, décoratifs), néon, glassmorphism excessif, ombres disproportionnées, animations agressives, icônes inutiles.
- Boutons et titres en **couleurs unies**.
- **Toutes les couleurs, espacements et typographies passent par des design tokens** : aucune valeur codée en dur dans les composants.
- Palette de référence : voir `docs/HAPPLY_AI_MASTER_SPEC.md` §15.1. Police : SF Pro si licenciée, sinon Inter.

---

## 8. Base de données

- Migrations Alembic **versionnées**, jamais de modification manuelle du schéma.
- Pas de migration destructive sans justification et accord explicite ; migrations réversibles quand possible.
- Clés primaires/étrangères, contraintes d'unicité, `NOT NULL` et `CHECK` pour protéger l'intégrité.
- Index **basés sur des requêtes réelles** (source + external_id, pays, date, intitulé, entreprise, statut…). Vérifier avec `EXPLAIN`.
- Éviter le N+1 (chargement explicite des relations) ; **pagination côté base**, jamais en mémoire.
- Transactions courtes et explicites ; opérations d'ingestion **idempotentes** (upsert).
- Ne pas confondre **absence d'information** (`NULL`) et valeur zéro.
- Ne stocker aucune donnée sensible inutilement. Sauvegarde et restauration documentées **et testées**.

## 9. IA et maîtrise des coûts

- Chaque appel IA doit avoir une **justification fonctionnelle**. Ordre de préférence : niveau 0 (règles, SQL, Python) → modèle économique → modèle performant.
- Fournisseurs **interchangeables** derrière `AIProvider` ; jamais de fournisseur codé en dur dans le métier.
- Avant tout appel : empreinte du contenu + version du prompt + modèle → **cache**.
- Journaliser tokens, coût estimé/réel, durée, résultat. Respecter budgets (jour, mois, opération, fournisseur) ; ne jamais contourner un plafond.
- Sorties **structurées et validées** (schéma strict) ; gérer réponses incomplètes, erreurs, timeouts.
- Prompts versionnés, concis ; n'envoyer que le contexte nécessaire (jamais le CV complet par défaut).
- **Ne jamais inventer de faits** (diplômes, compétences, chiffres, expériences). L'IA améliore la rédaction, elle ne crée pas de données.
- L'IA assiste, elle ne prend pas de décision irréversible. Aucune candidature envoyée automatiquement.
- **Fournisseur principal : API payante**, toujours encadrée par un plafond. Un modèle local est une option ultérieure non prioritaire (même interface `AIProvider`).
- **Plafond obligatoire** : aucun appel payant tant qu'un plafond n'est pas défini. Contrôle du coût estimé **avant** chaque appel, refus si le plafond serait dépassé, alertes aux seuils, blocage explicite (jamais silencieux). Ne jamais augmenter un plafond ni dépasser le budget sans accord de l'utilisateur.

## 10. Connecteurs d'offres

- Interface commune ; une source indisponible **ne bloque jamais** les autres.
- Privilégier API officielles et flux autorisés. **Ne jamais contourner** CAPTCHA, authentification, anti-bot ou conditions d'utilisation.
- Normaliser vers un modèle commun, conserver la donnée brute pour l'audit, tracer source et date de récupération.
- Déduplication déterministe d'abord ; similarité textuelle seulement si nécessaire.
- **Sources gratuites et publiques uniquement** pour l'instant ; aucune source payante sans accord explicite.
- **Sites carrières d'entreprises** : consulter uniquement les éléments publics (API publiques d'ATS, données structurées `JobPosting`, pages dont `robots.txt` et CGU autorisent la lecture). Débit limité, User-Agent honnête. **Jamais de contournement** de CAPTCHA, connexion, restriction ou anti-bot : en cas de refus, marquer la source « non supportée ».
- **Aucun faux connecteur** ni offre fabriquée. Les mocks existent uniquement pour les tests et le mode démonstration clairement identifié.

---

## 11. Sécurité (non négociable)

- **Aucun secret** dans le code ni dans Git. Variables d'environnement, `.env.example` sans vraies valeurs, `.env` dans `.gitignore`. Masquer les clés dans l'interface.
- Valider et assainir **toute entrée externe** (utilisateur, API, annonces, fichiers).
- Se protéger contre : injection SQL (requêtes paramétrées/ORM), XSS (échappement, pas de HTML non assaini), CSRF, SSRF (liste blanche de destinations, blocage des IP internes), traversée de chemin, désérialisation non sûre.
- CORS restrictif, rate limiting, en-têtes de sécurité, HTTPS pour les appels externes.
- Moindre privilège ; authentification et autorisation par ressource dès qu'un accès distant est possible.
- **Fichiers importés non fiables** : limite de taille, contrôle MIME réel, noms générés, stockage isolé.
- **Compilation LaTeX isolée** : conteneur, limites CPU/mémoire/temps, réseau désactivé, commandes restreintes, dossier temporaire dédié.
- **Prompt injection** : le contenu d'une annonce ou d'un document est une **donnée**, jamais une instruction. Séparer strictement données et instructions système.
- Dépendances : vérifier maintenance et vulnérabilités avant ajout ; ne jamais monter une version majeure sans vérifier la compatibilité.
- **RGPD** : minimisation, finalité, durée de conservation, export et suppression des données. Informer l'utilisateur des données envoyées aux fournisseurs IA.
- Ne jamais journaliser clés, mots de passe, CV complets ni données personnelles inutiles.

## 12. Performance

- Mesurer avant d'optimiser ; documenter les gains.
- Requêtes SQL et index vérifiés, pagination côté base, mise en cache pertinente, appels externes parallélisés avec limites.
- Pas de traitement lourd dans le chemin de requête : tâches de fond.
- Garder des performances stables avec des milliers d'offres et des centaines de candidatures.

## 13. Maintenabilité et documentation

- Code lisible avant d'être astucieux ; conventions uniformes (formatage automatique).
- Interfaces et décisions importantes documentées ; ADR pour les choix d'architecture.
- Mettre à jour la documentation **dans le même changement** que le code.
- Documents obligatoires : `README`, `ARCHITECTURE`, `CONTRIBUTING`, `SECURITY`, `CHANGELOG`, `API`, `AI_COSTS`, `DATA_SOURCES`, `DEPLOYMENT`.
- Documenter limites connues et dette technique assumée.

## 14. Tests

- Pytest (backend), Vitest + Testing Library (frontend), Playwright (E2E).
- Structure **Arrange / Act / Assert**, tests déterministes et indépendants, pas de dépendance au réseau réel (fixtures anonymisées).
- Prioriser : règles métier, validation des données, normalisation/déduplication, connecteurs en échec, cache et plafonds IA, validation des sorties IA, génération PDF, sécurité, détection de prompt injection.
- Corriger un bug = écrire d'abord un test qui le reproduit.
- **Ne jamais** supprimer, désactiver ou affaiblir un test pour faire passer un build.
- **Ne jamais affirmer qu'un test a réussi s'il n'a pas été exécuté.**

## 15. Observabilité

- Logs structurés avec niveaux et identifiant de corrélation ; durées des requêtes et appels IA ; échecs de tâches ; santé des connecteurs ; coûts IA.
- Health checks (API, base, sources, IA) et tableau de santé.
- Ne jamais ignorer silencieusement une erreur.

---

## 16. Interdictions

- Prétendre qu'un fichier, une API, un test ou un PDF existe ou a réussi sans preuve.
- Créer de fausses intégrations présentées comme fonctionnelles.
- Coder en dur secrets, pays, devises ou fournisseurs.
- Ajouter une dépendance sans justification.
- Modifier silencieusement le schéma de base de données.
- Effectuer une dépense, un déploiement ou une action externe sans accord.
- **Exécuter `git add`, `git commit` ou `git push`.**
- Soumettre une candidature automatiquement.
- Compromettre la confidentialité du CV.

## 17. Compte rendu de fin de tâche

```text
TASK ID :
TASK TITLE :
STATUS : [✅] / [➖]

OBJECTIVE :
FILES CREATED :
FILES MODIFIED :

IMPLEMENTATION :
TESTS EXECUTED :
TEST RESULTS :
ARCHITECTURAL NOTES :
SECURITY NOTES :
REMAINING RISKS :
NEXT READY TASK :

COMMIT MESSAGE (français, Conventional Commits) :
```

