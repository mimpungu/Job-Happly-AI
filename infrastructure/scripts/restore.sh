#!/usr/bin/env bash
# Restaure une sauvegarde dans une base CIBLE. Opération destructrice pour la cible.
# Usage : restore.sh <fichier.dump> <base-cible> --yes
# Pour restaurer sur la base courante, la passer explicitement comme cible : aucune cible implicite.
source "$(dirname "$0")/_common.sh"
[ -n "${POSTGRES_USER:-}" ] || { exiger_env; set -a; source .env; set +a; }
DUMP="${1:-}"; CIBLE="${2:-}"; CONFIRME="${3:-}"
[ -f "$DUMP" ] || { echo "Usage : restore.sh <fichier.dump> <base-cible> --yes" >&2; exit 1; }
[ -n "$CIBLE" ] || { echo "Base cible obligatoire (aucune cible implicite)." >&2; exit 1; }
[ "$CONFIRME" = "--yes" ] || { echo "Confirmation requise : ajouter --yes (la base '$CIBLE' sera remplacée)." >&2; exit 1; }
if [ -f "$DUMP.sha256" ]; then
  (cd "$(dirname "$DUMP")" && shasum -a 256 -c "$(basename "$DUMP").sha256") || { echo "Somme de contrôle invalide : restauration annulée." >&2; exit 1; }
fi
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS \"$CIBLE\" WITH (FORCE)" -c "CREATE DATABASE \"$CIBLE\""
docker compose exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$CIBLE" --no-owner --exit-on-error < "$DUMP"
echo "Base '$CIBLE' restaurée depuis $DUMP"
