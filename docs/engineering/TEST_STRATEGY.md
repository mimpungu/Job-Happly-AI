# Stratégie de tests

| Niveau | Outil | Portée |
|---|---|---|
| Unitaire backend | pytest | Règles métier, scoring, normalisation, déduplication, validation des sorties IA, plafonds de coût |
| Intégration backend | pytest + PostgreSQL réel (conteneur) | Repositories, migrations, transactions, contraintes SQL, file de tâches |
| API | pytest + client HTTP | Contrats, erreurs `problem+json`, validation d'entrée |
| Contrat connecteurs | pytest + fixtures anonymisées | Succès, pagination, erreurs, quotas, structure modifiée, accès refusé |
| Sécurité | pytest | SSRF, injections, traversée de chemin, fichiers malformés, prompt injection, secrets absents des logs |
| Architecture | pytest | Dépendances entre couches et modules conformes à `MODULE_CONTRACTS.md` |
| Composants frontend | Vitest + Testing Library | Composants, formulaires, états chargement/vide/erreur, accessibilité |
| Accessibilité (E2E, API simulée) | Playwright + axe | Chaque écran avec données, deux thèmes, trois tailles, sans débordement (`pnpm e2e`) |
| Parcours complets (E2E, pile réelle) | Playwright + API FastAPI + PostgreSQL + pdfLaTeX | Import du CV, recherche, CV, lettre, candidature, budget IA, entretien, confidentialité (`pnpm e2e:fullstack`, base dédiée `happly_e2e_test`) |
| Performance | pytest + PostgreSQL réel | 20 000 offres : durée de liste et de recherche, pagination, nombre de requêtes (pas de N+1), EXPLAIN ANALYZE réel, 10 workers concurrents |
| Garde-fous de gouvernance | pytest (AST, OpenAPI) | Entrées bornées, surface sortante, SQL, secrets, catalogue RGPD, appels IA documentés, mode local |
| Documents | pytest | Compilation LaTeX, extraction du texte PDF, ordre de lecture, accents |

## Règles

- Aucun appel réseau réel dans les tests ; horloge injectable.
- Les appels IA sont testés avec un faux fournisseur **explicitement identifié comme test** ; un test prouve qu'aucun appel ne dépasse le plafond.
- Un bug corrigé commence par un test qui le reproduit.
- Jamais de test supprimé, désactivé ou affaibli pour faire passer un build.
- Un test n'est déclaré réussi que s'il a été exécuté.
- Couverture backend mesurée (`pytest --cov=app`) avec un **seuil en CI** fixé sous la valeur mesurée pour qu'elle ne régresse pas ; la priorité reste aux modules critiques (budget IA, déduplication, sécurité) plutôt qu'à un pourcentage global. Valeurs et limites : `QUALITY_REPORT.md`.
- Les parcours E2E à pile réelle ne s'exécutent pas à chaque commit (durée) : ils se lancent avant une release et dans le job CI dédié.
