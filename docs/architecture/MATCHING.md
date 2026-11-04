# Moteur de correspondance (score de compatibilité)

Score **déterministe, sans IA**, sur 100, expliqué critère par critère. Il aide à trier les offres ; ce n'est **pas** une probabilité d'être recruté (l'avertissement est affiché avec chaque score).

Code : `backend/app/modules/job_intelligence/domain/matching/` (logique pure, sans base ni réseau).

## Principes

1. **Reproductible** : mêmes entrées + même date de référence + mêmes poids = même résultat. `weights_version` (`m1-<empreinte>`) identifie l'algorithme et les poids ; `ALGORITHM_VERSION` est à incrémenter dès que le calcul change.
2. **Donnée manquante ≠ échec** : chaque critère est *évalué* (note 0 à 1) ou en *données manquantes* (offre muette, profil vide). Un critère manquant **sort du calcul** et son poids est redistribué ; il n'est jamais compté 0.
3. **Fiabilité visible** : `coverage` = part du poids total réellement évaluée ; `reliability` = élevée (≥ 70 %), moyenne (≥ 40 %), faible. Un score sur 20 % des critères n'a pas la solidité d'un score sur 90 %.
4. **Faits validés uniquement** : le score se calcule sur la dernière version **validée** du CV maître (contrat `CandidateFactsReader`), jamais sur un brouillon d'import non relu. Sans profil validé : 409 `no_validated_profile`.
5. **Minimisation** : le moteur ne reçoit ni identité, ni coordonnées, ni texte libre du CV (voir `profile_facts`).

## Critères et poids par défaut (total 100)

| Critère | Poids | Évalué à partir de | Données manquantes si |
|---|---|---|---|
| Métier (`job_title`) | 20 | recouvrement entre l'intitulé de l'offre et les intitulés du profil (métiers recherchés, postes, titre pro) ; équivalences FR/EN | profil sans intitulé |
| Compétences (`skills`) | 25 | exigences de l'offre vs compétences du profil, 4 états | profil sans compétence, ou offre sans compétence identifiable |
| Expérience (`experience`) | 12 | années exigées vs durée cumulée du profil (fourchette) | offre sans exigence d'années, profil sans expérience |
| Formation (`education`) | 5 | niveau d'études exigé (Bac+N) vs diplôme le plus élevé reconnu | offre muette, ou diplômes de niveau non reconnu |
| Localisation (`location`) | 10 | ville / pays de l'offre vs préférences ; télétravail complet = neutre | préférences ou lieu de l'offre absents |
| Contrat (`contract`) | 5 | type de contrat vs préférences | l'un des deux absent |
| Salaire (`salary`) | 5 | sommet de la fourchette vs salaire souhaité | l'un des deux absent, **ou devises différentes** (aucune conversion) |
| Télétravail (`remote`) | 5 | mode de travail vs préférences (proche = 0,5) | l'un des deux absent |
| Ancienneté (`freshness`) | 3 | âge de l'annonce : ≤ 7 j = 1, décroît jusqu'à 0 à 180 j | date de publication inconnue |
| Exigences obligatoires (`mandatory_requirements`) | 10 | exigences que l'offre déclare **explicitement** obligatoires (compétences, années, diplôme) | aucune exigence marquée obligatoire |

`score = 100 × Σ(poids × note) / Σ(poids des critères évalués)`. Un poids à 0 désactive le critère (il disparaît du résultat). Les poids sont personnalisables (Paramètres, `PUT /matching/weights`) : seuls les rapports comptent.

## Compétences : quatre états

| État | Sens |
|---|---|
| **présente** | la compétence exigée figure au profil, ou un synonyme connu (`Postgres` → `PostgreSQL`, `JS` → `JavaScript`) |
| **partielle** | une compétence proche du même domaine figure au profil (ex. MySQL exigé, PostgreSQL au profil) : vaut 0,5 |
| **absente** | exigée par l'offre et introuvable au profil. **Ne prouve pas** que la personne ne la maîtrise pas |
| **non vérifiable** | exigence qu'on ne sait pas comparer (« esprit d'équipe ») : affichée, **jamais pénalisée** |

Pondération des exigences dans la note : obligatoire ×2, attendue ×1, souhaitée / citée ×0,5.

## Lecture des exigences d'une offre (règles, sans IA)

Une offre n'est pas structurée. `offer_requirements.py` extrait ce qui est **explicite** :

- **Rubriques** (FR/EN) : « Requirements », « Profil recherché », « Nice to have », « Atouts »… donnent l'importance (obligatoire / attendue / optionnelle). Un marqueur explicite dans la ligne (« requis », « minimum », « souhaité ») l'emporte sur la rubrique. Missions, avantages, présentation ne sont **pas** des exigences.
- **Années d'expérience** : « minimum 3 ans d'expérience », « 5+ years of experience », « 3 à 5 ans »… (le plus petit minimum) ; « débutant accepté » = 0.
- **Niveau d'études** : Bac+N, Licence/Bachelor, Master/Ingénieur, Doctorat… (le plus bas niveau cité).
- **Compétences** : jetons techniques (`C++`, `.NET`, `Node.js`), sigles (`SQL`, `AWS`) et, seulement en énumération ou ligne courte, mots capitalisés (`Docker`). Une phrase de prose ne livre pas de compétences.

### Expérience et dates partielles

Une année seule n'est jamais complétée. La durée cumulée est une **fourchette** (borne basse : début le plus tard / fin le plus tôt ; borne haute : l'inverse), chevauchements comptés une fois. Exigence satisfaite si la borne basse l'atteint ; **incertaine** (`uncertain`, note 0,9, « précisez les mois ») si seule la borne haute l'atteint.

## Persistance et lecture

- `job_match_scores` : un score par (offre, version de profil, version de poids), `breakdown` JSONB complet. Recalculer remplace (upsert) ; les scores d'une autre version de profil ou de poids sont purgés au recalcul.
- `matching_settings` : pondérations personnalisées du propriétaire (distinctes du profil : les modifier ne crée pas de version du CV).
- La recherche d'offres joint `job_match_scores` en lecture seule (tri `score_desc`, filtre `min_score`, colonne de score). Jointure volontaire entre contextes (modèle de lecture) pour trier côté base sans charger les offres en mémoire.
- Une offre **sans score** n'est pas « mauvaise » : elle passe après les offres notées et est exclue d'un filtre `min_score`.

## Performance (mesurée)

Calcul ≈ 1,2 ms par offre ; recalcul complet de 5 000 offres (calcul + écriture) ≈ 6,5 s, par lots de 200 hors de la boucle d'événements, mémoire bornée. Aujourd'hui synchrone et à la demande ; la planification automatique relève de l'EPIC 015.

## Limites connues

- Les exigences sont lues par règles : une offre très atypique (prose sans rubrique, listes lowercase) donnera moins d'exigences repérées, donc moins de critères évalués (la fiabilité le dit). L'analyse sémantique des offres relève de l'EPIC 011.
- Un nom propre capitalisé dans une énumération d'exigences peut être pris pour une compétence « absente » ; l'interface rappelle qu'une absence n'est pas une incompétence.
- Les langues exigées ne sont pas scorées. Aucune conversion de devises. Pas de calcul de distance (pas de géocodage) : la localisation compare villes et pays.
- Le score dépend de la date (ancienneté, expérience en cours) : il se recalcule à la demande.
- Les règles ont été validées sur des offres fictives et sur la pile complète ; **aucune offre réelle** n'a encore été évaluée (aucune source réelle n'est branchée).
