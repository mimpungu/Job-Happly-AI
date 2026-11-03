# Sources de données (TASK-006-14, 006-15)

Principe (ADR-0006) : sources **gratuites et publiques** uniquement, accès autorisé, aucun contournement de CAPTCHA, d'authentification, de restriction ou d'anti-bot.

**Statut :** aucune source réelle n'est encore intégrée. Aucune n'est présentée comme opérationnelle.

## Intégrées, configurées et testées

Aucune.

## Candidates à étudier

> Les informations ci-dessous viennent de la connaissance générale de l'équipe et **n'ont pas été vérifiées** auprès des documentations officielles (la page de France Travail est rendue par JavaScript et n'a pas pu être lue automatiquement). Chaque point doit être confirmé avant d'écrire le connecteur correspondant, et consigné ici avec la date de vérification.

| Source | Pays | Accès à vérifier | Statut |
|---|---|---|---|
| France Travail — API « Offres d'emploi » | FR | Inscription sur le portail développeurs, identifiants OAuth2 ; gratuité, quotas et conditions de réutilisation à confirmer | **À étudier** — candidate pour la première source française |
| APEC, HelloWork, Welcome to the Jungle, Indeed | FR | API publique ou partenaire non confirmée ; ne pas supposer d'accès | Non étudiée |
| EURES | Europe | À étudier (TASK-017-20) | Non étudiée |
| Flux publics d'ATS (Greenhouse, Lever, Ashby, SmartRecruiters, Workable) | Monde | Flux de lecture publics par entreprise : à confirmer par fournisseur avant intégration | Non étudiée (TASK-006-23) |
| Données structurées `JobPosting` des pages carrières | Monde | Dépend de chaque site : `robots.txt` et CGU | Non étudiée (TASK-006-24) |

## Blocage connu

**TASK-006-16** (obtenir et configurer les accès) dépend d'une action du propriétaire : créer un compte développeur auprès du fournisseur retenu et fournir les identifiants dans `.env` (jamais dans Git). Tant que ce n'est pas fait, aucun connecteur réel ne peut être testé, et les tâches 006-17 à 006-19 restent en attente. Les tâches indépendantes (framework, résilience) avancent.

## Règle de vérification d'une source

Avant tout connecteur, consigner ici : URL de la documentation officielle, gratuité, authentification, quotas, conditions de réutilisation et mentions obligatoires, date de vérification. Sans cette fiche, pas de connecteur.
