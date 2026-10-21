# SoftCart on Snowflake

Loads the SoftCart synthetic dataset into a **Snowflake Postgres** instance.

The data comes from the shared generator in [`src/main/generation`](../../src/main/generation),
the same code the open-source pipeline uses. This folder only holds what is
specific to Snowflake: the Postgres DDL, the loader, and connection settings.

## Files

| File | Purpose |
|---|---|
| `datawriter.py` | Generates the dataset with the shared core and bulk-loads it with `COPY` |
| `.env.example` | Connection template. Copy to `.env` (git-ignored) and fill in |
| `softcart_dbt/` | Placeholder for the Snowflake dbt project |

## Run locally

```bash
cp platforms/snowflake/.env.example platforms/snowflake/.env   # then fill in PG_* values
uv run python platforms/snowflake/datawriter.py                 # from the repo root
```

Only the `PG_*` variables are used. The `SNOWFLAKE_*` block is optional and
reserved for Snowpark / snowsql work.

Each run, in one transaction:

1. Creates the schema and tables if missing (`PG_SCHEMA`, default `softcart`)
2. Truncates and reloads every table (same seed = same data)
3. Appends a row to `generation_manifest` with the seed and row counts
4. Runs `ANALYZE` so row estimates (and Snowsight's metadata) are correct immediately

A failed run rolls back and leaves the previous load untouched.

## Run from a Snowflake Notebook

The writer imports the shared generator, so the notebook needs the repository
checked out next to it, not only this file. Options (not yet tested here):

- **Notebook from a Git repository** (Snowsight Git integration): create the
  notebook from this repo. `datawriter.py` walks up from the working
  directory to find `src/main/generation`.
- **Container runtime:** `!pip install git+https://github.com/akshatDE/softcart-ecom-data_platform@<tag>`
  (needs external access to GitHub).

Inside Snowflake, credentials come from a notebook secret instead of `.env`.
One-time setup as `ACCOUNTADMIN`:

```sql
CREATE OR REPLACE NETWORK RULE softcart_pg_rule
  MODE = EGRESS TYPE = HOST_PORT
  VALUE_LIST = ('<your-instance-host>:5432');

CREATE OR REPLACE SECRET softcart_pg_secret
  TYPE = PASSWORD USERNAME = '<pg_user>' PASSWORD = '<pg_password>';

CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION softcart_pg_eai
  ALLOWED_NETWORK_RULES = (softcart_pg_rule)
  ALLOWED_AUTHENTICATION_SECRETS = (softcart_pg_secret)
  ENABLED = TRUE;
```

Then enable `SOFTCART_PG_EAI` in the notebook's external access settings and
attach the secret as `pg_cred`.
