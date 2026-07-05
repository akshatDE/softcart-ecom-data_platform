-- SoftCart staging warehouse schema (PostgreSQL 16).
-- Staging tables are truncated and reloaded on every pipeline run, so they
-- intentionally carry no foreign keys: quality problems are surfaced by the
-- data-quality suite instead of load failures.

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.stg_sales_channels (
    channel_id      INTEGER PRIMARY KEY,
    channel_name    TEXT NOT NULL,
    channel_type    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.stg_promotions (
    promotion_id    INTEGER PRIMARY KEY,
    promotion_code  TEXT NOT NULL,
    description     TEXT,
    discount_type   TEXT NOT NULL,
    discount_value  NUMERIC(10, 2) NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.stg_customers (
    customer_id     INTEGER PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           TEXT NOT NULL,
    phone           TEXT,
    signup_date     DATE NOT NULL,
    city            TEXT,
    state           TEXT,
    country         TEXT
);

CREATE TABLE IF NOT EXISTS staging.stg_customer_addresses (
    address_id      INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    address_type    TEXT NOT NULL,
    street          TEXT,
    city            TEXT,
    state           TEXT,
    country         TEXT,
    postal_code     TEXT
);

CREATE TABLE IF NOT EXISTS staging.stg_orders (
    order_id        INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    channel_id      INTEGER NOT NULL,
    promotion_id    INTEGER,
    order_date      TIMESTAMP NOT NULL,
    status          TEXT NOT NULL,
    total_amount    NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.stg_order_items (
    order_item_id   INTEGER PRIMARY KEY,
    order_id        INTEGER NOT NULL,
    product_id      TEXT NOT NULL,
    quantity        INTEGER NOT NULL,
    unit_price      NUMERIC(10, 2) NOT NULL,
    discount_amount NUMERIC(10, 2) NOT NULL,
    line_total      NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.stg_payments (
    payment_id      INTEGER PRIMARY KEY,
    order_id        INTEGER NOT NULL,
    payment_method  TEXT NOT NULL,
    amount          NUMERIC(12, 2) NOT NULL,
    payment_date    TIMESTAMP NOT NULL,
    status          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.stg_returns (
    return_id       INTEGER PRIMARY KEY,
    order_id        INTEGER NOT NULL,
    order_item_id   INTEGER NOT NULL,
    return_date     TIMESTAMP NOT NULL,
    quantity        INTEGER NOT NULL,
    refund_amount   NUMERIC(12, 2) NOT NULL,
    reason          TEXT
);

-- Product catalog flattened out of MongoDB documents.
CREATE TABLE IF NOT EXISTS staging.stg_products (
    product_id      TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL,
    brand           TEXT,
    category_name   TEXT NOT NULL,
    parent_category TEXT NOT NULL,
    price           NUMERIC(10, 2) NOT NULL,
    cost            NUMERIC(10, 2) NOT NULL,
    tags            TEXT,
    attributes      JSONB,
    variant_count   INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP
);

-- Pipeline audit trail used by timeliness data-quality checks.
CREATE TABLE IF NOT EXISTS staging.etl_audit (
    audit_id        BIGSERIAL PRIMARY KEY,
    table_name      TEXT NOT NULL,
    row_count       BIGINT NOT NULL,
    loaded_at       TIMESTAMP NOT NULL DEFAULT NOW()
);
