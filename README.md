# SoftCart Data Platform

A complete, production-style, end-to-end data engineering platform for the
fictional e-commerce company **SoftCart**. It simulates the full data
engineering lifecycle — generation, ingestion, storage, transformation,
orchestration, dimensional modeling, analytics, dashboarding, and data
quality — and runs entirely locally with Docker Compose, including
AI-assisted SQL generation via a local Ollama model.

## Architecture

```
                    ┌──────────────────────── Airflow (orchestration) ───────────────────────┐
                    │                                                                         │
┌─────────────┐   ┌─▼──────────┐    ┌──────────────┐    ┌───────────────┐    ┌────────────┐  │
│  Faker data  │  │ MySQL 8.0  │    │ PostgreSQL 16 │    │    DuckDB     │    │  FastAPI   │  │
│  generation  ├─►│   (OLTP)   ├───►│   (staging)   ├───►│ (star schema) │◄───┤   (API)    │  │
│  (Python)    │  └────────────┘    └──────▲───────┘    └───────▲───────┘    └─────▲──────┘  │
│              │  ┌────────────┐           │                    │                  │         │
│              ├─►│ MongoDB 7  ├───────────┘             quality gates       ┌─────┴──────┐  │
└─────────────┘   │ (catalog)  │        (extract+clean)  (pytest + gates)    │ Streamlit  │  │
                  └────────────┘                                             │ dashboard  │  │
                       Ollama (Qwen) ── NLP→SQL ── SQLValidator ──► DuckDB   └────────────┘  │
                    └─────────────────────────────────────────────────────────────────────────┘
```

**Flow:** Faker generates referentially consistent flat files → they are
bulk-loaded into MySQL (transactions) and MongoDB (product catalog) → the
staging service extracts, cleans, and lands everything in PostgreSQL →
the transformation service builds a Kimball star schema in DuckDB →
FastAPI serves it to the Streamlit dashboard, including a natural-language
query endpoint backed by Ollama and a strict SQL safety validator.

## Technology stack

| Layer | Technology |
|---|---|
| OLTP | MySQL 8.0 |
| NoSQL catalog | MongoDB 7.0 |
| DWH staging | PostgreSQL 16 |
| DWH analytics | DuckDB (star schema) |
| ETL | Python, SQLAlchemy, pandas |
| Data generation | Python, Faker |
| Orchestration | Apache Airflow 2.9 (LocalExecutor) |
| API | FastAPI + Uvicorn |
| Dashboard | Streamlit + Plotly |
| NLP → SQL | Ollama (Qwen, local) |
| Testing | Pytest |
| Logging | Loguru |
| Containers | Docker Compose |

## Project layout

```
src/main/
  models/        # dataclass domain models (customer, product, order, ...)
  factories/     # Faker-based generators with realistic distributions
  databases/     # MySQL / MongoDB / PostgreSQL / DuckDB connectors
  services/      # generation, ingestion, staging, transformation,
                 # data quality, analytics, NLP-to-SQL
  api/           # FastAPI app + analytics and NLP routes
  dashboard/     # Streamlit app + chart components per tab
  utility/       # config loader, loguru setup, SQL validator, exceptions
  main.py        # CLI pipeline runner
airflow/dags/    # softcart_pipeline_dag.py
resources/config/# config_file.ini + all SQL schemas + seed data
scripts/         # init/load/run helper shell scripts
tests/           # pytest data-quality + NLP-SQL security suites
```

## Setup

Prerequisites: Docker Desktop (8 GB+ RAM recommended — Ollama needs a few GB).

```bash
cp .env.example .env          # adjust passwords if you like
docker compose up -d --build  # starts all services
```

First boot takes a few minutes: MySQL/Postgres run their init scripts,
Airflow migrates its metadata DB, and `ollama-pull` downloads the model
configured in `.env` (`OLLAMA_MODEL`, default `qwen3.5` — any Qwen-family
model tag available in your Ollama registry works; smaller tags run faster
on modest hardware).

| Service | URL |
|---|---|
| Airflow UI | http://localhost:8080 (user/pass from `.env`, default `admin`/`admin_change_me`) |
| FastAPI docs | http://localhost:8000/docs |
| Streamlit dashboard | http://localhost:8501 |
| Ollama | http://localhost:11434 |

## Running the pipeline

**Option A — Airflow (recommended).** Open the Airflow UI, enable the
`softcart_pipeline` DAG, and trigger it. Tasks:

```
generate_source_data → [load_mysql_oltp, load_mongodb_catalog]
  → extract_to_staging → staging_quality_gate
  → build_duckdb_analytics → analytics_quality_gate → refresh_serving_layer
```

Each task has retries, structured logging, and fails the run if a data
quality gate does not pass.

**Option B — one shot from the CLI:**

```bash
./scripts/run_pipeline.sh            # full pipeline inside the api container
./scripts/run_pipeline.sh stage      # or any single step
./scripts/load_data.sh               # just generate + load the source systems
```

**Option C — on the host** (needs `pip install -r requirements.txt`; the
default config already points at `localhost` and the published ports):

```bash
python -m src.main.main --step all
python -m src.main.main --step generate   # generate | load-sources | stage | quality | transform
```

