# Functional Specifications

Status: draft v0.2 — 2026-10-06. Owner: sole maintainer.

## 1. Purpose

A self-hosted web application to manage a household's **budget** (cash flows) and **net worth** (assets and liabilities), designed so that analytics, data-science and local generative-AI features can be added in later phases without reworking the core.

The project doubles as a reference implementation of the maintainer's Claude Code development practices (see `docs/CLAUDE_CODE.md`).

## 2. Scope and constraints

| Topic | Decision |
|---|---|
| Users | One household: a few user accounts sharing some accounts, each with private ones |
| Hosting | Self-hosted only (Docker Compose on a local machine / home server). No cloud dependency |
| Currency | **EUR only** for accounts, transactions and budgets (see open question Q3 for foreign-quoted securities) |
| Data sources | File import (CSV, OFX, QIF), manual entry, market-data APIs for prices |
| Out of scope | Bank aggregation APIs (DSP2), payments, tax filing, multi-household SaaS, native mobile app |
| Language | Code, docs, UI and commits in English |

## 3. Users and roles

- **Owner**: creates the household, manages members, backups and settings.
- **Member**: full access to shared accounts and to their own private accounts.
- Visibility is per account: `private` (owner only) or `shared` (all household members). Aggregated views (net worth, budget) let each user toggle *mine* / *household*.

## 4. Functional requirements

Priority: **M** = MVP, **S** = should (later in MVP), **L** = later phase.

### 4.1 Authentication and household (M)

- F-AUTH-1: Login with email + password (argon2id hashing), server-side session in an httpOnly cookie.
- F-AUTH-2: Mandatory TOTP 2FA, with one-time recovery codes.
- F-AUTH-3: Owner invites members (invite link, single use, expiring).
- F-AUTH-4: Login rate limiting and session revocation.

### 4.2 Accounts (M)

- F-ACC-1: Account types: checking, savings (livret A, LDDS, PEL…), brokerage (PEA, CTO), life insurance (assurance-vie), employee savings and retirement (PEE/PEG, PERCOL, PER), crypto wallet/exchange, loan, real estate, use asset (vehicle, instrument…), other.
- F-ACC-2: Each account has an institution, an owner, a visibility and an opening balance/date.
- F-ACC-3: Accounts can be closed (kept in history, hidden from current views).

### 4.3 Transactions (M)

- F-TX-1: Import CSV, OFX and QIF files. CSV import uses a per-bank **import profile** (column mapping, date format, decimal separator, sign convention), which is saved and reused.
- F-TX-2: Import preview before commit: parsed rows, detected duplicates, and errors with line numbers.
- F-TX-3: Deduplication via an import fingerprint (account, date, amount, normalised label) plus a hash of the source file. Re-importing the same file is a no-op.
- F-TX-4: Manual creation and editing, split transactions (one bank line spread over several categories), notes and tags.
- F-TX-5: Transfers between two own accounts are linked and excluded from income/expense totals.
- F-TX-6: Every import is recorded (file hash, profile, row count, user, timestamp) and can be rolled back.

### 4.4 Categorisation (M)

- F-CAT-1: Two-level category tree (e.g. *Housing > Rent*), with a default seed set that can be edited.
- F-CAT-2: Ordered rules (label contains/regex, amount range, account) that assign a category automatically on import. Rules can be re-applied to past transactions.
- F-CAT-3: Bulk recategorisation, plus a "create rule from this transaction" action.
- L: ML-assisted categorisation suggestions (phase 4, local LLM or classifier).

### 4.5 Budgets (M)

Goal of the budget module: **follow spending simply**, whether entered by hand or imported from the bank's export of recent operations; **turn it into KPIs and charts**; and **compare spending per category with a target** set beforehand.

- F-BUD-1: A monthly target per category (or per parent category, covering its children). A target applies to every following month until changed. Optional rollover of any surplus or deficit to the next month.
- F-BUD-2: Target vs actual for the current month, per category: spent, remaining, share used, with a progress bar, a warning at a configurable threshold (default 80 %) and an alert when exceeded. A "pace" marker shows where spending should be at today's date.
- F-BUD-3: Personal or household scope.
- F-BUD-4: Target vs actual over past months and year to date, to see which categories are regularly over or under target.
- F-BUD-5: Transactions without a category are listed as "to categorise" and counted apart, so totals are never silently wrong.
- F-BUD-6: **Budget matrix**, the main view of F-BUD-4. One row per expense category (parent categories with their total, children below), one column per month (default: the last 12), plus a first column with the category's **monthly target**. Each cell shows the month's spending, its **gap to the target in € and in %** ((spent − target) / target), and a colour:
  - **under**: spent more than 5 % below the target → green;
  - **on target**: within ±5 % → neutral (pale grey);
  - **over**: more than 5 % above the target → burnt orange / terracotta.
  The 5 % band is a setting. A category without a target shows its spending without a colour. A total row sums every category; a "to categorise" row (F-BUD-5) is always visible. Clicking a cell opens that month's transactions for the category.

