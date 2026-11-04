# Confidentialité et RGPD

L'application est locale : vos données restent sur votre machine. Seuls des appels **à la
demande** à un fournisseur d'IA peuvent faire partir du texte (voir §4).

## 1. Finalité et minimisation

Les données servent uniquement à chercher un emploi (profil, documents, candidatures,
entretiens). Aucune donnée de télémétrie. Aucune clé d'API en base.

## 2. Transparence et contrôle (Paramètres → Confidentialité)

| Droit | Fonction | API |
|---|---|---|
| Accès / transparence | Ce qui est stocké, par catégorie, avec le volume de fichiers | `GET /privacy/summary` |
| Portabilité | Archive ZIP : un JSON par table, les PDF générés, un manifeste | `GET /privacy/export` |
| Effacement | Par catégorie ou total, après saisie du mot `SUPPRIMER`, irréversible | `POST /privacy/erase` |
| Limitation | Politique d'envoi à l'IA : `allowed`, `local_only`, `never` | `PUT /privacy/settings` |

Effacement : les lignes sont supprimées dans l'ordre des dépendances ; les fichiers PDF le sont
ensuite. Supprimer les offres est refusé tant que des candidatures les suivent. L'effacement total
conserve le compte local (l'application reste utilisable) et supprime aussi ses tâches de fond.
Il est vérifié sur PostgreSQL réel, y compris l'**isolation** : les données d'un autre
propriétaire ne sont jamais touchées.

## 3. Politique de conservation

Appliquée par `POST /privacy/retention/purge` (déclenchable depuis l'interface) :

| Donnée | Durée | Automatique |
|---|---|---|
| Cache des réponses IA | 30 jours (ou expiration) | oui |
| Journal des appels IA | 365 jours | oui |
| Notifications lues | 90 jours | oui |
| Historique des recherches | 180 jours | oui |
| Tâches de fond terminées | 30 jours | oui |
| Profil, documents, candidatures, entretiens, offres | Jusqu'à votre suppression | non |

Ces durées sont dans `app/modules/privacy/domain/categories.py`, exposées par `GET
/privacy/retention` et affichées dans l'interface. La purge n'est pas planifiée automatiquement :
elle peut l'être via le planificateur (EPIC 015) ; en attendant, elle est manuelle.

## 4. Transferts vers les fournisseurs d'IA

Aucun appel IA n'est automatique. Les usages, ce qui est envoyé et ce qui ne l'est jamais sont
décrits dans `app/modules/privacy/domain/ai_transfers.py` (source unique, exposée par `GET
/privacy/ai-transfers`, affichée dans l'interface). Un test échoue si un appel IA est ajouté sans
fiche correspondante.

| Usage | Envoyé | Jamais envoyé | Données personnelles |
|---|---|---|---|
| Résumé d'offre | Texte public de l'offre | Profil, CV | non |
| Reformulation de CV | Réalisations retenues | Identité, coordonnées, employeurs, dates, CV complet | **oui** |
| Questions d'entretien | Texte public de l'offre | Profil, CV, réponses | non |
| Commentaire d'une réponse | Question + réponse saisie | Profil, CV, identité | **oui** |
| Test du fournisseur | Phrase fixe | Toute donnée | non |

Garanties appliquées par la passerelle IA : consentement explicite avant une API payante, plafond
de coût obligatoire, palier gratuit (qui peut réutiliser les contenus) **jamais** utilisé pour des
données personnelles, et politique utilisateur : `local_only` interdit tout fournisseur distant
pour ces données, `never` interdit tout appel qui en contiendrait.

## 5. Limites

- Pas d'export des sauvegardes ni de chiffrement au repos (`BACKUP_RESTORE.md`).
- Les données déjà transmises à un fournisseur relèvent de sa propre politique : l'application
  ne peut pas les supprimer chez lui.
