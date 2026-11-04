#!/usr/bin/env bash
# Réinitialise l'environnement de TEST uniquement (projet Docker et volume dédiés).
# Ne touche jamais aux données de développement.
source "$(dirname "$0")/_common.sh"
export COMPOSE_PROJECT_NAME="happly-ai-test"
export POSTGRES_PORT="55432"
export POSTGRES_USER="happly_test" POSTGRES_PASSWORD="test-only" POSTGRES_DB="happly_test"
docker compose down -v --remove-orphans
docker compose up -d --wait postgres
echo "Base de test prête sur 127.0.0.1:${POSTGRES_PORT}"
