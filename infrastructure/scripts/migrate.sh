#!/usr/bin/env bash
# Applique les migrations Alembic sur la base désignée par HAPPLY_DATABASE_URL (ou .env).
source "$(dirname "$0")/_common.sh"
if [ -z "${HAPPLY_DATABASE_URL:-}" ]; then
  exiger_env
  set -a; source .env; set +a
fi
(cd backend && uv run alembic upgrade head)
