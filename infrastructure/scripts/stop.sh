#!/usr/bin/env bash
# Arrête les services sans supprimer les données.
source "$(dirname "$0")/_common.sh"
docker compose down
