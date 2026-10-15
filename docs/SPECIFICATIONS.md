# Functional Specifications

Status: draft v0.16 — 2026-10-15. Owner: sole maintainer.

## 1. Purpose

A self-hosted web application to manage a household's **budget** (cash flows) and **net worth** (assets and liabilities), designed so that analytics, data-science and local generative-AI features can be added in later phases without reworking the core.

The project doubles as a reference implementation of the maintainer's Claude Code development practices (see `docs/CLAUDE_CODE.md`).

## 2. Scope and constraints

| Topic | Decision |
|---|---|
| Users | One household: a few user accounts sharing some accounts, each with private ones |
| Hosting | Self-hosted only (Docker Compose on a local machine / home server). No cloud dependency |
| Currency | **EUR only** for accounts, transactions, budgets and wealth values |
| Data sources | File import (CSV, OFX, QIF), manual entry; wealth values entered monthly (no market-data API) |
| Out of scope | Bank aggregation APIs (DSP2), payments, tax filing, multi-household SaaS, native mobile app |
| Language | Code, docs, UI and commits in English |

## 3. Users and roles

- **Owner**: creates the household, manages members, backups and settings.
- **Member**: full access to shared accounts and to their own private accounts.
- Visibility is per account: `private` (owner only), `shared` (all household members, still the owner's account) or `joint` (the household's common account, e.g. the one paying rent and groceries: all members, nobody's own). Aggregated views (net worth, budget) let each user choose *household* (every visible account), *joint* (the joint accounts) or *mine* (their own accounts, joint ones excluded).

## 4. Functional requirements

Priority: **M** = MVP, **S** = should (later in MVP), **L** = later phase.

### 4.1 Authentication and household (M)

- F-AUTH-1: Login with email + password (argon2id hashing), server-side session in an httpOnly cookie.
- F-AUTH-2: Mandatory TOTP 2FA, with one-time recovery codes.
- F-AUTH-3: Owner invites members (invite link, single use, expiring).
- F-AUTH-4: Login rate limiting and session revocation.

### 4.2 Accounts (M)

- F-ACC-1: Account types: checking, savings (livret A, LDDS, PEL…), brokerage (PEA, CTO), life insurance (assurance-vie), employee savings and retirement (PEE/PEG, PERCOL, PER), crypto wallet/exchange, loan, real estate, use asset (vehicle, instrument…), other. Since v0.15 only cash accounts (checking, savings) hold transactions that matter: holdings that are only valued (brokerage, life insurance, crypto, real estate, loans…) are wealth lines (F-WLT-2) instead.
- F-ACC-2: Each account has an institution, an owner, a visibility and an opening balance/date.
- F-ACC-3: Accounts can be closed (kept in history, hidden from current views).

### 4.3 Transactions (M)

- F-TX-1: Import CSV, OFX and QIF files. CSV import uses a per-bank **import profile** (column mapping, date format, decimal separator, sign convention), which is saved and reused.
- F-TX-2: Import preview before commit: parsed rows, detected duplicates, and errors with line numbers.
- F-TX-3: Deduplication via an import fingerprint (account, date, amount, normalised label) plus a hash of the source file. Re-importing the same file is a no-op.
- F-TX-4: Manual creation and editing (a transfer: F-TX-9), **split transactions** and **notes**. Tags are left out until a use for them shows up.
  - **Split**: any transaction, entered by hand or imported, can be spread over two or more **parts**, each a category and an amount of the transaction's sign (none zero). The user enters every part but the last, which takes the rest, so the parts always add up exactly to the transaction (invariant 2). A split transaction counts in each part's category, for its part's amount, in every figure by category (budget matrix, plans and their review, the month so far, overview, money flows), all in the transaction's budget month (F-TX-7). The list shows it once, as "Split" with its parts; filtering on a category, or opening a matrix cell, finds it through any of its parts. Removing the split brings back a single category (or "to categorise").
  - When the amount of a split manual entry changes, the last part takes the difference; the change is refused if that part would reach zero or change sign. Rules (F-CAT-2) and bulk categorisation leave a split transaction alone. A transfer (F-TX-5) cannot be split, and a split transaction cannot be linked as one.
  - **Notes**: free text (up to 500 characters) on any transaction, entered by hand or imported. The list's label search also searches the notes.
  - Reconciling a manual entry with a statement (F-TX-8) keeps its split and its note, as it keeps its category; rolling the import back restores them.
- F-TX-5: Transfers between two own accounts are linked and excluded from income/expense totals. In a scope narrower than the household (§3: *mine*, *joint*), a transfer with an account outside the scope is shown apart as *paid in* or *paid out*, and counts in the net cash flow and savings (savings rate = net / (income + paid in)); transfers within the scope still net to zero. A transfer is linked in one of three ways:
  - **detected**: pairs of an outflow and an inflow of the same amount on two of the household's cash accounts, at most 3 days apart, are offered for linking, one by one or all at once;
  - **"Link to…"** on a transaction, for a pair the detection missed: it lists the unlinked transactions of the opposite amount on the other cash accounts the user can see, within 31 days, closest first. The amounts must be equal (invariant 3): a transfer that lost a fee on the way is not a transfer;
  - **entered by hand** (F-TX-9).
- F-TX-6: Every import is recorded (file hash, profile, row count, user, timestamp) and can be rolled back.
- F-TX-7: **Budget month**. Each transaction keeps its real booking date and also counts in a **budget month**: by default the month of its date, shifted to the next month by its category's setting (F-CAT-5), or set by hand on the transaction to its booking month, the month before or the month after (e.g. a salary paid early, a bonus meant for another month). A hand-set month wins over the category's setting and is kept when the transaction is recategorised. Every figure by month uses the budget month: the budget matrix, plans and their review (projection, drift, money flows), the overview's KPIs and charts; in a day-by-day chart, a transaction counted in a later month is placed on that month's first day, in an earlier month on its last day. Account balances, imports, deduplication and the transaction list keep the real date; the list shows the budget month next to a shifted transaction and can be filtered by budget month, which is what a matrix cell opens. A transfer between two own accounts (F-TX-5) always counts in its booking month, as both its legs must; the parts of a split transaction (F-TX-4) share their parent's budget month, which follows its first part's category (F-CAT-5).
- F-TX-8: **Reconciling manual entries with a statement**. Most transactions are entered by hand during the month and the bank's statement is imported later (F-REC), so an import must not add them twice. In the import preview (F-TX-2), a statement row **matches** a manual entry not yet reconciled when it is on the same account, with exactly the same amount, and dated within 5 days of it; each entry matches one row at most and each row the closest entry (then the earliest entered). Matched rows are shown as "already entered", next to the entry, and the user can undo a wrong match, which imports the row as new. On commit, a matched entry is **reconciled**: it keeps its category, its label, its budget month set by hand (F-TX-7) and its transfer link (F-TX-5), takes the bank's date, and records the bank's label and the import; it is then deduplicated like an imported row (F-TX-3). The preview also lists the manual entries within the statement's dates that matched no row (a typo, or an operation not yet booked by the bank). Rolling back the import (F-TX-6) turns reconciled entries back into manual entries with their own date.
- F-TX-9: **Entering a transfer**. The manual entry (F-TX-4) offers a third kind next to expense and income: a **transfer** from one cash account to another (checking or savings, two different accounts the user can see), with an amount, a date and an optional label. It creates the two sides, already linked (F-TX-5): an outflow on the source account and an inflow on the destination, labelled "Transfer to <destination>" and "Transfer from <source>" in the user's language, or both with the label given. Each side is a manual entry, reconciled with its account's statement like any other (F-TX-8), which keeps the link.
  - Changing the amount or the date of one side changes the other side too, while it is still a manual entry. Once a side comes from a statement, the amount is locked; the manual side's date and label stay editable. A label is edited on one side only.
  - Deleting a side deletes the other side when it is a manual entry; a side that comes from a statement is only unlinked.

### 4.4 Categorisation (M)

- F-CAT-1: Two-level category tree (e.g. *Housing > Rent*), with a default seed set that can be edited.
- F-CAT-4: Each category has a **kind**, shared by its subcategories: **expense**, **income** or **savings** (*Savings & investments*). A savings category holds the money moved to savings or investments that are not tracked as an account of the app (a PEA, a life insurance or a PER until phase 3, a savings account that is not imported): its net outflows are **saved**, a withdrawal brought back counts against it. It is never spending nor income: the money stays in the net cash flow and the savings rate, as money moved to a savings account of the app does. A transfer to an account of the app stays a transfer (F-TX-5), whatever its category. The default seed has one: *Savings & investments* (*Savings accounts*, *Investments*, *Retirement*). An expense rule catches outflows, an income rule inflows, a savings rule both.
- F-CAT-5: **Next-month shift**. A category may say that a transaction booked **on or after a given day** (default: the 15th) counts for the **next month** (F-TX-7), e.g. a salary paid on the 20th or the 28th that pays for the next month's spending, or a rent taken on the 28th for the next month. Off by default, for any kind of category; a subcategory without a setting of its own follows its parent's. The setting applies to every transaction of the category, past ones included, except those whose budget month was set by hand: before saving, the page says how many transactions change month and which locked plans' reviews change with them. With a shifted salary, the first month of the household's history has no salary unless the previous month's statement is imported too.
- F-CAT-6: **One-off** expense categories, paid once in the month (rent, a subscription, an insurance premium), so their spending is complete from the day they are paid and is never judged against the pace of the month nor the warning threshold (F-BUD-2). Off by default; a subcategory follows its parent unless it says otherwise. The default seed marks *Housing* and *Subscriptions* as one-off; an existing household gets the same on its categories still carrying those default names.
- F-CAT-2: Ordered rules (label contains/regex, amount range, account) that assign a category automatically on import. Rules can be re-applied to past transactions.
- F-CAT-3: Bulk recategorisation, plus a "create rule from this transaction" action.
- L: ML-assisted categorisation suggestions (phase 4, local LLM or classifier).

### 4.5 Budgets (M)

Goal of the budget module: **follow spending simply**, whether entered by hand or imported from the bank's export of recent operations; **turn it into KPIs and charts**; and **compare spending per category with a target** set beforehand.

- F-BUD-1: A monthly target per expense category (or per parent category, covering its children), set within a budget plan (F-BUD-7). Within a plan, a cheaper month offsets a dearer one (the period envelope): this replaces a month-to-month rollover.
- F-BUD-2: **The month so far**, a section of the overview (F-DSH-1) for the month it shows (default: the current one), counted by budget month (F-TX-7). One line per expense category with a monthly target in the plan covering the month (F-BUD-7: a parent's target covers its children, and the scope rules of the plan apply), ranked by share used, highest first: spent (net of refunds, as in the matrix), target, remaining (or the overrun), **share used** (spent ÷ target) and a progress bar. Categories without a target and savings categories are not listed (savings objectives are followed in the review, F-BUD-9); a month outside any plan shows a link to create one instead. Each line has a status, shown with an icon and a word as well as a colour:
  - **on track**: share used below the warning threshold;
  - **watch**: from the threshold up to 100 %, except for a **one-off** category (F-CAT-6), which is on track up to 100 %: paid as planned, there is nothing to watch;
  - **over**: above 100 %.
  The **warning threshold** is a household setting (default 80 %, from 50 % to 100 %), changed by the owner. For the current month, a **pace** marker on each bar shows the share of the month elapsed (today's day ÷ the month's number of days), so spending ahead of the calendar shows before it reaches the threshold; it is not shown on a **one-off** category (F-CAT-6), paid once early in the month, nor for a past month. A line opens the month's transactions of the category, as a matrix cell does.
- F-BUD-3: Household, joint or personal scope (§3).
- F-BUD-4: Target vs actual over past months and year to date, to see which categories are regularly over or under target.
- F-BUD-5: Transactions without a category are listed as "to categorise" and counted apart, so totals are never silently wrong.
- F-BUD-6: **Budget matrix**, the main view of F-BUD-4. One row per expense category (parent categories with their total, children below), one column per month (default: the last 12), plus a first column with the category's **monthly target**. Each cell shows the month's spending, its **gap to the target in € and in %** ((spent − target) / target), and a colour:
  - **under**: spent more than 5 % below the target → green;
  - **on target**: within ±5 % → neutral (pale grey);
  - **over**: more than 5 % above the target → burnt orange / terracotta.
  The 5 % band is a setting. A category without a target shows its spending without a colour. A total row sums every category; a "to categorise" row (F-BUD-5) is always visible. Clicking a cell opens that month's transactions for the category. The monthly target shown is the one of the plan covering the month (F-BUD-7); a month outside any plan has no target.
- F-BUD-7: **Budget plans by period**, so targets follow life changes (job loss, a raise, a new recurring expense). A plan covers one **calendar period**: a year (January–December), a semester (January–June, July–December) or a quarter (January–March, …). It holds one **monthly target** per expense category (parent or child, as F-BUD-1) and, optionally, the expected monthly income and a note. A category's **envelope** for the plan is its monthly target times the plan's number of months.
  - Plans never overlap: a month belongs to one plan at most. Consecutive plans may have different lengths (e.g. S1 2027, then Q3 and Q4). A month outside any plan has no target.
  - A new plan starts pre-filled with the targets of the latest plan, and with who pays each.
  - Each target may say who pays its category: the **joint** accounts or **personal** ones (§3). This can change at any time, the envelopes stay the same. The *joint* and *mine* scopes judge only the targets paid from them, plus the unassigned ones; *household* keeps every target. The expected income is the household's, so only the *household* scope shows the planned savings.
  - A plan's targets can be edited until the end of its first month (to fix the set-up). After that, changes go through an **early close**: the user closes the plan at the end of a month, with an optional reason. The closed plan keeps its targets and is reviewed over the months it covered. A **replacement plan** then covers the rest of the original period (e.g. Q1 closed at the end of February → a replacement plan for March), pre-filled from the closed one; the calendar resumes after it.
  - The monthly targets of v0.2 are migrated into quarterly plans: one per past or current quarter in which a target was in force, with the targets in force in its first month; a change of target within a quarter becomes an early close followed by a replacement plan, so the matrix shows the same targets as before.
- F-BUD-8: **Plan review**, available during and after a plan, per category (parents with their children) and in total:
  - envelope, spent, gap in € and in % ((spent − envelope) / envelope) and the status with the band and colours of F-BUD-6: during the plan the status compares the projection with the envelope, after it the spending (the projection then equals the spending);
  - the number of months over / on / under the monthly target;
  - **during the plan**: the share of time elapsed (completed months plus the current month prorated by days), the envelope prorated to it (the **pace**, for reference), and a **projection** at the end of the plan. The projection takes the completed months as spent, the current month and each remaining one as the larger of its spending so far (an entry booked ahead) and the expected monthly spending. The expected monthly spending is the larger of the monthly target and the average of the completed months; with neither, the projection is linear (spent ÷ share elapsed). So a fixed cost paid early in the month (rent, a subscription) is not projected as an overrun, while spending above the target shows at once. Categories projected above their envelope (beyond the band) are flagged as **drifting**. Phase 4 forecasting can replace this projection;
  - **after the plan**: the final result per category and in total, with income, spending, savings and savings rate over the period (as F-DSH-4); when the plan has an expected income, the planned savings (expected income − envelopes) next to the actual ones;
  - a plan closed early is labelled so, with its reason, and reviewed over the months it covered;
  - while transactions in the period are left to categorise (F-BUD-5), their amount is shown apart and the review is marked provisional.
- F-BUD-9: **Savings objectives**. A savings category (F-CAT-4) may have a monthly **objective**, set in a plan like a target (F-BUD-7: parent or child, who pays it, frozen after the first month). An objective is a minimum: saving more is good. Its status mirrors a target's, with the same band and colours: **ahead** (saved more than the band above the objective) in green, **on** in neutral, **behind** (more than the band below) in burnt orange. Savings categories have their own section, below the expenses, in the matrix (F-BUD-6) and the review (F-BUD-8), with their own total; they never enter the spending total. In the review, the projection follows F-BUD-8 and a category projected behind its objective is flagged as drifting; the planned savings (expected income − expense envelopes) are shown next to the sum of the objectives.

### 4.6 Recurring transactions (M)

Most transactions are entered by hand, once a week or a fortnight, because the banks only export a statement once a month: recurring items mainly save that typing and say what is still to come.

- F-REC-1: A **recurring item** describes an expected transaction: a label (matched as a rule's, F-CAT-2), an account, a category, an amount (fixed, or **estimated** as the average of its last 3 occurrences, e.g. electricity, shown "≈ €85"), a frequency (weekly, monthly, quarterly or yearly) and an expected day (a weekday, or a day of the month, the last day standing in for a missing one), from a first date and optionally until an end date. Items are defined by hand (salary, rent, subscriptions) or confirmed from a suggestion (F-REC-2), and can be paused or ended. An item can instead be a **transfer** from one cash account to another (F-TX-9), with no category and no label to match, e.g. a member's monthly share paid into the joint account.
- F-REC-2: **Detection**, as suggestions to confirm, edit or dismiss (a dismissed series is not suggested again): over the last 6 months, at least 3 transactions of one account with the same normalised label, at a regular interval (weekly, ± 2 days, or monthly, ± 5 days; quarterly and yearly items, too rare to show in 6 months, are defined by hand) and an amount varying by less than 10 % (fixed below 1 %, estimated otherwise). Transfers between own accounts (F-TX-5) are not suggested.
- F-REC-3: **Occurrences**. An item has one occurrence per period, on its expected date. A transaction **fulfils** an occurrence when it is on the item's account, its label matches, its amount is within 10 % of the expected one (same sign; for an estimated item, which varies with the seasons, the sign is enough) and its date within 5 days of the expected date; each transaction fulfils one occurrence at most and each occurrence takes the closest one. A transfer item's occurrence is fulfilled by a linked transfer (F-TX-5) from its source to its destination account, with the same amount and date tolerances, the date being the outflow's. An occurrence is **upcoming** before its date plus 5 days, then **late** while unfulfilled; the user can **skip** one (a subscription paused for a month). Nothing is ever created by itself: an upcoming or late occurrence offers **"Enter it"**, which opens the manual entry (F-TX-4) pre-filled with the item's account, label, category, amount and expected date (today if later), to confirm or adjust; for a transfer item, the transfer entry (F-TX-9) pre-filled with its two accounts.
- F-REC-4: **Upcoming items**, on the overview (F-DSH-1) for the scope shown: the occurrences from today to the end of the month, late ones first, with "Enter it", and the **projected balance** at the end of the month: the current balance of the scope's cash accounts plus the upcoming and late occurrences of their items. A transfer item counts as an outflow of its source account and an inflow of its destination, each in the scopes that hold that account: it is listed in a scope holding either account and adds nothing to the household's projection. The projection uses real booking dates (not the budget month, F-TX-7): a salary expected on the 28th counts in this month's projected balance. A **Recurring** page, opened from Transactions, lists the items with their next occurrence and status, the suggestions, and each item's past occurrences (fulfilled, late, skipped). Statistical forecasting is phase 4.

### 4.7 Wealth / net worth (M)

Net worth is followed as a **monthly wealth matrix**, like the maintainer's own spreadsheet: what each holding is worth at the end of each month, by category. There are no securities positions, no market prices and no loan schedules: every value is entered by hand once a month, the bank accounts' too, which is what the maintainer already does.

- F-WLT-1: **Wealth categories**, two levels like the budget's (F-CAT-1). Defaults, in the owner's language: Savings accounts (Livrets), Current accounts (Comptes courants), Stocks (Actions), Crypto (Cryptos), Bonds (Obligations), Private equity, Gold (Or), Real estate (Immobilier), Equipment (Matériels), Exotic (Exotiques) and **Debts** (Dettes), the one liability category. Categories can be renamed, moved, added or deleted: a category holding lines cannot be (any line counts, a member's private ones included, which would be lost otherwise). Each category has its own colour from the `wealth-*` set (§7); its lines share it.
- F-WLT-2: **Wealth lines** are the subcategories: one holding each (e.g. "PEA Fortuneo" and "CTO Trade Republic" under Stocks, "Lynxéa Spirit 2" where the owner files it, "Crédit immobilier" under Debts). Like an account, a line has an **owner** and a **visibility** (`private`, `shared` or `joint`, §3); a private line is shown to its owner only. A line can be closed from a month on (sold, repaid): it keeps its history and leaves later months.
- F-WLT-3: **Monthly values**: each line has at most one value per calendar month, in EUR, positive (a debt is entered as what is still owed and counts negatively). A month without a value carries the previous one forward, shown as carried, until a new value is entered; before its first value a line is empty. A closed month takes no value, and the matrix ends with the current month at the latest: later months are unknown. Values are entered in the matrix or with **"Update this month"**, which lists the open lines with their last value pre-filled and saves them all at once, or none if one is refused.
- F-WLT-4: **Bank accounts are lines entered by hand** (since v0.16): Savings accounts and Current accounts are ordinary categories, where the user adds one line per account ("Livret A", "Compte joint"…) and enters its value each month like any other line. The app's cash accounts are not read: the matrix shows what the maintainer enters, whether the account is imported or not.
- F-WLT-5: **The wealth matrix**: lines grouped by category in rows, months in columns (the last 12 by default, from the analyses start, F-ADM-4), with category subtotals in the category's colour, **gross assets**, **debts** and **net worth**, and for each month the change against the previous one (€ and %). A column gives each category's **share** of gross assets for the last month shown. Scope: *household*, *joint* or *mine*, as for the budget (§3).
- F-WLT-6: **Wealth charts**: net worth over time, stacked by category in their colours (debts below zero); the allocation of the last month (share per category, then per line on demand); every chart has its table (no value reachable only by hovering).
- F-WLT-7: The overview (F-DSH-1) shows net worth and its change over the month.

### 4.8 Dashboard and reporting (M)

- F-DSH-1: Home page showing net worth with its change, the month's cash flow, budget status (the month so far, F-BUD-2), upcoming recurring items and recent transactions.
- F-DSH-4: Spending KPIs for any month (default: current): total spent, total income, net cash flow and savings rate ((income − spending) / income), with the part of the net cash flow put in savings categories (F-CAT-4); change vs the previous month and vs the 12-month average; top 5 categories; number of transactions left to categorise.
- F-DSH-5: Spending charts: by category (bar chart, one level, drill-down to subcategories); monthly evolution over 12 months (stacked bars by category, income line); cumulative spending within the month against the budget line. Transfers between own accounts are excluded everywhere (F-TX-5).
- F-DSH-6: **Plan steering dashboards**, on the plan review (F-BUD-8):
  - **cumulative chart**: cumulative spending by day over the plan against the cumulative envelope line, in total or for one category;
  - **gap chart**: the projected gap in % per category ((projection − envelope) / envelope, the gap itself once the plan is over), coloured with the status;
  - **money flows** (Sankey, a first piece of F-DSH-2): income by category and transfers paid in on the left, a central "available" node, then spending by top-level category (or subcategory, on demand), transfers paid out, **savings** (net transfers from the scope's other accounts into its savings accounts, plus the savings categories, F-CAT-4) and the **unallocated** rest on the right; a shortfall comes in on the left as a deficit, money taken back from savings as such. Both sides add up to the same total;
  - **drift list** (during a plan): categories ranked by projected overrun in €;
  - **plan comparison**: two plans side by side (by default the current one and the previous one, or the same period a year before), per category: monthly target and monthly average spent (for a running plan, its projection ÷ its number of months), with the change in € and in %. Monthly averages make plans of different lengths comparable.
- F-DSH-2: **Reports**: income and spending by category over any period of whole budget months (presets: this month, last month, this quarter, this year, last year, the last 12 months; or any first and last month, 10 years at most), in the *household*, *joint* or *mine* scope. Figures follow the home page's rules (F-DSH-4): budget months (F-TX-7), split parts (F-TX-4), transfers excluded except those crossing the scope. A period running past the current month stops there ("this year" means this year so far) and is compared with the same months of the period before, so monthly averages and changes compare like with like. A change is measured against the size of the previous figure: a net cash flow going from −500 € to +200 € is +140 %. A report shows:
  - the period's **totals**: income, spending, net cash flow, the part saved and the savings rate, each against the **previous period of the same length** (a year against the year before, a quarter against the quarter before);
  - a **table by category** in three sections (income, spending, savings), each top-level category with its subcategories: the total, the monthly average, the share of its section and the change against the previous period. Uncategorised outflows count as spending and inflows as income, as "to categorise";
  - a **monthly chart**: income and spending per month, with the net;
  - the **money flows** (Sankey) of the period, built as on the plan review (F-DSH-6) but without statuses: a report has no targets.

### 4.9 Administration (M)

- F-ADM-1: Automatic daily backup (`pg_dump`) with a retention policy (e.g. 7 daily, 4 weekly, 12 monthly) to a configurable directory.
- F-ADM-2: A documented restore procedure, plus a restore test script run regularly.
- F-ADM-3: **Activity log** of sensitive actions, written in the same database transaction as the action itself:
  - **sign-ins**: completed (with the second factor used: authenticator code or recovery code), failed on a known account (wrong password or wrong code), sign-outs, recovery codes renewed. They keep the client's address;
  - **household**: invites created, revoked or accepted, settings changed;
  - **imports**: a statement imported (file name, rows added) and an import rolled back;
  - **deletions**: transactions, categories, budget plans and recurring items;
  - **rules**: created, changed, deleted or applied to existing transactions (without the count, which would reveal matches on private accounts), and the default categories restored.

  Each entry records who, when and what, with a short description frozen at the time (label, amount, file name, count), so it still reads after the object is gone. The **owner** sees the whole household's log, a **member** only their own entries; an entry about a private account is shown only to that account's owner. The log is read-only in the app and can be filtered by kind and, for the owner, by member. An entry keeps the visibility it had when written: making an account private later does not hide its past entries. Attempts refused by the sign-in limit (F-AUTH-4) are not logged, the failures that reached it are.
- F-ADM-4: **Analyses start**: the owner may set the first month analyses count (none by default: every month; never a month to come, which would empty every analysis). History before it is often incomplete (accounts added later, statements without the everyday entries), so the overview (previous month, 12-month average), the reports (F-DSH-2: a period starts no earlier, and a comparison with earlier months finds nothing) and the detection of recurring items (F-REC-2) treat earlier months as empty. Transactions, balances and budget plans are untouched.

## 5. Later phases (roadmap)

| Phase | Content |
|---|---|
| 0 — Foundations | Repo, tooling, CI, Claude Code config, design tokens, Docker Compose skeleton |
| 1 — Budget MVP | Auth + household, accounts, import, manual entry, categorisation, transactions, budget targets vs actual (F-BUD-1, 2, 4, 5) with the budget matrix (F-BUD-6), spending KPIs and charts (F-DSH-4, 5) |
| 2 — Budget complete | Budget plans by period and their review, with steering dashboards (F-BUD-7, 8, F-DSH-6), then recurrences, reports and the activity log |
| 3 — Wealth | The monthly wealth matrix: categories and lines entered by hand, debts and net worth, evolution and allocation charts |
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

Month progress colours (F-BUD-2): the bar of a category on track is **green** (`primary`), watched **ochre** (`secondary-500`), over **burnt orange** (`budget-over`); the pace marker is a thin line in the text colour. Each status has its icon and word, so colour is never the only cue.

Money flows colours (the Sankey of the plan review, F-DSH-6) are semantic tokens too, `flow-*`, for both themes: money in is **blue** (`flow-in`, a steel blue, the one hue outside the blog palette, chosen to sit with its muted greens); spending within its target, or without one, is **ochre** (`secondary-500`), over its target **burnt orange** (`secondary-800`, `secondary-700` in dark); savings meeting their objectives are **green** (`primary`), below them **pale green** (`primary-300`, `primary-200` in dark); the unallocated rest and transfers paid out are **grey** (`neutral-400`), a deficit burnt orange. The status follows the review's (projected while the plan runs). The palette passes the CVD checks of the data-viz validator in both themes; every flow keeps its label, its table row with the status in words, and a legend.

Wealth category colours (F-WLT-1) are a categorical set of semantic tokens, `wealth-*`, one per default top-level category, for both themes: muted hues drawn around the blog palette: its greens (savings and current accounts), ochre (gold) and browns (real estate), the steel blue of `flow-in` (stocks), a slate grey kept well apart from the pale green of current accounts (equipment), and four muted hues the palette lacks, a violet (crypto), a light blue (bonds), a plum (private equity) and a teal (exotic), with Debts in burnt orange. Each category's colour marks its row (a swatch) and its lines (a side bar). Ten hues cannot all stay apart for every colour-vision deficiency, so colour is never the only cue: every category keeps its label in the matrix and the charts, a legend in the same order as the stack, and its table. A category added later takes a hue from the same set, chosen by the owner. The tokens sit in a `@theme static` block: the page reads them through `var()` only, and Tailwind would otherwise drop them from the build.

## 8. Domain invariants (to be enforced by tests)

1. An account balance equals its opening balance plus the sum of its transactions at any date.
2. The parts of a split transaction sum exactly to the parent amount, each of its sign; summed over categories, a split transaction counts its amount exactly once.
3. A linked transfer nets to zero across the two accounts and never counts as income or expense; its two sides keep opposite amounts through every edit (F-TX-9).
4. Importing the same file twice leaves the database unchanged.
5. A line's value in a month is the last value entered in that month or before (carried forward), and nothing before its first value or after its closing.
6. A month's net worth equals the sum of its asset lines minus the sum of its debt lines; each category's subtotal is the sum of its lines, and the scopes add up as in invariant 11 (*household* = *mine* + *joint* + the lines other members share).
7. Forecasts and back-tests (phase 4) never read data after their origin date.
8. Budget plans never overlap, and each lies within one calendar period (year, semester or quarter).
9. A category's envelope equals its monthly target times the plan's number of months; a parent without a target of its own takes the sum of its children's.
10. A plan review, the budget matrix and the month so far never disagree: the spending of a plan equals the sum of the matrix cells of its months, and a category's spending in the month so far equals its matrix cell for that month, category by category.
11. The *mine* and *joint* scopes never share an account, and the *household* scope is exactly *mine*, plus *joint*, plus the accounts other members share.
12. For any split of the accounts into two groups, what one group pays out by transfer is exactly what the other pays in; within the household scope nothing is paid in or out.
13. A plan's money flows balance: what comes in (income, paid in, taken from savings, deficit) equals what goes out (spending, paid out, saved, unallocated).
14. Savings categories are never spending nor income: the net cash flow of a period (income − spending, before transfers crossing the scope) equals the sum of its transactions, transfers excluded, plus what its savings categories received (net of withdrawals).
15. Every transaction counts in exactly one budget month, at most one month away from its booking month, and a transfer in its booking month: summed over all months, income, spending and savings are the same by budget month as by booking month. Shifting a transaction's month never changes an account balance.
16. A transaction fulfils at most one occurrence and an occurrence at most one transaction; the projected end-of-month balance equals the current balance plus the expected amounts of the unfulfilled, unskipped occurrences up to the end of the month, a transfer item counting only its sides on the scope's accounts.
17. Importing a statement whose operations were already entered by hand adds only the rows that match no entry: every bank row ends up as exactly one transaction, the account balance is the same as if only the statement had been imported, plus the entries that matched no row, and rolling the import back restores the manual entries as they were.
18. A report never disagrees with the home page: its income, spending and savings over a period equal the sums of the KPIs of its months (F-DSH-4), and in each section the category lines add up to the section's total.

## 9. Open questions

- **Q1** — ✅ Name: **Kwak Finance**; Python packages `kwak_core`, `kwak_api`, `kwak_analytics`.
- **Q2** — ✅ First import profiles: **Société Générale** (checking, Livret A, LDDS), the cash accounts of phase 1. SG exports two CSV layouts: checking (summary line with the balance, 5 columns) and savings (newer snake_case header, trailing `;`). **Helios** (the household's joint checking account, §3) exports one CSV layout: 8 columns separated by `; `, UTF-8 with a BOM, `.` decimals, the counterparty and the wording in separate columns, Helios' own categories (ignored) and only executed operations imported. The Fortuneo checking account is unused and out of scope. Investment accounts (Fortuneo PEA/CTO, Lynxéa Spirit 2 life insurance, Amundi PERCOL/PEG, Trade Republic CTO, Kraken) come with phase 3. Fixtures are synthetic files that copy each bank's exact layout.
- **Q3** — ✅ Moot since v0.15: wealth values are entered in EUR (no market prices, so no foreign quotes).
- **Q4** — ✅ Neither: wealth is a monthly matrix of categories and lines (F-WLT), each line valued once a month, as in the maintainer's spreadsheet. Life insurance is one line, filed under the category the maintainer chooses.
- **Q5** — ✅ Runs on the development machine (RTX 5070 Laptop, 8 GB VRAM, 30 GB RAM): Ollama limited to ~7–8B models (quantised).
- **Q6** — Remote access: LAN only, or VPN later (not in MVP)?
- **Q7** — Backup destination: local disk only, or an extra copy (external drive, NAS)? Local daily backups exist (docs/OPERATIONS.md); an off-machine copy is still manual.
- **Q8** — Data history to import at start (how many years, how many accounts)?
