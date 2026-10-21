"""SoftCart synthetic data -> Snowflake Postgres.

Generation comes from the shared core (``src.main.generation``), the same code
the open-source pipeline uses; this file only adds the Postgres DDL and loader.
Run from the repo root::

    uv run python platforms/snowflake/datawriter.py

Connection settings come from ``platforms/snowflake/.env`` (see .env.example).
To run from a Snowflake Notebook instead, see platforms/snowflake/README.md.
"""

# %% CELL 1 — imports, shared generator, connection
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2

# In a notebook __file__ is undefined, so fall back to the working directory.
_HERE = Path(globals().get("__file__", "datawriter.py")).resolve().parent


def _find_repo_root(start: Path) -> Path:
    """Nearest ancestor that contains the shared generator package."""
    for candidate in (start, *start.parents):
        if (candidate / "src" / "main" / "generation").is_dir():
            return candidate
    raise RuntimeError(f"SoftCart repo root not found above {start}")


sys.path.insert(0, str(_find_repo_root(_HERE)))

from src.main.generation import GeneratedDataset, GenerationSettings, generate_dataset  # noqa: E402


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines from .env into os.environ (no-op if the file is absent)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env_file(_HERE / ".env")

# Snowflake Postgres connection. Postgres folds unquoted names to lowercase,
# so PG_SCHEMA=SOFTCART creates the schema `softcart`.
PG_HOST = os.environ.get("PG_HOST", "")
PG_PORT = int(os.environ.get("PG_PORT") or 5432)
PG_DATABASE = os.environ.get("PG_DATABASE") or "postgres"
PG_SCHEMA = os.environ.get("PG_SCHEMA") or "softcart"
PG_SECRET_NAME = "pg_cred"           # notebook secret alias (see README)


def _pg_credentials() -> tuple[str, str]:
    """User/password from .env (PG_USER/PG_PASSWORD), else the notebook-attached secret."""
    if os.environ.get("PG_USER") and os.environ.get("PG_PASSWORD"):
        return os.environ["PG_USER"], os.environ["PG_PASSWORD"]
    import _snowflake  # only available inside Snowflake runtimes

    creds = _snowflake.get_username_password(PG_SECRET_NAME)
    return creds.username, creds.password


def connect() -> psycopg2.extensions.connection:
    if not PG_HOST:
        raise RuntimeError("PG_HOST is not set; add it to platforms/snowflake/.env")
    user, password = _pg_credentials()
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DATABASE,
        user=user,
        password=password,
        sslmode="require",  # Snowflake Postgres only accepts TLS connections
        connect_timeout=15,
    )


# %% CELL 2 — Postgres DDL
# The product catalog is stored as JSONB; typed columns are generated from it.
DDL = f"""
CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA};
SET search_path TO {PG_SCHEMA};

CREATE TABLE IF NOT EXISTS sales_channels (
    channel_id      INTEGER      PRIMARY KEY,
    channel_name    VARCHAR(100) NOT NULL UNIQUE,
    channel_type    VARCHAR(50)  NOT NULL
        CHECK (channel_type IN ('web', 'mobile', 'marketplace', 'social', 'retail'))
);

CREATE TABLE IF NOT EXISTS promotions (
    promotion_id    INTEGER        PRIMARY KEY,
    promotion_code  VARCHAR(40)    NOT NULL UNIQUE,
    description     VARCHAR(255)   NOT NULL,
    discount_type   VARCHAR(20)    NOT NULL
        CHECK (discount_type IN ('percentage', 'fixed_amount')),
    discount_value  NUMERIC(10, 2) NOT NULL CHECK (discount_value > 0),
    start_date      DATE           NOT NULL,
    end_date        DATE           NOT NULL,
    CONSTRAINT chk_promo_dates CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id     INTEGER      PRIMARY KEY,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    phone           VARCHAR(40),
    signup_date     DATE         NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_addresses (
    address_id      INTEGER      PRIMARY KEY,
    customer_id     INTEGER      NOT NULL REFERENCES customers (customer_id) ON DELETE CASCADE,
    address_type    VARCHAR(20)  NOT NULL CHECK (address_type IN ('billing', 'shipping')),
    street          VARCHAR(255) NOT NULL,
    city            VARCHAR(100) NOT NULL,
    state           VARCHAR(100) NOT NULL,
    country         VARCHAR(100) NOT NULL,
    postal_code     VARCHAR(20)  NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id      VARCHAR(40)    PRIMARY KEY,
    document        JSONB          NOT NULL,
    name            VARCHAR        GENERATED ALWAYS AS (document->>'name') STORED,
    brand           VARCHAR        GENERATED ALWAYS AS (document->'brand'->>'name') STORED,
    category        VARCHAR        GENERATED ALWAYS AS (document->'category'->>'name') STORED,
    parent_category VARCHAR        GENERATED ALWAYS AS (document->'category'->>'parent') STORED,
    price           NUMERIC(10, 2) GENERATED ALWAYS AS ((document->'pricing'->>'price')::NUMERIC(10, 2)) STORED,
    cost            NUMERIC(10, 2) GENERATED ALWAYS AS ((document->'pricing'->>'cost')::NUMERIC(10, 2)) STORED
);

CREATE TABLE IF NOT EXISTS orders (
    order_id        INTEGER        PRIMARY KEY,
    customer_id     INTEGER        NOT NULL REFERENCES customers (customer_id),
    channel_id      INTEGER        NOT NULL REFERENCES sales_channels (channel_id),
    promotion_id    INTEGER        REFERENCES promotions (promotion_id),
    order_date      TIMESTAMP      NOT NULL,
    status          VARCHAR(20)    NOT NULL
        CHECK (status IN ('processing', 'shipped', 'delivered', 'cancelled')),
    total_amount    NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0)
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id   INTEGER        PRIMARY KEY,
    order_id        INTEGER        NOT NULL REFERENCES orders (order_id) ON DELETE CASCADE,
    product_id      VARCHAR(40)    NOT NULL REFERENCES products (product_id),
    quantity        INTEGER        NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    discount_amount NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    line_total      NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id      INTEGER        PRIMARY KEY,
    order_id        INTEGER        NOT NULL REFERENCES orders (order_id) ON DELETE CASCADE,
    payment_method  VARCHAR(20)    NOT NULL
        CHECK (payment_method IN ('credit_card', 'debit_card', 'paypal', 'apple_pay',
                                  'gift_card', 'bank_transfer')),
    amount          NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    payment_date    TIMESTAMP      NOT NULL,
    status          VARCHAR(20)    NOT NULL
        CHECK (status IN ('completed', 'pending', 'failed', 'refunded'))
);

CREATE TABLE IF NOT EXISTS returns (
    return_id       INTEGER        PRIMARY KEY,
    order_id        INTEGER        NOT NULL REFERENCES orders (order_id) ON DELETE CASCADE,
    order_item_id   INTEGER        NOT NULL REFERENCES order_items (order_item_id) ON DELETE CASCADE,
    return_date     TIMESTAMP      NOT NULL,
    quantity        INTEGER        NOT NULL CHECK (quantity > 0),
    refund_amount   NUMERIC(12, 2) NOT NULL CHECK (refund_amount >= 0),
    reason          VARCHAR(255)   NOT NULL
);

CREATE TABLE IF NOT EXISTS generation_manifest (
    generated_at    TIMESTAMPTZ    NOT NULL DEFAULT now(),
    seed            INTEGER        NOT NULL,
    counts          JSONB          NOT NULL
);
"""

