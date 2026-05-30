#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/common.sh"

HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"

echo "Checking container status..."
compose ps

echo "Checking API health at ${HEALTH_URL}..."
curl --fail --silent --show-error "${HEALTH_URL}"
echo

echo "Release verification completed."
