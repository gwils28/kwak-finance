/**
 * "Using Kwak Finance": one section per feature, and the overview's "Getting started" checklist.
 * Keep it true to the app: a PR that changes what users see updates it, in both languages.
 */

/** The pages a guide section can open. */
export type GuidePage =
  | "/"
  | "/spending"
  | "/spending/fixed"
  | "/spending/categories"
  | "/budget"
  | "/wealth"
  | "/goals"
  | "/reports"
  | "/forecast"
  | "/members"
  | "/activity";
export type GuideSection = {
  id: string;
  title: string;
  paragraphs: string[];
  link?: { to: GuidePage; label: string };
};

export const guideEn = {
  title: "Using Kwak Finance",
  intro:
    "Kwak Finance keeps your household's spending, budget, wealth and goals in one place, on your own computer. This guide walks through each page. The app's name, at the top left, leads to the overview, the summary of the whole app. Next to it, “Spending”, “Wealth” and “Goals” switch between three spaces: the everyday pages (lines, budget, reports, forecast), the wealth (monthly tracking, analysis, projection, retirement) and your financial goals (pyramid, analysis), each with its tabs. Categories, members, the activity log, the demo, language and theme are in the menu under your name, next to this guide. To install, start or update the app, see “How to run the app” at the bottom of every page.",
  contents: "Contents",
  sections: [
    {
      id: "start",
      title: "Getting started",
      paragraphs: [
        "Four steps take you from an empty app to a working budget, and the “Getting started” list on the overview ticks them off as you go: enter this month's income as lines, enter your first expenses, add your fixed expenses and set your monthly targets; then set your emergency fund, and invite the rest of the household if you share your finances.",
        "After that, a session once a week or once a month is enough: open Spending, confirm the fixed expenses waiting at the top of the month, type what you spent since last time (the header says where you stopped), and look at the month's figures.",
      ],
      link: { to: "/", label: "Open the overview" },
    },
    {
      id: "lines",
      title: "Entering lines",
      paragraphs: [
        "Spending is a list of lines you enter by hand, to the cent: a date, a label, an amount and a category, whichever card or account paid. “Spending” opens the grid of a month, the current one; ‹ and › (or Alt+Page Up and Alt+Page Down) move to the previous and next months. Every cell can be changed in place: Enter saves the row, Escape puts it back as it was. The empty row at the bottom is always ready: Tab moves from cell to cell, Enter saves it and opens a new one on the same date. A new row takes the date of the last line you entered, otherwise today (a past month's last day).",
        "Type an expense as a positive amount. In a savings category (money put aside, see Categories), a positive amount is saved and a minus sign takes money back from savings. Income is entered as lines too, in an income category (salaries, benefits, refunds, other income), as a positive amount: a refund is an income line. A line is income or spending, never both, even when split.",
        "The quick line, above the grid, takes a whole line in any order: “bakery 12,50 yesterday”, “45 train 13/10”, “groceries 87.40 #home”. A date is a day word (today, yesterday, the day before yesterday), a weekday or a dd/mm date; the amount is the last number; “#word” picks the category whose name starts with that word (“#sal 2500 pay” is an income, kept positive); the rest is the label. It shows how it understood the line as you type. Enter saves it when it is complete; otherwise it goes into the empty row, the missing cell ready.",
        "Labels you used before are suggested as you type, the most used first, and a known label brings the category of its last line, never the amount. Change the category if needed: your latest choice is the one remembered.",
        "To spread a receipt over several categories, choose “Split…” as its category: enter each part but the last, which takes the rest, so the parts always add up. Each part counts in its own category everywhere.",
        "The header holds the month's income, spent, saved and the rest (income minus spent minus saved). The income is the sum of the month's income lines: a month without any has none. The line entered last is marked with a dot, and the header says its date and when it was entered, with a link to its month. A deleted line comes back with “Undo” in the message that confirms the deletion.",
      ],
      link: { to: "/spending", label: "Open the lines" },
    },
    {
      id: "fixed",
      title: "Fixed expenses",
      paragraphs: [
        "“Fixed expenses”, at the top of the grid, lists what comes back: rent, the childminder, subscriptions, insurance, or a monthly payment into savings. Each one has a label, a category, an amount, a frequency (every month, quarter or year), a day of the month (the last day standing in for a missing one), a first month and optionally a last one; pause it when it stops for a while.",
        "Nothing is entered by itself: each one due in a month waits at the top of that month's grid, greyed, on its date. Change what differs, then Enter (or “Confirm”) creates the line; “Skip this month” leaves it out, and “Undo” brings it back. A line you type yourself with the same label and category counts as confirming it.",
      ],
      link: { to: "/spending/fixed", label: "Open the fixed expenses" },
    },
    {
      id: "categories",
      title: "Categories",
      paragraphs: [
        "Spending categories have one level and are in the menu under your name: expense categories (housing, groceries, transport…), savings categories, for money put aside, which is never counted as spending and lowers the month's rest, and income categories (salaries, benefits, refunds, other income), whose lines make up the month's income. An income category has no target and no fixed expense. Rename them in place, add new ones, or delete one: when it holds lines, fixed expenses or targets, choose another category of the same kind to move them to.",
        "Tick “One-off” for an expense paid once in the month (rent, a subscription): the month so far never warns about it. Housing and Subscriptions are one-off by default. The household owner can restore the default categories that are missing.",
      ],
      link: { to: "/spending/categories", label: "Open the categories" },
    },
    {
      id: "budget",
      title: "Budget",
      paragraphs: [
        "The budget compares each category's spending with a monthly target, with nothing to sort first. Click a category's target in the table to set it: an amount per month, from a month on (this month by default), kept every month after until you change it. A change from a past month says which months take it; earlier months keep their target. “No target from this month” leaves the category without one from that month, and the list of changes below lets you remove one, the month then following the earlier target again.",
        "A savings category takes a monthly objective the same way. An objective is a minimum: saving more is good.",
        "The table shows one row per expense category and one column per month (the last 12 by default; 3, 6 or 24 in “Period”), with each category's current target first. It scrolls within its frame, the months staying at the top and the categories and targets on the left. Each cell gives the month's spending and its gap to that month's target in euros and in per cent: green when more than 5 % under the target, grey within 5 %, burnt orange more than 5 % over it, no colour without a target. Click a cell to open that month's lines of the category.",
        "Above the spending, the income categories show what each received every month, with no target and no colour. Below the spending, the savings categories have their own section, where the colours turn round: green when you saved more than 5 % above the objective, burnt orange more than 5 % below it. The last rows give each month's income, spent, saved and rest.",
      ],
      link: { to: "/budget", label: "Open the budget" },
    },
    {
      id: "year",
      title: "The year",
      paragraphs: [
        "“The year”, on the budget page, adds up a calendar year (the current one by default; a past year is shown whole). For each category: its target to date (the targets from January to this month, this month's counted in full, so a running month leans under), its spending to date, the gap in euros and in per cent with the same colours, how many completed months were over, on and under their target, and its target for the whole year. The savings objectives follow, then what each income category received to date. Above the table, tiles give the year's income, spending, savings, rest and savings rate.",
      ],
      link: { to: "/budget", label: "Open the budget" },
    },
    {
      id: "overview",
      title: "Overview",
      paragraphs: [
        "The overview sums up a month (the current one by default). Once your wealth has a line, it opens with your net worth at the end of the month and how it moved since the month before; once you have a goal, the pyramid of your goals follows. The view chosen at the top changes only these two: spending is the household's.",
        "Then the month's figures: income (the sum of the month's income lines), spent (with its change against last month and the 12-month average), saved, the rest and the savings rate (the share of income not spent).",
        "“Targets this month: spending budget” lists each expense category with a target that month, the most used first: what it spent, what is left (or the overrun) and a bar. It says “Watch” from the warning threshold (80 % of the target by default; the household owner can change it there) and “Over” beyond the target. For the current month, a line on the bar marks how much of the month has gone by. One-off categories, paid once in the month, have no line and no “Watch”. Click a category to open its lines.",
        "Below it, “Targets this month: savings” lists each savings category with an objective that month, the furthest from it first: what it received, what is left to put aside (or how far beyond it you went) and a bar, with “Reached” once the objective is met and “In progress” until then. It has no pace line and no “Watch”: saving often happens in one go, early in the month.",
        "“Fixed expenses to confirm” lists those of the month still waiting, each with “Confirm”, and the rest at the end of the month once they are paid. Last come the month's top categories, its spending added up day by day (up to today for the current month) against its targets spread evenly over the month, and the last lines entered.",
      ],
      link: { to: "/", label: "Open the overview" },
    },
    {
      id: "wealth",
      title: "Wealth",
      paragraphs: [
        "The wealth space follows what you own and owe at the end of each month, like a spreadsheet: categories (savings accounts, current accounts, stocks, crypto, bonds, private equity, gold, real estate, equipment, exotic, debts), each with its colour, and in each the lines you add: one per holding, such as “PEA Fortuneo” or “Crédit immobilier”. A line is yours; choose whether the household sees it, only you, or whether it is the household's joint holding. A savings account line can say which regulated account it is (Livret A, LDDS, LEP, PEL, Livret jeune), so the goals analysis can watch its deposit ceiling; a joint line cannot, since these accounts are a person's own.",
        "Every line is entered by hand, your current accounts and savings accounts too: add one line per account (“Livret A”, “Compte joint”…) in its category, then enter the values once a month with “Update this month”, which shows each line's last value: change what moved and save. You can also click any value in the table to change that month. A month without a value carries the previous one, shown in grey italics. A debt is entered as what is still owed and counts against your net worth.",
        "On the “Monthly tracking” tab, the table scrolls within its frame, the months staying at the top and the line names on the left. It shows each category's total, gross assets, debts, net worth and its change month by month, and each category's share of what you own. Click a line's name to rename it, move it, or close it from a month once sold or repaid: it keeps its history. “Manage categories” renames the categories, changes their colour or their order, and adds new ones (an asset or a debt); a category can be deleted once it holds no line. The view covers the household, the joint lines (offered once the household has several members) or only yours. It opens on the last 12 months, from the wealth start at the earliest (on the members page); choose any other months with “From” and “To”, and “Last 12 months” brings it back.",
        "The “Analysis” tab charts the months and the scope you choose there, below the same tiles: net worth over time by category; the allocation of a month you choose (the last one by default) as rings (categories inside, their lines outside) and as a mosaic, each category a tile as large as its value; and what moved net worth from the first month to the last, category by category. Point at a ring or a tile to read it, or open “Show the data” under each chart. The net worth tile also gives the change over the months shown, the debts tile the share of your gross assets they weigh.",
        "The “Projection” tab is a simulator of where your net worth could be in 1 to 40 years (20 by default), from this month's wealth in the scope you choose. On the left, your monthly contributions: one row per category you invest in, with its amount a month, its yearly return (the category's own, used for what it already holds too) and whether it follows prices (ticked, it grows with inflation; unticked, a standing order that stays the same). Their total is compared with your measured capacity, warned of above it. Without any contribution, the projection saves your goals' capacity, split like your wealth. Below, the horizon, the scope and today's or current euros. Everything is recomputed as you type; “Save the contributions” keeps them for next time (and saves a return you changed for the retirement and goals pages too), “Cancel” goes back to the saved ones. On the right, the answer: the median net worth at the horizon, the range eight outcomes in ten fall in, and an income at a withdrawal rate (4 % by default, from 2 to 5 %) on the liquid holdings, in half of the outcomes and in nine in ten, a rule of thumb with its caveats (the Retirement tab works it out). Since returns are uncertain, 5,000 possible futures are drawn. The chart has two views: “Where the money comes from” stacks today's net worth, the contributions added up, the debts repaid and the gains (after inflation in today's euros, below zero as losses); “The range” draws the median with the bands holding half and eight in ten of the outcomes. Hover a month to read every value then; each chart has its table under “Show the data”. Below: reaching an amount (enter it and a month to read the chance and by when half and nine in ten of the outcomes reach it, its line on the chart); up to two “what-ifs” changing the monthly total, the inflation or a category's return or volatility for this visit only, dashed on the chart and compared at the horizon; each category's own median today and at the horizon, debts below zero. Folded at the end, the advanced assumptions (the inflation, each category's return and volatility, each debt's payment, rate and borrower insurance, shared by the household) and the method and limits.",
        "The “Retirement” tab estimates the standard of living your household could keep once retired. It is not about retiring early: you choose when. Under the charts, each member enters their own birth month, the month they stop working with the net earnings that stop then, and their net pension and the month it starts (from info-retraite.fr, as it would reach the account, after withholding, in today's euros); the others see it. The household sets the retirement spending (80 % of today's spending outside the loans by default, or an amount), how pensions follow inflation (0.3 % a year less by default, as supplementary pensions often have) and the horizon (the youngest at 95). The page opens on tiles: the pensions plus the “sustainable withdrawal”, the most the liquid wealth can pay each month to the horizon in 9 outcomes in 10, as one bar against the spending, the share covered, and the chance that the wealth lasts with the age at which it might run out; then a timeline of each member's working years and pension, today and the horizon marked; the net worth to the horizon with the liquid part and the retirement marked; the monthly income once retired; one card per member with their inputs, and the limits, folded (no tax on withdrawals, no long-term care, the home never sold…). It is an estimate, not advice.",
      ],
      link: { to: "/wealth", label: "Open your wealth" },
    },
    {
      id: "goals",
      title: "Goals",
      paragraphs: [
        "The goals space follows amounts you want to gather by a date, in a pyramid: its foundation is your emergency fund, filled first; above it, three tiers given by how far the deadline is: first the long term (beyond five years: a home deposit, the children's studies); then the medium term (over a year, up to five: a trip, a car, a large purchase); at the top the short term (up to a year: holidays, a repair). You never pick the tier: a goal changes tier by itself when you move its deadline, and moves up a tier as the deadline nears, until it reaches the top. A goal can be “Permanent”: it stays in view once reached and needs no deadline (a fund for repairs, say); any other goal is archived by itself once it reaches its target. A goal can be your emergency fund (“This is the emergency fund” in the form): kept apart for the unexpected, filled first, always permanent, the pyramid's foundation. Each member can have one emergency fund, and the household one joint. The pyramid is drawn in stone: each tier's blocks take its colour from the bottom as its goals fill, and the emergency fund is the column the pyramid stands on, which takes its colour from its foot.",
        "A goal is funded by your wealth lines, each holding an envelope for it; the rest of the line stays free for anything else. For each line, set an opening amount, taken from what is free (0 to start from nothing), and the share of its rises that goes to the goal (100 % when the line only serves it). The goal then moves when you update your wealth each month, with nothing more to enter: a rise (a deposit, interest) fills its envelope up to its target; a withdrawal or a loss comes out of the free part first, and the goal only loses once the line is worth less than its goals hold, the farthest deadlines first and the emergency fund last. The form shows what is free on each line, the Wealth page what goals set aside on it. If a rise counted for a goal was not for it (a deposit for something else), “Adjust” in the goal's Envelopes sets what its envelope holds from a month you choose; it then rises and falls as before, and the adjustment can be removed. A line's shares of the rises never exceed 100 %, and a private line only funds a goal only you see. For the emergency fund, “Propose from my fixed expenses” multiplies the monthly total of your fixed expenses (rent, subscriptions, insurance…, a quarterly or yearly one counting a third or a twelfth of it) by the number of months you choose (6 by default); the amount stays fixed once saved.",
        "Each goal has a gauge with a marker where it should stand by now, on a straight line from its start to its target at its deadline, and a status: ahead, on track or behind (with a 5 % margin), reached, or “Fill first” for an emergency fund short of its target. It shows the effort it requires each month, your actual effort (the average gain of the last 6 months) and the date it should be reached at that pace, early or late. Its page draws the trajectory and lists each month.",
        "At the very top, the golden capstone holds your pleasure goals (“This is a pleasure goal” in the form): what you want just for the pleasure of it, not because you need it (boxing gloves, a record player, a fine bottle of rum). They have no deadline and are archived by themselves once reached. They are only funded once the rest is in order: the capstone stays locked, in stone with a padlock, until your emergency fund is full and at least 3 in 4 of your goals with a deadline are ahead (a reached goal counts as ahead), judged on last month. While it is locked, the rises of their lines stay free and the month's effort gives them nothing; what they already hold stays. Under the pyramid, a sentence says what is still missing. Once unlocked, they take what the other goals leave of the month's effort, in proportion to what each still lacks, and when a line falls they are the first to lose.",
        "“This month's effort” shares out what you can save (the household's average income minus spending over the last 6 complete months, or an amount the household owner sets in the effort settings): while the emergency fund falls short, it gets a share first (70 % by default, from 50 % to 100 %), the other goals the rest in proportion to the effort they require, and what they leave goes back to the emergency fund. It is a recommendation: nothing is moved. Each card has its actions: “Edit”, “Archive” once you are done with it (never for a permanent goal), “Cancel the goal” when it no longer matters. An archived or cancelled goal leaves the pyramid, frees its lines and is hidden from the page: “Show archived and cancelled goals” lists them, and a goal's page reopens it (a reached goal asks for a higher target, or to become permanent).",
        "The “Analysis” tab, next to “Pyramid”, looks at your goals together. It judges them at the last month whose funding lines all have a value entered, so a month you have not entered yet never looks like a month without savings. It opens on the points to look at: facts worked out by fixed rules (no emergency fund, or one under 3 or 6 months of fixed expenses, or kept on volatile lines or a current account; a goal no line funds; goals asking more each month than you can save, with the goal you could postpone, by how many months, or the target you could lower; a goal behind for three months, with what keeps its date; a goal with no gain in six months; a goal near its deadline still on volatile lines, with what it could lose one time in ten; a long goal on lines that earn no more than inflation, or a far target in today's euros; money left idle on your current accounts; a regulated savings account near its ceiling that a goal still counts on; how little would unlock the golden capstone; capacity left over; values to enter). Three are shown, the most serious first, at most one per goal; “Remind me next month” or “Hide until it worsens” hides one for you only, and “Show hidden points again” brings them all back. They are observations, never advice; the Pyramid tab says how many there are, with a link to them. Below: the effort each goal needs every month, stacked against what the household can save, with the months that go over shaded (the chart compares the household's goals in every view, since the capacity is the household's; choose how many months to show); a timeline of each goal from its start to its deadline, with where it lands at its pace (●) and at the plan's effort (◇); each goal's status month by month; and each goal placed by the months left to its deadline and the volatility of its lines, over zones named on the chart, two striped (near and volatile, far and eroding) and a plain one (between 2 and 5 years, where a goal should leave volatile lines step by step), a dotted ring marking a goal partly in a category that loses value (the areas are guides by horizon: only a ring says a goal needs a look, as the legend under the chart explains, and the table gives the share each goal between 2 and 5 years may keep on volatile lines); and where the goals' money sits, from each category to its lines, then to the goals' envelopes and each line's free part (real estate and equipment are left out unless you tick them; what a goal holds on lines not shown is listed below; “Free” may hold envelopes of goals you do not see). A point that names a goal without being about it, such as money to set aside from your current accounts, can sit next to that goal's own point. A table gives each goal's chance of reaching its target by its deadline, at the plan's allocation and at the required effort, from the Projection assumptions (a goal on lines that never move is “reached” or “short by” an amount; the precaution shows the months to fill it); chances are per goal, not of reaching them all. Two more points watch the debts entered with their rate and payment: a loan costing more than the goals' lines are assumed to earn, and loan payments above 35 % of the income, the lenders' ceiling. Every chart has its table.",
      ],
      link: { to: "/goals", label: "Open your goals" },
    },
    {
      id: "reports",
      title: "Reports",
      paragraphs: [
        "Reports look back over any period of whole months: this month, last month, this quarter, this year, last year, the last 12 months, or a custom period with a first and a last month (10 years at most). A period running past this month stops there (“this year” means this year so far) and is compared with the same months of the period before; months before your first line are left out, and when the period before reaches before them, nothing is compared.",
        "Each report gives the totals (income, spending, savings and the rest, against the period before of the same length, and the savings rate), a table by category in three sections (income, spending and savings) with the monthly average, each category's share of its section and the change, a chart of spending by category, for a period of several months a month-by-month chart of spending by category (the six largest of the period in colour, the rest in grey) against income, and the money flows: the income by category on the left, then spending by category, savings and the unallocated rest on the right, a shortfall coming in as a deficit and money taken back from savings as such. Spending over its targets for the period is burnt orange, within them (or without a target) ochre; every chart has its table.",
      ],
      link: { to: "/reports", label: "Open the reports" },
    },
    {
      id: "forecast",
      title: "Forecast",
      paragraphs: [
        "The “Forecast” tab, next to the reports, estimates the next twelve months of spending, the current month first, once your lines cover 12 complete months (until then, try it in the demo). The fixed expenses due are known in advance; the rest of each category is forecast from its own history by the method that erred least when it was asked to forecast the months already entered (an average, the same month last year, exponential smoothing, trees learnt on all the categories, or, if the app was built with them, two models pretrained on many public series, Chronos-2 and TimesFM 2.5), a method beating the 6-month average only when it does so by 10 % or more, and never when it forecast clearly less spending (or more income or savings) than was entered. If the forecast's rest was too high in the past months tested, the summary says so. Nothing entered this month is used: what you have entered so far is shown next to its forecast.",
        "The page opens on tiles: the twelve months' rest, this month's spending so far as a bar against its forecast with a mark at the day of the month, how many targets are at risk this month and this year, and the twelve months' income, spending and savings. Then one chart per question: month by month, the last 12 months entered and the 12 to come, each with a band that past errors held about 8 times in 10, the rest of each month in bars below (the table holds 24 months); against your targets, each category in percent of its target, a point for the forecast, a bar for its band and a line at 100 %, with its chance of going over, then the year's spending to date plus the forecast to December against the full-year target; this month's income and each savings objective's chance of falling short. Folded under “How reliable it is”: what each forecast rests on (its method, how much less it erred than the 6-month average, its bias in the past months tested, how often the band held); drawn as how much less it errs and how optimistic it was; the back-test, the totals forecast one month ahead against what was entered, with their bias; and the limits. It is an estimate from your past months, not advice: a new expense or a change of job is not in the history.",
      ],
      link: { to: "/forecast", label: "Open the forecast" },
    },
    {
      id: "members",
      title: "Members and security",
      paragraphs: [
        "The household owner invites members with a link that works once and expires after 7 days; Kwak Finance sends no email, so send it yourself.",
        "Everyone signs in with a password and a code from an authenticator app. Keep the recovery codes shown at set-up: each lets you sign in once if you lose your phone.",
        "The activity log, in the menu under your name, keeps the sensitive actions: sign-ins (with the address they came from, and failed attempts), invitations, household settings, restored categories and deletions. The owner sees the whole household's, a member only their own; what happens on a private wealth line or goal is only shown to its owner. Nothing in it can be changed or deleted.",
        "On the same page, the owner can set the wealth start: the wealth page opens on the last 12 months from that month at the earliest, for a history that goes back further than your spending's. Without one, it opens on the last 12 months. The budget, the overview and the reports start from your first line.",
      ],
      link: { to: "/members", label: "Open the members" },
    },
    {
      id: "demo",
      title: "The demo",
      paragraphs: [
        "Many pages need months of history before they say much: the budget matrix, the year, the reports, the wealth charts, the goals' analysis, the projection, the retirement and the forecast. To see them at work before your own data has that history, choose “Open the demo” in the menu under your name: it opens a fictitious household, a couple with a child and three years of lines, fixed expenses, targets, wealth, goals and retirement plans, dated up to today.",
        "While you are in it, a banner says so at the top of every page, and every page shows the demo instead of your household, which is untouched. You can change anything to try it; the demo is shared by every member and keeps the changes until someone resets it, so never enter real figures there. Members, invitations, your password, second factor and recovery codes are left out of the demo.",
        "“Back to my household”, on the banner or in the menu, takes you back; signing out does too. “Reset the demo” deletes it, with everyone's changes, and generates it again from today, after a confirmation.",
      ],
    },
  ] satisfies GuideSection[],
  checklist: {
    title: "Getting started",
    progress: (done: number, total: number) => `${done} of ${total} done`,
    hide: "Hide",
    readGuide: "Read the guide",
    steps: {
      income: "Enter this month's income as lines",
      line: "Enter your first lines",
      fixed: "Add your fixed expenses",
      plan: "Set your monthly targets",
      goal: "Set your emergency fund",
      invite: "Invite your household (optional)",
    },
    done: "Done",
  },
};

