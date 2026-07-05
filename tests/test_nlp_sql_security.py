"""Security tests for the NLP-to-SQL validation layer.

Pure unit tests over :class:`SQLValidator` — no database or Ollama required,
so this file always runs and acts as the regression suite for the safety
guarantees of the /nlp/query endpoint.
"""

from __future__ import annotations

import pytest

from src.main.utility.exceptions import SQLValidationError
from src.main.utility.sql_validator import APPROVED_TABLES, SQLValidator


@pytest.fixture()
def validator() -> SQLValidator:
    """Validator with a small row ceiling to make LIMIT behaviour visible."""
    return SQLValidator(max_result_rows=100)


class TestSelectOnly:
    """Only read queries may pass."""

    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO fact_sales VALUES (1)",
            "UPDATE dim_customer SET email = 'x'",
            "DELETE FROM fact_sales",
            "DROP TABLE dim_product",
            "ALTER TABLE fact_sales ADD COLUMN x INT",
            "TRUNCATE fact_sales",
            "CREATE TABLE evil (x INT)",
            "GRANT ALL ON fact_sales TO public",
        ],
    )
    def test_write_statements_rejected(self, validator: SQLValidator, sql: str) -> None:
        with pytest.raises(SQLValidationError):
            validator.validate(sql)

    def test_plain_select_allowed(self, validator: SQLValidator) -> None:
        sql = validator.validate("SELECT product_name FROM dim_product")
        assert sql.startswith("SELECT")

    def test_cte_select_allowed(self, validator: SQLValidator) -> None:
        sql = validator.validate(
            "WITH spend AS (SELECT customer_key, SUM(net_revenue) AS s "
            "FROM fact_sales GROUP BY 1) SELECT * FROM spend"
        )
        assert "WITH" in sql.upper()

    def test_empty_sql_rejected(self, validator: SQLValidator) -> None:
        with pytest.raises(SQLValidationError):
            validator.validate("   ")


class TestInjectionResistance:
    """Classic injection shapes must be blocked."""

    def test_stacked_statements_rejected(self, validator: SQLValidator) -> None:
        with pytest.raises(SQLValidationError):
            validator.validate("SELECT * FROM fact_sales; DROP TABLE fact_sales")

    def test_comment_hidden_payload_rejected(self, validator: SQLValidator) -> None:
        # Comment stripping must not let a second statement sneak through.
        with pytest.raises(SQLValidationError):
            validator.validate("SELECT 1 FROM fact_sales -- x\n; DELETE FROM fact_sales")

    def test_forbidden_keyword_anywhere_rejected(self, validator: SQLValidator) -> None:
        with pytest.raises(SQLValidationError):
            validator.validate(
                "SELECT * FROM fact_sales WHERE 1 = (SELECT 1) AND 'a' = 'a' "
                "UNION SELECT * FROM read_csv('/etc/passwd')"
            )

    @pytest.mark.parametrize(
        "sql",
        [
            "ATTACH '/tmp/other.db' AS other",
            "COPY fact_sales TO '/tmp/out.csv'",
            "PRAGMA database_list",
            "INSTALL httpfs",
            "SET memory_limit='1GB'",
            "CALL pragma_table_info('fact_sales')",
        ],
    )
    def test_duckdb_escape_hatches_rejected(self, validator: SQLValidator, sql: str) -> None:
        with pytest.raises(SQLValidationError):
            validator.validate(sql)


class TestTableAllowList:
    """Only the approved star schema is queryable."""

    def test_unknown_table_rejected(self, validator: SQLValidator) -> None:
        with pytest.raises(SQLValidationError):
            validator.validate("SELECT * FROM pipeline_runs")

    def test_system_catalog_rejected(self, validator: SQLValidator) -> None:
        with pytest.raises(SQLValidationError):
            validator.validate("SELECT * FROM information_schema.tables")

    def test_all_approved_tables_pass(self, validator: SQLValidator) -> None:
        for table in APPROVED_TABLES:
            assert validator.validate(f"SELECT * FROM {table}")

    def test_joins_across_approved_tables_pass(self, validator: SQLValidator) -> None:
        sql = validator.validate(
            "SELECT c.category_name, SUM(f.net_revenue) FROM fact_sales f "
            "JOIN dim_category c USING (category_key) GROUP BY 1"
        )
        assert "fact_sales" in sql

    def test_join_to_unapproved_table_rejected(self, validator: SQLValidator) -> None:
        with pytest.raises(SQLValidationError):
            validator.validate(
                "SELECT * FROM fact_sales f JOIN secret_table s ON f.order_id = s.id"
            )


class TestRowLimits:
    """Every query is capped."""

    def test_limit_appended_when_missing(self, validator: SQLValidator) -> None:
        sql = validator.validate("SELECT * FROM dim_product")
        assert sql.endswith("LIMIT 100")

    def test_existing_small_limit_preserved(self, validator: SQLValidator) -> None:
        sql = validator.validate("SELECT * FROM dim_product LIMIT 10")
        assert "LIMIT 10" in sql

    def test_oversized_limit_capped(self, validator: SQLValidator) -> None:
        sql = validator.validate("SELECT * FROM dim_product LIMIT 999999")
        assert "LIMIT 100" in sql and "999999" not in sql
