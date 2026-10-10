# Functional Specifications

Status: draft v0.3 — 2026-10-10. Owner: sole maintainer.

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

- F-BUD-1: A monthly target per category (or per parent category, covering its children), set within a budget plan (F-BUD-7). Within a plan, a cheaper month offsets a dearer one (the period envelope): this replaces a month-to-month rollover.
- F-BUD-2: Target vs actual for the current month, per category: spent, remaining, share used, with a progress bar, a warning at a configurable threshold (default 80 %) and an alert when exceeded. A "pace" marker shows where spending should be at today's date.
- F-BUD-3: Personal or household scope.
- F-BUD-4: Target vs actual over past months and year to date, to see which categories are regularly over or under target.
- F-BUD-5: Transactions without a category are listed as "to categorise" and counted apart, so totals are never silently wrong.
- F-BUD-6: **Budget matrix**, the main view of F-BUD-4. One row per expense category (parent categories with their total, children below), one column per month (default: the last 12), plus a first column with the category's **monthly target**. Each cell shows the month's spending, its **gap to the target in € and in %** ((spent − target) / target), and a colour:
  - **under**: spent more than 5 % below the target → green;
  - **on target**: within ±5 % → neutral (pale grey);
  - **over**: more than 5 % above the target → burnt orange / terracotta.
  The 5 % band is a setting. A category without a target shows its spending without a colour. A total row sums every category; a "to categorise" row (F-BUD-5) is always visible. Clicking a cell opens that month's transactions for the category. The monthly target shown is the one of the plan covering the month (F-BUD-7); a month outside any plan has no target.
- F-BUD-7: **Budget plans by period**, so targets follow life changes (job loss, a raise, a new recurring expense). A plan covers one **calendar period**: a year (January–December), a semester (January–June, July–December) or a quarter (January–March, …). It holds one **monthly target** per expense category (parent or child, as F-BUD-1) and, optionally, the expected monthly income and a note. A category's **envelope** for the plan is its monthly target times the plan's number of months.
  - Plans never overlap: a month belongs to one plan at most. Consecutive plans may have different lengths (e.g. S1 2027, then Q3 and Q4). A month outside any plan has no target.
  - A new plan starts pre-filled with the targets of the latest plan.
  - A plan's targets can be edited until the end of its first month (to fix the set-up). After that, changes go through an **early close**: the user closes the plan at the end of a month, with an optional reason. The closed plan keeps its targets and is reviewed over the months it covered. A **replacement plan** then covers the rest of the original period (e.g. Q1 closed at the end of February → a replacement plan for March), pre-filled from the closed one; the calendar resumes after it.
  - The monthly targets of v0.2 are migrated into quarterly plans: one per past or current quarter in which a target was in force, with the targets in force in its first month; a change of target within a quarter becomes an early close followed by a replacement plan, so the matrix shows the same targets as before.
- F-BUD-8: **Plan review**, available during and after a plan, per category (parents with their children) and in total:
  - envelope, spent, gap in € and in % ((spent − envelope) / envelope) and the status with the band and colours of F-BUD-6;
  - the number of months over / on / under the monthly target;
  - **during the plan**: the share of time elapsed (completed months plus the current month prorated by days), the envelope prorated to it (the **pace**), spent vs pace, and a linear **projection** at the end of the plan (spent ÷ share elapsed). Categories projected above their envelope are flagged as **drifting**. Phase 4 forecasting can replace the linear projection;
  - **after the plan**: the final result per category and in total, with income, spending, savings and savings rate over the period (as F-DSH-4); when the plan has an expected income, the planned savings (expected income − envelopes) next to the actual ones;
  - a plan closed early is labelled so, with its reason, and reviewed over the months it covered;
  - while transactions in the period are left to categorise (F-BUD-5), their amount is shown apart and the review is marked provisional.

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
- F-DSH-6: **Plan steering dashboards**, on the plan review (F-BUD-8):
  - **cumulative chart**: cumulative spending by day over the plan against the cumulative envelope line, in total or for one category;
  - **gap chart**: the gap in % per category, coloured under / on / over;
  - **drift list** (during a plan): categories ranked by projected overrun in €;
  - **plan comparison**: two plans side by side (by default the current one and the previous one, or the same period a year before), per category: monthly target and monthly average spent, with the change in € and in %. Monthly averages make plans of different lengths comparable.
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
| 2 — Budget complete | Budget plans by period and their review, with steering dashboards (F-BUD-7, 8, F-DSH-6), then recurrences, household sharing, reports |
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
8. Budget plans never overlap, and each lies within one calendar period (year, semester or quarter).
9. A category's envelope equals its monthly target times the plan's number of months; a parent without a target of its own takes the sum of its children's.
10. A plan review and the budget matrix never disagree: the spending of a plan equals the sum of the matrix cells of its months, category by category.

## 9. Open questions

- **Q1** — ✅ Name: **Kwak Finance**; Python packages `kwak_core`, `kwak_api`, `kwak_analytics`.
- **Q2** — ✅ First import profiles: **Société Générale** (checking, Livret A, LDDS), the cash accounts of phase 1. SG exports two CSV layouts: checking (summary line with the balance, 5 columns) and savings (newer snake_case header, trailing `;`). The Fortuneo checking account is unused and out of scope. Investment accounts (Fortuneo PEA/CTO, Lynxéa Spirit 2 life insurance, Amundi PERCOL/PEG, Trade Republic CTO, Kraken) come with phase 3. Fixtures are synthetic files that copy each bank's exact layout.
- **Q3** — ✅ Securities quoted in USD/GBP: store an FX rate (ECB reference rate) per price point, used only for market valuation; everything else stays EUR.
- **Q4** — Life insurance: track UC positions line by line, or only the contract's total value?
- **Q5** — ✅ Runs on the development machine (RTX 5070 Laptop, 8 GB VRAM, 30 GB RAM): Ollama limited to ~7–8B models (quantised).
- **Q6** — Remote access: LAN only, or VPN later (not in MVP)?
- **Q7** — Backup destination: local disk only, or an extra copy (external drive, NAS)? Local daily backups exist (docs/OPERATIONS.md); an off-machine copy is still manual.
- **Q8** — Data history to import at start (how many years, how many accounts)?
