-- SoftCart analytics layer (DuckDB) — Kimball-style star schema.
-- Dimensions carry surrogate *_key columns; business keys are retained for
-- lineage back to the source systems. Facts are at order-item grain.

CREATE TABLE IF NOT EXISTS dim_date (
    date_key        INTEGER PRIMARY KEY,     -- yyyymmdd
    full_date       DATE NOT NULL,
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    month_name      VARCHAR NOT NULL,
    day             INTEGER NOT NULL,
    day_of_week     INTEGER NOT NULL,
    day_name        VARCHAR NOT NULL,
    week_of_year    INTEGER NOT NULL,
    is_weekend      BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key    INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL,        -- business key (MySQL)
    full_name       VARCHAR NOT NULL,
    email           VARCHAR NOT NULL,
    city            VARCHAR,
    state           VARCHAR,
    country         VARCHAR,
    signup_date     DATE
);

CREATE TABLE IF NOT EXISTS dim_category (
    category_key    INTEGER PRIMARY KEY,
    category_name   VARCHAR NOT NULL,
    parent_category VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_key     INTEGER PRIMARY KEY,
    product_id      VARCHAR NOT NULL,        -- business key (MongoDB)
    product_name    VARCHAR NOT NULL,
    brand           VARCHAR,
    category_key    INTEGER NOT NULL REFERENCES dim_category (category_key),
    category_name   VARCHAR NOT NULL,
    unit_price      DECIMAL(10, 2) NOT NULL,
    unit_cost       DECIMAL(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_channel (
    channel_key     INTEGER PRIMARY KEY,
    channel_id      INTEGER NOT NULL,
    channel_name    VARCHAR NOT NULL,
    channel_type    VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_promotion (
    promotion_key   INTEGER PRIMARY KEY,
    promotion_id    INTEGER,                 -- NULL for the 'No Promotion' row
    promotion_code  VARCHAR NOT NULL,
    description     VARCHAR,
    discount_type   VARCHAR NOT NULL,
    discount_value  DECIMAL(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_payment_method (
    payment_method_key INTEGER PRIMARY KEY,
    payment_method     VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_sales (
    sales_key           BIGINT PRIMARY KEY,
    order_id            INTEGER NOT NULL,
    order_item_id       INTEGER NOT NULL,
    order_date_key      INTEGER NOT NULL REFERENCES dim_date (date_key),
    customer_key        INTEGER NOT NULL REFERENCES dim_customer (customer_key),
    product_key         INTEGER NOT NULL REFERENCES dim_product (product_key),
    category_key        INTEGER NOT NULL REFERENCES dim_category (category_key),
    channel_key         INTEGER NOT NULL REFERENCES dim_channel (channel_key),
    promotion_key       INTEGER NOT NULL REFERENCES dim_promotion (promotion_key),
    payment_method_key  INTEGER NOT NULL REFERENCES dim_payment_method (payment_method_key),
    quantity            INTEGER NOT NULL,
    unit_price          DECIMAL(10, 2) NOT NULL,
    gross_revenue       DECIMAL(12, 2) NOT NULL,
    discount_amount     DECIMAL(12, 2) NOT NULL,
    net_revenue         DECIMAL(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_returns (
    return_key          BIGINT PRIMARY KEY,
    return_id           INTEGER NOT NULL,
    order_id            INTEGER NOT NULL,
    order_item_id       INTEGER NOT NULL,
    return_date_key     INTEGER NOT NULL REFERENCES dim_date (date_key),
    customer_key        INTEGER NOT NULL REFERENCES dim_customer (customer_key),
    product_key         INTEGER NOT NULL REFERENCES dim_product (product_key),
    channel_key         INTEGER NOT NULL REFERENCES dim_channel (channel_key),
    quantity_returned   INTEGER NOT NULL,
    refund_amount       DECIMAL(12, 2) NOT NULL,
    reason              VARCHAR
);

-- Pipeline run log used by timeliness checks and the dashboard footer.
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id          BIGINT PRIMARY KEY,
    step_name       VARCHAR NOT NULL,
    row_counts      VARCHAR,
    completed_at    TIMESTAMP NOT NULL
);
