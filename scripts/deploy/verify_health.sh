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
attempt=1
while [[ "${attempt}" -le 12 ]]; do
  if curl --fail --silent --show-error "${HEALTH_URL}"; then
    echo
    echo "API health check passed on attempt ${attempt}."
    echo
    echo "Release verification completed."
    exit 0
  fi

  if [[ "${attempt}" -lt 12 ]]; then
    echo
    echo "API health check failed on attempt ${attempt}; retrying in 5 seconds..."
    sleep 5
  fi

  attempt=$((attempt + 1))
done

echo
echo "API health check failed after 12 attempts." >&2
exit 1
