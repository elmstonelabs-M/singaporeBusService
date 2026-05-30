#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="${SCRIPT_DIR}/deploy"
BACKUP_DIR="${SCRIPT_DIR}/backup"

RUN_BACKUP=1
RUN_INFRA=0
RUN_STATIC_SYNC=0
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"

usage() {
  cat <<'EOF'
Usage: ./scripts/release_prod.sh [options]

Default release rule:
  - backup: enabled
  - postgres/redis restart: disabled
  - static data sync: disabled

Options:
  --skip-backup              Skip pre-release backups
  --with-infra              Start postgres and redis before release
  --with-sync-static-data   Run static data sync during release
  --health-url <url>        Override health check URL
  --help                    Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-backup)
      RUN_BACKUP=0
      shift
      ;;
    --with-infra)
      RUN_INFRA=1
      shift
      ;;
    --with-sync-static-data)
      RUN_STATIC_SYNC=1
      shift
      ;;
    --health-url)
      if [[ $# -lt 2 ]]; then
        echo "--health-url requires a value" >&2
        exit 1
      fi
      HEALTH_URL="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

echo "Starting production release..."

if [[ "${RUN_BACKUP}" -eq 1 ]]; then
  echo
  echo "[1/5] Creating backups..."
  "${BACKUP_DIR}/backup_all.sh"
else
  echo
  echo "[1/5] Skipping backups by request."
fi

if [[ "${RUN_INFRA}" -eq 1 ]]; then
  echo
  echo "[2/5] Starting infrastructure by request..."
  "${DEPLOY_DIR}/up_infra.sh"
else
  echo
  echo "[2/5] Leaving PostgreSQL and Redis unchanged."
fi

echo
echo "[3/5] Applying database migrations..."
"${DEPLOY_DIR}/migrate.sh"

if [[ "${RUN_STATIC_SYNC}" -eq 1 ]]; then
  echo
  echo "[4/5] Syncing static data by request..."
  "${DEPLOY_DIR}/sync_static_data.sh"
else
  echo
  echo "[4/5] Leaving static data unchanged for this release."
fi

echo
echo "[5/5] Starting API and verifying release..."
"${DEPLOY_DIR}/up_api.sh"
HEALTH_URL="${HEALTH_URL}" "${DEPLOY_DIR}/verify_health.sh"

echo
echo "Production release completed successfully."
