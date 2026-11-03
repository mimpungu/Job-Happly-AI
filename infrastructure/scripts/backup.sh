#!/usr/bin/env bash
# Sauvegarde la base PostgreSQL (format custom, avec somme de contrôle) et le dossier storage/.
# Usage : backup.sh [dossier-de-destination]   (défaut : backups/)
# Ne modifie jamais les données ; les fichiers produits restent hors Git (backups/ est ignoré).
source "$(dirname "$0")/_common.sh"
[ -n "${POSTGRES_USER:-}" ] || { exiger_env; set -a; source .env; set +a; }
DEST="${1:-backups}"
HORODATAGE="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DEST"
DUMP="$DEST/happly-$HORODATAGE.dump"

docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "$DUMP"
[ -s "$DUMP" ] || { echo "Sauvegarde vide : échec." >&2; rm -f "$DUMP"; exit 1; }
(cd "$DEST" && shasum -a 256 "$(basename "$DUMP")" > "$(basename "$DUMP").sha256")

if [ -d storage ] && [ -n "$(ls -A storage 2>/dev/null)" ]; then
  tar -czf "$DEST/storage-$HORODATAGE.tar.gz" storage
fi
echo "Sauvegarde créée : $DUMP"
