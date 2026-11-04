# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Numérotation : voir `docs/engineering/RELEASE_PLAN.md`. **Aucune version n'a été publiée** (ni tag, ni release GitHub) : l'entrée ci-dessous est une version candidate préparée, non déclarée stable.

## [0.5.0-rc.1] — candidate, non publiée (2026-11-04)

Couvre les jalons 0.1 à 0.5 du plan de releases. La version **1.0** (stable) n'est pas atteinte : voir « Limites connues ».

### Ajouté

- **Fondations** : monorepo `frontend/` (Next.js, TypeScript strict) et `backend/` (FastAPI, Python 3.13), PostgreSQL, Docker Compose sur `127.0.0.1`, scripts, CI, design system sombre et clair.
- **Profil maître** : import de CV (PDF, DOCX, TXT), relecture, validation humaine, versions immuables, journal des modifications.
- **Offres** : modèle normalisé, déduplication multi-sources, cycle de vie, connecteurs Greenhouse et Lever, lecture de pages publiques conforme à `robots.txt`, saisie manuelle, recherche filtrée et paginée, recherches sauvegardées.
- **Compatibilité** : score expliqué et pondérable ; analyse d'offre par règles.
- **IA facultative** : passerelle hybride (modèle local Ollama, API Gemini) avec plafonds obligatoires, consentement, cache, journal ; paliers gratuits exclus des données personnelles.
- **CV et lettres** : génération LaTeX/PDF, contrôle strict des faits, audit ATS, audit éditorial, versions, téléchargement PDF et LaTeX ; reformulation facultative des réalisations (locale ou IA) avec garde-fou ; correcteur orthographique hors ligne. Pages **Espace CV** et **Lettres de motivation**.
- **Candidatures** : suivi (tableau, Kanban, historique, contacts, relances), envoi toujours confirmé manuellement, tableau de bord d'accueil.
- **Automatisation** : planificateur, notifications, résumé quotidien.
- **Entretiens** : préparation sans IA (questions, présentation, trames de réponse), simulation avec retours, fiches d'entretien et brouillon de relance, IA facultative à la demande.
- **Sécurité, confidentialité, exploitation** : corrélation, logs JSON masqués, en-têtes de sécurité, limites de taille et de débit, santé et mesures, modèle de menaces, export ZIP, effacement confirmé, conservation, politique d'envoi des données personnelles à l'IA, frontière de confiance des prompts, contrôle des PDF générés.
- **Recherche multi-sources** : `POST /api/v1/search` interroge en parallèle les sources compatibles (entreprises suivies, sources officielles configurées), agrège sans doublon, rapporte chaque source et ses erreurs ; `GET /api/v1/sources` et panneau « Sources de données » ; filtre de collecte par intitulés visés et mots-clés ; bouton « Interroger les sources » et liste des sources interrogées.
- **Recherche** : filtres par langue de l'annonce et par expérience exigée (déduite de l'annonce, migration 0012 ; exigence inconnue = offre conservée), recherche multilingue français ↔ anglais par lexique fermé, saisie des intitulés visés pour interroger les sources.
- **Budget IA** : plafond journalier par fournisseur appliqué avant chaque appel, alertes de seuil affichées dans le Centre IA, estimation du coût maximal d'une opération sans appel de modèle.
- **Budget IA (suite)** : plafonds journaliers par tâche (migration 0013), coût maximal affiché avant chaque opération IA (résumé d'offre, entretien, reformulation du CV), reformulation des réalisations regroupée par lots bornés.
- **Consommation IA** : en mode économique, le fournisseur le moins cher est essayé en premier ; garde-fous CI (repli sans IA, schéma JSON strict et sortie bornée pour chaque tâche).
- **International (EPIC 017, première partie)** : référentiel géographique (pays, langues officielles, devises) adossé à Babel, préférences générales et de mobilité (migration 0014), page « Paramètres généraux », interface française et anglaise (next-intl, navigation et paramètres), couverture géographique des sources affichée, recherche multi-pays, sponsoring de visa et droit de travailler déduits des annonces (migration 0015), équivalents FR↔EN des compétences. ADR-0021.
- **International (suite)** : dates et nombres selon la langue, le pays et le fuseau choisis ; cadre de l'application traduit ; préférences de notification (e-mail avec accord explicite) et panneau stockage/sauvegarde dans les paramètres ; lecture de pages publiques à débit limité (`Crawl-delay`) avec cache.
- **Ergonomie** : suivi d'une offre avec confirmation et possibilité de retirer une candidature (`DELETE /applications/{id}`) ; Kanban sur deux rangées défilantes ; bouton « retour » sur toutes les vues ; graphique de la dépense IA par jour avec le plafond journalier ; suggestions dans les champs de recherche (`GET /offers/suggestions`) ; recherche par mots dans n'importe quel ordre et sans accents ; « Rechercher » interroge aussi les sources ; ajout d'une autre entreprise depuis la page de recherche ; **poste + entreprise + lieu** : la recherche retrouve le site carrières public de l'entreprise tapée (Greenhouse, Lever), la suit si le nom correspond et ne lit que ses offres, avec l'intitulé et le lieu comme filtres.
- **Sources d'offres** : connecteurs **Ashby** et **Workable** (API publiques de lecture, sans clé), reconnus par l'adresse de la page carrières et trouvés par la recherche par nom d'entreprise (migration 0016). SmartRecruiters reste non supporté (`robots.txt` de l'API restrictif).
- **Qualité** : suite de tests backend et frontend, parcours E2E complets (vraie API, vraie base, vrai pdfLaTeX), accessibilité vérifiée (deux thèmes, trois tailles), tests de volume, de pagination et de concurrence, mesure de couverture.

### Corrigé

- La file de tâches échouait à partir de la 6ᵉ tâche mise en file sur une même connexion (prédicat d'index partiel de `ON CONFLICT` passé en paramètres) ; révélé par un test de charge.
- Une règle de contrôle des PDF trop stricte aurait refusé tous les PDF produits par pdfLaTeX (`/OpenAction` de destination posé par hyperref).
- Plusieurs défauts des générateurs de CV, lettres et du suivi de candidatures (audits des EPIC 012, 013, 014).

### Limites connues

- **Pas d'authentification** ni de multi-utilisateur (ADR-0008) : exécution locale uniquement.
- **Internationalisation** (EPIC 017) non réalisée : interface en français, pas de référentiel de pays ni de filtres multi-pays.
- **Sources d'offres** : seules Greenhouse, Lever et la saisie manuelle fonctionnent ; l'API France Travail est bloquée par le fournisseur (`docs/DATA_SOURCES.md`).
- Voir `docs/engineering/QUALITY_REPORT.md` pour la liste complète et les tâches du backlog encore ouvertes.
