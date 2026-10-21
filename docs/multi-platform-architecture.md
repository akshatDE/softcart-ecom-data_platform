# Multi-platform architecture: one generator, many platforms

SoftCart is an open-source data platform with platform-specific versions
(Snowflake now, Databricks next). This document explains how the code is
organised to support that, why it is organised this way, and how to add a new
platform.

## The goal

- The **Faker data generation** belongs to the open-source project and stays there.
- Each platform version (**Snowflake**, **Databricks**, ...) **reuses** that
  generator and adds only what is specific to its platform.
- A fix or improvement to the generator should reach every platform
  automatically, without copying code.

## What we found

Before this change, the same generation logic existed in **three places**:

| Copy | Status |
|---|---|
| `src/main/factories/` + `src/main/models/` + `DataGenerationService` | The original, tracked in git, used by Airflow |
| `softcart_data_generator.py` (+ `.ipynb`) | A standalone, notebook-friendly copy |
| `snowflake-version/datawriter.py` | A copy of the copy (about 700 of its 895 lines), plus Postgres code |

All three produced identical data, which we verified before touching anything.
But they had already begun to drift: only the standalone copy converted
`orders.promotion_id` to an integer type. Every future change would have had to
be made three times, and sooner or later one copy would have been missed.

We also considered using a **separate git branch per platform**, and decided
against it (see [Why not branches?](#why-not-branches)).

## What we changed

### 1. Split generation from output in the original code

The original `DataGenerationService` both **built** the data and **wrote** it
to CSV/JSON files. Because those two jobs were tangled together, nobody could
reuse the generation without also getting the file writing. That is why the
copies were made.

We split it into a new package, `src/main/generation/`:

```
src/main/generation/
├── __init__.py
├── dataset.py      # GenerationSettings, GeneratedDataset, generate_dataset()  (no I/O)
└── local_sink.py   # write_to_directory()  (CSV + products.json + manifest.json)
```

- `generate_dataset(settings)` runs the existing factories and returns the
  data **in memory**: one DataFrame per table, plus the product catalog as
  JSON documents. It never touches disk or a database.
- `GenerationSettings` holds the knobs (counts, date window, seed). Its
  defaults match `config_file.ini`, and `GenerationSettings.from_config()`
  reads that file.
- `write_to_directory()` is the open-source pipeline's output format, now
  just one of several possible outputs.

`DataGenerationService` is now a thin wrapper: read settings, call
`generate_dataset()`, call `write_to_directory()`. Its public interface
(`run()`, `PRODUCTS_FILE`, `CSV_ENTITIES`) is unchanged, so Airflow, the CLI
(`python -m src.main.main --step generate`) and `ingestion_service` work as
before.

**Verified:** with the configured seed, the refactored code produces exactly
the same rows in all 8 tables and the same 200 product documents as before.
The only exception is the wall-clock `created_at` timestamp, which differed
between runs before this change too.

### 2. Added tests for the guarantees every platform relies on

`tests/test_generation.py` is a set of fast unit tests that need no database:

| Test | Guarantees |
|---|---|
| `test_same_seed_produces_identical_data` | Same seed gives the same dataset, so all platforms load identical data |
| `test_different_seed_produces_different_data` | The seed actually matters |
| `test_all_tables_present_and_sized` | Every table exists, with the requested counts |
| `test_money_reconciles` | Order total = sum of line totals = payment amount |
| `test_foreign_keys_resolve` | Every reference points at a row that exists |
| `test_invalid_window_rejected` | Bad settings fail loudly |

Run them with `uv run pytest tests/test_generation.py`.

We also added `faker` (which the generator needs but `pyproject.toml` was
missing) and `pytest` (as a dev dependency).

### 3. Rebuilt the Snowflake version on top of the shared core

`snowflake-version/` became `platforms/snowflake/`:

```
platforms/snowflake/
├── README.md        # how to run it, locally or from a Snowflake Notebook
├── datawriter.py    # Postgres DDL + COPY loader; imports the shared generator
├── .env.example     # connection template (the real .env is git-ignored)
└── softcart_dbt/    # placeholder for the Snowflake dbt project
```

`datawriter.py` went from **895 lines to about 270**, and none of the
remaining lines generate data. Its core is now:

```python
from src.main.generation import GenerationSettings, generate_dataset

dataset = generate_dataset(GenerationSettings())
write_to_postgres(dataset)   # the only Snowflake-specific part
```

Other improvements made along the way:

- **`ANALYZE` after loading.** Small tables (`promotions`, `sales_channels`,
  `generation_manifest`) never reached Postgres's automatic-statistics
  threshold, so Snowsight showed them as having 0 rows. Their statistics are
  now refreshed as part of the load.
- **No hard-coded instance host.** `PG_HOST` must come from `.env`, so a
  personal Snowflake hostname isn't published in an open-source repo.
- **The `promotion_id` integer conversion lives in the Postgres loader**,
  where it's needed, instead of changing the shared output.

**Verified:** ran it end to end against Snowflake Postgres. It produced the same
row counts as before (17,237 order items, etc.), 0 order-total mismatches, and
correct row estimates for the small tables.

## The resulting layout

```
softcart-ecom-data_platform/
├── src/main/
│   ├── models/, factories/     # domain logic (unchanged)
│   ├── generation/             # SHARED: generate_dataset() + local file sink
│   └── services/               # open-source pipeline (Airflow / CLI)
├── platforms/
│   ├── snowflake/              # Snowflake-only code
│   └── databricks/             # (next)
├── tests/
│   └── test_generation.py      # guarantees all platforms depend on
└── docs/
    └── multi-platform-architecture.md
```

The rule that holds it together:

> **The generator returns data and nothing else. Each platform only adds a writer.**

## Why not branches?

A long-lived branch per platform (`main`, `snowflake-version`,
`databricks-version`) looks tidy at first, but:

| | Branch per platform | Folder per platform (what we did) |
|---|---|---|
| Fixing a generator bug | Fix on `main`, then merge into every platform branch by hand | Fix once; every platform gets it |
| Over time | Branches drift; platforms quietly run different generators | One generator, so drift isn't possible |
| Seeing everything | Switch branches to see each version | Everything is visible on `main` |
| Testing | Tests run per branch and can diverge | One test suite covers the core for all platforms |
| Contributors | Must know which branch to work on | One place to look |

Branches are still the right tool for **short-lived work**: create
`feat/databricks-writer`, open a PR into `main`, merge it, delete the branch.
This change itself was made on `refactor/shared-generator`.

## Advantages, summarised

1. **One source of truth.** The Faker logic exists once, in the open-source
   code.
2. **Identical data everywhere.** Same seed, same rows, so Snowflake and
   Databricks results can be compared directly with the open-source pipeline.
3. **Small platform code.** A platform folder holds only what is genuinely
   about that platform: DDL, loader, credentials, notebooks.
4. **Fixes spread automatically.** Improve a factory and every platform
   benefits on its next run.
5. **Tested foundation.** The core's guarantees are checked in milliseconds,
   with no database required.
6. **Open-source users aren't affected.** The Airflow/CLI pipeline behaves
   exactly as before, and platform code never leaks into it.
7. **Secrets stay out of git.** Each platform keeps its own git-ignored
   `.env`, with a tracked `.env.example`.

## Adding Databricks

Follow the same pattern:

1. Create a branch: `git switch -c feat/databricks-writer`.
2. Create `platforms/databricks/` with:
   - `datawriter.py`: call `generate_dataset()`, then write each DataFrame as a
     Delta table, for example
     `spark.createDataFrame(frame).write.mode("overwrite").saveAsTable(...)`.
     Store products as a `STRING`/`VARIANT` JSON column or a struct.
   - `README.md` and `.env.example` (workspace host and token, catalog/schema).
   - Optionally a Databricks Asset Bundle (`databricks.yml`) to deploy jobs.
3. **Do not copy any generation code.** If the writer needs something the core
   doesn't offer, add it to `src/main/generation` so all platforms get it.
4. Use a Databricks **Git folder** for this repo, so notebooks can import
   `src.main.generation` directly.
5. Open a PR into `main`.

## Open items

- **Leftover standalone copies.** `softcart_data_generator.py`,
  `softcart_data_generator.ipynb` and `softcart_data_generator_postgres.sql`
  (untracked) still contain or depend on duplicated logic. Delete them, or
  reduce the notebook to `from src.main.generation import generate_dataset`.
- **Snowflake Notebook execution** of the new writer hasn't been tested yet;
  local execution has. See `platforms/snowflake/README.md` for the options.
- **`pyproject.toml` lacks the full pipeline dependencies** (`pymongo`,
  `sqlparse`, `sqlalchemy`, ...) that `requirements.txt` lists, so a plain
  `uv run pytest` can't import every test module. Consolidating on
  `pyproject.toml`, with optional extras such as `softcart[snowflake]` and
  `softcart[databricks]`, is the natural next step.
- **Release tags** (`v0.1.0`, ...) would let platform notebooks pin an exact
  generator version.
- `tests/test_timeliness.py::test_pipeline_run_timestamp_is_recent` fails
  locally, both before and after this change, because the local DuckDB
  analytics build is more than 2 days old. It's unrelated to this refactor.
