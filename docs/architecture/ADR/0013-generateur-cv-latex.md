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

