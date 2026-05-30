#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

OUTPUT_DIR="${BACKUP_ROOT}/config-${TIMESTAMP}"
mkdir -p "${OUTPUT_DIR}"

cp "${ENV_FILE}" "${OUTPUT_DIR}/.env.production"
cp "${COMPOSE_FILE}" "${OUTPUT_DIR}/docker-compose.prod.yml"

if [[ -f "${PROJECT_ROOT}/nginx/singapore-bus-service.conf" ]]; then
  cp "${PROJECT_ROOT}/nginx/singapore-bus-service.conf" "${OUTPUT_DIR}/nginx-site.conf"
fi

if [[ -f "${PROJECT_ROOT}/alembic.ini" ]]; then
  cp "${PROJECT_ROOT}/alembic.ini" "${OUTPUT_DIR}/alembic.ini"
fi

echo "Config backup written to ${OUTPUT_DIR}"
