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
| Analytics | numpy (Monte Carlo), Nixtla **statsforecast** / **mlforecast** + LightGBM (forecast), and optionally PyTorch with **Chronos-2** and **TimesFM 2.5**, phase 5 | Small series read through the services; DuckDB kept for a later study of the real history |
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

The React app is the product. Dash is used only for **exploratory analytics pages** (forecast diagnostics, retirement), where Python-side interactivity saves a lot of front-end work. Dash is mounted inside FastAPI at `/dash` (WSGI, through `a2wsgi`; Caddy and Vite proxy `/dash` like `/api`). It reuses the session cookie for auth: a gate in front of it lets through only a fully signed-in session and passes the user's id (the demo owner's, in the demo) to the pages in a header it sets itself, replacing any the client sent. Dash pages only read (anything saved goes through the API, from React), so their callbacks need no CSRF token. They open their database sessions through `app.state.db_scope`. The app is embedded in React through a full-height route (an iframe of the same origin), which passes the language and the theme in the query string. The Dash app lives in `kwak_api.dash` (it needs the session and the same scope and visibility rules as the API's services); the engines it calls live in `kwak_analytics`. Its user-visible strings live in `kwak_api/dash/i18n.py`, one `EN` mapping and an `FR` mapping of the same keys (a test checks they match), and follow the user's language; its colours come from a Python copy of the design tokens kept equal to `frontend/src/styles/tokens.css` by a test. The pages share their pieces (tiles, status chips, cards, folded sections, links to the sections, spec §7) in `kwak_api.dash.layout`: a stylesheet in the Dash index lays them out, one column on a phone, and reads its colours as CSS variables that each page's root sets from the tokens.

The **wealth projection** (spec §4.11), first a Dash page, is now React: the page posts its settings to `/api/projection/run`, which runs the engine and returns the percentiles, the decomposition and the chances as JSON (a read-only computation: nothing is saved), and draws them with Recharts. The household's monthly contributions live on `wealth_category.monthly_contribution` (NULL for none, so one per category at most) and `contribution_indexed`, served and changed through `/api/projection` with the other assumptions. The forecast and the retirement follow it out of Dash, one PR each, then Dash is removed. `kwak_core.projection` holds the assumptions, their defaults, the starting point and the allocation, in `Decimal`; `kwak_analytics.montecarlo` draws the paths with numpy (`numpy.random.Generator` from a fixed seed), in floating point, and returns percentiles rounded back to `Decimal` cents. The assumptions are saved per household (the inflation on `household`, each asset category's return and volatility on `wealth_category`, NULL for the preset's default, and each debt line's payment, rate and insurance on `wealth_line`), served and changed through `/api/projection` (`kwak_api.projection`), and read by the goals analysis too. The **retirement** page (spec §4.13) is a Dash page on the same engine: `kwak_core.retirement` holds the members' months and amounts, the settings and the plan's savings month by month, `kwak_analytics.retirement` the sustainable withdrawal (a per-path bisection over the liquid categories, drawn from the same streams), and `kwak_api.services.retirement` reads them from `member_retirement` and the household; its inputs are set in React through `/api/retirement`. If a Dash page becomes a core feature, it is rewritten in React on top of a dedicated API endpoint.

