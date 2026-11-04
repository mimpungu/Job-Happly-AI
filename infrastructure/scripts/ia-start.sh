#!/usr/bin/env bash
# Démarre l'IA locale (Ollama) à la demande. Rien ne démarre tout seul : à arrêter avec ia-stop.sh.
source "$(dirname "$0")/_common.sh"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama n'est pas installé : brew install ollama" >&2
  exit 1
fi

URL="http://127.0.0.1:11434"
DOSSIER=".run"
mkdir -p "$DOSSIER"

if curl -s -m 2 "$URL/api/version" >/dev/null 2>&1; then
  echo "Ollama répond déjà sur $URL."
  if [ -f "$DOSSIER/ollama.pid" ]; then
    echo "(lancé par ce script : ia-stop.sh l'arrêtera)"
  else
    echo "(lancé autrement, par exemple l'application Ollama : fermez-la ou utilisez « ollama stop »)"
  fi
  exit 0
fi

# Lié à la boucle locale uniquement : jamais exposé sur le réseau (ADR-0008).
OLLAMA_HOST=127.0.0.1:11434 nohup ollama serve > "$DOSSIER/ollama.log" 2>&1 &
echo $! > "$DOSSIER/ollama.pid"

for _ in $(seq 1 30); do
  if curl -s -m 2 "$URL/api/version" >/dev/null 2>&1; then
    echo "Ollama démarré (PID $(cat "$DOSSIER/ollama.pid")). Modèles installés :"
    ollama list
    exit 0
  fi
  sleep 1
done
echo "Ollama n'a pas répondu en 30 s : voir $DOSSIER/ollama.log" >&2
exit 1
