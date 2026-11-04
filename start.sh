#!/usr/bin/env bash
# Script tout-en-un de démarrage pour Happly AI.
# Gère la configuration (.env), le démarrage des conteneurs et les migrations.

set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$RACINE"

COULEUR_VERT="\033[0;32m"
COULEUR_JAUNE="\033[1;33m"
COULEUR_ROUGE="\033[0;31m"
COULEUR_BLEU="\033[0;34m"
COULEUR_RESET="\033[0m"

info() {
  echo -e "${COULEUR_BLEU}ℹ${COULEUR_RESET} $1"
}

succes() {
  echo -e "${COULEUR_VERT}✔${COULEUR_RESET} $1"
}

attention() {
  echo -e "${COULEUR_JAUNE}⚠${COULEUR_RESET} $1"
}

erreur() {
  echo -e "${COULEUR_ROUGE}✖${COULEUR_RESET} $1" >&2
}

# 1. Vérification du fichier d'environnement .env
if [ ! -f .env ]; then
  attention "Le fichier .env est absent. Création automatique depuis .env.example..."
  cp .env.example .env
  succes "Fichier .env initialisé. Pensez à adapter les mots de passe si nécessaire."
fi

# 2. Vérification de la disponibilité de Docker
verifier_docker() {
  if ! docker info > /dev/null 2>&1; then
    attention "Docker n'est pas encore actif."
    # Si nous sommes sur macOS, tenter de lancer Docker Desktop
    if [[ "$OSTYPE" == "darwin"* ]] && [ -d "/Applications/Docker.app" ]; then
      info "Tentative de lancement de Docker Desktop..."
      open -a Docker
      echo -n "Attente du démarrage du démon Docker (jusqu'à 45 secondes) "
      local tentative=0
      while ! docker info > /dev/null 2>&1; do
        sleep 2
        echo -n "."
        tentative=$((tentative + 1))
        if [ $tentative -ge 23 ]; then
          echo ""
          erreur "Docker Desktop n'a pas répondu à temps."
          erreur "Veuillez vous assurer que Docker Desktop est ouvert et actif, puis relancez ce script."
          exit 1
        fi
      done
      echo ""
      succes "Docker Desktop est maintenant actif !"
    else
      erreur "Docker n'est pas démarré. Veuillez lancer Docker puis réessayer."
      exit 1
    fi
  fi
}

# Mode Développement local (PostgreSQL en Docker, Backend & Frontend sur la machine hôte)
lancer_mode_dev() {
  info "Lancement en mode Développement local (Postgres Docker + Backend/Frontend hôte)..."
  verifier_docker

  info "Démarrage de PostgreSQL..."
  docker compose up -d postgres

  info "Application des migrations de base de données..."
  ./infrastructure/scripts/migrate.sh

  info "Démarrage de l'API Backend et du Frontend..."
  echo "Appuyez sur Ctrl+C pour arrêter les deux services."

  trap 'kill 0' SIGINT SIGTERM EXIT

  (cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &
  (cd frontend && pnpm dev) &

  wait
}

# Mode Standard Docker (Tout dans des conteneurs isolés)
lancer_mode_docker() {
  verifier_docker

  info "Démarrage des services Happly AI via Docker Compose..."
  ./infrastructure/scripts/start.sh

  info "Application des migrations de base de données..."
  ./infrastructure/scripts/migrate.sh

  echo ""
  succes "Happly AI est opérationnel !"
  echo "--------------------------------------------------------"
  echo -e " Interface web (Frontend) : ${COULEUR_VERT}http://127.0.0.1:3000${COULEUR_RESET}"
  echo -e " API Backend (Health)      : ${COULEUR_VERT}http://127.0.0.1:8000/api/v1/health${COULEUR_RESET}"
  echo -e " Arrêter l'application    : ${COULEUR_JAUNE}./infrastructure/scripts/stop.sh${COULEUR_RESET} ou ${COULEUR_JAUNE}make stop${COULEUR_RESET}"
  echo "--------------------------------------------------------"
}

# Gestion des arguments
case "${1:-}" in
  dev)
    lancer_mode_dev
    ;;
  stop)
    ./infrastructure/scripts/stop.sh
    ;;
  status)
    docker compose ps
    ;;
  help|--help|-h)
    echo "Usage : $0 [dev|stop|status|help]"
    echo ""
    echo "Options :"
    echo "  (aucun argument)  Démarre l'ensemble des services via Docker (recommandé)"
    echo "  dev               Démarre Postgres dans Docker, puis lance Backend et Frontend en local"
    echo "  stop              Arrête tous les services"
    echo "  status            Affiche l'état des conteneurs"
    echo "  help              Affiche cette aide"
    ;;
  *)
    lancer_mode_docker
    ;;
esac