The **cash-flow forecast** (spec §4.14) is a Dash page, in the Spending space: `kwak_core.forecast` builds the monthly series by category from the lines (the fixed expenses' lines apart, their future occurrences known), the back-test's cuts, the error metrics (MASE, WAPE, RMSSE), the choice of a model per series against the baseline, the conformal bands and the chances, in `Decimal`; `kwak_analytics.forecast` fits the candidates at each cut and for the months to come, with Nixtla's `statsforecast` (statistical models, one per series) and `mlforecast` (LightGBM, one model for all the categories, with TreeSHAP contributions), in floating point and back to `Decimal` cents; in an image built with the foundation models (an optional extra of `kwak_analytics`, chosen by a build argument that `.env` sets), Chronos-2 and TimesFM 2.5 forecast too, on the CPU, from weights baked into the image at a pinned revision and checked against their checksums at build time, read offline (`HF_HUB_OFFLINE`); `kwak_api.services.forecast` reads the lines, fixed expenses and targets. Nothing is saved: the page computes it when it opens. The study behind the candidates lives in `notebooks/forecasting/`, a uv project of its own that depends on the workspace's packages by path and adds what the app's image does not carry (the other foundation models, skforecast, SHAP, Jupyter); it runs on synthetic data only.

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
│   │   └── analytics/       # kwak_analytics: Monte Carlo simulation, forecasting engine (phase 5)
│   └── tests/               # mirrors packages; every fixture is synthetic
├── frontend/
│   └── src/{routes,features,components,api(generated),styles}
├── data/                    # git-ignored: Parquet snapshots, backups
│   └── raw/                 # read-only for Claude (hook-enforced)
├── notebooks/forecasting/   # the forecasting study (own uv project, synthetic data); logic lives in packages
└── docs/
    ├── SPECIFICATIONS.md
    ├── ARCHITECTURE.md
    ├── CLAUDE_CODE.md
    └── adr/                 # one file per significant decision
```

**Layering rule**: `core` depends on nothing (stdlib + pydantic). `api` and `analytics` depend on `core`. Business rules (money, splits, the month's figures, targets, fixed expenses, the wealth matrix, goal envelopes) live in `core` and are unit and property tested without a database. Metrics are defined once (in SQL views or `core` functions) and reused by both API and analytics: there are no diverging pandas and SQL implementations of the same number.

## 4. Data model

- `household` (warn_at, wealth_start, precaution_share, goal_capacity; `is_demo` for the one demo household, F-ADM-5), `user` (table `app_user`: `user` is reserved in Postgres; + encrypted TOTP seed), `recovery_code` (SHA-256 only), `user_session` (only the SHA-256 of the cookie token is stored; `acting_user_id` while the session is in the demo: `UserSession.user` is then the demo's owner, `account` still whoever signed in, whose password, second factor and language the auth endpoints use), `invite` (single-use, 7 days, token hashed), `auth_failure` (failed login/TOTP attempts, kept 24 h for rate limiting), `audit_event` (the activity log; `private_to` hides an entry about a private wealth line or goal from the other members)
- spending, entered by hand since v1.0: `spending_category` (one level, expense, savings or income, one_off, position), `spending_line` (day, label, amount, category_id or its parts, fixed_expense_id, entered_by_id; `created_at` is when it was entered; the month's income is the sum of its income lines), `spending_line_part`, `fixed_expense` (frequency, day, first and last month, paused), `fixed_skip`, `spending_target` (a category's monthly target or savings objective from a month on, NULL for none). The accounts, imports, transactions, transfers, rules, recurring items and budget plans of v0 were dropped (migration c77a847d28b5).
- wealth: `wealth_category` (asset or debt, colour, position, preset: which default category it is, whatever its name or colour), `wealth_line` (owner, visibility, opened and closed months, regulated type for a savings account), `wealth_value` (a line's value entered for a month, carried forward)
- goals: `goal` (target, deadline, precaution, permanent, pleasure, owner, visibility, closed_as; the tier follows the deadline), `goal_funding` (a wealth line's envelope: opening amount, share of the rises), `goal_adjustment` (an envelope set by hand from a month), `goal_notice_dismissal` (a member's snoozed or dismissed point to look at: rule, goal or line, until month or severity and amount when dismissed)
- later phases, not built: `instrument`, `price`, `position_operation`; `property`, `loan` (+ generated `loan_schedule`), `use_asset`, `valuation`

Conventions: UUIDv7 primary keys, `created_at` / `updated_at` in UTC (`timestamptz`), booking dates as `date`, money as `NUMERIC` mapped to `Decimal`, quantities as `NUMERIC(28,10)`.

## 5. Analytics path

1. **Phases 1–3**: dashboards query Postgres (SQL views / materialised views refreshed by the worker).
2. **Phase 5**: the wealth projection needs no DuckDB: it starts from the current month of the wealth matrix, read through the API's services. Nor does the cash-flow forecast: a household's monthly series by category are a few thousand numbers, read through the services too. Forecasting follows a written protocol: temporal split only (rolling origins, nothing after a cut), a naive baseline first, scaled metrics (MASE, RMSSE) with WAPE, conformal bands checked for coverage, and fixed seeds. The experiments behind it run in `notebooks/forecasting/` on synthetic households, never on `data/` nor the real database, so DuckDB and Parquet snapshots are left for when a study needs the real history (read-only role).
3. **Phase 6**: an Ollama service. The LLM only sees a curated read-only analytics schema (text-to-SQL validated against an allow-list, executed under the read-only role). pgvector is added if RAG over documents is needed.

## 6. Decisions

Architecture decisions are recorded in `docs/adr/` (one file each, numbered, never rewritten: a changed decision gets a new ADR that supersedes the old one).