### 4.6 Recurring transactions (M)

- F-REC-1: Automatic detection of recurring series (same merchant, near-constant amount, regular period), confirmed by the user.
- F-REC-2: Manual definition of recurring items (salary, rent, subscriptions).
- F-REC-3: Upcoming-items calendar and a simple deterministic cash-flow projection to month end (statistical forecasting is phase 3).

### 4.7 Household sharing (S)

- F-SHR-1: Shared expenses tagged with a split rule (50/50, pro-rata income, custom).
- F-SHR-2: "Who owes whom" balance and settlement records.

### 4.8 Wealth / net worth (M)

- F-WLT-1: **Cash accounts**: the balance is derived from transactions, with optional balance checkpoints for reconciliation.
- F-WLT-2: **Securities (PEA, CTO, AV)**: positions (ISIN/ticker, quantity, PRU / average cost), buy/sell/dividend operations, and daily valuation from market prices. For life insurance, euro funds are valued manually and units of account (UC) are valued from prices.
- F-WLT-3: **Crypto**: positions per wallet/exchange, valued from a market API.
- F-WLT-4: **Real estate**: property with purchase price, fees, and a manual valuation history (optional €/m² estimate).
- F-WLT-5: **Loans**: principal, rate, duration, insurance, with a generated amortisation schedule. Outstanding capital is shown as a liability. A loan can be linked to a property.
- F-WLT-6: **Use assets** (vehicle, instrument, equipment): purchase value plus a depreciation model (linear, declining, or manual valuation).
- F-WLT-7: **Net-worth history**: daily snapshot of every account value. Charts show the breakdown by asset class, by liquidity and by owner.
- F-WLT-8: Asset allocation view (asset class, geography/sector when known for securities).

### 4.9 Dashboard and reporting (M)

- F-DSH-1: Home page showing net worth with its change, the month's cash flow, budget status, upcoming recurring items and recent transactions.
- F-DSH-4: Spending KPIs for any month (default: current): total spent, total income, net cash flow and savings rate ((income − spending) / income); change vs the previous month and vs the 12-month average; top 5 categories; number of transactions left to categorise.
- F-DSH-5: Spending charts: by category (bar chart, one level, drill-down to subcategories); monthly evolution over 12 months (stacked bars by category, income line); cumulative spending within the month against the budget line. Transfers between own accounts are excluded everywhere (F-TX-5).
- F-DSH-2: Income/expense reports by category and period, with a cash-flow chart (Sankey).
- F-DSH-3: CSV export of any table, plus a full JSON export of the household's data (portability).

### 4.10 Market data (M)

- F-MKT-1: A scheduled daily job fetches closing prices for held securities and crypto. Providers sit behind an adapter interface (initial candidates: Yahoo Finance via `yfinance`, CoinGecko).
- F-MKT-2: Prices are stored historically. Manual override and manual price entry are available for illiquid assets.
- F-MKT-3: A provider failure never blocks the app: the last known price is shown with a staleness indicator.

### 4.11 Administration (M)

- F-ADM-1: Automatic daily backup (`pg_dump`) with a retention policy (e.g. 7 daily, 4 weekly, 12 monthly) to a configurable directory.
- F-ADM-2: A documented restore procedure, plus a restore test script run regularly.
- F-ADM-3: Audit log of sensitive actions (login, import, deletion, rule changes).

## 5. Later phases (roadmap)

| Phase | Content |
|---|---|
| 0 — Foundations | Repo, tooling, CI, Claude Code config, design tokens, Docker Compose skeleton |
| 1 — Budget MVP | Auth + household, accounts, import, manual entry, categorisation, transactions, budget targets vs actual (F-BUD-1, 2, 4, 5) with the budget matrix (F-BUD-6), spending KPIs and charts (F-DSH-4, 5) |
| 2 — Budget complete | Rollover, recurrences, household sharing, reports |
| 3 — Wealth | Securities, crypto, real estate, loans, use assets, market data, net-worth history |
| 4 — Analytics & DS | Cash-flow **forecasting** (time-series, temporal back-testing, naive baseline first), **wealth simulation** (Monte Carlo, FIRE / retirement projection, allocation scenarios). Interactive Dash pages for exploration |
| 5 — Local GenAI | Ollama-based assistant: natural-language questions over your own data (text-to-SQL on a read-only analytics view), categorisation suggestions, monthly narrative summary. No data leaves the host |

