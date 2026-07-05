#!/usr/bin/env bash
# Re-applies the MySQL schema and seed data against a *running* container.
# On first boot the official mysql image applies these files automatically
# from /docker-entrypoint-initdb.d; use this script to reset an existing
# instance without recreating the volume.
#
# Usage: ./scripts/init_mysql.sh
set -euo pipefail

CONTAINER="${MYSQL_CONTAINER:-softcart-mysql}"
ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-root_change_me}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[init_mysql] applying schema to container ${CONTAINER}"
docker exec -i "${CONTAINER}" mysql -uroot -p"${ROOT_PASSWORD}" \
    < "${PROJECT_ROOT}/resources/config/mysql_schema.sql"

echo "[init_mysql] applying seed data"
docker exec -i "${CONTAINER}" mysql -uroot -p"${ROOT_PASSWORD}" \
    < "${PROJECT_ROOT}/resources/config/seed_data.sql"

echo "[init_mysql] done"
