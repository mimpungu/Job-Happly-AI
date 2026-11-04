# ADR-0003 — Frontend Next.js / TypeScript strict

- **Statut :** Accepté
- **Date :** 2026-11-03

## Décision

Next.js, React, TypeScript strict, Tailwind CSS, shadcn/ui, Lucide, React Hook Form + Zod, TanStack Query ; Zustand seulement si un état global est démontré nécessaire. Tests : Vitest + Testing Library, Playwright pour l'E2E. Gestionnaire de paquets : pnpm.

Design : thème sombre sobre, couleurs uniques (aucun dégradé), tous les styles passent par des design tokens.

## Alternatives étudiées

- SPA Vite + React : plus simple, mais routage et rendu serveur à réimplémenter.

## Conséquences

- Le frontend consomme uniquement l'API (aucun accès direct à la base).
- Les composants restent sans logique métier.
