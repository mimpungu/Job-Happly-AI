# ADR-0001 — Monolithe modulaire en Clean Architecture

- **Statut :** Accepté
- **Date :** 2026-11-03

## Contexte

Produit destiné à durer plusieurs années, développé par une seule personne avec des agents IA, exécuté en local d'abord. Il faut une séparation nette des responsabilités sans le coût opérationnel de plusieurs services.

## Décision

Un **monolithe modulaire** en Clean Architecture avec DDD pragmatique. Couches `domain` → `application` → `infrastructure` / `presentation`, dépendances dirigées vers le domaine. Modules par contexte métier : Candidate Profile, Job Discovery, Job Intelligence, AI Management, Document Generation, Application Management, Interview Preparation, Notifications.

Les modules communiquent par des interfaces explicites, jamais par accès direct aux tables d'un autre module.

## Alternatives étudiées

- **Microservices** : déploiement, observabilité et cohérence des données trop coûteux pour le besoin actuel.
- **Monolithe non structuré** : rapide au départ, dette technique certaine.

## Conséquences

- Extraction future d'un module en service possible grâce aux frontières claires.
- Discipline nécessaire : vérification des dépendances entre couches et modules (règle de lint ou test d'architecture, à prévoir en TASK-002-04).
