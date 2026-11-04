#!/usr/bin/env bash
# Arrête les services (application et base de test) sans supprimer les données de développement.
source "$(dirname "$0")/_common.sh"
docker compose down
# La base de TEST (projet dédié) reste sinon active après test.sh ; ses données sont jetables.
COMPOSE_PROJECT_NAME="happly-ai-test" POSTGRES_PORT="55432" \
  POSTGRES_USER="happly_test" POSTGRES_PASSWORD="test-only" POSTGRES_DB="happly_test" \
  docker compose down --remove-orphans
