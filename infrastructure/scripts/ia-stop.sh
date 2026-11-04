#!/usr/bin/env bash
# Arrête l'IA locale (Ollama) et libère la mémoire occupée par les modèles.
source "$(dirname "$0")/_common.sh"

DOSSIER=".run"
URL="http://127.0.0.1:11434"

# Décharge d'abord les modèles de la mémoire (le serveur peut les garder plusieurs minutes).
if command -v ollama >/dev/null 2>&1 && curl -s -m 2 "$URL/api/version" >/dev/null 2>&1; then
  ollama ps 2>/dev/null | awk 'NR>1 {print $1}' | while read -r modele; do
    [ -n "$modele" ] && ollama stop "$modele" >/dev/null 2>&1 && echo "Modèle déchargé : $modele"
  done
fi

if [ -f "$DOSSIER/ollama.pid" ]; then
  PID="$(cat "$DOSSIER/ollama.pid")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "Ollama arrêté (PID $PID)."
  else
    echo "Le processus $PID n'existe plus."
  fi
  rm -f "$DOSSIER/ollama.pid"
elif curl -s -m 2 "$URL/api/version" >/dev/null 2>&1; then
  echo "Ollama tourne mais n'a pas été lancé par ia-start.sh : fermez l'application Ollama" >&2
  echo "ou exécutez « brew services stop ollama » s'il a été démarré ainsi." >&2
  exit 1
else
  echo "Ollama n'est pas lancé."
fi
