# Architecture and Technical Stack

Status: draft v0.1 — 2026-10-06. Complements `docs/SPECIFICATIONS.md`.

## 1. Overview

```
                 LAN (TLS)
 Browser ──────────────► Caddy (reverse proxy, serves the built SPA)
                           │  /api/*            │  /dash/* (phase 4)
                           ▼                    ▼
                    FastAPI (uvicorn) ── mounted Dash app (WSGI)
                           │
          ┌────────────────┼──────────────────┬───────────────┐
          ▼                ▼                  ▼               ▼
     PostgreSQL 17    Scheduler (jobs)   DuckDB (analytics) Ollama (phase 5)
     (system of       prices, snapshots, attaches Postgres
      record)         recurrences,       read-only + Parquet
          │           backups            snapshots
          ▼
     backup volume (pg_dump, rotated)
```

Everything runs from a single `docker compose up`. The front end is served from the same origin as the API, so cookie sessions work without CORS.

## 2. Stack

### Backend (Python 3.13)

| Concern | Choice | Why |
|---|---|---|
| Package / env | **uv** (workspace, `uv.lock` committed) | Fast, reproducible, same as the maintainer's DS projects |
| API | **FastAPI** + Pydantic v2 | Typed, generates an OpenAPI schema that the TS client is generated from |
| ORM / migrations | **SQLAlchemy 2** (typed `Mapped[]`) + **Alembic** | Mature, explicit, async support |
| DB driver | `psycopg` 3 | Async and sync, works with DuckDB `postgres` extension setups |
| Auth | argon2-cffi, pyotp, server-side sessions table | Simple, no third-party identity provider in a self-hosted app |
| Jobs | APScheduler, in a dedicated `worker` container | Few, simple daily jobs. No broker needed |
| File parsing | `ofxtools` (OFX), a small in-house QIF parser, CSV via import profiles | QIF libraries are poorly maintained |
| Analytics | **DuckDB**, polars, numpy, statsmodels / statsforecast (phase 4) | DuckDB reads Postgres directly, so no ETL pipeline at first |
| Logging | structlog (JSON) | |
| Lint / format | **ruff** (lint + format) | |
| Types | **mypy --strict** (or pyright strict, to be decided in phase 0) | Money code must be typed |
| Tests | **pytest**, **hypothesis** (property-based), pytest-cov, **testcontainers** (real Postgres) | Financial invariants are tested as properties, never with a mocked DB |

### Frontend

| Concern | Choice |
|---|---|
| Framework | **React 19 + TypeScript (strict)**, **Vite** |
| Package manager | **pnpm** |
| Routing / data | TanStack Router, **TanStack Query** |
| API client | Generated from OpenAPI (`@hey-api/openapi-ts`). Never hand-written |
| UI | **Tailwind CSS v4** + **shadcn/ui**, themed with the blog tokens (`tokens.css`) |
| Charts | Recharts for standard charts. Plotly (`react-plotly.js`) for advanced/interactive ones, the same library Dash uses |
| Forms | react-hook-form + zod |
| Lint / format | **Biome** (the TS counterpart of ruff: one fast tool) |
| Tests | **Vitest** + Testing Library. **Playwright** for E2E smoke tests |

### Dash integration (phase 4)

The React app is the product. Dash is used only for **exploratory analytics pages** (forecast diagnostics, Monte Carlo explorers), where Python-side interactivity saves a lot of front-end work. Dash is mounted inside FastAPI at `/dash` (WSGI middleware). It reuses the session cookie for auth and the same Plotly theme, and is embedded in React through a full-height route. If a Dash page becomes a core feature, it is rewritten in React on top of a dedicated API endpoint.

### Infrastructure

- Docker Compose services: `caddy`, `api`, `worker`, `db` (Postgres 17), `backup`; then `ollama` (phase 5).
- Caddy provides local TLS (internal CA) on the LAN hostname.
- Secrets live in `.env` (template in `.env.example`, which is committed).
- GitHub Actions CI on each PR: ruff, mypy, pytest (with a Postgres service), Biome, tsc, Vitest, Docker build. `main` is protected and requires CI to pass.

