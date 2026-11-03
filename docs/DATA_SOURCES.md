# Sources de données (TASK-006-14, 006-15)

Principe (ADR-0006) : sources **gratuites et publiques** uniquement, accès autorisé, aucun contournement de CAPTCHA, d'authentification, de restriction ou d'anti-bot.

**Statut :** aucune source réelle n'est encore intégrée. Aucune n'est présentée comme opérationnelle.

## Intégrées, configurées et testées

Aucune source n'a été testée contre un service réel : les connecteurs ci-dessous sont **implémentés et testés sur des fixtures** (réponses fictives de même forme), sans appel au service réel. Un premier appel réel (lecture d'un job board public choisi par l'utilisateur) reste à effectuer et à consigner ici.

| Connecteur | Fichier | Accès | Vérifié le |
|---|---|---|---|
| Greenhouse Job Board (par entreprise) | `infrastructure/ats/greenhouse.py` | GET public `https://boards-api.greenhouse.io/v1/boards/{jeton}/jobs?content=true`, sans authentification. Pagination non documentée pour les offres, débit non documenté : 1 requête/s, filtrage local | 2026-11-03, documentation officielle (docs.greenhouse.io/job-board) |
| Lever Postings (par entreprise) | `infrastructure/ats/lever.py` | GET public `https://api.lever.co/v0/postings/{entreprise}?mode=json` (instance EU : `api.eu.lever.co`), sans clé pour la lecture, HTTPS obligatoire, offres publiées uniquement | 2026-11-03, documentation officielle (github.com/lever/postings-api) |
| Données structurées `JobPosting` | `infrastructure/jsonld.py` | Lecture du JSON-LD d'une page déjà récupérée | — |
| Lecture de pages publiques | `infrastructure/public_pages.py` | HTTPS, SSRF contrôlé, `robots.txt` respecté, arrêt sur refus ou défi anti-robot | — |

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
| Ashby, SmartRecruiters, Workable | Monde | À confirmer par fournisseur avant intégration | Non étudiées (TASK-006-23) |

## Blocage connu

**TASK-006-16** (obtenir et configurer les accès) dépend d'une action du propriétaire : créer un compte développeur auprès du fournisseur retenu et fournir les identifiants dans `.env` (jamais dans Git). Tant que ce n'est pas fait, aucun connecteur réel ne peut être testé, et les tâches 006-17 à 006-19 restent en attente. Les tâches indépendantes (framework, résilience) avancent.

## Règle de vérification d'une source

Avant tout connecteur, consigner ici : URL de la documentation officielle, gratuité, authentification, quotas, conditions de réutilisation et mentions obligatoires, date de vérification. Sans cette fiche, pas de connecteur.
