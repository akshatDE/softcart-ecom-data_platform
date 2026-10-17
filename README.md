# 🛒 SoftCart — E-commerce Data Platform + AI

`Airflow` `DuckDB` `PostgreSQL` `MySQL` `MongoDB` `FastAPI` `Ollama` `Docker`

End-to-end analytics platform pairing a conventional warehouse architecture with local LLM-powered Text-to-SQL.

<a href="https://github.com/akshatDE/softcart-ecom-data_platform">
  <img src="https://raw.githubusercontent.com/akshatDE/softcart-ecom-data_platform/main/softcart-ecom.png" alt="SoftCart architecture" width="100%" />
</a>

- 2 fact tables at order-item grain, 7 conformed dimensions with surrogate keys
- Two blocking DQ gates backed by a pytest suite that fails the run on violation
- SQL safety validator: SELECT-only, keyword denylist, table allowlist, injected LIMIT, read-only connection
- Docker Compose cut contributor setup from ~2 hours to under 10 minutes

---

An end-to-end ecommerce data engineering platform for the fictional retailer **SoftCart** — simulating real-world data infrastructure from source-system ingestion through dimensional modeling to analytics dashboards. The entire stack runs locally with Docker Compose and includes AI-assisted SQL generation powered by a local LLM via Ollama.

The platform covers the full data engineering lifecycle: **data generation → OLTP/NoSQL ingestion → staging warehouse → Kimball star schema → quality gates → API serving → dashboards → natural-language analytics**, orchestrated by Apache Airflow.

---

## Architecture

```
Data Generation (Python + Faker)
    ├── products.json ───────────→ MongoDB 7   (Product Catalog)
    └── orders / items / customers /
        payments / returns / promos
        / channels (CSV) ────────→ MySQL 8     (Transactional OLTP)
                      ↓
        Extraction + Cleaning (Python, SQLAlchemy, pandas)
                      ↓
        PostgreSQL 16  —  staging schema (stg_* tables + ETL audit trail)
                      ↓   [staging quality gate]
        DuckDB  —  analytics layer (Kimball star schema)
                      ↓   [analytics quality gate]
        FastAPI (serving layer)  ←──  Ollama (NLP → SQL + safety validator)
                      ↓
        Streamlit dashboard (Plotly)
```

All of the above is orchestrated end-to-end by **Apache Airflow** (`softcart_pipeline` DAG) and runs on a single Docker Compose network.

**Flow:** Faker generates referentially consistent flat files → they are bulk-loaded into MySQL (transactions) and MongoDB (product catalog) → the staging service extracts, cleans, and lands everything in PostgreSQL → a quality gate validates staging → the transformation service builds a Kimball star schema in DuckDB → a second quality gate validates analytics → FastAPI serves the star schema to the Streamlit dashboard, including a natural-language query endpoint backed by Ollama behind a strict SQL safety validator.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| OLTP | MySQL 8.0 | Transactional source of truth: customers, orders, order items, payments, returns, promotions, channels |
| NoSQL | MongoDB 7.0 | Product catalog as nested documents (attributes, tags, variants) |
| DWH staging | PostgreSQL 16 | Cleaned, flattened landing zone (`staging` schema) + ETL audit trail |
| DWH analytics | DuckDB | Kimball star schema at order-item grain (facts + conformed dimensions) |
| Orchestration | Apache Airflow 2.10 (LocalExecutor) | Daily scheduled DAG with retries and in-pipeline quality gates |
| ETL | Python, SQLAlchemy, pandas | DB-to-DB extraction, cleaning, and transformation |
| Data Generation | Python, Faker | Referentially consistent ecommerce datasets with realistic distributions |
| API | FastAPI + Uvicorn | Analytics endpoints over the star schema + NLP-to-SQL endpoint |
| Dashboard | Streamlit + Plotly | Four-tab analytics dashboard, including an "Ask AI" tab |
| NLP → SQL | Ollama (Qwen, fully local) | Natural-language questions translated into validated DuckDB SQL |
| Data Quality | Pytest | Accuracy, completeness, consistency, timeliness, uniqueness suites |
| Logging | Loguru | Structured, rotated logs across every service |
| Containerization | Docker Compose | Nine services on a shared bridge network |

---

## Project Structure

