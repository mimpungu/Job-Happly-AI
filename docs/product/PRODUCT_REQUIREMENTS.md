# Objectifs, périmètre et critères de réussite (TASK-001-03)

Date : 2026-11-03

## Positionnement

Happly AI n'est **pas un MVP jetable** : c'est un système robuste, sécurisé et maintenable, construit pour durer. Les « releases » du backlog (0.1 à 1.0) sont des **jalons de livraison incrémentale**, chacun livré avec ses tests, sa sécurité et sa documentation. Rien n'est livré « provisoirement ».

## Fonctionnalités indispensables (dans l'ordre des releases)

1. **0.1 Fondations** : projet démarrable, base de données migrée, design system, CI, bases de sécurité.
2. **0.2 Recherche** : au moins une source gratuite réelle, normalisation, déduplication, recherche, sauvegarde.
3. **0.3 Intelligence** : profil maître, scoring explicable, couche IA plafonnée, analyse d'offres.
4. **0.4 Documents et candidatures** : CV LaTeX/PDF, lettres, suivi des candidatures.
5. **0.5 Automatisation** : recherches planifiées, notifications, préparation d'entretiens.
6. **1.0 International et stabilisation** : multi-pays, audit sécurité/performance, documentation complète.

## Fonctionnalités différées (non abandonnées)

- Authentification et multi-utilisateur (ADR-0008, EPIC 018).
- Hébergement distant.
- Modèle IA local.
- Sources payantes ou partenaires.

## Parcours utilisateur de référence

Les parcours A à G de `docs/HAPPLY_AI_MASTER_SPEC.md` (§26) : recherche, analyse, CV, lettre, candidature, maîtrise des coûts, international.

## Critères de réussite

- Chaque parcours s'exécute de bout en bout avec de **vraies données** et de vraies sources autorisées.
- Aucun appel IA ne dépasse le plafond défini ; tests automatisés à l'appui.
- Aucun secret versionné ; données locales protégées ; compilation LaTeX isolée.
- Aucune candidature envoyée sans action explicite de l'utilisateur.
- Installation reproductible depuis un dépôt propre ; sauvegarde et restauration testées.
- Chaque information générée est traçable jusqu'au CV maître : aucune donnée inventée.
- Limites de couverture des sources affichées honnêtement.