## 3. Repository layout

```
.
├── CLAUDE.md
├── .claude/                 # Claude Code config (see docs/CLAUDE_CODE.md)
├── .githooks/               # commit-msg guard (conventional commits, no co-author)
├── .github/workflows/ci.yml
├── docker-compose.yml
├── Makefile                 # single entry point: make check / test / dev …
├── backend/
│   ├── pyproject.toml       # uv workspace root
│   ├── packages/
│   │   ├── core/            # kwak_core: pure domain, no I/O (money, rules, amortisation, dedup)
│   │   ├── api/             # kwak_api: FastAPI app, routers, schemas, persistence (SQLAlchemy, Alembic)
│   │   └── analytics/       # kwak_analytics: DuckDB queries, forecasting, simulation (phase 4)
│   └── tests/               # mirrors packages; fixtures/ holds synthetic bank files only
├── frontend/
│   └── src/{routes,features,components,api(generated),styles}
├── data/                    # git-ignored: raw imports, Parquet snapshots, backups
│   └── raw/                 # read-only for Claude (hook-enforced)
├── notebooks/               # explanation only; logic lives in packages
└── docs/
    ├── SPECIFICATIONS.md
    ├── ARCHITECTURE.md
    ├── CLAUDE_CODE.md
    └── adr/                 # one file per significant decision
```

**Layering rule**: `core` depends on nothing (stdlib + pydantic). `api` and `analytics` depend on `core`. Business rules (balances, splits, dedup fingerprints, amortisation, depreciation, rule matching) live in `core` and are unit and property tested without a database. Metrics are defined once (in SQL views or `core` functions) and reused by both API and analytics: there are no diverging pandas and SQL implementations of the same number.

## 4. Data model (initial sketch)

- `household`, `user` (+ `totp_secret`, `recovery_code`), `session`, `invite`
- `institution`, `account` (type, owner_id, visibility, opened_at, closed_at)
- `import_batch` (file_sha256, profile_id, row_count, status), `import_profile`
- `transaction` (account_id, booked_at, amount NUMERIC(14,2), label_raw, label_norm, fingerprint UNIQUE per account, category_id, transfer_group_id, import_batch_id, recurring_id), `transaction_split`
- `category` (parent_id), `categorization_rule` (priority, predicates JSONB)
- `budget` (category_id, month, amount, rollover, scope), `recurring_series`
- `shared_split_rule`, `settlement`
- `instrument` (isin, ticker, kind, quote_currency), `price` (instrument_id, date, close, fx_to_eur), `position_operation` (buy/sell/dividend/fee)
- `property`, `loan` (+ generated `loan_schedule`), `use_asset` (depreciation_method, params), `valuation` (manual value history for any non-market asset)
- `networth_snapshot` (date, account_id, value_eur)
- `audit_log`

Conventions: UUIDv7 primary keys, `created_at` / `updated_at` in UTC (`timestamptz`), booking dates as `date`, money as `NUMERIC` mapped to `Decimal`, quantities as `NUMERIC(28,10)`.

## 5. Analytics path

1. **Phases 1–3**: dashboards query Postgres (SQL views / materialised views refreshed by the worker).
2. **Phase 4**: `kwak_analytics` opens DuckDB, attaches Postgres **read-only** (a dedicated read-only role), and writes dated Parquet snapshots to `data/snapshots/` for reproducible experiments. Forecasting follows a written protocol: temporal split only, a naive baseline first (seasonal naive / moving average), metrics with dispersion across rolling origins, and fixed seeds.
3. **Phase 5**: an Ollama service. The LLM only sees a curated read-only analytics schema (text-to-SQL validated against an allow-list, executed under the read-only role). pgvector is added if RAG over documents is needed.

## 6. Decisions

Architecture decisions are recorded in `docs/adr/` (one file each, numbered, never rewritten: a changed decision gets a new ADR that supersedes the old one).