```
softcart-ecom-data_platform/
├── src/main/
│   ├── models/                     # Dataclass domain models
│   │   ├── customer.py             #   Customer + address
│   │   ├── product.py              #   Product with category/brand/attributes
│   │   ├── order.py                #   Order + order items
│   │   ├── payment.py              #   Payment (method, status)
│   │   ├── promotion.py            #   Promotion (percentage / fixed amount)
│   │   └── sales_channel.py        #   Sales channel (Online, Mobile App, ...)
│   ├── factories/                  # Faker-based generators, realistic distributions
│   │   ├── customer_factory.py     #   Customers + billing/shipping addresses
│   │   ├── product_factory.py      #   Catalog documents for MongoDB
│   │   ├── order_factory.py        #   Orders, items, payments, returns
│   │   └── promotion_factory.py    #   Promotions with validity windows
│   ├── databases/                  # Connection managers (one per engine)
│   │   ├── base_sql_connector.py   #   Shared SQLAlchemy engine handling
│   │   ├── mysql_connector.py      #   MySQL (PyMySQL + SQLAlchemy)
│   │   ├── mongodb_connector.py    #   MongoDB (pymongo)
│   │   ├── postgres_connector.py   #   PostgreSQL (psycopg2 + SQLAlchemy)
│   │   └── duckdb_connector.py     #   DuckDB (read-write + read-only modes)
│   ├── services/                   # Pipeline steps (shared by CLI and Airflow)
│   │   ├── data_generation_service.py  # Generate all source datasets
│   │   ├── ingestion_service.py        # Bulk-load MySQL OLTP + MongoDB catalog
│   │   ├── staging_service.py          # Extract + clean → PostgreSQL staging
│   │   ├── transformation_service.py   # Build the DuckDB star schema
│   │   ├── data_quality_service.py     # Staging / analytics quality gates
│   │   ├── analytics_service.py        # Business queries behind the API
│   │   └── nlp_sql_service.py          # Ollama prompt + SQL validation + execution
│   ├── api/
│   │   ├── app.py                  # FastAPI app factory + health endpoint
│   │   └── routes/
│   │       ├── analytics_routes.py # /analytics/* endpoints
│   │       └── nlp_sql_routes.py   # POST /nlp/query
│   ├── dashboard/
│   │   ├── streamlit_app.py        # Dashboard entry point (4 tabs)
│   │   └── components/
│   │       ├── product_charts.py   #   Products & categories tab charts
│   │       ├── customer_charts.py  #   Customers & concentration tab charts
│   │       └── channel_charts.py   #   Channels & promotions tab charts
│   ├── utility/
│   │   ├── config_loader.py        # INI config + env-var override mechanism
│   │   ├── logger.py               # Loguru setup (rotation, retention)
│   │   ├── sql_validator.py        # NLP-SQL safety validator (see below)
│   │   └── exceptions.py           # SoftCartError hierarchy
│   └── main.py                     # CLI pipeline runner (--step ...)
├── airflow/dags/
│   └── softcart_pipeline_dag.py    # 8-task DAG with quality gates
├── resources/config/
│   ├── config_file.ini             # Single source of configuration
│   ├── mysql_schema.sql            # OLTP DDL (applied on first boot)
│   ├── seed_data.sql               # Reference seed rows (channels, ...)
│   ├── postgres_staging_schema.sql # Staging DDL (applied on first boot)
│   └── duckdb_analytics_schema.sql # Star schema DDL
├── scripts/
│   ├── run_pipeline.sh             # Run full pipeline (or one step) in the API container
│   ├── load_data.sh                # Generate + load the source systems only
│   ├── init_mysql.sh               # Re-apply MySQL schema/seed to a running container
│   └── init_postgres.sh            # First-boot init (creates Airflow metadata DB)
├── tests/                          # Pytest suites (also run as Airflow quality gates)
│   ├── test_accuracy.py            #   Totals reconcile, valid emails, refunds ≤ line value
│   ├── test_completeness.py        #   Required fields and FKs not null
│   ├── test_consistency.py         #   Cross-system and cross-layer agreement
│   ├── test_timeliness.py          #   Freshness of audit trail and order dates
│   ├── test_uniqueness.py          #   PKs, surrogate keys, fact grain (rerun-safe)
│   └── test_nlp_sql_security.py    #   SQL-injection regression suite for /nlp/query
├── data/
│   ├── generated/                  # Faker output (CSV + JSON, gitignored)
│   └── analytics/                  # softcart.duckdb (gitignored)
├── snowflake-version/              # Placeholder: upcoming Snowflake cloud DWH port
├── docker-compose.yml              # MySQL, MongoDB, Postgres, Ollama (+pull),
│                                   # Airflow (init/webserver/scheduler), API, dashboard
├── Dockerfile                      # Shared image for the API and dashboard services
├── .env.example                    # Copy to .env; credentials and port overrides
└── requirements.txt                # Pinned Python dependencies
```

