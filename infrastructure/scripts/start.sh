#!/usr/bin/env bash
# Démarre PostgreSQL, l'API et le frontend (ports liés à 127.0.0.1).
source "$(dirname "$0")/_common.sh"
exiger_env
docker compose up -d --build --wait
echo "Frontend : http://127.0.0.1:3000   API : http://127.0.0.1:8000/api/v1/health"
