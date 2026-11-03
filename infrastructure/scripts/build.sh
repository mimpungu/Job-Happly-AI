#!/usr/bin/env bash
# Construit les images Docker et le frontend.
source "$(dirname "$0")/_common.sh"
docker compose build
