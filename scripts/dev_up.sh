#!/usr/bin/env bash
# Démarre toute la pile en local pour tester : Postgres (conteneur jetable),
# migrations, API sur :8810, front sur :3010 avec une identité simulée.
#
#   bash scripts/dev_up.sh              # pile seule
#   bash scripts/dev_up.sh --demo       # + 6 vrais liens résumés par Codex
#   bash scripts/dev_up.sh --telegram   # + un cycle worker (Telegram réel)
#   bash scripts/dev_down.sh            # tout arrêter
#
# L'identité simulée (ZENEWS_DEV_USER_EMAIL) ne marche qu'en dev : le proxy
# l'ignore dès que NODE_ENV=production.
set -euo pipefail
cd "$(dirname "$0")/.."

EMAIL="${ZENEWS_DEV_USER_EMAIL:-dev@example.com}"
PG_CONTAINER=zenews-dev-db
PG_PORT=55433
export DATABASE_URL="postgresql+psycopg://zenews:devpass@127.0.0.1:${PG_PORT}/zenews"
# codex est en npm global : absent du PATH des process lancés par un agent.
export CODEX_BIN="${CODEX_BIN:-$HOME/.npm-global/bin/codex}"
LOGS=/tmp/zenews
mkdir -p "$LOGS"

kill_port() {  # tuer PAR LE PORT, jamais par pkill -f
  local pid
  pid=$(ss -ltnp 2>/dev/null | grep -oP "(?<=:$1 ).*pid=\K[0-9]+" | head -1 || true)
  [ -n "${pid:-}" ] && kill "$pid" 2>/dev/null || true
}

echo "→ Postgres (conteneur $PG_CONTAINER, port $PG_PORT)"
if ! docker ps --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
  docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
  docker run -d --name "$PG_CONTAINER" \
    -e POSTGRES_USER=zenews -e POSTGRES_PASSWORD=devpass -e POSTGRES_DB=zenews \
    -p "127.0.0.1:${PG_PORT}:5432" postgres:16-alpine >/dev/null
fi
for _ in $(seq 1 30); do
  docker exec "$PG_CONTAINER" pg_isready -U zenews -q && break
  sleep 1
done

echo "→ migrations"
uv run alembic upgrade head >"$LOGS/alembic.log" 2>&1

echo "→ API sur http://127.0.0.1:8810"
kill_port 8810
setsid nohup uv run uvicorn app.main:app --host 127.0.0.1 --port 8810 \
  >"$LOGS/api.log" 2>&1 </dev/null &
for _ in $(seq 1 30); do
  curl -sf http://127.0.0.1:8810/health >/dev/null && break
  sleep 1
done

if [ "${1:-}" = "--demo" ]; then
  echo "→ liens de démo (Codex, ~1 min)"
  uv run python -m scripts.demo_seed "$EMAIL"
elif [ "${1:-}" = "--telegram" ]; then
  echo "→ un cycle worker : ingestion Telegram + résumés Codex"
  uv run python -m app.worker --once
fi

echo "→ front sur http://127.0.0.1:3010 (connecté en tant que $EMAIL)"
kill_port 3010
cd web
[ -d node_modules ] || npm install --no-audit --no-fund >"$LOGS/npm.log" 2>&1
ZENEWS_DEV_USER_EMAIL="$EMAIL" API_INTERNAL_URL=http://127.0.0.1:8810 \
  setsid nohup npx next dev -p 3010 -H 127.0.0.1 >"$LOGS/web.log" 2>&1 </dev/null &
for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:3010/ >/dev/null && break
  sleep 1
done

echo
echo "Prêt : http://127.0.0.1:3010"
echo "Logs : $LOGS/{api,web,alembic}.log — arrêt : bash scripts/dev_down.sh"
