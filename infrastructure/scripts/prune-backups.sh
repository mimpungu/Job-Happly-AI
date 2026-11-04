#!/usr/bin/env bash
# Rétention des sauvegardes : conserve les N plus récentes (défaut 14), supprime les plus anciennes.
# Usage : prune-backups.sh [dossier] [nombre-à-conserver]
source "$(dirname "$0")/_common.sh"
DEST="${1:-backups}"; GARDER="${2:-14}"
[[ "$GARDER" =~ ^[0-9]+$ ]] && [ "$GARDER" -ge 1 ] || { echo "Nombre à conserver invalide." >&2; exit 1; }
[ -d "$DEST" ] || exit 0
ls -1 "$DEST"/happly-*.dump 2>/dev/null | sort -r | tail -n +"$((GARDER + 1))" | while read -r f; do
  echo "Suppression de $f"; rm -f -- "$f" "$f.sha256"
done
ls -1 "$DEST"/storage-*.tar.gz 2>/dev/null | sort -r | tail -n +"$((GARDER + 1))" | while read -r f; do
  echo "Suppression de $f"; rm -f -- "$f"
done