export const guideFr: typeof guideEn = {
  title: "Utiliser Kwak Finance",
  intro:
    "Kwak Finance réunit les dépenses, le budget, le patrimoine et les objectifs de votre foyer, sur votre propre ordinateur. Ce guide parcourt chaque page. Le nom de l'application, en haut à gauche, mène à la vue d'ensemble, le résumé de toute l'application. À côté, « Dépenses », « Patrimoine » et « Objectifs » passent d'un espace à l'autre : les pages du quotidien (lignes, budget, rapports, prévision), le patrimoine (suivi mensuel, analyse, projection, retraite) et vos objectifs financiers (pyramide, analyse), chacun avec ses onglets. Les catégories, les membres, le journal d'activité, la démo, la langue et le thème sont dans le menu à votre nom, à côté de ce guide. Pour installer, lancer ou mettre à jour l'application, voyez « Lancer et arrêter l'application » en bas de chaque page.",
  contents: "Sommaire",
  sections: [
    {
      id: "start",
      title: "Bien démarrer",
      paragraphs: [
        "Quatre étapes mènent d'une application vide à un budget qui fonctionne, et la liste « Bien démarrer » de la vue d'ensemble les coche au fur et à mesure : saisir les revenus du mois en lignes, saisir vos premières dépenses, ajouter vos dépenses fixes et fixer vos objectifs mensuels ; ensuite, constituer votre épargne de précaution, et inviter le reste du foyer si vous partagez vos finances.",
        "Ensuite, une séance par semaine ou par mois suffit : ouvrez Dépenses, confirmez les dépenses fixes qui attendent en haut du mois, tapez ce que vous avez dépensé depuis la dernière fois (l'en-tête dit où vous vous êtes arrêté) et regardez les chiffres du mois.",
      ],
      link: { to: "/", label: "Ouvrir la vue d'ensemble" },
    },
    {
      id: "lines",
      title: "Saisir les lignes",
      paragraphs: [
        "Les dépenses sont une liste de lignes saisies à la main, au centime : une date, un libellé, un montant et une catégorie, quelle que soit la carte ou le compte qui a payé. « Dépenses » ouvre la grille d'un mois, le mois en cours ; ‹ et › (ou Alt+Page préc. et Alt+Page suiv.) passent au mois précédent et au suivant. Chaque cellule se modifie sur place : Entrée enregistre la ligne, Échap la remet comme elle était. La ligne vide en bas est toujours prête : Tab passe d'une cellule à l'autre, Entrée l'enregistre et en ouvre une nouvelle à la même date. Une nouvelle ligne prend la date de la dernière ligne saisie, sinon aujourd'hui (le dernier jour d'un mois passé).",
        "Tapez une dépense en montant positif. Dans une catégorie d'épargne (l'argent mis de côté, voir Catégories), un montant positif est épargné et un signe moins reprend de l'argent à l'épargne. Les revenus se saisissent aussi en lignes, dans une catégorie de revenus (salaires, aides et allocations, remboursements, autres revenus), en montant positif : un remboursement est une ligne de revenus. Une ligne est un revenu ou une dépense, jamais les deux, même ventilée.",
        "La saisie rapide, au-dessus de la grille, prend une ligne entière dans n'importe quel ordre : « boulangerie 12,50 hier », « 45 sncf 13/10 », « carrefour 87,40 #foyer ». Une date est un mot (aujourd'hui, hier, avant-hier), un jour de la semaine ou une date jj/mm ; le montant est le dernier nombre ; « #mot » choisit la catégorie dont le nom commence par ce mot (« #sal 2500 paie » est un revenu, gardé positif) ; le reste est le libellé. Elle montre comment elle a compris la ligne pendant la frappe. Entrée l'enregistre si elle est complète ; sinon elle passe dans la ligne vide, la cellule manquante prête.",
        "Les libellés déjà utilisés sont proposés pendant la frappe, les plus utilisés d'abord, et un libellé connu reprend la catégorie de sa dernière ligne, jamais le montant. Changez la catégorie si besoin : votre dernier choix est celui qui est retenu.",
        "Pour répartir un ticket sur plusieurs catégories, choisissez « Ventiler… » comme catégorie : saisissez chaque part sauf la dernière, qui prend le reste, si bien que les parts tombent toujours juste. Chaque part compte partout dans sa propre catégorie.",
        "L'en-tête donne les revenus, le dépensé, l'épargné et le reste du mois (revenus moins dépensé moins épargné). Les revenus sont la somme des lignes de revenus du mois : un mois qui n'en a pas n'a pas de revenus. La ligne saisie en dernier est marquée d'un point, et l'en-tête donne sa date et quand elle a été saisie, avec un lien vers son mois. Une ligne supprimée revient avec « Annuler » dans le message qui confirme la suppression.",
      ],
      link: { to: "/spending", label: "Ouvrir les lignes" },
    },
    {
      id: "fixed",
      title: "Dépenses fixes",
      paragraphs: [
        "« Dépenses fixes », en haut de la grille, liste ce qui revient : loyer, nounou, abonnements, assurances, ou un versement mensuel sur l'épargne. Chacune a un libellé, une catégorie, un montant, une fréquence (tous les mois, trimestres ou ans), un jour du mois (le dernier jour remplaçant un jour manquant), un premier mois et éventuellement un dernier ; mettez-la en pause quand elle s'arrête un temps.",
        "Rien n'est saisi tout seul : chacune due dans un mois attend en haut de la grille de ce mois, grisée, à sa date. Corrigez ce qui diffère, puis Entrée (ou « Confirmer ») crée la ligne ; « Sauter ce mois-ci » la laisse de côté, et « Annuler » la fait revenir. Une ligne que vous tapez vous-même avec le même libellé et la même catégorie vaut confirmation.",
      ],
      link: { to: "/spending/fixed", label: "Ouvrir les dépenses fixes" },
    },
    {
      id: "categories",
      title: "Catégories",
      paragraphs: [
        "Les catégories de dépenses ont un seul niveau et sont dans le menu à votre nom : les catégories de dépense (logement, courses, transport…), les catégories d'épargne, pour l'argent mis de côté, qui ne compte jamais comme dépense et réduit le reste du mois, et les catégories de revenus (salaires, aides et allocations, remboursements, autres revenus), dont les lignes forment les revenus du mois. Une catégorie de revenus n'a ni cible ni dépense fixe. Renommez-les sur place, ajoutez-en, ou supprimez-en une : si elle contient des lignes, des dépenses fixes ou des cibles, choisissez une autre catégorie du même type où les déplacer.",
        "Cochez « Ponctuelle » pour une dépense payée une fois dans le mois (loyer, abonnement) : le mois en cours n'alerte jamais à son sujet. Logement et Abonnements sont ponctuelles par défaut. Le propriétaire du foyer peut restaurer les catégories par défaut qui manquent.",
      ],
      link: { to: "/spending/categories", label: "Ouvrir les catégories" },
    },
    {
      id: "budget",
      title: "Budget",
      paragraphs: [
        "Le budget compare les dépenses de chaque catégorie à une cible mensuelle, sans rien à trier d'abord. Cliquez sur la cible d'une catégorie dans le tableau pour la fixer : un montant par mois, à partir d'un mois (ce mois-ci par défaut), gardé chaque mois ensuite jusqu'à ce que vous le changiez. Un changement à partir d'un mois passé dit quels mois le prennent ; les mois d'avant gardent leur cible. « Plus de cible à partir de ce mois » laisse la catégorie sans cible à partir de ce mois, et la liste des changements en dessous permet d'en retirer un, le mois suivant alors de nouveau la cible d'avant.",
        "Une catégorie d'épargne prend de la même façon un objectif mensuel. Un objectif est un minimum : épargner plus est une bonne chose.",
        "Le tableau montre une ligne par catégorie de dépense et une colonne par mois (les 12 derniers par défaut ; 3, 6 ou 24 dans « Période »), avec d'abord la cible actuelle de chaque catégorie. Il défile dans son cadre, les mois restant en haut et les catégories et cibles à gauche. Chaque case donne les dépenses du mois et leur écart à la cible de ce mois, en euros et en pourcentage : vert à plus de 5 % sous la cible, gris à 5 % près, orange brûlé à plus de 5 % au-dessus, sans couleur sans cible. Cliquez sur une case pour ouvrir les lignes de la catégorie ce mois-là.",
        "Au-dessus des dépenses, les catégories de revenus montrent ce que chacune a reçu chaque mois, sans cible ni couleur. Sous les dépenses, les catégories d'épargne ont leur propre section, où les couleurs s'inversent : vert quand vous avez épargné plus de 5 % au-dessus de l'objectif, orange brûlé à plus de 5 % en dessous. Les dernières lignes donnent les revenus, le dépensé, l'épargné et le reste de chaque mois.",
      ],
      link: { to: "/budget", label: "Ouvrir le budget" },
    },
    {
      id: "year",
      title: "L'année",
      paragraphs: [
        "« L'année », sur la page du budget, fait le compte d'une année civile (l'année en cours par défaut ; une année passée est montrée en entier). Pour chaque catégorie : sa cible à date (les cibles de janvier à ce mois, celle du mois en cours comptée en entier, si bien qu'un mois en cours penche vers le dessous), ses dépenses à date, l'écart en euros et en pourcentage avec les mêmes couleurs, combien de mois terminés ont été au-dessus, dans et sous leur cible, et sa cible pour l'année entière. Les objectifs d'épargne suivent, puis ce que chaque catégorie de revenus a reçu à date. Au-dessus du tableau, des tuiles donnent les revenus, les dépenses, l'épargne, le reste et le taux d'épargne de l'année.",
      ],
      link: { to: "/budget", label: "Ouvrir le budget" },
    },
    {
      id: "overview",
      title: "Vue d'ensemble",
      paragraphs: [
        "La vue d'ensemble résume un mois (le mois en cours par défaut). Dès que votre patrimoine a une ligne, elle s'ouvre sur votre patrimoine net en fin de mois et son évolution depuis le mois précédent ; dès que vous avez un objectif, la pyramide de vos objectifs suit. La vue choisie en haut ne change que ces deux-là : les dépenses sont celles du foyer.",
        "Viennent ensuite les chiffres du mois : les revenus (la somme des lignes de revenus du mois), le dépensé (avec son évolution face au mois dernier et à la moyenne sur 12 mois), l'épargné, le reste et le taux d'épargne (la part des revenus non dépensée).",
        "« Cibles du mois : budget dépenses » liste chaque catégorie de dépense qui a une cible ce mois-là, la plus utilisée d'abord : ce qu'elle a dépensé, ce qui reste (ou le dépassement) et une barre. Elle indique « Attention » à partir du seuil d'alerte (80 % de la cible par défaut ; le propriétaire du foyer peut le changer là) et « Dépassé » au-delà de la cible. Pour le mois en cours, un trait sur la barre marque la part du mois écoulée. Les catégories ponctuelles, payées une fois dans le mois, n'ont ni trait ni « Attention ». Cliquez sur une catégorie pour ouvrir ses lignes.",
        "En dessous, « Cibles du mois : épargne » liste chaque catégorie d'épargne qui a un objectif ce mois-là, la plus loin de son objectif d'abord : ce qu'elle a reçu, ce qui reste à mettre de côté (ou de combien vous l'avez dépassé) et une barre, avec « Atteint » une fois l'objectif rempli et « En cours » jusque-là. Elle n'a ni trait de rythme ni « Attention » : on épargne souvent en une fois, en début de mois.",
        "« Dépenses fixes à confirmer » liste celles du mois qui attendent encore, chacune avec « Confirmer », et le reste en fin de mois une fois qu'elles sont payées. Viennent enfin les principales catégories du mois, ses dépenses cumulées jour après jour (jusqu'à aujourd'hui pour le mois en cours) face à ses cibles réparties sur le mois, et les dernières lignes saisies.",
      ],
      link: { to: "/", label: "Ouvrir la vue d'ensemble" },
    },
    {
      id: "wealth",
      title: "Patrimoine",
      paragraphs: [
        "L'espace Patrimoine suit ce que vous possédez et devez à la fin de chaque mois, comme un tableur : des catégories (livrets, comptes courants, actions, cryptos, obligations, private equity, or, immobilier, matériels, exotiques, dettes), chacune avec sa couleur, et dans chacune les lignes que vous ajoutez : une par avoir, comme « PEA Fortuneo » ou « Crédit immobilier ». Une ligne est à vous ; choisissez si le foyer la voit, vous seul, ou si c'est un avoir commun du foyer. Une ligne de livret peut dire quel livret réglementé elle est (Livret A, LDDS, LEP, PEL, Livret jeune), pour que l'analyse des objectifs surveille son plafond de dépôts ; une ligne commune ne le peut pas, ces livrets étant personnels.",
        "Chaque ligne se saisit à la main, comptes courants et livrets compris : ajoutez une ligne par compte (« Livret A », « Compte joint »…) dans sa catégorie, puis saisissez les valeurs une fois par mois avec « Mettre à jour ce mois-ci », qui affiche la dernière valeur de chaque ligne : changez ce qui a bougé et enregistrez. Vous pouvez aussi cliquer sur une valeur du tableau pour changer ce mois-là. Un mois sans valeur reprend la précédente, affichée en gris italique. Une dette se saisit pour ce qui reste dû et compte en moins dans votre patrimoine net.",
        "Dans l'onglet « Suivi mensuel », le tableau défile dans son cadre, les mois restant en haut et les noms des lignes à gauche. Il montre le total de chaque catégorie, l'actif brut, les dettes, le patrimoine net et sa variation d'un mois à l'autre, et la part de chaque catégorie dans ce que vous possédez. Cliquez sur le nom d'une ligne pour la renommer, la déplacer ou la clôturer à partir d'un mois une fois vendue ou remboursée : elle garde son historique. « Gérer les catégories » renomme les catégories, change leur couleur ou leur ordre et en ajoute de nouvelles (un actif ou une dette) ; une catégorie se supprime une fois vide. La vue couvre le foyer, les lignes communes (proposées dès que le foyer a plusieurs membres) ou seulement les vôtres. Elle s'ouvre sur les 12 derniers mois, au plus tôt à partir du début du patrimoine (page Membres) ; choisissez d'autres mois avec « Du » et « Au », et « 12 derniers mois » la ramène.",
        "L'onglet « Analyse » présente en graphiques les mois et le périmètre que vous y choisissez, sous les mêmes tuiles : le patrimoine dans le temps par catégorie ; la répartition d'un mois au choix (le dernier par défaut) en anneaux (les catégories au centre, leurs lignes autour) et en mosaïque, chaque catégorie en tuile aussi grande que sa valeur ; et ce qui a fait bouger le patrimoine du premier mois au dernier, catégorie par catégorie. Pointez un anneau ou une tuile pour le lire, ou ouvrez « Afficher les données » sous chaque graphique. La tuile du patrimoine net donne aussi la variation sur les mois affichés, celle des dettes leur poids dans votre actif brut.",
        "L'onglet « Projection » est un simulateur de ce que pourrait valoir votre patrimoine net dans 1 à 40 ans (20 par défaut), à partir du patrimoine de ce mois dans le périmètre choisi. À gauche, vos versements mensuels : une ligne par catégorie où vous placez, avec son montant par mois, son rendement annuel (celui de la catégorie, qui sert aussi pour ce qu'elle détient déjà) et s'il suit les prix (coché, il grandit avec l'inflation ; décoché, un virement programmé qui reste le même). Leur total est comparé à votre capacité mesurée, avec un avertissement au-delà. Sans versement, la projection épargne la capacité de vos objectifs, répartie comme votre patrimoine. En dessous, l'horizon, le périmètre et les euros d'aujourd'hui ou courants. Tout se recalcule pendant que vous tapez ; « Enregistrer les versements » les garde pour la prochaine fois (et enregistre aussi un rendement modifié pour les pages Retraite et Objectifs), « Annuler » revient à ceux enregistrés. À droite, la réponse : le patrimoine net médian à l'horizon, la fourchette où tombent huit résultats sur dix, et un revenu à un taux de retrait (4 % par défaut, de 2 à 5 %) sur les avoirs liquides, dans la moitié des cas et dans neuf sur dix, un repère avec ses mises en garde (l'onglet Retraite fait le calcul). Les rendements étant incertains, 5 000 futurs possibles sont tirés. Le graphique a deux vues : « D'où vient l'argent » empile le patrimoine net d'aujourd'hui, les versements cumulés, les dettes remboursées et les plus-values (après inflation en euros d'aujourd'hui, sous zéro en cas de pertes) ; « La fourchette » trace la médiane avec les bandes qui contiennent la moitié et huit sur dix des résultats. Survolez un mois pour lire toutes ses valeurs ; chaque graphique a son tableau sous « Afficher les données ». Plus bas : atteindre un montant (saisissez-le avec un mois pour lire la chance et la date à laquelle la moitié puis neuf résultats sur dix l'atteignent, sa ligne sur le graphique) ; jusqu'à deux « et si » qui changent le total mensuel, l'inflation ou le rendement ou la volatilité d'une catégorie, pour cette visite seulement, en pointillés sur le graphique et comparés à l'horizon ; la médiane propre à chaque catégorie aujourd'hui et à l'horizon, les dettes sous zéro. Repliées à la fin, les hypothèses avancées (l'inflation, le rendement et la volatilité de chaque catégorie, la mensualité, le taux et l'assurance emprunteur de chaque dette, communs au foyer) et la méthode et les limites.",
        "L'onglet « Retraite » estime le niveau de vie que votre foyer pourrait garder une fois retraité. Il ne s'agit pas de partir tôt : vous choisissez quand. Sous les graphiques, chaque membre saisit son mois de naissance, le mois où il arrête de travailler avec le revenu net qui s'arrête alors, et sa pension nette et le mois où elle commence (d'après info-retraite.fr, telle qu'elle arriverait sur le compte, après prélèvement à la source, en euros d'aujourd'hui) ; les autres la voient. Le foyer règle les dépenses de retraite (80 % des dépenses d'aujourd'hui hors prêts par défaut, ou un montant), la façon dont les pensions suivent l'inflation (0,3 % de moins par an par défaut, comme souvent les complémentaires) et l'horizon (le plus jeune à 95 ans). La page s'ouvre sur des tuiles : les pensions plus le « retrait soutenable », le plus que le patrimoine liquide peut verser chaque mois jusqu'à l'horizon dans 9 cas sur 10, en une barre face aux dépenses, la part couverte, et la chance que le patrimoine tienne avec l'âge où il pourrait s'épuiser ; puis le parcours de chaque membre, ses années de travail et sa pension, aujourd'hui et l'horizon marqués ; le patrimoine net jusqu'à l'horizon avec sa partie liquide et la retraite marquée ; les revenus mensuels une fois retraité ; une fiche par membre avec ses données, et les limites, repliées (pas d'impôt sur les retraits, pas de dépendance, le logement jamais vendu…). C'est une estimation, pas un conseil.",
      ],
      link: { to: "/wealth", label: "Ouvrir votre patrimoine" },
    },
    {
      id: "goals",
      title: "Objectifs",
      paragraphs: [
        "L'espace Objectifs suit les montants que vous voulez réunir pour une date, en pyramide : son socle est votre épargne de précaution, servie en premier ; au-dessus, trois étages donnés par l'éloignement de l'échéance : d'abord le long terme (au-delà de cinq ans : un apport immobilier, les études des enfants) ; puis le moyen terme (plus d'un an, jusqu'à cinq : un voyage, une voiture, un gros achat) ; au sommet le court terme (jusqu'à un an : des vacances, une réparation). Vous ne choisissez jamais l'étage : un objectif change d'étage tout seul quand vous déplacez son échéance, et monte d'un étage à mesure qu'elle approche, jusqu'au sommet. Un objectif peut être « Permanent » : il reste affiché une fois atteint et n'a pas besoin d'échéance (un fonds travaux, par exemple) ; tout autre objectif s'archive de lui-même quand il atteint sa cible. Un objectif peut être votre épargne de précaution (« C'est l'épargne de précaution » dans le formulaire) : mise de côté pour les imprévus, servie en premier, toujours permanente, le socle de la pyramide. Chaque membre peut avoir une épargne de précaution, et le foyer une commune. La pyramide est dessinée en pierre : les blocs de chaque étage prennent sa couleur par le bas à mesure que ses objectifs se remplissent, et l'épargne de précaution est la colonne sur laquelle elle repose, qui se colore depuis son pied.",
        "Un objectif est financé par vos lignes de patrimoine, chacune lui réservant une enveloppe ; le reste de la ligne reste libre pour autre chose. Pour chaque ligne, indiquez un montant de départ, pris sur ce qui est libre (0 pour partir de rien), et la part de ses hausses qui revient à l'objectif (100 % si la ligne ne sert qu'à lui). L'objectif avance ensuite quand vous mettez votre patrimoine à jour chaque mois, sans autre saisie : une hausse (un versement, des intérêts) remplit son enveloppe jusqu'à sa cible ; un retrait ou une perte est d'abord pris sur la partie libre, et l'objectif ne baisse que si la ligne vaut moins que ce que ses objectifs y réservent, les échéances les plus lointaines d'abord et l'épargne de précaution en dernier. Le formulaire montre ce qui est libre sur chaque ligne, la page Patrimoine ce que les objectifs y réservent. Si une hausse comptée pour un objectif n'était pas pour lui (un versement destiné à autre chose), « Ajuster », dans les Enveloppes de l'objectif, fixe ce que son enveloppe réserve à partir du mois choisi ; elle suit ensuite les hausses et les baisses comme avant, et l'ajustement peut être retiré. Les parts des hausses d'une ligne ne dépassent jamais 100 %, et une ligne privée ne finance qu'un objectif que vous seul voyez. Pour l'épargne de précaution, « Proposer à partir de mes dépenses fixes » multiplie le total mensuel de vos dépenses fixes (loyer, abonnements, assurances…, une trimestrielle ou annuelle comptant pour un tiers ou un douzième) par le nombre de mois choisi (6 par défaut) ; le montant reste fixe une fois enregistré.",
        "Chaque objectif a une jauge avec un repère là où il devrait en être, sur une ligne droite de son début à sa cible à l'échéance, et un statut : en avance, dans les temps ou en retard (à 5 % près), atteint, ou « À combler en priorité » pour une épargne de précaution incomplète. Il donne l'effort requis chaque mois, votre effort réel (le gain moyen des 6 derniers mois) et la date à laquelle il serait atteint à ce rythme, en avance ou en retard. Sa page trace la trajectoire et détaille chaque mois.",
        "Tout en haut, la pointe dorée accueille vos objectifs plaisir (« C'est un objectif plaisir » dans le formulaire) : ce qui vous ferait simplement plaisir, sans besoin (des gants de boxe, une platine vinyle, une belle bouteille de rhum). Ils n'ont pas d'échéance et s'archivent d'eux-mêmes une fois atteints. Ils ne sont financés qu'une fois le reste en ordre : la pointe reste verrouillée, en pierre avec un cadenas, tant que votre épargne de précaution n'est pas pleine et que moins de 3 objectifs datés sur 4 sont en avance (un objectif atteint compte comme en avance), jugé sur le mois dernier. Tant qu'elle est verrouillée, les hausses de leurs lignes restent libres et l'effort du mois ne leur donne rien ; ce qu'ils ont déjà reste acquis. Sous la pyramide, une phrase dit ce qu'il manque encore. Une fois débloqués, ils reçoivent ce que les autres objectifs laissent de l'effort du mois, au prorata de ce qu'il manque à chacun, et quand une ligne baisse, ce sont eux qui perdent en premier.",
        "« L'effort du mois » répartit ce que vous pouvez épargner (les revenus moins les dépenses du foyer, en moyenne sur les 6 derniers mois complets, ou un montant que le propriétaire du foyer fixe dans les réglages de l'effort) : tant que l'épargne de précaution n'est pas complète, elle reçoit d'abord une part (70 % par défaut, de 50 % à 100 %), les autres objectifs le reste au prorata de l'effort qu'ils demandent, et ce qu'ils laissent revient à la précaution. C'est une recommandation : rien n'est déplacé. Chaque carte a ses actions : « Modifier », « Archiver » quand vous en avez terminé (jamais pour un objectif permanent), « Annuler l'objectif » quand il n'est plus d'actualité. Un objectif archivé ou annulé quitte la pyramide, libère ses lignes et n'apparaît plus sur la page : « Afficher les objectifs archivés et annulés » les liste, et la page d'un objectif permet de le rouvrir (un objectif atteint demande une cible plus haute, ou de devenir permanent).",
        "L'onglet « Analyse », à côté de « Pyramide », regarde vos objectifs ensemble. Il les juge au dernier mois où toutes leurs lignes de financement ont une valeur saisie : un mois pas encore saisi ne passe jamais pour un mois sans épargne. Il s'ouvre sur les points d'attention, des constats calculés par des règles fixes (pas d'épargne de précaution, ou une sous 3 ou 6 mois de charges fixes, ou placée sur des lignes volatiles ou un compte courant ; un objectif qu'aucune ligne ne finance ; des objectifs qui demandent chaque mois plus que vous ne pouvez épargner, avec l'objectif que vous pourriez repousser, de combien de mois, ou la cible que vous pourriez baisser ; un objectif en retard depuis trois mois, avec ce qui tient sa date ; un objectif sans gain depuis six mois ; un objectif proche de son échéance encore sur des lignes volatiles, avec ce qu'il pourrait perdre une fois sur dix ; un objectif lointain sur des lignes qui ne rapportent pas plus que l'inflation, ou une cible lointaine en euros d'aujourd'hui ; de l'argent qui dort sur vos comptes courants ; un livret réglementé proche de son plafond sur lequel un objectif compte encore ; le peu qu'il faudrait pour débloquer la pointe dorée ; de la capacité non allouée ; des valeurs à saisir). Trois sont affichés, les plus sérieux d'abord, au plus un par objectif ; « Me le rappeler le mois prochain » ou « Masquer jusqu'à ce que ça empire » en masque un pour vous seul, et « Réafficher les points masqués » les ramène tous. Ce sont des observations, jamais des conseils ; l'onglet Pyramide indique combien il y en a, avec un lien vers eux. Plus bas : l'effort que chaque objectif demande chaque mois, empilé face à ce que le foyer peut épargner, avec les mois en dépassement grisés (le graphique compare les objectifs du foyer dans toutes les vues, la capacité étant celle du foyer ; choisissez combien de mois afficher) ; une frise de chaque objectif de son début à son échéance, avec où il arrive à son rythme (●) et à l'effort du plan (◇) ; le statut de chaque objectif mois par mois ; et chaque objectif placé selon les mois avant son échéance et la volatilité de ses lignes, sur des zones nommées sur le graphique, deux hachurées (proche et volatil, lointain et grignoté) et une unie (entre 2 et 5 ans, où un objectif devrait quitter les lignes volatiles pas à pas), un anneau en pointillés signalant un objectif en partie dans une catégorie qui perd de la valeur (les aires sont des repères d'horizon : seul un anneau signale un objectif à regarder, comme l'explique la légende sous le graphique, et le tableau donne la part que chaque objectif entre 2 et 5 ans peut garder sur des lignes volatiles) ; et où est l'argent des objectifs, de chaque catégorie à ses lignes, puis aux enveloppes des objectifs et à la part libre de chaque ligne (l'immobilier et les matériels sont laissés de côté sauf si vous les cochez ; ce qu'un objectif détient sur des lignes non montrées est listé dessous ; « Libre » peut contenir des enveloppes d'objectifs que vous ne voyez pas). Un point qui cite un objectif sans le concerner, comme de l'argent à mettre de côté depuis vos comptes courants, peut s'ajouter au point de cet objectif. Un tableau donne la chance de chaque objectif d'atteindre sa cible avant son échéance, à l'allocation du plan et à l'effort requis, d'après les hypothèses de la Projection (un objectif sur des lignes qui ne bougent pas est « atteint » ou « il manque » un montant ; la précaution montre les mois pour la remplir) ; les chances sont par objectif, pas de tous les atteindre. Deux points de plus surveillent les dettes saisies avec leur taux et leur mensualité : un prêt qui coûte plus que ce que les lignes des objectifs sont censées rapporter, et des mensualités au-delà de 35 % du revenu, le plafond des banques. Chaque graphique a son tableau.",
      ],
      link: { to: "/goals", label: "Ouvrir vos objectifs" },
    },
    {
      id: "reports",
      title: "Rapports",
      paragraphs: [
        "Les rapports reviennent sur n'importe quelle période de mois entiers : ce mois-ci, le mois dernier, ce trimestre, cette année, l'année dernière, les 12 derniers mois, ou une période libre avec un premier et un dernier mois (10 ans au plus). Une période qui dépasse ce mois-ci s'y arrête (« cette année » veut dire cette année à ce jour) et se compare aux mêmes mois de la période d'avant ; les mois avant votre première ligne sont laissés de côté, et quand la période d'avant commence avant eux, rien n'est comparé.",
        "Chaque rapport donne les totaux (revenus, dépenses, épargne et reste, face à la période d'avant de même durée, et le taux d'épargne), un tableau par catégorie en trois sections (revenus, dépenses et épargne) avec la moyenne par mois, la part de chaque catégorie dans sa section et l'évolution, un graphique des dépenses par catégorie, pour une période de plusieurs mois un graphique mois par mois des dépenses par catégorie (les six plus grosses de la période en couleur, les autres en gris) face aux revenus, et les flux d'argent : les revenus par catégorie à gauche, puis les dépenses par catégorie, l'épargne et le reste non alloué à droite, un manque arrivant comme déficit et l'argent repris à l'épargne comme tel. Les dépenses au-dessus de leurs cibles sur la période sont en orange brûlé, dans leurs cibles (ou sans cible) en ocre ; chaque graphique a son tableau.",
      ],
      link: { to: "/reports", label: "Ouvrir les rapports" },
    },
    {
      id: "forecast",
      title: "Prévision",
      paragraphs: [
        "L'onglet « Prévision », à côté des rapports, estime les douze prochains mois de dépenses, le mois en cours en premier, dès que vos lignes couvrent 12 mois complets (d'ici là, essayez-le dans la démo). Les dépenses fixes à venir sont connues d'avance ; le reste de chaque catégorie est prévu d'après son propre historique par la méthode qui s'est le moins trompée quand on lui a demandé de prévoir les mois déjà saisis (une moyenne, le même mois l'an dernier, un lissage exponentiel, des arbres appris sur toutes les catégories, ou, si l'application a été construite avec eux, deux modèles pré-entraînés sur de nombreuses séries publiques, Chronos-2 et TimesFM 2.5), une méthode ne battant la moyenne des 6 derniers mois que si elle le fait d'au moins 10 %, et jamais quand elle a prévu nettement moins de dépenses (ou plus de revenus ou d'épargne) que ce qui a été saisi. Si le reste prévu était trop haut sur les mois passés testés, le résumé le dit. Rien de ce qui est saisi ce mois-ci n'est utilisé : ce que vous avez déjà saisi est montré à côté de sa prévision.",
        "La page s'ouvre sur des tuiles : le reste des douze mois, les dépenses du mois jusqu'ici en une barre face à leur prévision avec un trait au jour du mois, le nombre d'objectifs à risque ce mois-ci et cette année, et les revenus, les dépenses et l'épargne des douze mois. Puis un graphique par question : mois par mois, les 12 derniers mois saisis et les 12 à venir, chacun avec une fourchette que les erreurs passées ont tenue environ 8 fois sur 10, le reste de chaque mois en barres dessous (le tableau garde 24 mois) ; face à vos objectifs, chaque catégorie en pourcentage de son objectif, un point pour la prévision, une barre pour sa fourchette et un trait à 100 %, avec sa probabilité de dépasser, puis les dépenses de l'année jusqu'ici plus la prévision jusqu'à décembre face à l'objectif annuel ; les revenus du mois et, pour chaque objectif d'épargne, la probabilité d'un manque. Replié sous « Fiabilité de la prévision » : sur quoi repose chaque prévision (sa méthode, de combien elle se trompe moins que la moyenne sur 6 mois, son biais sur les mois passés testés, combien de fois la fourchette a tenu) ; dessiné en erreur évitée et en optimisme ; le back-test, les totaux prévus un mois à l'avance face à ce qui a été saisi, avec leur biais ; et les limites. C'est une estimation tirée de vos mois passés, pas un conseil : une nouvelle dépense ou un changement d'emploi ne sont pas dans l'historique.",
      ],
      link: { to: "/forecast", label: "Ouvrir la prévision" },
    },
    {
      id: "members",
      title: "Membres et sécurité",
      paragraphs: [
        "Le propriétaire du foyer invite des membres avec un lien valable une fois et pendant 7 jours ; Kwak Finance n'envoie pas d'e-mail, transmettez-le vous-même.",
        "Chacun se connecte avec un mot de passe et un code d'application d'authentification. Gardez les codes de secours affichés à la configuration : chacun permet de se connecter une fois si vous perdez votre téléphone.",
        "Le journal d'activité, dans le menu à votre nom, garde les actions sensibles : connexions (avec l'adresse d'où elles viennent, et les tentatives refusées), invitations, réglages du foyer, catégories restaurées et suppressions. Le propriétaire voit celui de tout le foyer, un membre seulement le sien ; ce qui touche à une ligne de patrimoine ou à un objectif privés n'est montré qu'à son titulaire. Rien ne peut y être modifié ni supprimé.",
        "Sur la même page, le propriétaire peut fixer le début du patrimoine : la page Patrimoine s'ouvre sur les 12 derniers mois à partir de ce mois au plus tôt, pour un historique qui remonte plus loin que celui des dépenses. Sans lui, elle s'ouvre sur les 12 derniers mois. Le budget, la vue d'ensemble et les rapports partent de votre première ligne.",
      ],
      link: { to: "/members", label: "Ouvrir les membres" },
    },
    {
      id: "demo",
      title: "La démo",
      paragraphs: [
        "Beaucoup de pages ont besoin de mois d'historique pour dire quelque chose : la matrice du budget, l'année, les rapports, les graphiques du patrimoine, l'analyse des objectifs, la projection, la retraite et la prévision. Pour les voir à l'œuvre avant que vos données aient cet historique, choisissez « Ouvrir la démo » dans le menu à votre nom : elle ouvre un foyer fictif, un couple avec un enfant et trois ans de lignes, de dépenses fixes, de cibles, de patrimoine, d'objectifs et de retraites, datés jusqu'à aujourd'hui.",
        "Tant que vous y êtes, un bandeau le rappelle en haut de chaque page, et chaque page montre la démo au lieu de votre foyer, qui n'est pas touché. Vous pouvez tout y modifier pour essayer ; la démo est partagée par tous les membres et garde les modifications jusqu'à ce que quelqu'un la réinitialise : n'y saisissez jamais de vrais chiffres. Les membres, les invitations, votre mot de passe, la double authentification et les codes de secours restent hors de la démo.",
        "« Revenir à mon foyer », dans le bandeau ou dans le menu, vous ramène chez vous ; se déconnecter aussi. « Réinitialiser la démo » la supprime, avec les modifications de chacun, et la génère à nouveau à partir d'aujourd'hui, après confirmation.",
      ],
    },
  ],
  checklist: {
    title: "Bien démarrer",
    progress: (done, total) => `${done} sur ${total} faites`,
    hide: "Masquer",
    readGuide: "Lire le guide",
    steps: {
      income: "Saisir les revenus du mois en lignes",
      line: "Saisir vos premières lignes",
      fixed: "Ajouter vos dépenses fixes",
      plan: "Fixer vos objectifs mensuels",
      goal: "Constituer votre épargne de précaution",
      invite: "Inviter votre foyer (facultatif)",
    },
    done: "Fait",
  },
};
