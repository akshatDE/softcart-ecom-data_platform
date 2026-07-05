#!/usr/bin/env bash
# Runs the full end-to-end pipeline (generate -> load sources -> stage ->
# quality gate -> transform) inside the API container.
#
# Usage:
#   ./scripts/run_pipeline.sh          # full pipeline
#   ./scripts/run_pipeline.sh stage    # a single step (see --step choices)
set -euo pipefail

CONTAINER="${SOFTCART_APP_CONTAINER:-softcart-api}"
STEP="${1:-all}"

echo "[run_pipeline] running step '${STEP}' in container ${CONTAINER}"
docker exec "${CONTAINER}" python -m src.main.main --step "${STEP}"

echo "[run_pipeline] done"
