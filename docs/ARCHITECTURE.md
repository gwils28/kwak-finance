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

The React app is the product. Dash is used only for **exploratory analytics pages** (forecast diagnostics, Monte Carlo explorers), where Python-side interactivity saves a lot of front-end work. Dash is mounted inside FastAPI at `/dash` (WSGI, through `a2wsgi`; Caddy and Vite proxy `/dash` like `/api`). It reuses the session cookie for auth: a gate in front of it lets through only a fully signed-in session and passes the user's id to the pages in a header it sets itself, replacing any the client sent. Dash pages only read (anything saved goes through the API, from React), so their callbacks need no CSRF token. They open their database sessions through `app.state.db_scope`. The app is embedded in React through a full-height route (an iframe of the same origin), which passes the language and the theme in the query string. The Dash app lives in `kwak_api.dash` (it needs the session and the same scope and visibility rules as the API's services); the engines it calls live in `kwak_analytics`. Its user-visible strings live in `kwak_api/dash/i18n.py`, one `EN` mapping and an `FR` mapping of the same keys (a test checks they match), and follow the user's language; its colours come from a Python copy of the design tokens kept equal to `frontend/src/styles/tokens.css` by a test.

The first Dash page is the **wealth projection** (spec §4.11): `kwak_core.projection` holds the assumptions, their defaults, the starting point and the allocation, in `Decimal`; `kwak_analytics.montecarlo` draws the paths with numpy (`numpy.random.Generator` from a fixed seed), in floating point, and returns percentiles rounded back to `Decimal` cents. The assumptions are saved per household (the inflation on `household`, each asset category's return and volatility on `wealth_category`, NULL for the preset's default, and each debt line's payment, rate and insurance on `wealth_line`), served and changed through `/api/projection` (`kwak_api.projection`), and read by the goals analysis too. The **retirement** page (spec §4.13) is a second Dash page on the same engine: `kwak_core.retirement` holds the members' months and amounts, the settings and the plan's savings month by month, `kwak_analytics.retirement` the sustainable withdrawal (a per-path bisection over the liquid categories, drawn from the same streams), and `kwak_api.services.retirement` reads them from `member_retirement` and the household; its inputs are set in React through `/api/retirement`. If a Dash page becomes a core feature, it is rewritten in React on top of a dedicated API endpoint.

The **goals analysis** (spec §4.12) is React, not Dash: `kwak_core.goal_analysis` computes the reference month, the forward efforts, the goals' weights, volatilities and real returns, the status history and the points to look at (pure, every threshold a named constant); the chance of reaching each goal reuses `kwak_analytics.montecarlo` and is served by the API with the other views.

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
- wealth: `wealth_category` (asset or debt, colour, position, preset: which default category it is, whatever its name or colour), `wealth_line` (owner, visibility, opened and closed months, regulated type for a savings account), `wealth_value` (a line's value entered for a month, carried forward)
- goals: `goal` (target, deadline, precaution, permanent, pleasure, owner, visibility, closed_as; the tier follows the deadline), `goal_funding` (a wealth line's envelope: opening amount, share of the rises), `goal_adjustment` (an envelope set by hand from a month), `goal_notice_dismissal` (a member's snoozed or dismissed point to look at: rule, goal or line, until month or severity and amount when dismissed)
- later phases, not built: `instrument`, `price`, `position_operation`; `property`, `loan` (+ generated `loan_schedule`), `use_asset`, `valuation`

Conventions: UUIDv7 primary keys, `created_at` / `updated_at` in UTC (`timestamptz`), booking dates as `date`, money as `NUMERIC` mapped to `Decimal`, quantities as `NUMERIC(28,10)`.

## 5. Analytics path

1. **Phases 1–3**: dashboards query Postgres (SQL views / materialised views refreshed by the worker).
2. **Phase 5**: the wealth projection needs no DuckDB: it starts from the current month of the wealth matrix, read through the API's services. For the forecasting that follows, `kwak_analytics` opens DuckDB, attaches Postgres **read-only** (a dedicated read-only role), and writes dated Parquet snapshots to `data/snapshots/` for reproducible experiments. Forecasting follows a written protocol: temporal split only, a naive baseline first (seasonal naive / moving average), metrics with dispersion across rolling origins, and fixed seeds.
3. **Phase 6**: an Ollama service. The LLM only sees a curated read-only analytics schema (text-to-SQL validated against an allow-list, executed under the read-only role). pgvector is added if RAG over documents is needed.

## 6. Decisions

Architecture decisions are recorded in `docs/adr/` (one file each, numbered, never rewritten: a changed decision gets a new ADR that supersedes the old one).
