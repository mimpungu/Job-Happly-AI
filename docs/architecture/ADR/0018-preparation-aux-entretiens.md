# ADR-0018 — Préparation aux entretiens et suivi des entretiens (EPIC 016)

- **Statut :** Accepté
- **Date :** 2026-11-04

## Contexte

L'EPIC 016 accompagne le candidat après l'envoi : préparer l'entretien, s'entraîner, suivre les
entretiens réels et relancer. La spécification (§14) impose : génération **à la demande**, aucune
simulation coûteuse automatique, réponses fondées sur le **vrai parcours** (règle absolue : aucun
fait inventé) et historique conservé. Le fournisseur d'IA payante n'est pas choisi (ADR-0005) :
l'IA reste facultative, derrière la passerelle existante.

## Décision

1. **Module `interview_preparation`** (domain / application / infrastructure / presentation),
   trois tables additives (migration 0009) : `interview_preparations` (une par candidature,
   régénérable), `interview_simulations` (historique, **questions copiées** : régénérer la
   préparation ne réécrit pas le passé) et `interviews` (fiches d'entretiens réels).
2. **Niveau 0 par défaut, sans IA ni coût** : le générateur est une fonction pure et déterministe.
   Questions RH et comportementales (modèles FR/EN), questions techniques tirées des compétences de
   l'offre **présentes dans le profil**, questions « écart de compétence » pour celles qui sont
   absentes (jamais présentées comme maîtrisées), présentation composée uniquement de faits du
   profil, expériences classées par recoupement avec l'offre, questions pour le recruteur.
3. **Trames de réponse (Situation – Actions – Résultat)** adossées à une expérience réelle ; le
   résultat n'est **jamais** rempli : il est marqué « à compléter » (idem pour la motivation de
   l'accroche). Offre non analysée : seules les compétences du profil citées dans son texte sont
   utilisées, avec un avertissement.
4. **IA à la demande, jamais implicite** : paramètre `mode` = `none` (défaut) / `local` / `ai`,
   comme pour la reformulation du CV (ADR-0013). Deux usages seulement : questions
   supplémentaires (le seul texte public de l'offre est transmis, aucune donnée du candidat) et
   commentaire d'une réponse (la réponse est une donnée personnelle : requête marquée comme telle,
   aucun palier gratuit qui réutilise les contenus). `local` restreint l'appel aux modèles locaux
   (`AIRequest.allowed_kinds`). Consentement, plafonds, cache et journal sont ceux de la
   passerelle. Une indisponibilité de l'IA ne bloque jamais : le résultat de base est livré et le
   statut (`ai.status = unavailable` + motif) est affiché.
5. **Retours de simulation niveau 0** : score /100 fondé sur des critères vérifiables (longueur,
   structure S-A-R, exemple chiffré, termes de l'offre, chiffres). Les chiffres absents du profil
   et de l'offre sont signalés « à vérifier », jamais validés. La simulation démarre sans appel IA ;
   une simulation terminée est en lecture seule ; suppression possible à la demande (RGPD).
6. **Fiches d'entretien et CRM** : une date d'entretien est écrite **une seule fois**, dans
   l'historique de la candidature via `ApplicationTrackerPort` (adaptateur sur le service du suivi
   de candidatures) : l'agenda du tableau de bord la voit sans second modèle. Report et issue sont
   tracés ; les dates exigent un fuseau. La relance post-entretien est un **brouillon** copié par
   l'utilisateur (rien n'est envoyé) ; sa planification passe par le suivi, qui n'autorise une
   relance que sur une candidature envoyée.
7. **Frontend** : page `/interview-preparation?application=…` en trois onglets (Préparation,
   Simulation, Entretiens), lien depuis la fiche candidature, états chargement / vide / erreur,
   avertissement explicite quand l'IA est indisponible, tests Vitest et E2E axe (2 thèmes, 3 tailles).

## Limites assumées

- La préparation s'appuie sur le **profil validé**, non sur le texte du PDF du CV envoyé ; si aucun
  CV n'est associé à la candidature, un avertissement le dit.
- Questions et trames sont des modèles, pas une analyse sémantique de l'offre : l'IA optionnelle
  ajoute des questions spécifiques, elle ne remplace pas la base.
- Le contenu généré réutilise les modèles immuables du domaine comme contrat d'API (pas de copie).
- Pas de saisie vocale ni de simulation chronométrée.

## Conséquences

Aucune dépendance ajoutée. Coût nul par défaut ; tout appel IA est explicite, journalisé et
plafonné. Le contrat avec le suivi de candidatures reste un port : l'historique est unique.