## 6. Non-functional requirements

- **Privacy**: all data stays on the host. No telemetry. Real financial files are never committed to Git (`data/` is ignored; test fixtures are synthetic or anonymised).
- **Correctness of money**: amounts use `Decimal` / `NUMERIC`, never floats. Sign convention: negative = outflow. Every aggregate is reproducible from the transactions.
- **Security**: 2FA, argon2id, CSRF protection on cookie sessions, secrets in `.env` (not committed), dependency audit in CI. The app is served on the LAN behind a reverse proxy with TLS.
- **Performance**: the app should feel responsive on a home server with about 100k transactions (lists < 300 ms, dashboard < 1 s).
- **Accessibility**: WCAG AA contrast in light and dark themes, keyboard navigation.
- **Quality**: test-first development. Property-based tests for financial invariants (see §8). CI must pass before any merge to `main`.
- **Reproducibility**: locked dependencies (`uv.lock`, `pnpm-lock.yaml`), versioned migrations, fixed and logged random seeds for simulations and forecasts.

## 7. Visual identity

The palette is reused from the maintainer's blog (https://gwils28.github.io/, Blowfish theme customised). Fonts are loaded from Google Fonts.

| Token | Value | Use |
|---|---|---|
| `primary-500` | `#54A630` (84 166 48) | Main actions, positive amounts, income |
| `primary-600` | `#418523` | Hover, links on light background |
| `primary-50 / 900` | `#F3F9F0` / `#1B390E` | Tinted surfaces / dark accents |
| `secondary-500` | `#EC9C13` (236 156 19) | Highlights, budget warnings |
| `secondary-600` | `#C57D11` | Secondary hover |
| `neutral-50 … 900` | `#F7F8F6` → `#0F110D` (green-tinted greys) | Backgrounds, text, borders |
| Danger (to add) | to be chosen, harmonised red | Overspending, negative balance |

Full scales (50–900) are in the blog's CSS variables `--color-primary-*`, `--color-secondary-*` and `--color-neutral-*`. They will be copied into `frontend/src/styles/tokens.css`.

Typography: **Archivo** 700–900 (headings), **IBM Plex Sans** (UI text), **IBM Plex Mono** (amounts in tables use tabular numerals; code).

Light and dark themes (the dark theme uses `neutral-900` / `neutral-800` surfaces, like the blog).

Budget status colours (F-BUD-6) are semantic tokens built from the palette, defined for both themes: `budget-under` (from `primary`), `budget-on` (from `neutral`) and `budget-over` (from `secondary-700/800`, a burnt orange that reads as "over" without the alarm of the danger red).

## 8. Domain invariants (to be enforced by tests)

1. An account balance equals its opening balance plus the sum of its transactions at any date.
2. The parts of a split transaction sum exactly to the parent amount.
3. A linked transfer nets to zero across the two accounts and never counts as income or expense.
4. Importing the same file twice leaves the database unchanged.
5. A loan's amortisation schedule: principal repayments sum to the borrowed amount, and outstanding capital decreases monotonically.
6. Net worth on date D equals assets minus liabilities, using only prices known on or before D (no look-ahead).
7. Forecasts and back-tests (phase 4) never read data after their origin date.

## 9. Open questions

- **Q1** — ✅ Name: **Kwak Finance**; Python packages `kwak_core`, `kwak_api`, `kwak_analytics`.
- **Q2** — ✅ First import profiles: **Société Générale** (checking, Livret A, LDDS), the cash accounts of phase 1. SG exports two CSV layouts: checking (summary line with the balance, 5 columns) and savings (newer snake_case header, trailing `;`). The Fortuneo checking account is unused and out of scope. Investment accounts (Fortuneo PEA/CTO, Lynxéa Spirit 2 life insurance, Amundi PERCOL/PEG, Trade Republic CTO, Kraken) come with phase 3. Fixtures are synthetic files that copy each bank's exact layout.
- **Q3** — ✅ Securities quoted in USD/GBP: store an FX rate (ECB reference rate) per price point, used only for market valuation; everything else stays EUR.
- **Q4** — Life insurance: track UC positions line by line, or only the contract's total value?
- **Q5** — ✅ Runs on the development machine (RTX 5070 Laptop, 8 GB VRAM, 30 GB RAM): Ollama limited to ~7–8B models (quantised).
- **Q6** — Remote access: LAN only, or VPN later (not in MVP)?
- **Q7** — Backup destination: local disk only, or an extra copy (external drive, NAS)? Local daily backups exist (docs/OPERATIONS.md); an off-machine copy is still manual.
- **Q8** — Data history to import at start (how many years, how many accounts)?
