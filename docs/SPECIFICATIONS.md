# Functional Specifications

Status: draft v1.4 — 2026-10-22 (v1.0: spending redesigned, lines entered by hand, no accounts, import nor transfers; v1.1: spending category colours, §7; v1.2: the pyramid in stone on a column, §7; v1.3: income categories, the month's income is its income lines, F-INC-1; v1.4: pleasure goals in a golden capstone, unlocked by a full precaution and goals ahead, F-GOAL-10). Owner: sole maintainer.

## 1. Purpose

A self-hosted web application to manage a household's **budget** (cash flows), **net worth** (assets and liabilities) and **financial goals** (amounts to gather by a date), designed so that analytics, data-science and local generative-AI features can be added in later phases without reworking the core.

The project doubles as a reference implementation of the maintainer's Claude Code development practices (see `docs/CLAUDE_CODE.md`).

## 2. Scope and constraints

| Topic | Decision |
|---|---|
| Users | One household: a few members sharing the spending, each with private wealth lines and goals if they wish |
| Hosting | Self-hosted only (Docker Compose on a local machine / home server). No cloud dependency |
| Currency | **EUR only** for spending lines, income, budgets and wealth values |
| Data sources | Manual entry only: spending and income lines as they come (weekly or monthly), wealth values monthly. No bank file import (since v1.0) and no market-data API |
| Out of scope | Bank aggregation APIs (DSP2), payments, tax filing, multi-household SaaS, native mobile app |
| Language | Code, docs, UI and commits in English |

## 3. Users and roles

- **Owner**: creates the household, manages members, backups and settings.
- **Member**: full access to the spending (lines, income, budget, shared by the whole household), to shared and joint wealth lines and goals, and to their own private ones.
- The spending has no visibility: every member sees and edits every line (since v1.0). Visibility is per wealth line and per goal: `private` (owner only), `shared` (all household members, still the owner's) or `joint` (the household's common holding: all members, nobody's own). The wealth and the goals let each user choose *household* (everything visible), *joint* (the joint lines and goals) or *mine* (their own, joint ones excluded).

## 4. Functional requirements

Priority: **M** = MVP, **S** = should (later in MVP), **L** = later phase.

### 4.1 Authentication and household (M)

- F-AUTH-1: Login with email + password (argon2id hashing), server-side session in an httpOnly cookie.
- F-AUTH-2: Mandatory TOTP 2FA, with one-time recovery codes.
- F-AUTH-3: Owner invites members (invite link, single use, expiring).
- F-AUTH-4: Login rate limiting and session revocation.

### 4.2 Spending lines and income (M)

Since v1.0 the spending side has no accounts, no bank import and no transfers: the maintainer enters every expense by hand, once a week or once a month, and a statement only got in the way (rows to sort again, duplicates of what was already entered). An expense is **one line**, whichever account or card paid it.

- F-LIN-1: A **line** has a date, a label (1 to 100 characters), an amount to the cent and a category (F-CAT-1), required: a line is never left "to categorise". It records who entered it and when. Spending belongs to the household: every member sees and edits every line.
- F-LIN-2: A line counts in the **month of its date**, in every figure. There is no budget month: a salary paid on the 28th is the income of the month of its date, unless the line is dated otherwise (F-INC-1).
- F-LIN-3: An **expense** line is an outflow, entered as a positive amount (stored negative, §6). A **savings** line (F-CAT-4) is money put aside, entered as a positive amount, or money taken back from savings, entered with a minus sign. An **income** line (F-CAT-1) is money received, entered as a positive amount (stored positive); refunds (health insurance, a returned item) are income lines. A line is income or spending, never both: a split line's parts are all income or none (F-LIN-4).
- F-LIN-4: **Split**: a line can be spread over two or more **parts**, each a category and a positive amount. The user enters every part but the last, which takes the rest, so the parts always add up exactly to the line (invariant 2). A split line counts in each part's category, for its part's amount, in every figure by category; the grid shows it once, as "Split" with its parts. When the amount of a split line changes, the last part takes the difference; the change is refused if that part would reach zero or less. Removing the split leaves the line in its first part's category.
- F-LIN-5: Deleting a line can be undone straight away, from the message that confirms it; it is recorded in the activity log (F-ADM-3).
- F-INC-1: **Monthly income** (since v1.3): a month's income is the sum of its **income lines** (F-LIN-3), in the income categories (salaries, benefits, refunds…). A month without income lines has none; nothing is carried from the month before. The single monthly amount of v1.0 was turned into one income line on the first of each month, in Other income, from the first amount entered to the month of the migration, the carried months included.

### 4.3 Entering lines (M)

Entry is made for a session at a computer, keyboard first: every action below is reachable without the mouse.

- F-ENT-1: **The grid**, the Spending space's main page: one month (the current one by default, the previous and next ones a key away), its lines sorted by date then by entry order, every cell editable in place. An **empty row** is always ready at the bottom: date, label, amount, category; **Tab** moves to the next cell, **Enter** saves the row and opens a new one with the same date, **Escape** cancels the row's changes. A row is saved only once complete. A new row's date is the previous row's in the session, otherwise today (for a past month, its last day). The header shows the month's income (its income lines, F-INC-1), spent, saved and the rest (F-DSH-4).
- F-ENT-2: **Quick line**: a text field above the grid takes a line written **in any order**, e.g. `boulangerie 12,50 hier`, `45 sncf 13/10` or `carrefour 87.40 #foyer`:
  - a **date** is a day word (*today*, *yesterday*, *the day before yesterday*), a weekday (the latest such day up to today) or a `dd/mm` or `dd/mm/yyyy` date, in the user's language; without one, the date follows F-ENT-1;
  - the **amount** is the last number left (comma or dot decimals, an optional `€`, a leading `-` for a savings withdrawal), stored positive when the category is an income one (F-LIN-3); the other numbers stay in the label;
  - `#word` **forces the category** whose name starts with that word (case and accents ignored), when exactly one does;
  - the rest is the **label**, whose category comes from the label memory (F-ENT-3).
  Below the field, the line is shown as understood while it is typed. Enter saves it when it is complete; otherwise it goes into the grid's empty row, the missing cell focused.
- F-ENT-3: **Label memory**: the label cell and the quick line suggest the labels already used in the household that start with what is typed (case and accents ignored), the most used over the last 12 months first. Choosing a known label, or typing one exactly, fills in the **category** of the latest line with that label, never the amount; the user may change it, and the latest choice is the one remembered. There are no categorisation rules.
- F-ENT-4: **Where I stopped**: the line entered last (by entry time) is marked in the grid, and the header says its date and when it was entered ("last entry: Tue 15/10, entered on 16/10"), with a link to its month when it is in another one.

### 4.4 Categories (M)

- F-CAT-1: **One level** of categories (since v1.0), each with a **kind**: **expense**, **savings** or **income** (since v1.3). The default set, in the owner's language: Housing (Logement), Groceries (Courses), Transport, Children (Enfants), Health (Santé), Subscriptions (Abonnements), Home (Foyer), Leisure (Loisirs), Shopping, Gifts (Cadeaux), Miscellaneous (Divers), Savings (Épargne), the one savings category, and four income categories: Salaries (Salaires), Benefits (Aides et allocations), Refunds (Remboursements) and Other income (Autres revenus). An income category has no target (F-BUD-1) and no fixed expense (F-FIX-1); the budget and the reports show what it received. Categories can be renamed, added and deleted; deleting a category that holds lines, split parts, fixed expenses or targets asks for another category of the same kind to move them to. "Restore defaults" adds back the default categories that are missing.
- F-CAT-4: A **savings** category holds the money put aside (a payment into a savings account, an investment): its lines are **saved**, never spending, and reduce the month's rest (F-DSH-4); a withdrawal counts against them. Savings are valued in the wealth matrix (§4.7), which reads nothing from these lines.
- F-CAT-6: **One-off** expense categories, paid once in the month (rent, a subscription), so their spending is complete from the day they are paid and is never judged against the pace of the month nor the warning threshold (F-BUD-2). Off by default; the default set marks Housing and Subscriptions as one-off.

### 4.5 Budgets (M)

Goal of the budget module: **compare spending per category with a target** set beforehand, month by month and over the year, with nothing to sort first.

- F-BUD-1: A **monthly target** per expense category, set **from a month on** (this month by default) and kept until it is changed: a change from a month leaves the earlier months' targets as they were, and removing a target leaves the category without one from that month. Setting a target from a past month says which months change.
- F-BUD-9: A **savings objective** per savings category, a monthly minimum set like a target (F-BUD-1): saving more is good. Its status mirrors a target's with the band and colours of F-BUD-6: **ahead** (saved more than the band above the objective) in green, **on** in neutral, **behind** (more than the band below) in burnt orange.
- F-BUD-2: **The month so far**, a section of the overview (F-DSH-1) for the month it shows (default: the current one): one line per expense category with a target that month, ranked by share used, highest first: spent, target, remaining (or the overrun), **share used** (spent ÷ target) and a progress bar. Categories without a target and savings categories are not listed. Each line has a status, shown with an icon and a word as well as a colour:
  - **on track**: share used below the warning threshold;
  - **watch**: from the threshold up to 100 %, except for a **one-off** category (F-CAT-6), which is on track up to 100 %;
  - **over**: above 100 %.
  The **warning threshold** is a household setting (default 80 %, from 50 % to 100 %), changed by the owner. For the current month, a **pace** marker on each bar shows the share of the month elapsed (today's day ÷ the month's number of days); it is not shown on a one-off category nor for a past month. A line opens the month's grid filtered on the category.
- F-BUD-6: **Budget matrix**: one row per expense category, one column per month (default: the last 12), plus a first column with the category's current target. The matrix scrolls within its frame: the month headers stay at the top and the category and target columns on the left. Each cell shows the month's spending, its **gap to that month's target in € and in %** ((spent − target) / target), and a colour:
  - **under**: spent more than 5 % below the target → green;
  - **on target**: within ±5 % → neutral (pale grey);
  - **over**: more than 5 % above the target → burnt orange / terracotta.
  The 5 % band is a setting. A month without a target shows its spending without a colour. Above the expenses, an **income** section shows what each income category received, without target nor colour; below the expenses, a **savings** section holds the savings categories against their objectives (F-BUD-9); then rows for the month's **income**, **spent**, **saved** and **rest**. Clicking a cell opens that month's grid filtered on the category.
- F-BUD-10: **The year**: for a calendar year (the current one by default), per category: the targets **to date** (the targets of January to this month added up, the current month in full, so a running month leans under) and for the **full year**, the spending to date, the gap to date in € and in % with the status of F-BUD-6, and the number of months over, on and under their target; the same for the savings objectives, what each income category received to date, then the year's income, spending, savings, rest and savings rate. A past year is shown whole.

### 4.6 Fixed expenses (M)

Rent, the childminder, subscriptions and insurance come back every period: fixed expenses save typing them and say what is still to come.

- F-FIX-1: A **fixed expense** has a label, a category (expense or savings, e.g. a monthly payment into a savings account; never income), an amount, a **frequency** (monthly, quarterly or yearly), a day of the month (the last day standing in for a missing one), a first month and optionally a last month; it can be paused. Fixed expenses are listed, added and changed on their own page, opened from the grid.
- F-FIX-2: **To confirm**: each occurrence due in a month (every month from the first one, every third month, or every twelfth) is shown at the top of that month's grid, greyed, with its date. **Confirming** it (Enter on the row, or its button) creates the line with the fixed expense's label, category, amount and date, each of which can be changed first; an occurrence can also be **skipped** for the month, which can be undone. An occurrence counts as confirmed as soon as its month holds a line created from it, or a line typed by hand with the same label (case and accents ignored) and category that no other occurrence took. Nothing is ever created by itself.
- F-FIX-3: A fixed expense's **monthly equivalent** is its amount for a monthly one, a third of it for a quarterly one and a twelfth for a yearly one (used by F-GOAL-2).
- F-FIX-4: The overview (F-DSH-1) lists the current month's occurrences still to confirm, with "Confirm", and the **projected rest** at the end of the month: the rest (F-DSH-4) minus the occurrences still to confirm.

### 4.7 Wealth / net worth (M)

Net worth is followed as a **monthly wealth matrix**, like the maintainer's own spreadsheet: what each holding is worth at the end of each month, by category. There are no securities positions, no market prices and no loan schedules: every value is entered by hand once a month, the bank accounts' too, which is what the maintainer already does.

- F-WLT-1: **Wealth categories**, two levels. Defaults, in the owner's language: Savings accounts (Livrets), Current accounts (Comptes courants), Stocks (Actions), Crypto (Cryptos), Bonds (Obligations), Private equity, Gold (Or), Real estate (Immobilier), Equipment (Matériels), Exotic (Exotiques) and **Debts** (Dettes), the one liability category. Categories can be renamed, recoloured, moved, added (an asset or a debt) or deleted, from "Manage categories" on the wealth page: a category holding lines cannot be (any line counts, a member's private ones included, which would be lost otherwise). Each category has its own colour from the `wealth-*` set (§7); its lines share it.
- F-WLT-2: **Wealth lines** are the subcategories: one holding each (e.g. "PEA Fortuneo" and "CTO Trade Republic" under Stocks, "Lynxéa Spirit 2" where the owner files it, "Crédit immobilier" under Debts). A line has an **owner** and a **visibility** (`private`, `shared` or `joint`, §3); a private line is shown to its owner only. A line can be closed from a month on (sold, repaid): it keeps its history and leaves later months.
- F-WLT-3: **Monthly values**: each line has at most one value per calendar month, in EUR, positive (a debt is entered as what is still owed and counts negatively). A month without a value carries the previous one forward, shown as carried, until a new value is entered; before its first value a line is empty. A closed month takes no value, and the matrix ends with the current month at the latest: later months are unknown. Values are entered in the matrix or with **"Update this month"**, which lists the open lines with their last value pre-filled and saves them all at once, or none if one is refused.
- F-WLT-4: **Bank accounts are lines entered by hand** (since v0.16): Savings accounts and Current accounts are ordinary categories, where the user adds one line per account ("Livret A", "Compte joint"…) and enters its value each month like any other line. Nothing is read from the spending (F-CAT-4): the matrix shows what the maintainer enters.
- F-WLT-5: **The wealth matrix**: lines grouped by category in rows, months in columns (the last 12 by default, from the **wealth start** at the earliest; any other period of up to 120 months can be chosen, ending this month at the latest), with category subtotals in the category's colour, **gross assets**, **debts** and **net worth**, and for each month the change against the previous one (€ and %). A column gives each category's **share** of gross assets for the last month shown. Scope: *household*, *joint* or *mine* (§3). As the budget matrix (F-BUD-6), it scrolls within its frame, its month headers and its line names staying in view both ways.
- F-WLT-6: **Wealth charts**, on the wealth's *Analysis* page, over the months and scope chosen there (as F-WLT-5), below the same summary tiles, each category in its colour:
  - **net worth over time**: each category's total per month, stacked (debts below zero), with net worth as a line;
  - **allocation** of a chosen month (the last one shown by default, one choice for both charts) as a **sunburst**: categories in the inner ring, their lines in the outer one, gross assets in the centre;
  - the same allocation as a **mosaic** (a squarified treemap, as Finary shows it): one tile per category, as large as its value, the largest first, labelled with its name, value and share when it has the room;
  - **what moved net worth**: a bridge from the first month's net worth to the last's, one step per category that moved (a debt repaid lifts it);
  - the net worth tile adds its change over the months shown, the debts tile the **debt ratio** (debts / gross assets).
  Every chart has its table, and the sunburst and the mosaic read the pointed or focused mark out in words: no value is reachable only by hovering.
- F-WLT-7: The overview (F-DSH-1) opens with net worth at the end of its month and its change over that month, in its scope, once the wealth has a line, with a link to the wealth page.

### 4.8 Dashboard and reporting (M)

- F-DSH-1: Home page showing net worth with its change, the month's figures (F-DSH-4), the month so far (F-BUD-2), the fixed expenses still to confirm with the projected rest (F-FIX-4), the goals (F-GOAL-9) and the last lines entered.
- F-DSH-4: Spending KPIs for any month (default: current): **income** (income lines, F-INC-1), **spent** (expense lines), **saved** (savings lines, net of withdrawals), the **rest** (income − spent − saved) and the **savings rate** ((income − spent) / income); change vs the previous month and vs the 12-month average; top 5 categories.
- F-DSH-5: Spending charts: by category (bar chart); monthly evolution over 12 months (stacked bars by category, income line); cumulative spending within the month against the sum of its targets.
- F-DSH-2: **Reports**: income, spending and savings by category over any period of whole months (presets: this month, last month, this quarter, this year, last year, the last 12 months; or any first and last month, 10 years at most). A period running past the current month stops there ("this year" means this year so far) and is compared with the same months of the period before, so monthly averages and changes compare like with like. A change is measured against the size of the previous figure: a rest going from −500 € to +200 € is +140 %. Months before the first line entered are left out. A report shows:
  - the period's **totals**: income, spent, saved, the rest and the savings rate, each against the **previous period of the same length** (a year against the year before, a quarter against the quarter before);
  - a **table by category** in three sections (income, spending, savings): the total, the monthly average, the share of its section and the change against the previous period;
  - a **monthly chart**: income and spending per month, with the rest;
  - the **money flows** (Sankey): the income by category on the left, a central "available" node, then spending by category, savings and the **unallocated** rest on the right; a shortfall comes in on the left as a deficit, money taken back from savings as such. Both sides add up to the same total. The spending of a category over its targets for the period is burnt orange, within them (or without a target) ochre.

### 4.9 Administration (M)

- F-ADM-1: Automatic daily backup (`pg_dump`) with a retention policy (e.g. 7 daily, 4 weekly, 12 monthly) to a configurable directory.
- F-ADM-2: A documented restore procedure, plus a restore test script run regularly.
- F-ADM-3: **Activity log** of sensitive actions, written in the same database transaction as the action itself:
  - **sign-ins**: completed (with the second factor used: authenticator code or recovery code), failed on a known account (wrong password or wrong code), sign-outs, recovery codes renewed. They keep the client's address;
  - **household**: invites created, revoked or accepted, settings changed;
  - **deletions**: lines, categories (with the category their lines moved to), fixed expenses and goals (F-GOAL-8);
  - the default categories restored.

  Each entry records who, when and what, with a short description frozen at the time (label, amount, count), so it still reads after the object is gone. The **owner** sees the whole household's log, a **member** only their own entries; an entry about a private goal or wealth line is shown only to its owner. The log is read-only in the app and can be filtered by kind and, for the owner, by member. Attempts refused by the sign-in limit (F-AUTH-4) are not logged, the failures that reached it are.
- F-ADM-4: **Wealth start**: the owner may set the first month the wealth matrix opens from (F-WLT-5), never a month to come; without one, nothing limits it.

### 4.10 Financial goals (phase 4)

A **goal** is an amount to gather by a date: an emergency fund, a trip, a home deposit. It has nothing to do with the budget's monthly targets (F-BUD-1) or savings objectives (F-BUD-9), which judge a month's flows. Goals are arranged as a **pyramid** of three tiers on a **foundation**, the emergency fund, under a golden **capstone** for pleasure goals (F-GOAL-10), and funded by **wealth lines** (F-WLT-2), so their progress follows the values entered each month in the wealth matrix, with nothing more to enter.

- F-GOAL-1: **The pyramid**: its **foundation** is the precaution (below); above it, three **tiers**, from the base, given by the deadline's distance from this month, never chosen: **long term** (beyond 5 years: a home deposit, the children's studies), **medium term** (over 12 months, up to 5 years: a trip, a large purchase) and, at the top, **short term** (up to 12 months: holidays, a repair). A goal **moves tier by itself** when its deadline changes or, as months pass, when it comes within a nearer tier's horizon, climbing towards the top. A goal may be **permanent**: it stays in view once its target is reached (any other goal is then archived by itself, F-GOAL-8), and its deadline is optional (without one, it is in the short term, and its status is **open** rather than ahead or behind). A goal may be the **precaution**, the emergency fund, filled first (F-GOAL-6), always permanent and in the foundation, whatever its deadline. A goal may instead be a **pleasure** goal, in the capstone (F-GOAL-10). A goal has a name, a **target** amount (EUR, positive), a **deadline** month (required but for a permanent goal, none for a pleasure goal, never a past month), a **start** month (the month it is created by default, or an earlier one, from the wealth start, to count progress already made), an **owner** and a **visibility** (`private`, `shared` or `joint`, as a line, §3). Each member has at most one open precaution goal, and the household at most one joint one.
- F-GOAL-2: **The precaution's target** is a fixed amount. The form proposes one: a number of months (6 by default, from 1 to 12) of the **average monthly fixed expenses**, the sum of the monthly equivalents (F-FIX-3) of the fixed expenses in an expense category not paused nor ended, shown with its detail; the spending being the household's, the proposal is the same in every scope. Accepting it copies the amount into the target, which never changes by itself afterwards. Without a fixed expense there is no proposal, but a link to the fixed expenses page.
- F-GOAL-3: **Funding** by **envelopes**: a goal is funded by asset lines (never a debt), each holding an envelope, the part of the line set aside for it; the rest of the line is **free**, for anything else. A funding has an **opening amount** (in euros, 0 by default, taken from the line's free part in the goal's start month) and a **share of the rises** (1 to 100 %, 100 % by default); a line's shares of the rises sum to 100 % at most across open goals. Month by month from the goal's start, with only the lines' values entered (F-WLT-3, carried forward, nothing after a line's closing): when a line **rises** (a deposit, interest, a gain), each goal it funds receives its share of the rise, never beyond its target, nor a locked pleasure goal (F-GOAL-10), the rest staying free; when a line **falls** (a withdrawal, a loss), the fall comes out of the **free part first**, and its goals only lose once the line is worth less than they hold, cut from the pleasure goals first, then from the farthest deadline to the nearest and the precaution last, so they never hold more than the line. When the app credits a goal with a rise that was not for it (a deposit for something else), its envelope can be **adjusted** by hand from a month: from then on it holds the amount set (never more than the line's free part plus what it held, nor beyond its target), and goes on rising and falling as before; an adjustment can be removed. An archived or cancelled goal frees its envelopes. A goal's **value** in a month is the sum of its envelopes. Changing an opening amount or a share recomputes the goal from its start, which the form says. The goal form shows each line's free part, and the Wealth page each line's part set aside for goals; both count only the goals the viewer sees. A goal uses its owner's lines and joint ones; a joint goal joint lines only; a private line funds only a private goal, whose value would otherwise show it, and cannot turn private while it funds another.
- F-GOAL-4: **Monthly tracking and status**: for each month from the start, the goal's value, its **progress** (value ÷ target) and what it gained over the month. The **expected** value follows a straight line from the value of the start month to the target at the deadline. The status uses the band of the budget (F-BUD-6): **reached** (the value meets the target), **ahead** (above the expected value by more than the band), **on track** (within it) or **behind** (below it by more than the band), in green, neutral and burnt orange as a savings objective (F-BUD-9). A precaution goal short of its target is **to fill first** instead, in ochre; the other short-term goals have the statuses above. A pleasure goal short of its target is **locked**, behind a padlock, or **open** (F-GOAL-10). Every status has its icon and word.
- F-GOAL-5: **Estimates**: the amount still to gather; for a goal with a deadline, the months left and the **required effort** (what is left ÷ the months left, at least one); the **actual effort**, the average monthly gain over the last 6 months (fewer for a younger goal; with no complete month yet: "not enough history"); the **estimated date** (this month plus what is left ÷ the actual effort, rounded up), or "never at this pace" when the actual effort is nil or negative; against the deadline, how many months early or late, and when late, the extra effort per month that keeps the date (required − actual).
- F-GOAL-6: **The month's effort plan**, a recommendation (nothing is moved): the **capacity** is the household's average monthly income minus spending (F-DSH-4, savings lines left in, since they are what goals are funded from) over the last 6 complete months from the first one with a line, the same in every scope, never below zero, unless the owner sets it by hand (a household setting). While the scope's precaution goals fall short, they receive their gap, up to a **precaution share** of the capacity (a household setting, from 50 % to 100 %, 70 % by default), split by gap; the rest goes to the other open goals not yet reached, short-term ones included, in proportion to their required effort and never beyond it; what they leave goes to the precaution until its gap is filled, then to the pleasure goals that are not locked, in proportion to what each still lacks and never beyond it (F-GOAL-10), then is shown as **unallocated**. The plan says in how many months the precaution is filled at this pace and how much the other goals fall behind each month until then.
- F-GOAL-7: **The Goals page**, a space of its own (§7), in the *household*, *joint* or *mine* scope (§3): the **pyramid**, its foundation, each tier and the capstone filled by its goals' values over their targets and labelled with the percentage; while a precaution goal falls short, a warning with the missing amount; the effort plan (F-GOAL-6); then each tier with its goals as cards: a **gauge** with a **pace** marker at the expected value, the value and target, the progress, the status, the deadline, the estimated date, the required and actual efforts, and a sentence ("at this pace, 6 months after the deadline: +€80 a month keeps the date"), and its actions: edit, archive, cancel (F-GOAL-8). A card opens the goal's page: the estimates as tiles, a **trajectory** chart (the values, the expected line, the projection at the actual effort, the target and the deadline) and its table by month (value, gained, expected, gap), the latest first, and its envelopes, line by line, with their opening amount, share of the rises, what they hold and their adjustments (F-GOAL-3).
- F-GOAL-8: **Life cycle**: a goal can be edited, from its card or its page, then **archived** (done with, kept for the record) or **cancelled** (no longer wanted), after this month on its card or from a chosen month on its page; a goal that is not permanent is **archived by itself** after the month it reaches its target, and reopening it asks for a higher target or for it to become permanent; a permanent goal can be cancelled, not archived. An archived or cancelled goal leaves the pyramid, its lines' shares are freed, and it stays readable but **hidden by default** on the Goals page, which can show the archived and cancelled goals; one can be reopened. Deleting a goal removes it and its funding, never a line.
- F-GOAL-9: The overview (F-DSH-1) shows, once a goal exists, the progress of the foundation, the three tiers and the capstone, and the precaution warning, with a link to the Goals page.
- F-GOAL-10: **The capstone**, the pyramid's golden tip, holds the **pleasure goals**: things wanted only for the pleasure of it, not needed (a pair of boxing gloves, a record player, a fine bottle of rum). A pleasure goal has **no deadline**, is never the precaution nor permanent (it is archived by itself once reached, F-GOAL-8), and is funded like any goal (F-GOAL-3), but only once the essentials are in order: it is **locked** in a month unless, at the end of the month before, in its scope (its owner's goals and the joint ones; the joint ones only for a joint goal): there is a precaution goal and **every precaution goal is reached**, and **at least three quarters** of the open goals with a deadline are **ahead** or reached (on track or behind do not count; permanent goals without a deadline are left out; with no such goal, only the precaution counts). While locked, the line rises it would have received stay free, the effort plan gives it nothing, and what it already holds stays; its opening amount and its adjustments by hand, set on purpose, still apply. Once unlocked, its status is **open**. Its estimates are those of a goal without a deadline (F-GOAL-5): what is left, the actual effort and the estimated date. The capstone shows when it is locked, with a padlock, the word and why ("precaution at 82 %", "2 of 4 goals ahead, 3 needed").

