#!/usr/bin/env bash
# PostgreSQL initialization: runs inside the official postgres image's
# /docker-entrypoint-initdb.d on first boot. Creates the Airflow metadata
# database alongside the staging database (created via POSTGRES_DB).
# The staging schema itself is applied by 02_staging_schema.sql, which the
# entrypoint executes automatically after this script.
set -euo pipefail

echo "[init_postgres] creating airflow metadata database"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    SELECT 'CREATE DATABASE airflow'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
    GRANT ALL PRIVILEGES ON DATABASE airflow TO "$POSTGRES_USER";
SQL

echo "[init_postgres] done"
