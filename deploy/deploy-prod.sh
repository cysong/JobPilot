#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/jobpilot}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-.env}"
ENV_FILE="${ENV_FILE:-deploy/env/backend.env}"
GITHUB_API_URL="${GITHUB_API_URL:-https://api.github.com}"
FRONTEND_DEST="${FRONTEND_DEST:-/var/www/jobpilot/current}"

if [[ -f "${APP_DIR}/${COMPOSE_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${APP_DIR}/${COMPOSE_ENV_FILE}"
  set +a
fi

if [[ -z "${JOBPILOT_IMAGE:-}" ]]; then
  echo "ERROR: JOBPILOT_IMAGE is required."
  exit 1
fi

if [[ -z "${GHCR_USERNAME:-}" || -z "${GHCR_TOKEN:-}" ]]; then
  echo "ERROR: GHCR_USERNAME and GHCR_TOKEN are required."
  exit 1
fi

download_frontend_artifact() {
  if [[ -z "${FRONTEND_ARTIFACT_ID:-}" ]]; then
    echo "FRONTEND_ARTIFACT_ID is empty, skip frontend artifact deployment."
    return 0
  fi

  if [[ -z "${GITHUB_REPOSITORY:-}" || -z "${GITHUB_TOKEN:-}" ]]; then
    echo "ERROR: GITHUB_REPOSITORY and GITHUB_TOKEN are required when FRONTEND_ARTIFACT_ID is set."
    exit 1
  fi

  if ! command -v unzip >/dev/null 2>&1; then
    echo "ERROR: unzip is required to extract GitHub artifact zip."
    exit 1
  fi

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' RETURN

  local zip_path="${tmp_dir}/frontend-artifact.zip"
  local extract_dir="${tmp_dir}/artifact"
  local url="${GITHUB_API_URL}/repos/${GITHUB_REPOSITORY}/actions/artifacts/${FRONTEND_ARTIFACT_ID}/zip"

  echo "Downloading frontend artifact id=${FRONTEND_ARTIFACT_ID} from GitHub..."
  curl -fsSL \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    "${url}" \
    -o "${zip_path}"

  mkdir -p "${extract_dir}"
  unzip -q "${zip_path}" -d "${extract_dir}"

  mkdir -p "${FRONTEND_DEST}"
  rm -rf "${FRONTEND_DEST:?}/"*
  cp -a "${extract_dir}/." "${FRONTEND_DEST}/"

  echo "Frontend artifact deployed to ${FRONTEND_DEST}."
}

cd "${APP_DIR}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "ERROR: compose file not found: ${APP_DIR}/${COMPOSE_FILE}"
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: env file not found: ${APP_DIR}/${ENV_FILE}"
  exit 1
fi

DATABASE_URL="$(grep -E '^DATABASE_URL=' "${ENV_FILE}" | tail -n 1 | cut -d= -f2-)"
if [[ -z "${DATABASE_URL}" ]]; then
  echo "ERROR: DATABASE_URL is missing from ${APP_DIR}/${ENV_FILE}"
  exit 1
fi

MONITORING_ENV_FILE="${MONITORING_ENV_FILE:-deploy/env/monitoring.env}"
if [[ ! -f "${MONITORING_ENV_FILE}" ]]; then
  echo "ERROR: monitoring env file not found: ${APP_DIR}/${MONITORING_ENV_FILE}"
  exit 1
fi

echo "Logging in to GHCR..."
echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin

export JOBPILOT_IMAGE

echo "Pulling images..."
docker compose -f "${COMPOSE_FILE}" pull

download_frontend_artifact

echo "Running migrations..."
docker compose -f "${COMPOSE_FILE}" run --rm --no-deps jobpilot-api uv run alembic upgrade head

echo "Starting services..."
docker compose -f "${COMPOSE_FILE}" up -d \
  jobpilot-redis \
  jobpilot-api \
  jobpilot-worker \
  jobpilot-beat \
  jobpilot-prometheus \
  jobpilot-alertmanager \
  jobpilot-grafana \
  jobpilot-redis-exporter \
  jobpilot-cadvisor

echo "Waiting for API health..."
for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:18000/health" >/dev/null; then
    echo "Reloading nginx..."
    nginx -t
    systemctl reload nginx
    echo "Deployment succeeded."
    exit 0
  fi
  sleep 2
done

echo "ERROR: API health check failed."
docker compose -f "${COMPOSE_FILE}" ps
exit 1
