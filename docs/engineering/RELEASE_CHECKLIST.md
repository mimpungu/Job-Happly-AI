# Checklist de release

À dérouler avant d'annoncer une version. **Aucune étape n'est cochée d'avance** : chacune se vérifie. Statut honnête d'une version : voir `QUALITY_REPORT.md`.

## 1. Qualité automatique

- [ ] CI verte sur la branche à livrer (`.github/workflows/ci.yml` : formatage, lint, types, tests, couverture, build, secrets).
- [ ] `pnpm e2e` (accessibilité) et `pnpm e2e:fullstack` (parcours complets) passent localement ou en CI.
- [ ] Couverture backend au-dessus du seuil.
- [ ] Aucun test ignoré en silence (`HAPPLY_REQUIRE_PDFLATEX=1`).

## 2. Données

- [ ] Toutes les migrations s'appliquent sur une base vide **et** sur une base de la version précédente.
- [ ] Sauvegarde puis restauration d'essai vers une base temporaire (`docs/operations/RECOVERY.md`).

## 3. Sécurité et confidentialité

- [ ] Aucun secret dans l'historique (gitleaks), `.env.example` sans valeur réelle.
- [ ] Mode local vérifié : ports sur `127.0.0.1`, CORS restreint.
- [ ] Dépendances : alertes de sécurité examinées (Dependabot).
- [ ] Catalogues à jour : transferts IA, catégories RGPD, surface sortante.

## 4. Documentation

- [ ] `README.md`, `INSTALL.md`, `USER_GUIDE.md`, `API.md`, `CHANGELOG.md` à jour.
- [ ] Backlog et ADR cohérents avec le code ; limites connues listées.

## 5. Critères de version

- [ ] Les critères de la release visée (`RELEASE_PLAN.md`) sont **réellement** satisfaits ; sinon la version porte un suffixe `-rc` ou `-dev` et le dit.
- [ ] Aucun défaut bloquant connu (`QUALITY_REPORT.md`, « Défauts connus »).

## 6. Publication (action externe : sur demande explicite du propriétaire)

- [ ] Numéro de version aligné (`backend/pyproject.toml`, `frontend/package.json`, API).
- [ ] Entrée datée dans `CHANGELOG.md`.
- [ ] Tag Git et notes de version : **jamais sans accord du propriétaire**.
