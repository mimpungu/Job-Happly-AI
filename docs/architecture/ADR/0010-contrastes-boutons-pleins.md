# ADR-0010 — Texte sombre sur les boutons pleins (contraste)

- **Statut :** Accepté
- **Date :** 2026-11-03

## Contexte

La palette de la spécification (§15.1) donne `#0A84FF` pour l'accent et `#FF453A` pour l'erreur. Le contraste mesuré (WCAG) du texte blanc sur ces fonds est de 3,65:1 et 3,41:1, sous le seuil de 4,5:1 exigé pour le texte courant. Le texte `#71717A` est à 4,07:1 sur le fond principal.

## Décision

- Les couleurs de la palette sont conservées telles quelles.
- Les boutons pleins (accent, danger) utilisent un **texte sombre** (`--color-on-accent`, `--color-on-danger` = `#0B0B0D`), soit 5,4:1 et 5,8:1.
- `--color-foreground-subtle` est réservé aux placeholders, textes de grande taille et indications non essentielles ; jamais pour une information indispensable.
- Les contrastes sont documentés dans `frontend/src/styles/tokens.css`.

## Conséquences

- Accessibilité conforme AA pour les actions principales.
- Rendu visuellement différent du blanc sur bleu habituel ; à réévaluer si la palette change.
