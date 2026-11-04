# API REST — Happly AI

Base : `http://127.0.0.1:8000/api/v1`. Locale uniquement, sans authentification (ADR-0008) : tout passe par l'unique utilisateur local, créé à la première requête. La documentation interactive générée (OpenAPI) est disponible sur `/docs` en développement.

## Conventions

- Format JSON, versionnée dans l'URL.
- Montants (`salary_*`) sérialisés en **chaînes** décimales : aucune perte de précision.
- Une information absente vaut `null`, jamais `0` ni `""`.
- Erreurs normalisées, sans trace technique :

```json
{ "error": { "code": "validation_error", "message": "…", "details": [{ "field": "page_size", "message": "…" }] } }
```

| Statut | `code` | Cas |
|---|---|---|
| 404 | `offer_not_found`, `saved_search_not_found` | ressource absente (ou appartenant à un autre propriétaire) |
| 409 | `saved_search_duplicate` | nom déjà pris (insensible à la casse) |
| 422 | `validation_error`, `saved_search_invalid` | entrée invalide ; la valeur reçue n'est jamais renvoyée |
| 500 | `internal_error` | erreur inattendue (détail dans les logs uniquement) |
| 503 | `http_error` | base de données non configurée |

## Santé

`GET /health` → `{"status": "ok"}`.

## Offres collectées

### `GET /offers`

Recherche dans les offres déjà collectées, paginée côté base. Tous les paramètres sont facultatifs.

| Paramètre | Rôle |
|---|---|
| `text` | mots recherchés dans l'intitulé, l'entreprise ou la description : **chaque mot** doit figurer, dans n'importe quel ordre, sans tenir compte de la casse ni des accents (`%` et `_` sont littéraux) |
| `keywords` (répétable) | tous les mots-clés doivent figurer dans l'intitulé ou la description |
| `company`, `city` | sous-chaîne de l'entreprise / du lieu |
| `language` | langue de l'annonce (code ISO 639-1, variantes régionales acceptées) |
| `max_experience_years` | expérience exigée au plus N ans (0-40), déduite de l'annonce ; **les offres à exigence inconnue restent incluses** |
| `multilingual` | `true` : cherche aussi les équivalents français/anglais de `text` et `keywords` (lexique fermé, un terme inconnu est cherché tel quel) |
| `country_codes` (répétable) | codes ISO 3166-1 alpha-2 |
| `remote_types`, `employment_types` (répétables) | valeurs des énumérations de contrat et de télétravail |
| `salary_min` + `salary_currency` | seuil de salaire ; la devise est **obligatoire**, les offres sans salaire connu sont exclues |
| `published_since` | date ISO 8601 |
| `language` | `fr` retrouve aussi `fr-FR` |
| `statuses` (répétable) | défaut : `active` |
| `state` | `visible` (défaut : sans les offres ignorées), `saved`, `ignored`, `all` |
| `sort` | `published_desc` (défaut), `published_asc`, `title_asc`, `company_asc`, `salary_desc`, `recently_seen` |
| `page`, `page_size` | défaut 1 et 25 ; `page_size` ≤ 100 |

Réponse : `{items, total, page, page_size, page_count}`. Chaque offre liste ses `source_keys` (attribution des sources). Les ex æquo sont départagés par identifiant : les pages ne répètent ni ne sautent d'offre.

### `GET /offers/suggestions?field=title|company|city&q=…&limit=8`

Suggestions pour compléter un champ de recherche : valeurs **déjà présentes** dans les offres actives, les plus fréquentes d'abord, insensibles aux accents. Jamais de valeur inventée. `q` : 1 à 100 caractères.

### `GET /offers/{offer_id}`

Fiche détaillée : description, URL de candidature, dates et **sources** (clé, nom, URL, dernière observation, `still_listed`).

### `POST /offers/manual`

Ajoute une offre copiée à la main depuis un site (utile quand celui-ci bloque les robots, comme BNP Paribas). Aucune requête n'est faite vers le site d'origine. Corps : `title`, `description` (≥ 20 caractères), `application_url` (**https** obligatoire, sans identifiants), et facultatifs `company_name`, `location`, `country_code`, `employment_type`, `remote_type`, `published_at`. Réponse 201 : `{offer_id, created, merged, changed, already_known}`. L'adresse (sans fragment) identifie l'offre : la saisir deux fois ne crée pas de doublon (`already_known: true`). L'offre porte la source « Saisie manuelle » et suit ensuite la même normalisation, déduplication, recherche et le même score que les autres. 422 `manual_offer_invalid` si la saisie est refusée.

### `PUT /offers/{offer_id}/state`