## 5. Later phases (roadmap)

| Phase | Content |
|---|---|
| 0 — Foundations | Repo, tooling, CI, Claude Code config, design tokens, Docker Compose skeleton |
| 1 — Budget MVP | Auth + household, accounts, import, manual entry, categorisation, transactions, budget targets vs actual with the budget matrix, spending KPIs and charts |
| 2 — Budget complete | Budget plans by period and their review, with steering dashboards, then recurrences, reports and the activity log |
| 3 — Wealth | The monthly wealth matrix: categories and lines entered by hand, debts and net worth, evolution and allocation charts |
| 4 — Financial goals | Goals in a pyramid (the precaution as its foundation, then short, medium and long term, under a golden capstone of pleasure goals) funded by wealth lines: monthly tracking with gauges, status, estimated dates and a monthly effort plan that fills the precaution first (§4.10) |
| 4b — Spending redesign (v1.0) | Phases 1–2 replaced by simpler spending: lines entered by hand in a keyboard grid with a quick line and label memory, one level of categories, monthly income, fixed expenses to confirm, monthly targets with a matrix and a year view (§4.2–4.6). Accounts, import, transfers, rules, recurrences, budget months and plans are removed with their data: the spending starts afresh |
| 5 — Analytics & DS | Cash-flow **forecasting** (time-series, temporal back-testing, naive baseline first), **wealth simulation** (Monte Carlo, FIRE / retirement projection, allocation scenarios). Interactive Dash pages for exploration |
| 6 — Local GenAI | Ollama-based assistant: natural-language questions over your own data (text-to-SQL on a read-only analytics view), categorisation suggestions, monthly narrative summary. No data leaves the host |

