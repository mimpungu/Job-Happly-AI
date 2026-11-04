#!/usr/bin/env bash
# Applique les migrations Alembic sur la base désignée par HAPPLY_DATABASE_URL (ou .env).
source "$(dirname "$0")/_common.sh"
if [ -z "${HAPPLY_DATABASE_URL:-}" ]; then
  exiger_env
  # Seule l'URL de la base est lue : `source .env` retirait les guillemets de valeurs JSON (liste
  # CORS) et faisait échouer la lecture de la configuration.
  HAPPLY_DATABASE_URL="$(grep -E '^HAPPLY_DATABASE_URL=' .env | head -1 | cut -d= -f2-)"
  export HAPPLY_DATABASE_URL
  if [ -z "$HAPPLY_DATABASE_URL" ]; then
    echo "HAPPLY_DATABASE_URL est absent de .env." >&2
    exit 1
  fi
fi
(cd backend && uv run alembic upgrade head)