---

## Data Model

### Source Systems (OLTP)

**MySQL — `softcart_oltp`** (full relational model with FKs and CHECK constraints)

| Table | Contents |
|-------|----------|
| `customers` | customer_id, name, unique email, phone, signup_date |
| `customer_addresses` | billing/shipping addresses per customer |
| `orders` | order_id, customer, channel, optional promotion, order_date, status, total_amount |
| `order_items` | line items — product_id (business key into MongoDB), quantity, unit_price, discount, line_total |
| `payments` | payment per order — method (credit_card … bank_transfer), amount, status |
| `returns` | returned items — quantity, refund_amount, reason |
| `promotions` | promo code, percentage or fixed_amount discount, validity window |
| `sales_channels` | channel name + type (Online, Mobile App, In-Store, …) |

**MongoDB — `softcart_catalog`**
- `products` collection: nested documents with `product_id`, name, brand, category, price, cost, tags, attributes, and variants.

### Staging Layer (PostgreSQL — `staging` schema)

Truncate-and-reload tables, intentionally without foreign keys — quality problems surface in the data-quality suite rather than as load failures:

- `stg_customers`, `stg_customer_addresses` — cleaned replicas of MySQL (addresses denormalized onto the customer for the city/state/country used downstream)
- `stg_orders`, `stg_order_items`, `stg_payments`, `stg_returns` — cleaned transactional replicas
- `stg_promotions`, `stg_sales_channels` — reference data
- `stg_products` — MongoDB documents flattened to rows (attributes kept as JSONB)
- `etl_audit` — row counts + load timestamps per table, consumed by the timeliness checks

### Analytics Layer (DuckDB — Kimball star schema)

Facts at **order-item grain**; every dimension carries an integer surrogate key plus the original business key for lineage:

**Facts**
- `fact_sales` — order_id, order_item_id, FKs to all dimensions, quantity, unit_price, gross_revenue, discount_amount, net_revenue
- `fact_returns` — return_date_key, customer/product/channel keys, quantity_returned, refund_amount, reason

**Dimensions**
- `dim_date` — yyyymmdd key, year/quarter/month/week, day names, weekend flag
- `dim_customer` — name, email, city/state/country, signup_date
- `dim_product` — name, brand, category, unit price and cost
- `dim_category` — category + parent category
- `dim_channel` — channel name + type
- `dim_promotion` — promo code, discount type/value, with a reserved **"No Promotion"** row so facts never need NULL keys
- `dim_payment_method` — payment method

Plus `pipeline_runs`, a run log used by the timeliness checks and the dashboard footer. The model supports revenue (gross/net), quantity, discount, returns, repeat-purchase, CLV, promotion, product/category, and channel analyses.

---

## Airflow DAG

The `softcart_pipeline` DAG (schedule `@daily`, retries ×2, `max_active_runs=1` since the pipeline is truncate-and-reload end to end):

```
generate_source_data
    ├── load_mysql_oltp ──────────┐
    └── load_mongodb_catalog ─────┴─→ extract_to_staging
                                        └─→ staging_quality_gate
                                             └─→ build_duckdb_analytics
                                                  └─→ analytics_quality_gate
                                                       └─→ refresh_serving_layer
```

Tasks are thin wrappers around `src/main/services`, so the identical code runs from the CLI and from Airflow. The two quality gates fail the run if the data-quality suite does not pass; `refresh_serving_layer` probes the API to confirm it serves the fresh build.

---

## Business Questions

1. Which product categories and individual products drive the most revenue vs quantity — and how does gross compare to net after discounts?
2. How are sales trending over time — are certain categories growing or declining?
3. What does customer purchasing behavior look like — repeat buyers vs one-time, spending tiers, customer lifetime value?
4. What is the revenue concentration — do a small number of products/customers account for most sales (Pareto)?
5. Which products sell best on which channel, and do promotions drive more volume or just discount away revenue?

Every question maps to a dashboard tab and a dedicated `/analytics/*` API endpoint — or you can simply ask it in plain English on the **Ask AI** tab.