## 6. Non-functional requirements

- **Privacy**: all data stays on the host. No telemetry. Real financial files are never committed to Git (`data/` is ignored; test fixtures are synthetic or anonymised).
- **Correctness of money**: amounts use `Decimal` / `NUMERIC`, never floats. Sign convention: negative = outflow (the grid shows expenses as positive amounts, F-LIN-3). Every aggregate is reproducible from the lines and the wealth values.
- **Security**: 2FA, argon2id, CSRF protection on cookie sessions, secrets in `.env` (not committed), dependency audit in CI. The app is served on the LAN behind a reverse proxy with TLS.
- **Performance**: the app should feel responsive on a home server with about 100k lines (lists < 300 ms, dashboard < 1 s).
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

Money flows colours (the Sankey of the reports, F-DSH-2) are semantic tokens too, `flow-*`, for both themes: money in is **blue** (`flow-in`, a steel blue, the one hue outside the blog palette, chosen to sit with its muted greens); spending within its target, or without one, is **ochre** (`secondary-500`), over its target **burnt orange** (`secondary-800`, `secondary-700` in dark); savings meeting their objectives are **green** (`primary`), below them **pale green** (`primary-300`, `primary-200` in dark); the unallocated rest is **grey** (`neutral-400`), a deficit burnt orange. The palette passes the CVD checks of the data-viz validator in both themes; every flow keeps its label, its table row with the status in words, and a legend.

