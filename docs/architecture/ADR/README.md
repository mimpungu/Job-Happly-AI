# Architecture Decision Records (ADR)

Un ADR documente une décision d'architecture importante : contexte, décision, alternatives, conséquences.

## Règles

- Un fichier par décision : `NNNN-titre-court.md`. Numéros stables, jamais réutilisés.
- Une décision remplacée n'est pas supprimée : son statut passe à `Remplacé par ADR-NNNN`.
- Statuts : `Proposé`, `Accepté`, `Remplacé`, `Abandonné`.
- Toute décision structurante prise pendant le développement doit produire un ADR dans le même changement.

## Index

| ADR | Titre | Statut |
|---|---|---|
| [0001](0001-monolithe-modulaire.md) | Monolithe modulaire en Clean Architecture | Accepté |
| [0002](0002-backend-python-fastapi.md) | Backend Python / FastAPI | Accepté |
| [0003](0003-frontend-nextjs.md) | Frontend Next.js / TypeScript strict | Accepté |
| [0004](0004-base-de-donnees-postgresql.md) | Base de données PostgreSQL | Accepté |
| [0005](0005-strategie-ia-et-plafonds.md) | Stratégie IA, API payante et plafonds | Accepté (fournisseur à décider) |
| [0006](0006-strategie-connecteurs.md) | Stratégie des connecteurs de sources | Accepté |
| [0007](0007-stockage-documentaire.md) | Stockage documentaire | Accepté |
| [0008](0008-authentification-differee.md) | Authentification différée, exécution locale | Accepté |
| [0009](0009-taches-de-fond-postgresql.md) | Tâches de fond adossées à PostgreSQL | Accepté |
| [0010](0010-contrastes-boutons-pleins.md) | Texte sombre sur les boutons pleins (contraste) | Accepté |
| [0011](0011-ia-hybride-local-et-api.md) | IA hybride local et API | Accepté |
| [0012](0012-fournisseurs-ia-de-demarrage.md) | Fournisseurs IA de démarrage (Gemini + Ollama) | Accepté |
| [0013](0013-generateur-cv-latex.md) | Architecture du générateur de CV LaTeX et contrôle ATS | Accepté |
| [0014](0014-generateur-lettres-de-motivation.md) | Architecture du générateur de lettres de motivation et audit qualité | Accepté |
| [0015](0015-suivi-des-candidatures-et-crm.md) | Architecture du suivi des candidatures (CRM) et tableau de bord | Accepté |
| [0016](0016-planification-automatisation-et-notifications.md) | Planification, automatisation des recherches et centre de notifications | Accepté |
| [0017](0017-page-d-accueil-themes-et-derogation-graphique.md) | Page d'accueil, thèmes clair et sombre, dérogation du graphique d'entonnoir | Accepté |

Modèle : [TEMPLATE.md](TEMPLATE.md)
