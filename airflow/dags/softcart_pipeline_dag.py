"""Airflow DAG orchestrating the full SoftCart data pipeline.

Task graph::

    generate_source_data
        ├── load_mysql_oltp ──┐
        └── load_mongodb_catalog ──┴─> extract_to_staging
                                        └─> staging_quality_gate
                                             └─> build_duckdb_analytics
                                                  └─> analytics_quality_gate
                                                       └─> refresh_serving_layer

The heavy lifting lives in ``src/main/services``; tasks are thin wrappers so
the same code runs from the CLI (``python -m src.main.main``) and Airflow.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.main.utility.config_loader import get_config

_config = get_config()

DEFAULT_ARGS = {
    "owner": _config.get("airflow", "dag_owner", "softcart-data-eng"),
    "retries": _config.get_int("airflow", "retries", 2),
    "retry_delay": timedelta(minutes=_config.get_int("airflow", "retry_delay_minutes", 5)),
    "depends_on_past": False,
}


def _generate_source_data(**_context) -> dict[str, int]:
    """Task: generate referentially consistent source data files."""
    from src.main.services import data_generation_service

    return data_generation_service.run()


def _load_mysql(**_context) -> dict[str, int]:
    """Task: truncate-and-load the MySQL OLTP database."""
    from src.main.services import ingestion_service

    return ingestion_service.run_mysql()


def _load_mongodb(**_context) -> int:
    """Task: replace the MongoDB product catalog."""
    from src.main.services import ingestion_service

    return ingestion_service.run_mongodb()


def _extract_to_staging(**_context) -> dict[str, int]:
    """Task: extract sources into PostgreSQL staging with cleaning."""
    from src.main.services import staging_service

    return staging_service.run()


def _staging_quality_gate(**_context) -> int:
    """Task: fail the run if staging data quality is unacceptable."""
    from src.main.services import data_quality_service

    return data_quality_service.run_staging_checks()


def _build_analytics(**_context) -> dict[str, int]:
    """Task: rebuild the DuckDB star schema from staging."""
    from src.main.services import transformation_service

    return transformation_service.run()


def _analytics_quality_gate(**_context) -> int:
    """Task: validate the freshly built analytics layer."""
    from src.main.services import data_quality_service

    return data_quality_service.run_analytics_checks()


def _refresh_serving_layer(**_context) -> str:
    """Task: verify the API is serving the new analytics build.

    The FastAPI service reads DuckDB per request and Streamlit caches expire
    after five minutes, so a health probe confirming the API can query the
    new build is all the 'refresh' the serving layer needs.
    """
    import requests

    from src.main.utility.logger import get_logger

    logger = get_logger("refresh_serving_layer")
    try:
        response = requests.get("http://api:8000/analytics/kpi-summary", timeout=30)
        response.raise_for_status()
        logger.info("Serving layer verified: {}", response.json()["data"])
        return "api-verified"
    except requests.RequestException as exc:
        # The API container may simply not be running in a pipeline-only
        # deployment; warn rather than fail the whole DAG run.
        logger.warning("Serving layer not reachable, skipping verification: {}", exc)
        return "api-unreachable"


with DAG(
    dag_id="softcart_pipeline",
    description="End-to-end SoftCart pipeline: generate -> sources -> staging -> DuckDB analytics",
    schedule=_config.get("airflow", "schedule", "@daily"),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    # The pipeline is truncate-and-reload end to end; concurrent runs would
    # race on the source loads and the DuckDB rebuild.
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["softcart", "ecommerce", "elt"],
) as dag:
    generate_source_data = PythonOperator(
        task_id="generate_source_data", python_callable=_generate_source_data
    )
    load_mysql_oltp = PythonOperator(
        task_id="load_mysql_oltp", python_callable=_load_mysql
    )
    load_mongodb_catalog = PythonOperator(
        task_id="load_mongodb_catalog", python_callable=_load_mongodb
    )
    extract_to_staging = PythonOperator(
        task_id="extract_to_staging", python_callable=_extract_to_staging
    )
    staging_quality_gate = PythonOperator(
        task_id="staging_quality_gate", python_callable=_staging_quality_gate
    )
    build_duckdb_analytics = PythonOperator(
        task_id="build_duckdb_analytics", python_callable=_build_analytics
    )
    analytics_quality_gate = PythonOperator(
        task_id="analytics_quality_gate", python_callable=_analytics_quality_gate
    )
    refresh_serving_layer = PythonOperator(
        task_id="refresh_serving_layer", python_callable=_refresh_serving_layer
    )

    generate_source_data >> [load_mysql_oltp, load_mongodb_catalog] >> extract_to_staging
    extract_to_staging >> staging_quality_gate >> build_duckdb_analytics
    build_duckdb_analytics >> analytics_quality_gate >> refresh_serving_layer
