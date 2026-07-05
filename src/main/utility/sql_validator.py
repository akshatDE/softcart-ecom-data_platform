"""Safety validation for SQL executed against the DuckDB analytics layer.

Every query produced by the NLP-to-SQL service (or any external caller) must
pass through :class:`SQLValidator` before execution. Defence in depth:

1. Comments are stripped and exactly one statement is allowed.
2. The statement must be a plain ``SELECT`` (CTEs via ``WITH`` are allowed).
3. A deny-list blocks DDL/DML and DuckDB-specific escape hatches
   (``ATTACH``, ``COPY``, ``INSTALL``, ``PRAGMA``, ...).
4. Every referenced table must be on the analytics-schema allow-list.
5. A ``LIMIT`` is enforced so a single query cannot return unbounded rows.

On top of this the executing connection is opened read-only and wrapped in a
timeout (see ``nlp_sql_service``), so validation is not the only barrier.
"""

from __future__ import annotations

import re

import sqlparse

from src.main.utility.exceptions import SQLValidationError

#: Tables the NLP layer may query — the DuckDB star schema only.
APPROVED_TABLES: frozenset[str] = frozenset(
    {
        "dim_date",
        "dim_customer",
        "dim_product",
        "dim_category",
        "dim_channel",
        "dim_promotion",
        "dim_payment_method",
        "fact_sales",
        "fact_returns",
    }
)

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|truncate|create|replace|merge|"
    r"grant|revoke|attach|detach|copy|export|import|install|load|call|"
    r"pragma|set|reset|begin|commit|rollback|vacuum|checkpoint|"
    r"read_csv|read_parquet|read_json|glob|sniff_csv"
    r")\b",
    re.IGNORECASE,
)

# Table references directly after FROM/JOIN; subqueries start with '(' and
# are therefore skipped, then validated via their own FROM clauses.
_TABLE_PATTERN = re.compile(
    r"\b(?:from|join)\s+([a-zA-Z_][\w.\"]*)",
    re.IGNORECASE,
)

_LIMIT_PATTERN = re.compile(r"\blimit\s+(\d+)", re.IGNORECASE)


class SQLValidator:
    """Validates that a SQL string is a safe, read-only analytics query."""

    def __init__(self, max_result_rows: int = 500) -> None:
        """Args:
        max_result_rows: LIMIT ceiling enforced on every query.
        """
        if max_result_rows <= 0:
            raise ValueError("max_result_rows must be positive")
        self.max_result_rows = max_result_rows

    def validate(self, sql: str) -> str:
        """Validate ``sql`` and return a sanitized, LIMIT-capped version.

        Raises:
            SQLValidationError: if the query is empty, not a single SELECT,
                references unapproved tables, or contains forbidden keywords.
        """
        if not sql or not sql.strip():
            raise SQLValidationError("Empty SQL statement.")

        cleaned = sqlparse.format(sql, strip_comments=True).strip()
        statements = [s for s in sqlparse.parse(cleaned) if str(s).strip(" ;\n\t")]
        if len(statements) != 1:
            raise SQLValidationError(
                f"Exactly one SQL statement is allowed, found {len(statements)}."
            )

        statement = str(statements[0]).strip().rstrip(";").strip()
        self._assert_select(statement)
        self._assert_no_forbidden_keywords(statement)
        self._assert_approved_tables(statement)
        return self._enforce_limit(statement)

    def _assert_select(self, statement: str) -> None:
        """Reject anything that is not a SELECT (or WITH ... SELECT)."""
        first_token = statement.split(None, 1)[0].lower() if statement else ""
        if first_token not in {"select", "with"}:
            raise SQLValidationError("Only SELECT queries are permitted.")
        if first_token == "with" and not re.search(r"\bselect\b", statement, re.IGNORECASE):
            raise SQLValidationError("WITH clause must terminate in a SELECT.")

    def _assert_no_forbidden_keywords(self, statement: str) -> None:
        """Deny-list scan across the whole statement (including strings —
        keywords inside literals are rare in analytics questions and blocking
        them errs on the safe side)."""
        match = _FORBIDDEN_KEYWORDS.search(statement)
        if match:
            raise SQLValidationError(
                f"Forbidden keyword detected: {match.group(1).upper()!r}."
            )

    def _assert_approved_tables(self, statement: str) -> None:
        """Every table after FROM/JOIN must be on the allow-list.

        CTE names defined in the statement itself are also allowed, since
        their contents are validated through their own FROM clauses.
        """
        cte_names = {
            name.lower()
            for name in re.findall(
                r"(?:\bwith\s+|,\s*)([a-zA-Z_]\w*)\s+as\s*\(", statement, re.IGNORECASE
            )
        }
        referenced = _TABLE_PATTERN.findall(statement)
        if not referenced:
            raise SQLValidationError("Query must reference at least one analytics table.")
        for raw_name in referenced:
            name = raw_name.strip('"').lower()
            if name.startswith("("):
                continue
            # Strip a schema/database qualifier if present (e.g. main.fact_sales).
            unqualified = name.rsplit(".", maxsplit=1)[-1]
            if unqualified in cte_names:
                continue
            if unqualified not in APPROVED_TABLES:
                raise SQLValidationError(
                    f"Table {raw_name!r} is not in the approved analytics schema."
                )

    def _enforce_limit(self, statement: str) -> str:
        """Cap an existing LIMIT to the ceiling, or append one."""
        match = _LIMIT_PATTERN.search(statement)
        if match:
            requested = int(match.group(1))
            if requested > self.max_result_rows:
                statement = _LIMIT_PATTERN.sub(
                    f"LIMIT {self.max_result_rows}", statement, count=1
                )
            return statement
        return f"{statement} LIMIT {self.max_result_rows}"
