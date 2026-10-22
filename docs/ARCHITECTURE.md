# Architecture and Technical Stack

Status: draft v0.1 — 2026-10-06. Complements `docs/SPECIFICATIONS.md`.

## 1. Overview

```
                 LAN (TLS)
 Browser ──────────────► Caddy (reverse proxy, serves the built SPA)
                           │  /api/*            │  /dash/* (phase 5)
                           ▼                    ▼
                    FastAPI (uvicorn) ── mounted Dash app (WSGI)
                           │
          ┌────────────────┼──────────────────┬───────────────┐
          ▼                ▼                  ▼               ▼
     PostgreSQL 17    Scheduler (jobs)   DuckDB (analytics) Ollama (phase 6)
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
| Analytics | **DuckDB**, polars, numpy, statsmodels / statsforecast (phase 5) | DuckDB reads Postgres directly, so no ETL pipeline at first |
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

### Dash integration (phase 5)

The React app is the product. Dash is used only for **exploratory analytics pages** (forecast diagnostics, Monte Carlo explorers), where Python-side interactivity saves a lot of front-end work. Dash is mounted inside FastAPI at `/dash` (WSGI middleware). It reuses the session cookie for auth and the same Plotly theme, and is embedded in React through a full-height route. If a Dash page becomes a core feature, it is rewritten in React on top of a dedicated API endpoint.

### Infrastructure

- Docker Compose services: `caddy`, `api`, `worker`, `db` (Postgres 17), `backup`; then `ollama` (phase 6).
- Caddy provides local TLS (internal CA) on the LAN hostname.
- Secrets live in `.env` (template in `.env.example`, which is committed).
- GitHub Actions CI on each PR: ruff, mypy, pytest (Postgres started by testcontainers), Biome, tsc, Vitest, Docker build. `main` is protected and requires CI to pass.

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
│   │   ├── core/            # kwak_core: pure domain, no I/O (money, spending, budget, wealth, goals)
│   │   ├── api/             # kwak_api: FastAPI app, routers, schemas, persistence (SQLAlchemy, Alembic)
│   │   └── analytics/       # kwak_analytics: DuckDB queries, forecasting, simulation (phase 5)
│   └── tests/               # mirrors packages; every fixture is synthetic
├── frontend/
│   └── src/{routes,features,components,api(generated),styles}
├── data/                    # git-ignored: Parquet snapshots, backups
│   └── raw/                 # read-only for Claude (hook-enforced)
├── notebooks/               # explanation only; logic lives in packages
└── docs/
    ├── SPECIFICATIONS.md
    ├── ARCHITECTURE.md
    ├── CLAUDE_CODE.md
    └── adr/                 # one file per significant decision
```

**Layering rule**: `core` depends on nothing (stdlib + pydantic). `api` and `analytics` depend on `core`. Business rules (money, splits, the month's figures, targets, fixed expenses, the wealth matrix, goal envelopes) live in `core` and are unit and property tested without a database. Metrics are defined once (in SQL views or `core` functions) and reused by both API and analytics: there are no diverging pandas and SQL implementations of the same number.

## 4. Data model

- `household` (warn_at, wealth_start, precaution_share, goal_capacity), `user` (table `app_user`: `user` is reserved in Postgres; + encrypted TOTP seed), `recovery_code` (SHA-256 only), `user_session` (only the SHA-256 of the cookie token is stored), `invite` (single-use, 7 days, token hashed), `auth_failure` (failed login/TOTP attempts, kept 24 h for rate limiting), `audit_event` (the activity log; `private_to` hides an entry about a private wealth line or goal from the other members)
- spending, entered by hand since v1.0: `spending_category` (one level, expense, savings or income, one_off, position), `spending_line` (day, label, amount, category_id or its parts, fixed_expense_id, entered_by_id; `created_at` is when it was entered; the month's income is the sum of its income lines), `spending_line_part`, `fixed_expense` (frequency, day, first and last month, paused), `fixed_skip`, `spending_target` (a category's monthly target or savings objective from a month on, NULL for none). The accounts, imports, transactions, transfers, rules, recurring items and budget plans of v0 were dropped (migration c77a847d28b5).
- wealth: `wealth_category` (asset or debt, colour, position), `wealth_line` (owner, visibility, opened and closed months), `wealth_value` (a line's value entered for a month, carried forward)
- goals: `goal` (tier, target, deadline, precaution, owner, visibility, closed_as), `goal_funding` (a wealth line's envelope: opening amount, share of the rises), `goal_adjustment` (an envelope set by hand from a month)
- later phases, not built: `instrument`, `price`, `position_operation`; `property`, `loan` (+ generated `loan_schedule`), `use_asset`, `valuation`

Conventions: UUIDv7 primary keys, `created_at` / `updated_at` in UTC (`timestamptz`), booking dates as `date`, money as `NUMERIC` mapped to `Decimal`, quantities as `NUMERIC(28,10)`.

## 5. Analytics path

1. **Phases 1–3**: dashboards query Postgres (SQL views / materialised views refreshed by the worker).
2. **Phase 5**: `kwak_analytics` opens DuckDB, attaches Postgres **read-only** (a dedicated read-only role), and writes dated Parquet snapshots to `data/snapshots/` for reproducible experiments. Forecasting follows a written protocol: temporal split only, a naive baseline first (seasonal naive / moving average), metrics with dispersion across rolling origins, and fixed seeds.
3. **Phase 6**: an Ollama service. The LLM only sees a curated read-only analytics schema (text-to-SQL validated against an allow-list, executed under the read-only role). pgvector is added if RAG over documents is needed.

## 6. Decisions

Architecture decisions are recorded in `docs/adr/` (one file each, numbered, never rewritten: a changed decision gets a new ADR that supersedes the old one).
