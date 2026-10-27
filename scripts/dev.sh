#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
uv sync --project backend --frozen --group dev --group spikes
uv run --project backend python -m workbench.tools bootstrap
case "${1:-native}" in
  native) exec uv run --project backend uvicorn workbench.api.main:app --host 127.0.0.1 --port 8000 --no-access-log ;;
  up)
    docker compose --env-file .env -f infra/compose/compose.yaml build migrate parser
    docker compose --env-file .env -f infra/compose/compose.yaml up -d --wait
    uv run --project backend python -m workbench.tools seed-db
    uv run --project backend python -m workbench.tools seed-buckets ;;
  check)
    uv run --project backend python backend/tools/platform_smoke.py
    uv run --project backend python backend/tools/check_oidc.py ;;
  stop) docker compose --env-file .env -f infra/compose/compose.yaml down ;;
  doctor) uv run --project backend python -m workbench.tools doctor ;;
  *) echo 'Usage: dev.sh [native|up|check|stop|doctor]' >&2; exit 2 ;;
esac
