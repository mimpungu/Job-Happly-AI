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
| E2E | Playwright | Parcours A à G de la spec (recherche, analyse, CV, lettre, candidature, budget IA, international) |
| Documents | pytest | Compilation LaTeX, extraction du texte PDF, ordre de lecture, accents |

## Règles

- Aucun appel réseau réel dans les tests ; horloge injectable.
- Les appels IA sont testés avec un faux fournisseur **explicitement identifié comme test** ; un test prouve qu'aucun appel ne dépasse le plafond.
- Un bug corrigé commence par un test qui le reproduit.
- Jamais de test supprimé, désactivé ou affaibli pour faire passer un build.
- Un test n'est déclaré réussi que s'il a été exécuté.
- Couverture suivie, avec priorité aux modules critiques (budget IA, déduplication, sécurité) plutôt qu'à un pourcentage global.
