# ADR-0021 — Internationalisation et référentiel géographique (EPIC 017)

- **Statut :** Accepté
- **Date :** 2026-11-05

## Contexte

L'application doit servir des recherches d'emploi hors de France. Les règles du projet interdisent de
coder en dur pays, devises et fournisseurs (`CLAUDE.md` §16) : le référentiel géographique doit donc
venir de données normalisées, pas d'une liste écrite à la main. L'interface doit aussi exister en
plusieurs langues (français et anglais d'abord, décision du propriétaire).

## Décision

1. **Référentiel géographique via Babel (données CLDR / ISO 3166 / ISO 4217)**, derrière le port
   `GeographyReference` (`modules/localization/domain`). Le domaine ne connaît que le contrat ;
   l'adaptateur `BabelGeographyReference` est dans l'infrastructure. Un pays est un territoire à deux
   lettres dont le CLDR connaît une langue, hors plages réservées par l'ISO (AA, QM–QZ, XA–XZ, ZZ).
   Les langues d'usage (`de_facto`) sont retenues : les États-Unis ou l'Australie n'ont pas de langue
   officielle légale mais ne sont pas « muets ».
   - *Dépendance ajoutée : `babel` (BSD-3, maintenue, données CLDR).* Rejeté : `pycountry` (LGPL),
     liste maison (interdite, non maintenable).
2. **Préférences** (`user_preferences`, migration 0014, additive) : langue d'interface (`fr`, `en`),
   pays, devise, fuseau IANA (validé contre `zoneinfo`), mobilité. `NULL` = non renseigné, jamais une
   valeur par défaut déguisée. Aucune conversion de devise : la devise choisie ne fait que
   pré-remplir les filtres ; chaque offre garde la sienne.
3. **Interface : `next-intl` côté client uniquement** (`LocaleProvider`). Le serveur rend toujours
   le français ; le choix enregistré (`localStorage` + préférences) est appliqué au montage. Rejeté
   pour l'instant : routage par locale ou lecture d'un cookie côté serveur, incompatibles avec les
   pages statiques (`cacheComponents`). Limite assumée : un bref affichage en français avant
   l'application de l'anglais. Traduction progressive : navigation et paramètres généraux d'abord ;
   les clés manquantes sont détectées par un test (mêmes clés dans toutes les langues).
4. **Couverture géographique explicite.** Une source qui ne déclare aucun pays n'est **jamais**
   comptée comme couvrante : la recherche renvoie `coverage` (demandés, déclarés, non déclarés,
   sources sans couverture déclarée) et l'interface l'affiche.
5. **Mobilité des offres** (migration 0015) : sponsoring de visa (`offered`, `not_offered`) et
   droit de travailler exigé, déduits de l'annonce par règles FR/EN ; annonce muette ou
   contradictoire = inconnu (`NULL`).
6. **Compétences multilingues** : équivalents FR↔EN d'un lexique fermé et revu, comme pour les
   intitulés (008-10) ; un nom technique inconnu n'est jamais « traduit ».

## Conséquences

- Les pays, devises et langues officielles évoluent avec Babel, sans code à écrire.
- Pas de source internationale réelle intégrée : les tâches 017-20 à 017-23 exigent de lire la
  documentation et les conditions d'utilisation des fournisseurs (réseau de la session bloqué).
- Dette assumée : l'analyse d'offre (EPIC 011) extrait déjà `mobility.visa` ; les deux détections
  sont à unifier. Le fuseau des préférences n'est pas encore utilisé pour l'affichage des dates,
  et les notifications gardent leur propre fuseau.
