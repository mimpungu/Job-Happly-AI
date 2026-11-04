# Sources de données (TASK-006-14, 006-15)

Principe (ADR-0006) : sources **gratuites et publiques** uniquement, accès autorisé, aucun contournement de CAPTCHA, d'authentification, de restriction ou d'anti-bot.

**Statut :** quatre sources publiques d'ATS (Greenhouse, Lever, Ashby, Workable) sont intégrées et ont été appelées en réel ; la saisie manuelle fonctionne sans réseau ; l'API France Travail est bloquée par le fournisseur. Aucune autre source n'est présentée comme opérationnelle.

## Intégrées, configurées et testées

Greenhouse et Lever ont été appelés en réel le 2026-11-04 (découverte de Stripe, Datadog, Spotify ; collecte réelle de Datadog et Spotify : 484 offres, relance sans doublon). Ashby et Workable ont été appelés en réel le 2026-11-04 (board public d'Ashby : 71 offres, salaires annuels extraits ; compte Workable de Blueground : 9 offres, trouvé par la recherche par nom). Les tests automatisés restent sur fixtures, sans réseau. Les autres sources (France Travail, pages carrières) n'ont pas été testées en réel.

| Connecteur | Fichier | Accès | Vérifié le |
|---|---|---|---|
| Greenhouse Job Board (par entreprise) | `infrastructure/ats/greenhouse.py` | GET public `https://boards-api.greenhouse.io/v1/boards/{jeton}/jobs?content=true`, sans authentification. Pagination non documentée pour les offres, débit non documenté : 1 requête/s, filtrage local | 2026-11-03, documentation officielle (docs.greenhouse.io/job-board) |
| Lever Postings (par entreprise) | `infrastructure/ats/lever.py` | GET public `https://api.lever.co/v0/postings/{entreprise}?mode=json` (instance EU : `api.eu.lever.co`), sans clé pour la lecture, HTTPS obligatoire, offres publiées uniquement | 2026-11-03, documentation officielle (github.com/lever/postings-api) |
| Ashby Job Postings (par entreprise) | `infrastructure/ats/ashby.py` | GET public `https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true`, sans authentification ; 404 si le board n'existe pas. Pas de détail par offre (le détail relit le board), offres `isListed = false` ignorées. Pays fourni en toutes lettres : aucun code ISO déduit. Salaire retenu seulement s'il existe une unique composante annuelle. Débit non documenté : 1 requête/s, filtrage local | 2026-11-04, documentation officielle (developers.ashbyhq.com/docs/public-job-posting-api) ; `robots.txt` de jobs.ashbyhq.com n'interdit que `/api/`, `/b/`, `/meeting/` (l'API est sur api.ashbyhq.com) |
| Workable (par compte) | `infrastructure/ats/workable.py` | Endpoint public documenté `GET https://www.workable.com/api/accounts/{compte}?details=true` (« Public Endpoints », sans authentification) ; il redirige (302) vers `https://apply.workable.com/api/v1/widget/accounts/{compte}`, appelé directement car les redirections ne sont jamais suivies. 404 si le compte n'existe pas. Pas de détail public par offre (le détail relit la liste). Code pays ISO pris dans `locations[].countryCode` s'il est unique ; `telecommuting = false` reste « inconnu » (sur site ou hybride). Débit non documenté : 1 requête/s | 2026-11-04, documentation officielle (workable.readme.io/reference/jobs-1) ; `robots.txt` d'apply.workable.com autorise tout |
| France Travail, Offres d'emploi v2 (API officielle) | `infrastructure/france_travail.py` | OAuth2 « client credentials » (`HAPPLY_FRANCE_TRAVAIL_CLIENT_ID` / `_SECRET`, scope `api_offresdemploiv2 o2dsoffre`), GET `/offresdemploi/v2/offres/search` (plage ≤ 150, ≤ 1150 résultats par recherche, 204 = aucun résultat, 206 = partiel), débit limité à 2 requêtes/s | **BLOQUÉE : l'API est retirée du portail** (annonce constatée le 2026-11-04 : France Travail analyse ses modalités de distribution après des usages automatisés massifs ; accès sur demande via le formulaire de contact de francetravail.io). Le connecteur reste en place, désactivé de fait faute d'identifiants, et n'a jamais été appelé en réel : écrit d'après la connaissance de l'API (portail illisible automatiquement), testé sur fixtures fictives. À valider avec de vrais identifiants et la documentation officielle. |
| Données structurées `JobPosting` | `infrastructure/jsonld.py` | Lecture du JSON-LD d'une page déjà récupérée | — |
| Saisie manuelle | `application/manual_offers.py` | Aucun accès réseau : l'utilisateur copie l'adresse et le texte d'une offre qu'il a lue dans son navigateur. Source `manual`, migration 0006 | 2026-11-04, testé (unitaires + intégration) |
| Lecture de pages publiques | `infrastructure/public_pages.py` | HTTPS, SSRF contrôlé, `robots.txt` respecté, arrêt sur refus ou défi anti-robot ; débit limité à 1 requête/s par hôte, `Crawl-delay` respecté (au-delà de 30 s : source non supportée), cache borné de 15 min (pages réussies seulement) | — |

