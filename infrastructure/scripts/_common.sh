#!/usr/bin/env bash
# Fonctions communes aux scripts. Se place à la racine du dépôt.
set -euo pipefail
RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RACINE"

exiger_env() {
  if [ ! -f .env ]; then
    echo "Fichier .env absent : copier .env.example vers .env puis adapter les valeurs." >&2
    exit 1
  fi
}
