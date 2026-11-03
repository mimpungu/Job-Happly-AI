#!/usr/bin/env bash
# Applique les migrations Alembic.
source "$(dirname "$0")/_common.sh"
if [ ! -f backend/alembic.ini ]; then
  echo "Alembic n'est pas encore initialisé (TASK-004-06) : aucune migration à appliquer." >&2
  exit 1
fi
(cd backend && uv run alembic upgrade head)