---

## Getting Started

### Prerequisites

- Docker Desktop with 8 GB+ RAM allocated (Ollama needs a few GB for the model)
- Optional, for host-side runs: Python 3.12+ and `pip` / `uv`

### Setup

```bash
# Clone the repo
git clone https://github.com/akshatDE/softcart-ecom-data_platform.git
cd softcart-ecom-data_platform

# Configure credentials (defaults work out of the box)
cp .env.example .env

# Start everything: databases, Ollama, Airflow, API, dashboard
docker compose up -d --build
```

First boot takes a few minutes: MySQL/Postgres run their init scripts, Airflow migrates its metadata DB, and the one-shot `ollama-pull` container downloads the model configured in `.env` (`OLLAMA_MODEL`, default `qwen3.5`; smaller Qwen tags run faster on modest hardware). Already running Ollama natively with models downloaded? Set `OLLAMA_UPSTREAM_HOST=host.docker.internal` in `.env` instead.

| Service | URL |
|---------|-----|
| Airflow UI | http://localhost:8080 (default `admin` / `admin_change_me`) |
| FastAPI docs | http://localhost:8000/docs |
| Streamlit dashboard | http://localhost:8501 |
| Ollama | http://localhost:11434 |

### Running the pipeline

**Option A — Airflow (recommended).** Open the Airflow UI, enable the `softcart_pipeline` DAG, and trigger it.

**Option B — one shot from the CLI** (runs inside the API container, no host Python needed):

```bash
./scripts/run_pipeline.sh            # full pipeline
./scripts/run_pipeline.sh stage      # or any single step
./scripts/load_data.sh               # just generate + load the source systems
```

**Option C — on the host** (`pip install -r requirements.txt`; the default config already points at `localhost` and the published ports):

```bash
python -m src.main.main --step all
python -m src.main.main --step generate   # generate | load-sources | stage | quality | transform
```

By default the generator produces **500 customers, 200 products, 6,000 orders** (up to 5 items each), 20 promotions, and an 8% return rate across 2024-01-01 → 2026-06-30, with a fixed seed (42) for reproducibility — all tunable in `resources/config/config_file.ini` under `[data_generation]`.

### Verify

```bash
# MySQL: order count in the OLTP database
docker exec softcart-mysql mysql -usoftcart -psoftcart_change_me \
  -e "SELECT COUNT(*) FROM softcart_oltp.orders;"

# MongoDB: product catalog document count
docker exec softcart-mongodb mongosh -u softcart -p softcart_change_me \
  --authenticationDatabase admin softcart_catalog \
  --quiet --eval "db.products.countDocuments()"

# PostgreSQL: staged order rows
docker exec softcart-postgres psql -U softcart -d softcart_staging \
  -c "SELECT COUNT(*) FROM staging.stg_orders;"

# DuckDB: fact table row count
docker exec softcart-api python -c "import duckdb; \
  print(duckdb.connect('/opt/softcart/data/analytics/softcart.duckdb', read_only=True) \
  .sql('SELECT COUNT(*) FROM fact_sales').fetchone()[0])"

# API: KPI summary over the star schema
curl -s http://localhost:8000/analytics/kpi-summary
```

---

## Configuration

Everything lives in a single file, `resources/config/config_file.ini` — database connections, data-generation volumes, pipeline knobs, Airflow schedule, Ollama model, API/dashboard hosts, and logging.

Any value can be overridden with an environment variable named `SOFTCART_<SECTION>__<KEY>`, e.g.:

```bash
SOFTCART_MYSQL__HOST=mysql
SOFTCART_DATA_GENERATION__NUM_ORDERS=50000
SOFTCART_OLLAMA__MODEL=qwen3.5
```

That is exactly how `docker-compose.yml` retargets the same config from `localhost` (host runs) to container hostnames — no values are hard-coded in scripts. Credentials and published host ports are set in `.env` (copy from `.env.example`; `.env` is gitignored).

---

## API

Interactive docs at `http://localhost:8000/docs`. Highlights:

```
GET  /analytics/kpi-summary              GET  /analytics/channel-performance
GET  /analytics/revenue-by-category      GET  /analytics/channel-product-matrix
GET  /analytics/revenue-by-product       GET  /analytics/promotion-performance
GET  /analytics/sales-trend?granularity= GET  /analytics/revenue-concentration?entity=
GET  /analytics/customer-segments        GET  /analytics/repeat-vs-one-time
POST /nlp/query                          {"question": "..."}
```

