#!/usr/bin/env bash
# Generates source data and bulk-loads it into MySQL and MongoDB.
# Runs the Python steps inside the API container so no host-side Python
# environment is required.
#
# Usage: ./scripts/load_data.sh
set -euo pipefail

CONTAINER="${SOFTCART_APP_CONTAINER:-softcart-api}"

echo "[load_data] generating source data"
docker exec "${CONTAINER}" python -m src.main.main --step generate

echo "[load_data] loading MySQL OLTP and MongoDB catalog"
docker exec "${CONTAINER}" python -m src.main.main --step load-sources

echo "[load_data] done"