Points de vigilance :
- Les résumés de documentation ont été obtenus par lecture automatique : relire la page officielle avant de s'appuyer sur un détail de quota ou de format.
- Ne jamais utiliser les endpoints de candidature (POST) de ces services : l'envoi reste manuel.
- Le jeton d'une entreprise (identifiant de son job board) est public ; il est tout de même validé strictement avant d'entrer dans une URL.
- Les conditions d'utilisation d'une page carrières ne sont pas lisibles par une machine : une personne doit les vérifier (`tos_verified_at`) avant d'activer la lecture d'un site non ATS.

## Candidates à étudier

> Les informations ci-dessous viennent de la connaissance générale de l'équipe et **n'ont pas été vérifiées** auprès des documentations officielles (la page de France Travail est rendue par JavaScript et n'a pas pu être lue automatiquement). Chaque point doit être confirmé avant d'écrire le connecteur correspondant, et consigné ici avec la date de vérification.

| Source | Pays | Accès à vérifier | Statut |
|---|---|---|---|
| France Travail — API « Offres d'emploi » | FR | Inscription sur le portail développeurs, identifiants OAuth2 ; gratuité, quotas et conditions de réutilisation à confirmer | **À étudier** — candidate pour la première source française |
| APEC, HelloWork, Welcome to the Jungle, Indeed | FR | API publique ou partenaire non confirmée ; ne pas supposer d'accès | Non étudiée |
| EURES | Europe | À étudier (TASK-017-20) | Non étudiée |
| SmartRecruiters (Posting API) | Monde | Étudiée le 2026-11-04 : `GET https://api.smartrecruiters.com/v1/companies/{entreprise}/postings` répond sans clé, mais le `robots.txt` d'api.smartrecruiters.com interdit `/v1/companies/` à tous les robots sauf LinkedInBot, et la documentation (developers.smartrecruiters.com/docs/posting-api) présente une authentification par clé API ou OAuth2. Une entreprise inexistante répond 200 avec une liste vide (découverte par nom peu fiable) | **Non supportée** (décision du propriétaire, 2026-11-04) : à reconsidérer avec une clé officielle ou un accord explicite |

## Blocage connu

**TASK-006-16** (obtenir et configurer les accès) dépend d'une action du propriétaire : créer un compte développeur auprès du fournisseur retenu et fournir les identifiants dans `.env` (jamais dans Git). Tant que ce n'est pas fait, aucun connecteur réel ne peut être testé, et les tâches 006-17 à 006-19 restent en attente. Les tâches indépendantes (framework, résilience) avancent.

## Règle de vérification d'une source

Avant tout connecteur, consigner ici : URL de la documentation officielle, gratuité, authentification, quotas, conditions de réutilisation et mentions obligatoires, date de vérification. Sans cette fiche, pas de connecteur.
