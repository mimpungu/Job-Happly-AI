# ADR-0014 — Architecture du générateur de lettres de motivation et audit qualité

- **Statut :** Accepté
- **Date :** 2026-11-04

## Contexte

L'EPIC 013 a pour objectif de concevoir et générer des lettres de motivation personnalisées, professionnelles et percutantes, conformément au prompt maître `docs/HAPPLY_AI_COVER_LETTER_PROMPT.md` et à la spécification `docs/HAPPLY_AI_MASTER_SPEC.md` §11.
Les exigences majeures sont :
1. Une structure stricte en 4 parties (Introduction accrocheuse, Valorisation du parcours, Valeur ajoutée et motivation, Conclusion et demande d'entretien).
2. Un calibrage rigoureux sur une seule page (250 à 350 mots ciblés).
3. L'interdiction absolue d'inventer des faits (anti-hallucination stricte vis-à-vis du profil maître).
4. La détection et le bannissement des clichés creux et formules artificielles ("extrêmement motivé", "candidat idéal", etc.).
5. Le support bilingue (français et anglais) avec adaptation des formules de salutation, de politesse et du ton selon le pays cible.
6. La compilation LaTeX locale et sécurisée avec téléchargement PDF/source, versioning immuable et comparaison de versions (`diff`).

## Décision

1. **Modèle de domaine et gabarit LaTeX dédié (`CoverLetterContent` & `render_latex_cover_letter`)** :
   - Gabarit épistolaire sobre et élégant basé sur la classe `article` avec marges soignées (2cm).
   - En-tête standardisé à deux blocs : coordonnées de l'expéditeur à gauche, coordonnées du destinataire à droite.
   - Mention explicite du lieu et de la date, objet du poste visé, formule de salutation personnalisée.
   - Corps en 4 paragraphes aérés, formule de politesse adaptée (FR/EN) et signature.
   - Échappement des caractères spéciaux TeX via `latex_escape` garantissant l'intégrité des caractères accentués UTF-8.

2. **Extraction de contexte et génération déterministe (`CompanyOfferContext` & `generate_cover_letter_content`)** :
   - Extraction des informations clés de l'offre (titre, entreprise, localisation, secteur, mots-clés, responsabilités).
   - Sélection ciblée des compétences et expériences du profil maître les plus pertinentes sans inventer aucun fait ni chiffre imaginaire.
   - Adaptation du ton et des formulations selon la langue sélectionnée (`fr` ou `en`) et le pays.

3. **Audit éditorial et détection des clichés (`audit_cover_letter`)** :
   - Analyse automatique du texte produit selon la grille sur 100 points du prompt maître :
     - Pertinence par rapport au poste (30 points).
     - Personnalisation et ciblage de l'entreprise (25 points).
     - Valorisation du parcours sans répétition brute du CV (20 points).
     - Qualité rédactionnelle et détection des clichés (15 points).
     - Clarté, structure et respect de la longueur optimale (10 points).
   - Détection des clichés creux interdits entraînant des pénalités explicites et un rejet de validation (`passed = False`) si un cliché est présent.

4. **Service applicatif et compilation (`CoverLetterService`)** :
   - Orchestration complète : création du document avec type `cover_letter`, compilation initiale via `IsolatedLaTeXCompiler`, calcul du hash SHA-256 et stockage du PDF dans `LocalDocumentStorage`.
   - Support de la recompilation manuelle d'une version éditée par l'utilisateur (création d'une nouvelle version immuable incrémentée).
   - Comparaison visuelle unifiée (`difflib`) entre deux versions du source LaTeX.

5. **Exposition REST (`/api/v1/cover-letters`)** :
   - Endpoints pour générer une lettre, recompiler une version modifiée, télécharger le PDF ou le source LaTeX, lister les versions, inspecter les détails et comparer deux versions.

## Alternatives étudiées

- **Format Markdown ou texte brut seul** : rejeté car l'envoi d'une candidature professionnelle nécessite un document PDF prêt à l'emploi avec une typographie irréprochable et un code LaTeX modifiable sous Overleaf.
- **Rédaction non contrainte par IA** : rejetée car risquant d'introduire des formulations clichées, un style pompeux ou des hallucinations factuelles. Le cadre déterministe avec grille d'audit sur 100 points garantit un contrôle qualité systématique.

## Conséquences

- Les lettres générées complètent parfaitement le CV sans redondance textuelle.
- L'audit qualité fournit un retour immédiat sur la conformité de la lettre avant soumission.
- La chaîne de compilation réutilise l'infrastructure sécurisée de l'EPIC 012 sans duplication.


## Révision du 2026-11-04 — audit et corrections

Un audit avec génération, compilation et exécution des tests d'intégration sur PostgreSQL a
montré que l'EPIC 013 ne tenait pas ses promesses. Décisions correctives :

1. **Aucun fait inventé** : l'ancien générateur affirmait « compétences solides », « rigueur
   éprouvée », « résultats mesurables », une ville « France » par défaut et un poste
   « Ingénieur » par défaut. Chaque phrase est désormais bâtie sur un champ du profil validé
   ou de l'offre (période, intitulé, société, réalisations citées telles quelles) ; les
   formulations sont neutres en genre ; aucune compétence absente du profil n'est citée.
2. **Contrôle des faits bloquant** (`verify_letter_facts`) : employeurs, intitulés, compétences,
   réalisations, diplômes et coordonnées doivent exister dans le profil maître ; tout nombre du
   texte généré doit provenir du profil ou de l'offre. Les textes saisis par l'utilisateur
   (`custom_opening`, `motivation`) ne sont pas jugés. `cv_coherent` est calculé (il valait
   toujours « vrai »).
3. **Audit réel** : grille sur 100 réellement évaluée (pertinence, personnalisation, parcours,
   rédaction, structure), longueur 250–350 mots, une page vérifiée sur le PDF compilé (la mise en
   page est resserrée si la lettre déborde, jamais coupée). Une version éditée est auditée sur le
   texte du PDF ; l'ancien faux score `{"score": 85}` est supprimé.
4. **Langues et pays** : `fr` et `en` seulement (toute autre langue est refusée au lieu de produire
   du français étiqueté autrement) ; salutation, formule de politesse et date selon le pays,
   pays de l'offre utilisé par défaut ; libellés « Objet » / « Subject ».
5. **Sélection** : expériences et compétences choisies par pertinence avec la même logique que le
   CV (`content_selection`), et non « la première expérience ».
6. **Architecture** : profil **validé** uniquement ; accès aux données derrière
   `GenerationInputsPort` (les clés d'analyse d'offre étaient mal lues) ; `DocumentLibrary`
   commune au CV et à la lettre (un CV n'est plus servi comme une lettre) ; routes minces ;
   erreurs centralisées ; réponse de génération enrichie (texte, audit, traçabilité).
7. **Prompt versionné** : empreinte du document source contrôlée par un test, version journalisée
   avec chaque lettre.
8. **Template** : `cmap` avant `fontenc`, lien `mailto` correctement échappé, bloc destinataire
   omis s'il est vide.

Limites assumées : la lettre produite sans IA est factuelle mais sobre (≈ 130 mots) ; les 250 à
350 mots visés s'obtiennent avec le champ `motivation` ou une future rédaction par IA (accord
utilisateur et plafond de coût requis). Pas de correction orthographique par dictionnaire
(dépendance à valider). Aucune recherche externe sur l'entreprise.
