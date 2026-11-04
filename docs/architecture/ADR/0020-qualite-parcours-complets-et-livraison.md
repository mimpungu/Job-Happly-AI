# ADR-0020 — Qualité, parcours complets et préparation de la livraison (EPIC 019)

- **Statut :** Accepté
- **Date :** 2026-11-04

## Contexte

L'EPIC 019 doit établir que le produit est réellement utilisable. Les tests unitaires et d'intégration étaient nombreux, mais deux manques restaient : aucun test ne parcourait l'application comme un candidat (navigateur, API, base, pdfLaTeX), et les pages Espace CV (CV générés) et Lettres de motivation n'existaient pas côté interface (seul le backend existait), ce qui rendait les parcours « générer un CV / une lettre » impossibles à tester ou à utiliser.

## Décision

1. **Parcours E2E à pile réelle** (`frontend/e2e-fullstack`, `pnpm e2e:fullstack`) : base PostgreSQL dédiée `happly_e2e_test` recréée et migrée à chaque lancement, API FastAPI et interface Next.js lancées par Playwright sur des ports distincts, vrai pdfLaTeX. Huit parcours enchaînés : import du CV, recherche, CV, lettre, candidature, budget IA, préparation d'entretien, confidentialité. Rejeté : les remplacer par des appels API seuls (ne détecte ni les écrans manquants ni les libellés ou liens cassés).
2. **Les tests d'accessibilité restent à API simulée** (`pnpm e2e`, rapides, deux thèmes, trois tailles) ; les deux familles sont complémentaires.
3. **Construire les pages manquantes** (CV générés dans l'Espace CV, Lettres de motivation) plutôt que de documenter l'absence : un parcours principal non utilisable bloque toute déclaration de version stable.
4. **Performance mesurée, pas supposée** : tests sur 20 000 offres (liste, recherche, pagination profonde, comptage de requêtes indépendant de la taille de page, EXPLAIN ANALYZE rejoué sur la vraie requête, 10 workers concurrents). Les seuils sont larges (CI lente) : ils détectent un ordre de grandeur, pas une milliseconde.
5. **Couverture backend mesurée** (`pytest-cov`, outil de développement uniquement) avec un seuil en CI fixé sous la valeur mesurée ; la couverture n'est pas un objectif en soi.
6. **Livraison préparée, jamais publiée sans accord** : version `0.5.0rc1`, CHANGELOG, checklist de release, rapport de qualité chiffré. Aucun tag ni release tant que le propriétaire ne le demande pas ; la version 1.0 reste conditionnée aux critères du plan de releases (EPIC 017, authentification, sources réelles).

## Conséquences

Un défaut réel a été trouvé et corrigé grâce au test de charge (enqueue de la file de tâches échouant à la 6ᵉ exécution sur une connexion). Les parcours complets coûtent plusieurs dizaines de secondes : ils tournent avant une release et dans un job CI dédié, pas à chaque sauvegarde. Les écarts restants (EPIC 017, authentification, sources) sont consignés dans `docs/engineering/QUALITY_REPORT.md` et non masqués.