---

## Dashboard

Three business tabs plus an AI tab (`http://localhost:8501`):

1. **Products & Categories** — revenue vs quantity by category, top products, gross vs net revenue, category trends over time.
2. **Customers & Concentration** — repeat vs one-time buyers, spending tiers, CLV distribution, top customers, Pareto revenue-concentration curves for products and customers.
3. **Channels & Promotions** — revenue/quantity per channel, best sellers per channel, promotion volume vs discount cost and net-revenue impact.
4. **Ask AI** — natural-language questions answered via the local Ollama model; the generated SQL is always displayed alongside the result.

---

## NLP-to-SQL Safety

The `/nlp/query` endpoint never trusts the model. Every generated query is:

1. Stripped of comments and restricted to **exactly one statement**;
2. Required to be a **SELECT** (CTEs allowed);
3. Scanned against a **keyword deny-list** (DML/DDL plus DuckDB escape hatches like `ATTACH`, `COPY`, `INSTALL`, `PRAGMA`, `read_csv`);
4. Checked against a **table allow-list** (the star schema only);
5. Capped with an enforced **LIMIT**;
6. Executed on a **read-only** DuckDB connection under a **query timeout**.

`tests/test_nlp_sql_security.py` is the regression suite for these guarantees, including stacked-statement and comment-hidden injection shapes.

---

## Data Quality

Five dimensions, testable from the command line — the same checks also run *inside* the pipeline as Airflow quality gates:

```bash
docker exec softcart-api pytest tests/ -v     # or plain `pytest` on the host
```

| Dimension | What is checked |
|-----------|-----------------|
| **Accuracy** | Order totals = Σ line totals, payments match orders, net = gross − discount, refunds ≤ line value, valid email formats |
| **Completeness** | Emails, order dates, categories, and fact FKs are not null |
| **Consistency** | Items↔orders agree, MySQL product ids exist in the Mongo catalog, fact keys resolve in every dimension, categories standardized, staging vs analytics row counts match |
| **Timeliness** | Staging audit trail is fresh, latest order date within the configured staleness window, recent pipeline-run timestamp |
| **Uniqueness** | PKs, emails, surrogate keys, and fact grain unique — rerun-safe: full-refresh loads cannot double-count |

Database-backed tests skip cleanly if a layer hasn't been built yet.

---

## Troubleshooting

- **`docker compose up` fails on ports** — 3306 / 5432 / 27017 / 8000 / 8080 / 8501 / 11434 must be free; stop local MySQL/Postgres/Ollama instances or remap via the `*_HOST_PORT` variables in `.env`.
- **Airflow webserver keeps restarting** — first boot installs extra pip packages (`_PIP_ADDITIONAL_REQUIREMENTS`); give it 1–2 minutes, then check `docker logs softcart-airflow-webserver`.
- **Dashboard shows "No analytics data yet"** — the pipeline hasn't run; trigger the DAG or `./scripts/run_pipeline.sh`.
- **NLP tab errors with "Ollama request failed"** — the model is still downloading; check `docker logs softcart-ollama-pull`. On low-RAM machines set `OLLAMA_MODEL` in `.env` to a smaller tag and rerun `docker compose up -d ollama-pull`.
- **`fact_sales` DELETE fails with FK errors** — rebuilds clear facts before dimensions by design; if you edited the transformation, keep that order.
- **Reset everything** — `docker compose down -v` (drops all volumes), then `docker compose up -d --build`.

---

## Roadmap

- [x] Data generation pipeline (customers, products, orders, payments, returns, promotions, channels)
- [x] Docker Compose (MySQL, MongoDB, PostgreSQL, Ollama, Airflow, API, dashboard)
- [x] Connection managers per database engine
- [x] ETL: MySQL/MongoDB → PostgreSQL staging with cleaning
- [x] Dimensional modeling (Kimball star schema in DuckDB)
- [x] Data-quality suite (accuracy, completeness, consistency, timeliness, uniqueness)
- [x] Apache Airflow orchestration with quality gates
- [x] FastAPI serving layer
- [x] Streamlit dashboard
- [x] Ollama text-to-SQL analytics with SQL safety validation
- [ ] Snowflake cloud DWH port (see `snowflake-version/`)

---

## License

This project is for educational and portfolio purposes.