The app's name, top left, leads to the **Overview**, a summary of the whole app (F-DSH-1, with net worth, F-WLT-7) that belongs to no space. Next to it, three spaces are switched: **Spending** (the grid, budget, reports; its switch opens the grid, F-ENT-1, which leads to the fixed expenses, F-FIX-1), **Wealth** (*Monthly tracking*: the matrix and its entries, F-WLT-1 to 5; *Analysis*: the charts, F-WLT-6), each with its own tabs, and **Goals** (the pyramid and each goal's page, F-GOAL-7), with none. The account menu holds the household pages (categories, members, activity log), which belong to neither space, as the guide.

Wealth category colours (F-WLT-1) are a categorical set of semantic tokens, `wealth-*`, one per default top-level category, for both themes: earthy hues in the blog palette's spirit, all at one chroma level in OKLCH and alternating light and dark along the matrix order so neighbours stay apart: a forest green (savings accounts), a sage (current accounts), a denim blue (stocks), a heather (crypto), a petrol blue (bonds), a dusty rose (private equity), an ochre (gold), a rust (real estate), a periwinkle (equipment), a sea green (exotic) and a brick for debts. The dark theme has its own steps, within its band of lightness, checked against the dark surface (dataviz validator: lightness band, chroma floor, colour-vision separation of neighbours, normal-vision floor). Each category's colour marks its row (a swatch) and its lines (a side bar). Ten hues cannot all stay apart for every colour-vision deficiency, so colour is never the only cue: every category keeps its label in the matrix and the charts, a legend in the same order as the stack, and its table. A category added later takes a hue from the same set, chosen by the owner. The tokens sit in a `@theme static` block: the page reads them through `var()` only, and Tailwind would otherwise drop them from the build.