# Parents before children so foreign keys resolve during the load.
LOAD_ORDER = (
    "sales_channels", "promotions", "customers", "customer_addresses",
    "products", "orders", "order_items", "payments", "returns",
)


# %% CELL 3 — Postgres persistence
def _copy_frame(cur: psycopg2.extensions.cursor, table: str, df: pd.DataFrame) -> None:
    """Bulk-load a DataFrame with COPY ... FROM STDIN (much faster than INSERTs)."""
    df = df.copy()
    # promotion_id has None for most orders -> pandas makes it float ("12.0"); keep it integer.
    if "promotion_id" in df.columns:
        df["promotion_id"] = df["promotion_id"].astype("Int64")
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")  # unquoted empty -> NULL in CSV COPY
    buf.seek(0)
    columns = ", ".join(df.columns)
    cur.copy_expert(f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv)", buf)


def write_to_postgres(dataset: GeneratedDataset) -> dict[str, int]:
    tables = dict(dataset.frames)
    tables["products"] = pd.DataFrame(
        {"product_id": [d["product_id"] for d in dataset.products],
         "document": [json.dumps(d) for d in dataset.products]}
    )

    counts: dict[str, int] = {}
    conn = connect()
    try:
        # One transaction: a failed run leaves the previous load untouched.
        with conn, conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute(f"TRUNCATE {', '.join(LOAD_ORDER)} CASCADE")
            for name in LOAD_ORDER:
                _copy_frame(cur, name, tables[name])
                counts[name] = len(tables[name])
            cur.execute(
                "INSERT INTO generation_manifest (seed, counts) VALUES (%s, %s)",
                (dataset.settings.seed, json.dumps(counts)),
            )
            # Small tables never reach autovacuum's analyze threshold; refresh
            # planner stats so row estimates (and Snowsight's metadata) are right.
            cur.execute(f"ANALYZE {', '.join(LOAD_ORDER)}, generation_manifest")
    finally:
        conn.close()

    print(f"Wrote dataset to {PG_DATABASE}.{PG_SCHEMA} on {PG_HOST}")
    for name, n in counts.items():
        print(f"  {name:<20} {n:>7,} rows")
    return counts


# %% CELL 4 — sanity check
def check_order_totals() -> int:
    """Orders whose total disagrees with the sum of their line items (expect 0)."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SET search_path TO {PG_SCHEMA}")
        cur.execute("""
            SELECT o.order_id
            FROM orders o
            JOIN order_items i USING (order_id)
            GROUP BY o.order_id, o.total_amount
            HAVING ABS(o.total_amount - SUM(i.line_total)) > 0.01
        """)
        return len(cur.fetchall())


# %% CELL 5 — run
if __name__ == "__main__" or "__file__" not in globals():
    dataset = generate_dataset(GenerationSettings())
    counts = write_to_postgres(dataset)
    print(f"order total mismatches: {check_order_totals()}")
