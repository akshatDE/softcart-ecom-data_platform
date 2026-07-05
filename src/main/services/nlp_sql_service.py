"""Natural-language-to-SQL over the DuckDB analytics layer via Ollama.

Safety model (defence in depth):

1. The prompt instructs the model to emit a single SELECT over the approved
   star schema — but the prompt is *not* trusted.
2. :class:`~src.main.utility.sql_validator.SQLValidator` enforces
   SELECT-only, an allow-list of tables, a keyword deny-list, and a LIMIT.
3. Execution happens on a **read-only** DuckDB connection.
4. A watchdog thread interrupts queries that exceed the configured timeout.
"""

from __future__ import annotations

import re
import threading
from typing import Any

import pandas as pd
import requests

from src.main.databases.duckdb_connector import DuckDBConnector
from src.main.utility.config_loader import get_config
from src.main.utility.exceptions import ETLError, NLPServiceError, SQLValidationError
from src.main.utility.logger import get_logger
from src.main.utility.sql_validator import APPROVED_TABLES, SQLValidator

logger = get_logger(__name__)

_SCHEMA_REFERENCE = """
Tables you may query (DuckDB star schema, order-item grain facts):

fact_sales(sales_key, order_id, order_item_id, order_date_key, customer_key,
    product_key, category_key, channel_key, promotion_key, payment_method_key,
    quantity, unit_price, gross_revenue, discount_amount, net_revenue)
fact_returns(return_key, return_id, order_id, order_item_id, return_date_key,
    customer_key, product_key, channel_key, quantity_returned, refund_amount, reason)
dim_date(date_key, full_date, year, quarter, month, month_name, day,
    day_of_week, day_name, week_of_year, is_weekend)
dim_customer(customer_key, customer_id, full_name, email, city, state, country, signup_date)
dim_product(product_key, product_id, product_name, brand, category_key,
    category_name, unit_price, unit_cost)
dim_category(category_key, category_name, parent_category)
dim_channel(channel_key, channel_id, channel_name, channel_type)
dim_promotion(promotion_key, promotion_id, promotion_code, description,
    discount_type, discount_value)
dim_payment_method(payment_method_key, payment_method)

Join facts to dimensions via the *_key columns (order_date_key -> dim_date.date_key).
""".strip()

_SYSTEM_PROMPT = f"""You are a SQL analyst for the SoftCart e-commerce warehouse.
Translate the user's question into exactly ONE DuckDB SQL SELECT statement.

Rules:
- Output ONLY the SQL statement, no explanation, no markdown fences.
- SELECT statements only. Never write INSERT, UPDATE, DELETE, DROP, ALTER,
  TRUNCATE, CREATE or any other statement type.
- Use only these tables and columns:

{_SCHEMA_REFERENCE}

- If the question cannot be answered from this schema, or is ambiguous or
  unsafe, output exactly: CANNOT_ANSWER
"""


class NLPSQLService:
    """Turns natural-language questions into validated, executed SQL."""

    def __init__(self) -> None:
        config = get_config()
        host = config.get("ollama", "host")
        port = config.get_int("ollama", "port")
        self._endpoint = f"http://{host}:{port}/api/chat"
        self.model = config.get("ollama", "model")
        self._temperature = config.get_float("ollama", "temperature", 0.0)
        self._request_timeout = config.get_int("ollama", "request_timeout_seconds", 120)
        self._query_timeout = config.get_int("nlp_sql", "query_timeout_seconds", 30)
        self._validator = SQLValidator(config.get_int("nlp_sql", "max_result_rows", 500))

    # ------------------------------------------------------------ generation

    def generate_sql(self, question: str) -> str:
        """Ask the local Ollama model for SQL answering ``question``."""
        question = (question or "").strip()
        if not question:
            raise NLPServiceError("Question must not be empty.")
        if len(question) > 1000:
            raise NLPServiceError("Question is too long (max 1000 characters).")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        logger.info("NLP-to-SQL request: {!r}", question[:120])
        try:
            response = requests.post(
                self._endpoint, json=payload, timeout=self._request_timeout
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise NLPServiceError(f"Ollama request failed: {exc}") from exc

        sql = self._extract_sql(content)
        if sql.upper() == "CANNOT_ANSWER":
            raise NLPServiceError(
                "The model could not answer this question from the analytics schema. "
                "Try rephrasing with concrete metrics (revenue, quantity, returns...)."
            )
        return sql

    @staticmethod
    def _extract_sql(content: str) -> str:
        """Strip markdown fences and reasoning chatter from a model reply."""
        text = content.strip()
        # Remove <think> blocks some Qwen variants emit.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()
        return text

    # ------------------------------------------------------------- execution

    def execute_validated(self, sql: str) -> tuple[str, pd.DataFrame]:
        """Validate ``sql`` and run it read-only under a timeout."""
        safe_sql = self._validator.validate(sql)
        duck = DuckDBConnector(read_only=True)
        watchdog = threading.Timer(self._query_timeout, duck.interrupt)
        watchdog.start()
        try:
            frame = duck.query_df(safe_sql)
        except ETLError as exc:
            if "INTERRUPT" in str(exc).upper():
                raise NLPServiceError(
                    f"Query exceeded the {self._query_timeout}s timeout and was cancelled."
                ) from exc
            raise
        finally:
            watchdog.cancel()
            duck.close()
        logger.info("NLP-to-SQL executed, {} rows", len(frame))
        return safe_sql, frame

    def answer(self, question: str) -> dict[str, Any]:
        """Full pipeline: question -> SQL -> validation -> result rows."""
        raw_sql = self.generate_sql(question)
        try:
            safe_sql, frame = self.execute_validated(raw_sql)
        except SQLValidationError as exc:
            logger.warning("Generated SQL rejected: {} — sql={!r}", exc, raw_sql[:300])
            raise NLPServiceError(f"Generated SQL was rejected by the safety validator: {exc}") from exc

        for column in frame.columns:
            if pd.api.types.is_datetime64_any_dtype(frame[column]):
                frame[column] = frame[column].dt.strftime("%Y-%m-%d")
        return {
            "question": question,
            "sql": safe_sql,
            "row_count": len(frame),
            "rows": frame.to_dict(orient="records"),
            "approved_tables": sorted(APPROVED_TABLES),
        }
