#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

compose run --rm --build api python -m app.tasks.sync_lta_data