Corps `{"state": "saved" | "ignored" | null}` → 204. Idempotent ; `null` retire l'état. Une offre ignorée est masquée par défaut mais reste retrouvable (`state=ignored`).

## Entreprises suivies et collecte

Aucune liste fermée d'entreprises : l'utilisateur tape un nom, l'application cherche le job board public correspondant.

| Route | Rôle |
|---|---|
| `POST /target-companies/discover` `{name}` | Sonde les API publiques Greenhouse, Lever, Ashby et Workable avec des jetons dérivés du nom. Ne persiste rien. Retourne `[{ats_kind, token, careers_url, board_name, offer_count}]` (liste vide si rien n'est trouvé). |
| `POST /target-companies` `{name, careers_url?, enabled?}` | Suit une entreprise (422 `company_invalid` si doublon ou source non supportée à l'activation). |
| `GET /target-companies` | Entreprises suivies, avec état de la dernière collecte. |
| `PATCH /target-companies/{id}` `{enabled}` | Active ou désactive (404 `company_not_found`). |
| `POST /collection/run` | Collecte en parallèle les entreprises activées ; bilan par source. 409 `no_company_enabled` si aucune. |
| `POST /search` `{filter?, titles?, refresh?}` | Recherche multi-sources : interroge **en parallèle** les entreprises activées et les sources officielles configurées dont la couverture (pays) correspond, enregistre les offres sans doublon, puis renvoie `{queried, status, sources[], results}` (offres agrégées paginées, bilan par source, erreurs nommées). `titles` : intitulés visés. `refresh:false` lit la base locale seule. Sans source activée : `queried:false`, jamais une erreur. Quand `filter.company` est renseigné, la recherche **lit le site carrières de cette entreprise** : `company_search` indique `tracked` (déjà suivie), `followed` (site Greenhouse, Lever, Ashby ou Workable trouvé dont le nom correspond : suivie automatiquement), `candidates` (sites trouvés au nom différent : proposés, jamais activés), `not_found` ou `disabled` (suivie mais désactivée : jamais réactivée sans l'utilisateur). Seule cette entreprise est lue ; l'intitulé (mots dans n'importe quel ordre) et le lieu filtrent à la collecte. `coverage` : `{requested, declared, undeclared, sources_without_declared_countries}`, la couverture géographique réelle des sources interrogées par rapport aux `country_codes` demandés. Refusé en mode démonstration. |
| `GET /sources` | Sources de données : clé, nom, pays, activation, `configured`/`requires_configuration`, `status` (`ok`, `error`, `unsupported`, `not_configured`, `never_checked`), dernier accès/succès/erreur, nombre d'offres. Une source officielle sans identifiants est listée « non configurée ». |
| `GET /sources?country=FR` | Ne garde que les sources qui déclarent ce pays **ou** dont la couverture n'est pas déclarée (`coverage_declared: false`, jamais présentée comme couvrante). |

Une source en échec n'affecte pas les autres (statut `partial`). Un refus d'accès (401/403) rend l'entreprise « non supportée » : jamais contourné. La découverte propose un résultat à confirmer : deux sociétés peuvent partager un jeton.

## France Travail (API officielle)

| Route | Rôle |
|---|---|
| `GET /france-travail/status` | `{configured}` : vrai si les deux identifiants sont présents dans l'environnement. Ne les révèle jamais. |
| `POST /france-travail/search` `{title?, company?, keywords?, city?, department?, max_pages?}` | Interroge la source et enregistre les offres (idempotent). Au moins un de `title`, `company`, `keywords`. `department` (ex. `75`) restreint la recherche côté source ; `city` et `company` affinent localement. 409 `source_not_configured` sans identifiants. |

Un échec de la source (identifiants refusés, quota, panne) est renvoyé dans `error_type` avec `succeeded: false`, jamais présenté comme « 0 offre ».

## IA (réglages et suivi)

Aucun appel de modèle n'est exposé : ces routes règlent et observent la plateforme IA (ADR-0011).

| Route | Rôle |
|---|---|
| `GET /ai/settings` | Mode (`disabled`, `economy`, `balanced`, `quality`), préférence (`local_only`, `api_only`, `hybrid`), limites par opération, plafonds, consentement, fournisseurs branchés, `paid_calls_possible`. |
| `PUT /ai/settings` | Modifie mode, préférence, limites par opération. |
| `PUT /ai/budget` | `{daily, monthly, currency, alert_thresholds}` : plafonds (> 0, 2 décimales, seuils 1–100 %). Seul l'utilisateur les change. |
| `PUT /ai/consent` | `{accepted}` : accord (ou retrait) d'envoi de données à une API payante. |
| `POST /ai/test` | `{level: 1\|2}` : passe un petit texte d'offre fictif et public par toute la chaîne (routage, accord, plafonds, appel, validation, journal, cache). Erreurs : 409 (`ai_disabled`, `ai_not_configured`, `ai_consent_required`, `ai_budget_not_defined`, `ai_budget_exceeded`), 502 (`ai_provider_failure`, `ai_invalid_output`, `ai_incomplete_output`). |
| `GET /ai/usage` | Dépense du jour et du mois (avec pourcentage du plafond), `daily_spend` (un point par jour du mois, jours sans dépense à 0), par fournisseur, derniers appels (refus et cache compris), et `alerts` : plus haut seuil d'alerte atteint par période, tant qu'il est franchi. |
| `PUT /ai/provider-caps/{provider}` | `{daily}` : plafond journalier d'un fournisseur payant, en plus des plafonds globaux (`null` le retire). 409 si le fournisseur payant n'existe pas. Visible dans `provider_daily_caps` des réglages. |
| `PUT /ai/task-caps/{task_type}` | `{daily}` : plafond journalier d'un type de tâche IA (`offer_summary`, `interview_questions`, `interview_review`, `cv_rewrite`), en plus des plafonds globaux ; `null` le retire. 409 si la tâche est inconnue. Visible dans `task_daily_caps` et `tasks` des réglages. |
| `POST /ai/estimate` | `{task_type}` (profil connu de la tâche) ou `{characters, level?, max_output_tokens?}` : coût maximal d'une opération et faisabilité (`allowed`, `reason`) sans appeler de modèle ni rien journaliser. Seule la taille du texte est envoyée. |

## Recherches sauvegardées

| Route | Rôle |
|---|---|
| `GET /saved-searches` | liste, triée par nom |
| `POST /saved-searches` | `{name, filter, active}` → 201 |
| `PATCH /saved-searches/{id}` | modification partielle (`name`, `filter`, `active`) |
| `DELETE /saved-searches/{id}` | → 204 ; l'historique est conservé |
| `POST /saved-searches/{id}/run` | relance les critères depuis la première page ; renvoie `{run, results}` |
| `GET /search-runs?limit=50` | historique d'exécution, le plus récent d'abord |

`filter` accepte les mêmes champs que `GET /offers`, hors `page`, qui n'est jamais mémorisée. Le propriétaire n'est jamais fourni par le client (corps inconnus refusés).

## Profil candidat

### `POST /profile/import`

Import d'un CV, en `multipart/form-data` (champ `fichier`). **Lecture seule : le fichier n'est pas conservé et rien n'est enregistré** (minimisation RGPD) ; le texte et le profil proposé sont renvoyés pour validation par l'utilisateur.

| Contrôle | Règle |
|---|---|
| Formats | PDF, DOCX, TXT ; le format est déduit du **contenu réel** et une extension qui ment est refusée (415) |
| Taille | 5 Mo maximum, vérifiée pendant la lecture (413) ; PDF ≤ 30 pages |
| Fichiers dangereux | PDF protégé par mot de passe refusé (jamais déchiffré) ; DOCX : entités XML externes et « milliard de rires » refusés, taux de compression plafonné, XML plafonné à 20 Mo |
| Documents inexploitables | corrompu ou sans texte (scan : pas d'OCR) → 422 avec un message explicite |

Réponse : `{filename, format, page_count, warnings, text, proposed_profile}`. `filename` est un nom d'affichage assaini, jamais un chemin.

`proposed_document` est la même proposition sous forme de brouillon éditable (éléments `imported`, non validés), prête à être relue puis envoyée à `PUT /profile/draft`.

`proposed_profile` est une **proposition**, pas un fait : coordonnées, expériences, formations, compétences, langues, certifications, résumé. Garanties :

- Une information absente du document vaut `null`. Une date partielle (`{"year": 2020, "month": null}`) n'est jamais complétée.
- Un niveau de langue n'est reconnu que s'il est explicite (A1–C2 ou langue maternelle) ; « courant » reste du texte (`level_text`), jamais converti en C1.
- Chaque expérience ou formation porte `source_text` (traçabilité) et `confidence` : `low` signale une lecture ambiguë (ex. intitulé et entreprise interchangeables) à vérifier.
- `warnings` liste ce qui n'a pas pu être lu.

### Profil maître (brouillon, validation, versions)

| Route | Rôle |
|---|---|
| `GET /profile` | dernière version (`{meta, document}`) ; `null` s'il n'existe pas |
| `PUT /profile/draft` | enregistre le brouillon (le crée à la première sauvegarde) ; 409 `no_draft` si la dernière version est validée |
| `POST /profile/validate` | valide le brouillon ; 422 `profile_incomplete` avec la liste des champs manquants |
| `POST /profile/versions` | nouveau brouillon copié de la dernière version validée (201) ; 409 `draft_exists` s'il y en a déjà un |
| `GET /profile/versions` · `/versions/{n}` | versions, de la plus récente à la plus ancienne |
| `GET /profile/history?limit=100` | journal des modifications, le plus récent d'abord |

`document` = `{identity, summary, experiences[], educations[], skills[], languages[], certifications[], preferences}`. Les éléments portent `id`, `origin` (`imported`/`manual`), `validated` et `source_text` ; les dates sont `{year, month|null}`.

- **Enregistrer** remplace le contenu du brouillon : un élément avec `id` est mis à jour, sans `id` il est créé, absent il est supprimé. Un `id` inconnu est refusé (422 `unknown_item`).
- **Brouillon libre, validation stricte** : un brouillon peut être incomplet. Un élément envoyé avec `validated: true` doit être complet (expérience : intitulé, entreprise, début ; formation : diplôme, établissement ; langue : niveau). Valider le profil exige prénom, nom et **tous** les éléments confirmés : rien n'est validé à la place de l'utilisateur. Après modification d'un élément déjà confirmé, le client doit renvoyer `validated: false` pour exiger une nouvelle relecture.
- **Préférences** : métiers, pays, villes, télétravail, contrats, salaire souhaité (avec devise) et langues de candidature, versionnées avec le profil.

## Analyse d'une offre

Analyse **par règles** (sans IA, sans coût), calculée au premier appel puis réutilisée tant que l'annonce ne change pas. Elle ne restitue que ce qui est écrit dans l'annonce : ce qui n'y figure pas reste vide ou est listé dans « informations manquantes ».

| Route | Rôle |
|---|---|
| `GET /offers/{id}/analysis` | `{analysis_id, computed_at, reused, analysis}` : `missions`, `mandatory_skills`, `expected_skills`, `desired_skills`, `technologies` (vocabulaire fermé), `years_experience` / `years_mandatory`, `languages` (langue, niveau écrit, exigé ou souhaité), `mobility` (`visa`, `relocation_offered`, `travel`), `missing` (code + libellé), `summary` (extractif : phrases de l'annonce, jamais reformulées). 404 `offer_not_found`. |
| `GET /offers/{id}/analysis/history` | Versions successives (une par texte d'annonce, champ structuré ou version de règles). Les anciennes ne sont jamais réécrites. |
| `POST /offers/{id}/analysis/ai-summary` | Résumé **par IA, facultatif**, via la passerelle (consentement, plafonds, cache, journal). Seul le texte public de l'offre est transmis. Réponse : `summary`, `key_points`, `provider`, `model`, `cache_hit`, `cost`. Erreurs IA : 409 / 502 (voir `/ai/test`). |

## Compatibilité (score)

Score indicatif, déterministe, expliqué (`docs/architecture/MATCHING.md`). Calculé sur le profil **validé** : sans lui, 409 `no_validated_profile`.

| Route | Rôle |
|---|---|
| `GET /offers/{id}/match` | score détaillé : `{result, profile_version, computed_at}` ; `result` = score, couverture, fiabilité, critères (statut, note, explication), correspondances, écarts, résumé, avertissement ; le score est mémorisé |
| `POST /matching/recompute` | recalcule toutes les offres actives (profil validé, poids courants) → `{computed, not_computable, profile_version, weights_version}` |
| `GET /matching/weights` | pondérations courantes, par défaut et version |
| `PUT /matching/weights` | `{weights: {critère: nombre 0-100}}` ; un critère omis garde son poids par défaut, 0 le désactive ; 422 `invalid_weights` sinon |
| `DELETE /matching/weights` | rétablit les pondérations par défaut |

`GET /offers` accepte aussi `min_score` (0-100) et `sort=score_desc` ; chaque offre porte `match_score` et `match_reliability` (`null` = pas encore évaluée). Sans profil validé, `min_score` et `sort=score_desc` renvoient 409 `scoring_unavailable` plutôt qu'une liste trompeuse.

Les critères dont les données manquent ont `status: "missing_data"` et `score: null` : ils ne sont pas comptés.

## Confidentialité (RGPD)

| Route | Rôle |
|---|---|
| `GET /privacy/summary` | Ce qui est stocké, par catégorie (lignes, volume de fichiers, détail par table) |
| `GET /privacy/export` | Archive ZIP : `manifest.json`, un JSON par table, les PDF générés |
| `POST /privacy/erase` | `{scope, confirmation}` : `scope` = catégorie ou `all` ; `confirmation` doit valoir `SUPPRIMER` (422 `confirmation_required`) ; 409 `deletion_blocked` si les offres sont encore suivies par des candidatures ; 422 `unknown_category` |
| `GET /privacy/retention` | Politique de conservation (durée, purge automatique ou non) |
| `POST /privacy/retention/purge` | Applique maintenant la conservation automatique → lignes purgées par table |
| `GET /privacy/ai-transfers` | Ce qui part vers un fournisseur d'IA, par usage ; `personal_data` indique les données personnelles |
| `GET`/`PUT /privacy/settings` | Politique d'envoi des données personnelles à l'IA : `allowed`, `local_only`, `never` (409 `ai_personal_data_blocked` côté IA si interdit) |

## Santé et mesures

| Route | Rôle |
|---|---|
| `GET /health` | Vivacité (sans base) |
| `GET /health/ready` | Base et stockage ; 503 si l'un est en panne |
| `GET /health/details` | `{status, components[]}` : base, stockage, LaTeX, IA, sources, tâches (`ok`, `degraded`, `down`, `not_configured`) |
| `GET /health/metrics` | Durées (moyenne, p50, p95) et volumes par modèle de route, depuis le démarrage |

Toutes les réponses portent `X-Request-ID` (corrélation avec les logs) et les en-têtes de sécurité.
Au-delà des limites : `429 rate_limited` avec `Retry-After` ; requête trop grande : `413
payload_too_large`.

## Limites actuelles

- Ces routes lisent les offres **déjà présentes en base**. Le déclenchement d'une collecte auprès des sources (ingestion) n'est pas encore exposé : il viendra avec les connecteurs réels et l'EPIC 015.
- L'import de CV fonctionne par règles (aucune IA) sur des CV aux sections titrées en français ou en anglais ; une mise en page très inhabituelle (colonnes entremêlées, tableaux) donnera davantage de `low` et d'avertissements. Pas de reconnaissance de caractères pour les scans.
- Filtres par rayon (`radius_km`) et par niveau d'expérience : non disponibles, car l'offre ne stocke ni coordonnées ni expérience requise.


## Préférences et référentiel géographique (`/api/v1`)

| Route | Rôle |
|---|---|
| `GET /preferences` | Langue d'interface, pays, devise, fuseau IANA, mobilité (`willing_to_relocate`, `target_countries`, `work_permit_countries`, `needs_sponsorship`) et `supported_ui_languages`. `null` = non renseigné. |
| `PUT /preferences` | Remplace les préférences ; chaque valeur est vérifiée contre le référentiel. 422 `preferences_invalid` avec un message explicite (langue, pays, devise ou fuseau inconnu). |
| `GET /reference/countries?locale=fr\|en` | Pays ISO 3166-1 avec langues officielles et devises, triés par nom. |
| `GET /reference/currencies?locale=fr\|en` | Devises ISO 4217 (code, nom, symbole). |
| `GET /reference/timezones` | Fuseaux IANA reconnus par le serveur. |

`GET /offers/{id}` expose aussi `visa_sponsorship` (`offered`, `not_offered`, `null`) et `work_authorization_required` (`true` ou `null`), déduits de l'annonce ; `null` signifie que l'annonce n'en parle pas.

## Candidatures (`/api/v1/applications`)

| Route | Rôle |
|---|---|
| `POST /applications` | `{offer_id, initial_status?}` : suit une offre (une offre = une candidature). 409 `duplicate_application` si elle l'est déjà. L'interface demande une confirmation avant cet appel. |
| `GET /applications` | Liste filtrée et paginée. `GET /applications/kanban` : colonnes par statut ; `GET /applications/stats` : statistiques fondées sur les données réelles. |
| `GET /applications/{id}` | Fiche : contacts, historique, documents, transitions autorisées. |
| `DELETE /applications/{id}` | Retire la candidature du suivi (par exemple ajoutée par erreur) avec son historique, ses contacts et ses documents associés. **L'offre est conservée** et peut être suivie à nouveau. 204 ; 404 `application_not_found` si elle n'existe pas ou appartient à un autre utilisateur. |
| `PATCH /applications/{id}/status`, `POST …/confirm-submission` | Changement de statut validé par la machine à états ; l'envoi est toujours confirmé à la main. |
| `POST …/notes`, `POST …/interviews`, `POST …/contacts`, `PATCH …/follow-up`, `PUT …/documents` | Historique, entretiens, contacts, relance, CV et lettre associés. |
| `GET …/dossier`, `GET …/open-url` | Dossier de candidature et lien d'origine de l'offre. |
