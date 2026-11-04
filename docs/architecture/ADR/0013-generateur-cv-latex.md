# ADR-0013 — Architecture du générateur de CV LaTeX et contrôle ATS

- **Statut :** Accepté
- **Date :** 2026-11-04

## Contexte

L'EPIC 012 a pour objectif de produire des CV personnalisés, professionnels et compatibles avec les contraintes sévères des logiciels ATS (Applicant Tracking Systems), conformément au prompt maître `docs/HAPPLY_AI_CV_GENERATION_PROMPT.md` et à la spécification `docs/HAPPLY_AI_MASTER_SPEC.md` §10.
Les contraintes clés sont :
1. Mise en page strictement mono-colonne pour un parsing linéaire direct (haut en bas).
2. Aucune invention de faits (anti-hallucination stricte : entreprises, diplômes, compétences non sourcés sont interdits).
3. Compilation LaTeX locale et isolée (dossier temporaire, désactivation du shell-escape, absence d'accès réseau, quotas de taille et timeout).
4. Audit ATS automatisé du PDF compilé (extraction texte via pypdf, contrôle de l'ordre de lecture, préservation des accents français).
5. Immuabilité des versions de documents et liaison avec l'offre d'emploi ciblée.

## Décision

1. **Modèle de domaine et template déterministe** :
   - Classe `article`, packages standards (`geometry`, `lmodern`, `inputenc`, `fontenc` T1, `titlesec`, `enumitem`, `hyperref`, `cmap`).
   - Structure mono-colonne stricte sans tableaux de mise en page, sans minipages côte à côte, sans multicolonnes.
   - Échappement en une seule passe (`latex_escape`) de tous les caractères spéciaux TeX tout en préservant l'encodage UTF-8 et les accents français.
   - Adaptation paramétrée de la longueur (`one_page` vs `two_pages` vs `auto`).

2. **Sélection et Fact-Checking** :
   - Contexte de génération combinant profil maître et offre d'emploi.
   - Algorithme déterministe de scoring et réorganisation des compétences/expériences pertinentes.
   - Contrôleur de faits `verify_facts` / `assert_facts_verified` garantissant qu'aucune entité non présente dans le profil maître ne peut être injectée.

3. **Service de compilation isolé (`IsolatedLaTeXCompiler`)** :
   - Exécution asynchrone non bloquante (`asyncio.to_thread`) de `pdflatex`.
   - Arguments sécurisés : `-no-shell-escape`, `-interaction=nonstopmode`, `-halt-on-error`.
   - Isolation dans un dossier temporaire dédié (`tempfile.TemporaryDirectory`) auto-nettoyé.
   - Limite de taille source (1 Mo) et timeout d'exécution (15s par défaut).

4. **Audit qualité ATS (`analyze_pdf_ats`)** :
   - Extraction du texte sélectionnable via `pypdf`.
   - Vérification de l'intégrité des caractères accentués français.
   - Vérification de la présence des rubriques standards et de l'ordre séquentiel.
   - Calcul d'un score de conformité ATS (0-100) et génération d'un rapport structuré `ATSReport`.

5. **Persistance et exports REST** :
   - Documents logiques (`generated_documents`) associés ou non à une offre (`offer_id`).
   - Versions immuables (`document_versions`) avec calcul de hash SHA-256 et stockage du PDF dans `LocalDocumentStorage`.
   - Endpoints pour générer, recompiler une version modifiée, télécharger le PDF, télécharger le source LaTeX, comparer deux versions et auditer un PDF.

## Alternatives étudiées

- **Moteurs HTML vers PDF (WeasyPrint / Puppeteer)** : rejeté car LaTeX est le standard exigé par la spécification (§10) pour sa qualité typographique et son rendu Overleaf directement éditable par l'utilisateur.
- **Compilation via API cloud externe** : rejeté pour préserver la confidentialité totale des données personnelles du candidat et respecter l'exécution 100% locale sans frais tiers.

## Conséquences

- Les développeurs doivent disposer de `pdflatex` (TeX Live / MacTeX) ou de l'image conteneur pour la compilation réelle.
- Le CV maître n'est jamais altéré lors de la production de versions ciblées.


## Révision du 2026-11-04 — audit et corrections

Un audit avec compilation et extraction réelles a montré que plusieurs contrôles annoncés ne
l'étaient pas. Décisions correctives :

1. **Sécurité de la compilation** (CLAUDE.md §11) : liste de refus statique des commandes et
   paquets qui lisent ou écrivent des fichiers (`latex_safety`), TeX en mode paranoïaque
   (`openin_any=p`, `openout_any=p`, `shell_escape=f`), environnement minimal (aucune clé d'API
   transmise), limites CPU/mémoire/taille, groupe de processus tué au délai, espace réseau vide
   via `unshare --net` quand le système l'autorise (sinon avertissement journalisé). Limite
   assumée : l'isolation par conteneur dédié n'est pas faite ; la barrière réseau est
   best-effort, le shell-escape coupé restant la protection principale.
2. **Audit ATS fondé sur la géométrie réelle** : détection des colonnes par le flux de lecture et
   la position des fragments, rubriques reconnues sur des lignes de titre, ordre réel des
   rubriques, accents vérifiés sur les textes du profil, marges, polices, pages, images.
3. **Aucun fait inventé** : accroche sans chiffre ni qualificatif, contrôle champ par champ des
   expériences, formations, certifications, langues et réalisations, chiffres de l'accroche
   rattachés au profil. Le CV n'est généré que depuis un **profil validé**.
4. **Caractères** : symboles remplacés, emojis retirés, latin rare réduit à sa base, écritures
   non latines refusées explicitement (pdfLaTeX) ; `cmap` chargé avant `fontenc`, sans quoi
   « œ » ressort en « ÷ ». Piste ultérieure : XeLaTeX pour le cyrillique, le grec ou le CJK.
5. **Mots-clés** : lecture des clés réelles de l'analyse d'offre (`mandatory_skills`,
   `expected_skills`, `desired_skills`, `technologies`) et normalisation partagée avec le matching.
6. **Architecture** : accès aux données derrière `GenerationInputsPort`, routes minces, erreurs
   traduites centralement, compilateur résolu à l'usage (consulter un CV n'exige pas TeX).
7. **Déploiement** : TeX Live dans l'image Docker et la CI, volume pour les documents.

8. **Reformulation facultative (012-08)** : `rewrite_mode` = `none` (défaut), `local` ou `ai`.
   Elle passe par `AIGateway` (consentement, plafonds, cache, journal) via `ResumeRewriterPort` ;
   la requête est marquée « données personnelles » (aucun palier gratuit qui réutilise les
   contenus) et ne contient que le texte des réalisations. `local` s'appuie sur la nouvelle
   restriction `AIRequest.allowed_kinds`, qui ne peut que *réduire* le réglage de l'utilisateur.
   Garde-fou déterministe (`resume_rewrite`) : une reformulation est écartée si elle ajoute un
   chiffre, un nom propre, un sigle ou une technologie absents de l'original et du profil, si
   elle est trop longue ou multi-lignes. Le contrôle des faits accepte une réalisation
   reformulée uniquement si elle est déclarée comme reformulation de son original. Refus de l'IA
   (désactivée, plafond, consentement, panne) : génération poursuivie avec le texte d'origine et
   statut consigné dans `generation.ai_rewrite`. Limite : l'accroche reste déterministe.

Reste à faire : interface frontend de génération.