Spending category colours (F-DSH-5, the reports' monthly chart stacked by category) are semantic tokens too, `spend-1` to `spend-6` then `spend-other`, for both themes: the period's six largest expense categories in that order, the rest in grey (`neutral-400`). The hues come from the wealth set (a denim blue, a heather, a petrol blue, a dusty rose, a periwinkle, a sea green), its greens, ochre and rusts left out since they mean a budget or flow status; the dark theme has its own steps. They pass the dataviz validator in both themes (colour-vision separation of neighbours, normal-vision floor); the lighter hues are under 3:1 on white, so every series has its legend entry and its table column.

Goal colours (F-GOAL) are semantic tokens too, `goal-*`, for both themes: the pyramid's tiers are steps of one hue, darkest at the base: `goal-tier-1` for the long term (`primary-700`, `primary-600` in dark), `goal-tier-2` for the medium term (`primary-500`, `primary-400`) and `goal-tier-3` for the short term (`primary-300`, `primary-200`), each with a text colour that keeps its label readable, on a **foundation** in ochre, `goal-foundation` (`secondary-600`, `secondary-500` in dark), the precaution's colour; a goal's status reuses the savings objective's colours (F-BUD-9), and **to fill first** is ochre (`secondary-500`, `secondary-400` in dark). The pyramid is drawn as a stone monument: each tier a few courses of staggered blocks on two faces (the left lit, the right in shade), filling from the bottom; the foundation a Roman column under it (abacus, capital with volutes and acanthus, fluted shaft, base and plinth), filling from its foot. The stone is `goal-stone` (`neutral-100`, `neutral-700` in dark), its lit tops `goal-stone-top` (`neutral-50`, `neutral-600`) and its carved edges `goal-stone-edge` (`neutral-300`, `neutral-500`); light and shade are `neutral-50` and `neutral-900` at low opacity. The **capstone** is a gilded pyramidion on the top course, `goal-gold` (`secondary-400`, `secondary-300` in dark) lit with `goal-gold-shine` (`secondary-200`, `secondary-100` in dark), filling from its base; while locked it stays bare stone with a padlock. The foundation, every tier and the capstone keep their name and percentage on the pyramid and a legend; every status its icon and word, **locked** a padlock in the muted text colour.

## 8. Domain invariants (to be enforced by tests)

Numbers are kept stable: an invariant retired with v1.0 keeps its number.

1. *(retired in v1.0: no accounts)*
2. The parts of a split line sum exactly to the line, each positive; summed over categories, a split line counts its amount exactly once.
3. *(retired in v1.0: no transfers)*
4. *(retired in v1.0: no import)*
5. A wealth line's value in a month is the last value entered in that month or before (carried forward), and nothing before its first value or after its closing.
6. A month's net worth equals the sum of its asset lines minus the sum of its debt lines; each category's subtotal is the sum of its lines, and the scopes add up as in invariant 11 (*household* = *mine* + *joint* + the lines other members share).
7. Forecasts and back-tests (phase 5) never read data after their origin date.
8. A category has at most one target (or objective) in force in any month: the one set from the latest month not after it.
9. A year's target to date equals the sum of the monthly targets in force from January to the month shown, and its full-year target the sum over the twelve months.
10. The matrix, the month so far, the year and the reports never disagree: a category's spending in a month is the same everywhere, and a year's or a period's is the sum of its months'.
11. The *mine* and *joint* scopes of the wealth and the goals never share a line, and the *household* scope is exactly *mine*, plus *joint*, plus the lines other members share.
12. *(retired in v1.0: no transfers)*
13. Money flows balance: what comes in (income, taken from savings, deficit) equals what goes out (spending, saved, unallocated).
14. Savings lines are never spending: a month's rest equals the sum of its lines, income, expense and savings alike (income positive, the others negative); its income is the sum of its income lines (and income parts) and its spending the sum of its expense lines (and expense parts) only.
15. *(retired in v1.0: no budget month; every line counts in the month of its date)*
16. A line fulfils at most one fixed-expense occurrence and an occurrence at most one line; the projected rest equals the rest minus the amounts of the occurrences of the month neither confirmed nor skipped.
17. *(retired in v1.0: no import)*
18. A report never disagrees with the home page: its income, spending and savings over a period equal the sums of the KPIs of its months (F-DSH-4), and the category lines of each section add up to the section's total.
19. A line's shares of the rises across open goals never exceed 100 %. In every month, on every line, the goals' envelopes are never negative and together never exceed the line's value (nor zero when it has none); no goal holds more than its target; and a fall that leaves the line worth at least what its goals held changes none of them.
20. The effort plan never hands out more than the capacity and no goal more than it needs (its gap for the precaution, its required effort otherwise); while a precaution goal falls short, the precaution receives the least of its gap and its share of the capacity before any other goal.
21. The quick line loses no word: every word typed ends up in exactly one of the date, the amount, the category word or the label.
22. A pleasure goal never gains from a line's rise in a month it is locked, and the effort plan gives it nothing then; when unlocked, the plan gives the pleasure goals only what is left once every other goal has what it needs and the precaution its gap, never more than each still lacks.

## 9. Open questions

- **Q1** — ✅ Name: **Kwak Finance**; Python packages `kwak_core`, `kwak_api`, `kwak_analytics`.
- **Q2** — ✅ Moot since v1.0: bank import was removed (it was Société Générale and Helios CSV profiles); the investment accounts are wealth lines (phase 3).
- **Q3** — ✅ Moot since v0.15: wealth values are entered in EUR (no market prices, so no foreign quotes).
- **Q4** — ✅ Neither: wealth is a monthly matrix of categories and lines (F-WLT), each line valued once a month, as in the maintainer's spreadsheet. Life insurance is one line, filed under the category the maintainer chooses.
- **Q5** — ✅ Runs on the development machine (RTX 5070 Laptop, 8 GB VRAM, 30 GB RAM): Ollama limited to ~7–8B models (quantised).
- **Q6** — Remote access: LAN only, or VPN later (not in MVP)?
- **Q7** — Backup destination: local disk only, or an extra copy (external drive, NAS)? Local daily backups exist (docs/OPERATIONS.md); an off-machine copy is still manual.
- **Q8** — ✅ Moot since v1.0: the spending starts afresh, with no history imported.
