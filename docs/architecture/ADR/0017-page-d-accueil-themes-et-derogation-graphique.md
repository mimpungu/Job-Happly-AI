# ADR-0017 — Page d'accueil, thèmes clair et sombre, dérogation du graphique d'entonnoir

- **Statut :** Accepté
- **Date :** 2026-11-04

## Contexte

Le propriétaire a fourni une maquette de tableau de bord (thème clair, barre latérale en
pastilles, cartes arrondies, graphique d'entonnoir en dégradé et hachures) et demandé qu'elle soit
reproduite fidèlement pour l'accueil, en conservant les entrées de navigation existantes.

Trois points de cette maquette contredisent `CLAUDE.md` §7 et la spécification §15 :

1. le design system impose un **thème sombre** ;
2. il interdit les **dégradés** (texte, boutons, décor) ;
3. la maquette est celle d'un **recruteur** (candidats, pourcentages prédits, fournisseurs de
   visioconférence), alors que Happly AI sert un candidat et n'affiche aucun chiffre sans donnée.

Le propriétaire a tranché : bascule clair/sombre, dégradé et hachures reproduits pour le seul
graphique, contenu adapté aux données réelles du candidat.

## Décision

1. **Deux thèmes par jetons.** Les valeurs sombres restent la référence (`@theme`) ; le thème clair
   les redéfinit sous `:root[data-theme="light"]`. Aucun composant ne dépend du thème. Contrastes
   mesurés (WCAG AA) consignés dans `tokens.css`. Le thème est choisi avant le premier rendu par un
   court script en tête de document : choix mémorisé (`happly-theme`), sinon préférence du système,
   sinon sombre. Une bascule est proposée dans l'en-tête.
2. **Nouveaux jetons** : rayons (`xl`, `2xl`, `3xl`), `shell` (conteneur de page), teintes douces
   avec leur texte (`*-soft`, `on-*-soft`), `highlight` (jour sélectionné), quatre couleurs de
   catégories (`chart-1..4`) et les jetons du graphique d'entonnoir. Les badges utilisent désormais
   les teintes douces : l'accent sur fond translucide n'atteignait que 4,48:1 en thème clair.
3. **Dérogation unique et bornée** : le graphique « Progression de la recherche » (page d'accueil)
   utilise un dégradé (colonne active) et des hachures (autres colonnes), uniquement via les jetons
   `--color-chart-*`. Tout autre dégradé reste interdit. Le dessin est décoratif (`aria-hidden`) ;
   chiffres, conversions et pertes sont exposés en texte et par des boutons focusables.
4. **Coque** : barre latérale en pastilles (logo, recherche globale avec raccourci « / », les 9
   entrées actuelles, Paramètres rangé en bas), conteneur arrondi, en-tête d'actions commun à
   toutes les pages (thème, profil, notifications, « Ajouter une offre »). Le titre d'une page
   peut être injecté à gauche de l'en-tête (`PageHeading`), ce qui permet à l'accueil d'afficher
   son message de bienvenue sur la même ligne que les actions.
5. **Contenu adapté, jamais inventé** :
   - « Top 3 des offres les plus compatibles » : vrais scores du moteur, hors offres ignorées ou
     suivies ;
   - trois indicateurs avec **variation réelle** (mois civil précédent, semaine précédente) ; sans
     période de référence, « Pas de comparaison » ;
   - entonnoir Offres → Suivies → Envoyées → Réponses → Offres reçues (chaque étape sous-ensemble
     de la précédente), conversion et perte calculées, et lecture du plus gros écart avec une action
     réelle ;
   - agenda des entretiens enregistrés dans les candidatures (lundi→dimanche, navigation par
     semaine) ;
   - statut des candidatures (répartition par étape, taux de réponse réel) et activité récente.
   Les informations exigées par l'EPIC 014 qui n'ont pas de place dans la maquette (offres
   nouvelles et pertinentes, budget IA, dernières recherches) forment une rangée de cartes sous la
   grille.
6. **Données** : le tableau de bord de l'API est étendu (prénom du profil, tendances mensuelles,
   meilleures correspondances, entonnoir, répartition par statut, entretiens datés).

## Écarts assumés par rapport à la maquette

- pas de photos de candidats : monogrammes (initiales sur une teinte stable) ;
- pas de logos Google Meet ou Teams : la plateforme de visioconférence n'est pas une donnée connue ;
- pas d'entrée « Feedback » : aucune fonction derrière ;
- pas d'étiquette « AI Insights » : ces correspondances sont calculées sans IA ; l'étiquette
  « Correspondances » est employée ;
- sept jours dans l'agenda (lundi→dimanche) au lieu de six ;
- les « … » des cartes sont des liens d'approfondissement étiquetés, pas des menus décoratifs ;
- la mise en page suit la maquette en proportions et en hiérarchie ; les tailles s'adaptent à la
  largeur de l'écran (grille à une colonne sous `xl`).

## Conséquences

- `CLAUDE.md` §7 et la spécification §15 doivent être mis à jour par le propriétaire pour refléter
  les deux thèmes et la dérogation du graphique (non modifiés ici).
- Les tests E2E d'accessibilité s'exécutent dans les deux thèmes, aux trois tailles, y compris avec
  des données (accueil, candidatures, Kanban, fiche).
- Toute nouvelle couleur doit être déclarée dans les deux thèmes avec son contraste.
