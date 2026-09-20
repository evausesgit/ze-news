#!/usr/bin/env bash
# Arrête la pile locale lancée par dev_up.sh. La base est SUPPRIMÉE
# (conteneur jetable) : relancer dev_up.sh repart d'une base vide.
set -uo pipefail

kill_port() {
  local pid
  pid=$(ss -ltnp 2>/dev/null | grep -oP "(?<=:$1 ).*pid=\K[0-9]+" | head -1)
  [ -n "${pid:-}" ] && kill "$pid" 2>/dev/null && echo "→ port $1 libéré"
}

kill_port 3010
kill_port 8810
docker rm -f zenews-dev-db >/dev/null 2>&1 && echo "→ Postgres supprimé"
echo "Pile arrêtée."
