#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."

runtime_image="${SIH_RUNTIME_IMAGE:-ghcr.io/indhuja007-hub/sih_26:latest}"
parser_image="${SIH_PARSER_IMAGE:-ghcr.io/indhuja007-hub/sih_26-parser:latest}"
compose_files="-f infra/compose/compose.yaml -f infra/compose/compose.distribution.yaml"

case "${1:-up}" in
  up)
    docker pull "$runtime_image"
    docker pull "$parser_image"
    docker run --rm --user "$(id -u):$(id -g)" \
      --mount "type=bind,source=$(pwd),target=/workspace" \
      -e WB_PROJECT_ROOT=/workspace -w /workspace \
      "$runtime_image" python -m workbench.tools bootstrap
    docker compose --env-file .env $compose_files up -d --wait
    echo 'Workbench backend ready: API http://127.0.0.1:8000/docs'
    ;;
  check)
    docker compose --env-file .env $compose_files ps
    docker compose --env-file .env $compose_files exec -T api \
      python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready')"
    echo 'Container stack is ready.'
    ;;
  stop) docker compose --env-file .env $compose_files down ;;
  *) echo 'Usage: container.sh [up|check|stop]' >&2; exit 2 ;;
esac