Data volumes (customers, products, orders, date range, seed) are configured
in `resources/config/config_file.ini` under `[data_generation]`.

## Configuration

Everything lives in `resources/config/config_file.ini`. Any value can be
overridden with an environment variable `SOFTCART_<SECTION>__<KEY>`, e.g.
`SOFTCART_MYSQL__HOST=mysql`. That is exactly how docker-compose retargets
the same config from `localhost` to container hostnames — no values are
hard-coded in scripts.

## Data model (DuckDB star schema)

Facts are at **order-item grain**:

- `fact_sales(sales_key, order_id, order_item_id, order_date_key, customer_key, product_key, category_key, channel_key, promotion_key, payment_method_key, quantity, unit_price, gross_revenue, discount_amount, net_revenue)`
- `fact_returns(return_key, ..., return_date_key, quantity_returned, refund_amount, reason)`

Dimensions: `dim_date`, `dim_customer`, `dim_product`, `dim_category`,
`dim_channel`, `dim_promotion` (with a reserved *No Promotion* row),
`dim_payment_method`. All dimensions carry integer surrogate keys plus the
original business keys for lineage. The model supports revenue (gross/net),
quantity, discounts, returns, repeat purchase behaviour, CLV, promotion,
product/category, and channel analyses.

## API

Interactive docs at `http://localhost:8000/docs`. Highlights:

```
GET  /analytics/revenue-by-category      GET  /analytics/channel-performance
GET  /analytics/revenue-by-product       GET  /analytics/channel-product-matrix
GET  /analytics/sales-trend?granularity= GET  /analytics/promotion-performance
GET  /analytics/customer-segments        GET  /analytics/revenue-concentration?entity=
GET  /analytics/repeat-vs-one-time       GET  /analytics/kpi-summary
POST /nlp/query                          {"question": "..."}
```

## Dashboard

Three business tabs plus an AI tab:

1. **Products & Categories** — revenue vs quantity by category, top products,
   gross vs net revenue, category trends.
2. **Customers & Concentration** — repeat vs one-time buyers, spending
   tiers, CLV distribution, top customers, Pareto revenue-concentration
   curves for products and customers.
3. **Channels & Promotions** — revenue/quantity per channel, best sellers
   per channel, promotion volume vs discount cost and net-revenue impact.
4. **Ask AI** — natural-language questions answered via Ollama; the
   generated SQL is always displayed alongside the result.

## NLP-to-SQL safety

The `/nlp/query` endpoint never trusts the model. Every generated query is:

1. Stripped of comments and restricted to **exactly one statement**;
2. Required to be a **SELECT** (CTEs allowed);
3. Scanned against a **keyword deny-list** (DML/DDL plus DuckDB escape
   hatches like `ATTACH`, `COPY`, `INSTALL`, `PRAGMA`, `read_csv`);
4. Checked against a **table allow-list** (the star schema only);
5. Capped with an enforced **LIMIT**;
6. Executed on a **read-only** DuckDB connection under a **query timeout**.

`tests/test_nlp_sql_security.py` is the regression suite for these
guarantees, including stacked-statement and comment-hidden injection shapes.

## Data quality

Five dimensions, testable from the command line:

```bash
docker exec softcart-api pytest tests/ -v     # or plain `pytest` on the host
```

- **Accuracy** — order totals = Σ line totals, payments match orders,
  net = gross − discount, refunds ≤ line value, valid email formats.
- **Completeness** — emails, order dates, categories, fact FKs not null.
- **Consistency** — items↔orders, MySQL product ids exist in the Mongo
  catalog, fact keys resolve in every dimension, standardized categories,
  staging vs analytics row counts agree.
- **Timeliness** — staging audit trail is fresh, latest order date within
  the configured staleness window, recent pipeline-run timestamp.
- **Uniqueness** — PKs, emails, surrogate keys, and fact grain unique
  (rerun-safe: full-refresh loads cannot double-count).

Database-backed tests skip cleanly if a layer hasn't been built yet; the
same checks also run *inside* the pipeline as Airflow quality gates.

## Troubleshooting

- **`docker compose up` fails on ports** — 3306/5432/27017/8000/8080/8501/11434
  must be free; stop local MySQL/Postgres instances or remap ports.
- **Airflow webserver keeps restarting** — first boot installs extra pip
  packages (`_PIP_ADDITIONAL_REQUIREMENTS`); give it 1–2 minutes, then check
  `docker logs softcart-airflow-webserver`.
- **Dashboard shows "No analytics data yet"** — the pipeline hasn't run;
  trigger the DAG or `./scripts/run_pipeline.sh`.
- **NLP tab errors with "Ollama request failed"** — the model is still
  downloading; check `docker logs softcart-ollama-pull`. On low-RAM machines
  set `OLLAMA_MODEL` in `.env` to a smaller tag and rerun
  `docker compose up -d ollama-pull`.
- **`fact_sales` DELETE fails with FK errors** — rebuilds clear facts before
  dimensions by design; if you edited the transformation, keep that order.
- **Reset everything** — `docker compose down -v` (drops all volumes), then
  `docker compose up -d --build`.

## License

Internal SoftCart engineering project — for local development and learning.
