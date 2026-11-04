# ADR-0004 — Base de données PostgreSQL

- **Statut :** Accepté
- **Date :** 2026-11-03

## Contexte

Données relationnelles (offres, candidatures, versions de documents), recherche, déduplication, historique et usage IA.

## Décision

**PostgreSQL** comme unique base, lancée via Docker Compose en local. Migrations Alembic versionnées. Index fondés sur les requêtes réelles, contraintes d'intégrité, pagination côté base.

Pas de double implémentation (pas de SQLite parallèle) : une seule couche de persistance cohérente. Les tests d'intégration s'exécutent sur PostgreSQL.

## Alternatives étudiées

- SQLite : installation plus simple, mais comportements différents (types, concurrence, recherche) qui obligeraient à tester deux moteurs.

## Conséquences

- Docker requis en développement (disponible sur la machine).
- Sauvegarde/restauration documentées et testées (EPIC 004 et 018).
- Recherche plein texte et trigrammes PostgreSQL utilisables avant d'envisager un moteur dédié.
