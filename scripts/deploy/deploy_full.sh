#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/up_infra.sh"
"${SCRIPT_DIR}/migrate.sh"
"${SCRIPT_DIR}/sync_static_data.sh"
"${SCRIPT_DIR}/up_api.sh"
