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
| `text` | intitulé, entreprise ou description (insensible à la casse ; `%` et `_` sont littéraux) |
| `keywords` (répétable) | tous les mots-clés doivent figurer dans l'intitulé ou la description |
| `company`, `city` | sous-chaîne de l'entreprise / du lieu |
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

### `GET /offers/{offer_id}`

Fiche détaillée : description, URL de candidature, dates et **sources** (clé, nom, URL, dernière observation, `still_listed`).

### `PUT /offers/{offer_id}/state`

Corps `{"state": "saved" | "ignored" | null}` → 204. Idempotent ; `null` retire l'état. Une offre ignorée est masquée par défaut mais reste retrouvable (`state=ignored`).

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

## Limites actuelles

- Ces routes lisent les offres **déjà présentes en base**. Le déclenchement d'une collecte auprès des sources (ingestion) n'est pas encore exposé : il viendra avec les connecteurs réels et l'EPIC 015.
- Filtres par rayon (`radius_km`) et par niveau d'expérience : non disponibles, car l'offre ne stocke ni coordonnées ni expérience requise.
