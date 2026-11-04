# ADR-0006 — Stratégie des connecteurs de sources

- **Statut :** Accepté
- **Date :** 2026-11-03

## Décision

- Interface commune `JobSourceConnector` (recherche, détails, santé, capacités) ; registre de connecteurs activables.
- **Sources gratuites et publiques uniquement** pour l'instant. Aucune source payante sans accord explicite.
- Ordre de préférence : API officielles gratuites, flux publics d'ATS (Greenhouse, Lever, Ashby, SmartRecruiters, Workable), données structurées `JobPosting`, puis pages publiques seulement si `robots.txt` et CGU l'autorisent.
- **Jamais de contournement** de CAPTCHA, authentification, restriction ou anti-bot. En cas de refus, la source est « non supportée ».
- Résilience : timeouts, retries avec backoff, rate limiting, circuit breaker si utile. Une source en échec n'arrête pas les autres.
- Normalisation vers un modèle commun, conservation de la donnée brute, trace de la source et de la date de récupération.
- Aucune source simulée présentée comme réelle ; mocks réservés aux tests et au mode démonstration identifié.

## Conséquences

- Couverture limitée aux sources autorisées ; elle est affichée honnêtement à l'utilisateur.
- Chaque connecteur exige une vérification préalable des conditions d'utilisation, consignée dans `DATA_SOURCES.md`.
