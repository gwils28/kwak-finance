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
  | "/accounts"
  | "/transactions"
  | "/recurring"
  | "/budget"
  | "/budget/review"
  | "/wealth"
  | "/goals"
  | "/reports"
  | "/categories"
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
    "Kwak Finance keeps your household's spending, budget, wealth and goals in one place, on your own computer. This guide walks through each page. The app's name, at the top left, leads to the overview, the summary of the whole app. Next to it, “Spending”, “Wealth” and “Goals” switch between three spaces: the everyday pages (lines, budget, reports) and the wealth (monthly tracking, analysis), each with its tabs, and your financial goals. Categories, members, accounts, the activity log, language and theme are in the menu under your name, next to this guide. To install, start or update the app, see “How to run the app” at the bottom of every page.",
  contents: "Contents",
  sections: [
    {
      id: "start",
      title: "Getting started",
      paragraphs: [
        "Four steps take you from an empty app to a working budget, and the “Getting started” list on the overview ticks them off as you go: enter this month's income, enter your first lines, add your fixed expenses and set your monthly targets; then set your emergency fund, and invite the rest of the household if you share your finances.",
        "After that, a session once a week or once a month is enough: open Spending, confirm the fixed expenses waiting at the top of the month, type what you spent since last time (the header says where you stopped), and look at the month's figures.",
      ],
      link: { to: "/", label: "Open the overview" },
    },
    {
      id: "lines",
      title: "Entering lines",
      paragraphs: [
        "Spending is a list of lines you enter by hand, to the cent: a date, a label, an amount and a category, whichever card or account paid. “Spending” opens the grid of a month, the current one; ‹ and › (or Alt+Page Up and Alt+Page Down) move to the previous and next months. Every cell can be changed in place: Enter saves the row, Escape puts it back as it was. The empty row at the bottom is always ready: Tab moves from cell to cell, Enter saves it and opens a new one on the same date. A new row takes the date of the last line you entered, otherwise today (a past month's last day).",
        "Type an expense as a positive amount. In a savings category (money put aside, see Categories), a positive amount is saved and a minus sign takes money back from savings. Refunds are not lines: add them to the month's income.",
        "The quick line, above the grid, takes a whole line in any order: “bakery 12,50 yesterday”, “45 train 13/10”, “groceries 87.40 #home”. A date is a day word (today, yesterday, the day before yesterday), a weekday or a dd/mm date; the amount is the last number; “#word” picks the category whose name starts with that word; the rest is the label. It shows how it understood the line as you type. Enter saves it when it is complete; otherwise it goes into the empty row, the missing cell ready.",
        "Labels you used before are suggested as you type, the most used first, and a known label brings the category of its last line, never the amount. Change the category if needed: your latest choice is the one remembered.",
        "To spread a receipt over several categories, choose “Split…” as its category: enter each part but the last, which takes the rest, so the parts always add up. Each part counts in its own category everywhere.",
        "The header holds the month's income, spent, saved and the rest (income minus spent minus saved). The income is one amount for the month (salaries, benefits, refunds): type it there. A month without one carries the previous month's, as the note below it says; emptying it goes back to that. The line entered last is marked with a dot, and the header says its date and when it was entered, with a link to its month. A deleted line comes back with “Undo” in the message that confirms the deletion.",
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
        "Spending categories have one level and are in the menu under your name: expense categories (housing, groceries, transport…) and savings categories, for money put aside, which is never counted as spending and lowers the month's rest. Rename them in place, add new ones, or delete one: when it holds lines, fixed expenses or targets, choose another category of the same kind to move them to.",
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
        "Below the spending, the savings categories have their own section, where the colours turn round: green when you saved more than 5 % above the objective, burnt orange more than 5 % below it. The last rows give each month's income, spent, saved and rest.",
      ],
      link: { to: "/budget", label: "Open the budget" },
    },
    {
      id: "year",
      title: "The year",
      paragraphs: [
        "“The year”, on the budget page, adds up a calendar year (the current one by default; a past year is shown whole). For each category: its target to date (the targets from January to this month, this month's counted in full, so a running month leans under), its spending to date, the gap in euros and in per cent with the same colours, how many completed months were over, on and under their target, and its target for the whole year. The savings objectives follow. Above the table, tiles give the year's income, spending, savings, rest and savings rate.",
      ],
      link: { to: "/budget", label: "Open the budget" },
    },
    {
      id: "overview",
      title: "Overview",
      paragraphs: [
        "The overview sums up a month (the current one by default). Once your wealth has a line, it opens with your net worth at the end of the month and how it moved since the month before; once you have a goal, the pyramid of your goals follows. The view chosen at the top changes only these two: spending is the household's.",
        "Then the month's figures: income (carried from the previous month when none is entered), spent (with its change against last month and the 12-month average), saved, the rest and the savings rate (the share of income not spent).",
        "“Targets this month” lists each expense category with a target that month, the most used first: what it spent, what is left (or the overrun) and a bar. It says “Watch” from the warning threshold (80 % of the target by default; the household owner can change it there) and “Over” beyond the target. For the current month, a line on the bar marks how much of the month has gone by. One-off categories, paid once in the month, have no line and no “Watch”. Click a category to open its lines.",
        "“Fixed expenses to confirm” lists those of the month still waiting, each with “Confirm”, and the rest at the end of the month once they are paid. Last come the month's top categories and the last lines entered.",
      ],
      link: { to: "/", label: "Open the overview" },
    },
    {
      id: "wealth",
      title: "Wealth",
      paragraphs: [
        "The wealth space follows what you own and owe at the end of each month, like a spreadsheet: categories (savings accounts, current accounts, stocks, crypto, bonds, private equity, gold, real estate, equipment, exotic, debts), each with its colour, and in each the lines you add: one per holding, such as “PEA Fortuneo” or “Crédit immobilier”. A line is yours; choose whether the household sees it, only you, or whether it is the household's joint holding.",
        "Every line is entered by hand, your current accounts and savings accounts too: add one line per account (“Livret A”, “Compte joint”…) in its category, then enter the values once a month with “Update this month”, which shows each line's last value: change what moved and save. You can also click any value in the table to change that month. A month without a value carries the previous one, shown in grey italics. A debt is entered as what is still owed and counts against your net worth.",
        "On the “Monthly tracking” tab, the table scrolls within its frame, the months staying at the top and the line names on the left. It shows each category's total, gross assets, debts, net worth and its change month by month, and each category's share of what you own. Click a line's name to rename it, move it, or close it from a month once sold or repaid: it keeps its history. “Manage categories” renames the categories, changes their colour or their order, and adds new ones (an asset or a debt); a category can be deleted once it holds no line. The view covers the household, the joint lines or only yours. It opens on the last 12 months, from the wealth start at the earliest (on the members page; without one, the analyses start); choose any other months with “From” and “To”, and “Last 12 months” brings it back.",
        "The “Analysis” tab charts the months and the scope you choose there, below the same tiles: net worth over time by category; the allocation of a month you choose (the last one by default) as rings (categories inside, their lines outside) and as a mosaic, each category a tile as large as its value; and what moved net worth from the first month to the last, category by category. Point at a ring or a tile to read it, or open “Show the data” under each chart. The net worth tile also gives the change over the months shown, the debts tile the share of your gross assets they weigh.",
      ],
      link: { to: "/wealth", label: "Open your wealth" },
    },
    {
      id: "goals",
      title: "Goals",
      paragraphs: [
        "The goals space follows amounts you want to gather by a date, in a pyramid: its foundation is your emergency fund, filled first; above it, three tiers given by how far the deadline is: first the long term (beyond five years: a home deposit, the children's studies); then the medium term (over a year, up to five: a trip, a car, a large purchase); at the top the short term (up to a year: holidays, a repair). You never pick the tier: a goal changes tier by itself when you move its deadline, and moves up a tier as the deadline nears, until it reaches the top. A goal can be “Permanent”: it stays in view once reached and needs no deadline (a fund for repairs, say); any other goal is archived by itself once it reaches its target. A goal can be your emergency fund (“This is the emergency fund” in the form): kept apart for the unexpected, filled first, always permanent, the pyramid's foundation. Each member can have one emergency fund, and the household one joint.",
        "A goal is funded by your wealth lines, each holding an envelope for it; the rest of the line stays free for anything else. For each line, set an opening amount, taken from what is free (0 to start from nothing), and the share of its rises that goes to the goal (100 % when the line only serves it). The goal then moves when you update your wealth each month, with nothing more to enter: a rise (a deposit, interest) fills its envelope up to its target; a withdrawal or a loss comes out of the free part first, and the goal only loses once the line is worth less than its goals hold, the farthest deadlines first and the emergency fund last. The form shows what is free on each line, the Wealth page what goals set aside on it. If a rise counted for a goal was not for it (a deposit for something else), “Adjust” in the goal's Envelopes sets what its envelope holds from a month you choose; it then rises and falls as before, and the adjustment can be removed. A line's shares of the rises never exceed 100 %, and a private line only funds a goal only you see. For the emergency fund, “Propose from my fixed expenses” multiplies the monthly total of your fixed expenses (rent, subscriptions, insurance…, a quarterly or yearly one counting a third or a twelfth of it) by the number of months you choose (6 by default); the amount stays fixed once saved.",
        "Each goal has a gauge with a marker where it should stand by now, on a straight line from its start to its target at its deadline, and a status: ahead, on track or behind (with a 5 % margin), reached, or “Fill first” for an emergency fund short of its target. It shows the effort it requires each month, your actual effort (the average gain of the last 6 months) and the date it should be reached at that pace, early or late. Its page draws the trajectory and lists each month.",
        "“This month's effort” shares out what you can save (the household's average income minus spending over the last 6 complete months, or an amount the household owner sets in the effort settings): while the emergency fund falls short, it gets a share first (70 % by default, from 50 % to 100 %), the other goals the rest in proportion to the effort they require, and what they leave goes back to the emergency fund. It is a recommendation: nothing is moved. Each card has its actions: “Edit”, “Archive” once you are done with it (never for a permanent goal), “Cancel the goal” when it no longer matters. An archived or cancelled goal leaves the pyramid, frees its lines and is hidden from the page: “Show archived and cancelled goals” lists them, and a goal's page reopens it (a reached goal asks for a higher target, or to become permanent).",
      ],
      link: { to: "/goals", label: "Open your goals" },
    },
    {
      id: "reports",
      title: "Reports",
      paragraphs: [
        "Reports look back over any period of whole months: this month, last month, this quarter, this year, last year, the last 12 months, or a custom period with a first and a last month (10 years at most). A period running past this month stops there (“this year” means this year so far) and is compared with the same months of the period before; months before your first line or income are left out, and when the period before reaches before them, nothing is compared.",
        "Each report gives the totals (income, spending, savings and the rest, against the period before of the same length, and the savings rate), a table by category in two sections (spending and savings) with the monthly average, each category's share of its section and the change, a chart of spending by category, for a period of several months a month-by-month chart of spending against income, and the money flows: the income on the left, then spending by category, savings and the unallocated rest on the right, a shortfall coming in as a deficit and money taken back from savings as such. Spending over its targets for the period is burnt orange, within them (or without a target) ochre; every chart has its table.",
      ],
      link: { to: "/reports", label: "Open the reports" },
    },
    {
      id: "members",
      title: "Members and security",
      paragraphs: [
        "The household owner invites members with a link that works once and expires after 7 days; Kwak Finance sends no email, so send it yourself.",
        "Everyone signs in with a password and a code from an authenticator app. Keep the recovery codes shown at set-up: each lets you sign in once if you lose your phone.",
        "The activity log, in the menu under your name, keeps the sensitive actions: sign-ins (with the address they came from, and failed attempts), invitations, imports and their rollback, deletions, and changes to rules and categories. The owner sees the whole household's, a member only their own; what happens on a private account is only shown to its owner. Nothing in it can be changed or deleted.",
        "On the same page, the owner can set the wealth start: the wealth page opens on the last 12 months from that month at the earliest, for a history that goes back further than your spending's. Without one, it follows the analyses start, also set there; the budget, the overview and the reports no longer use it: their figures start from your first line or income.",
      ],
      link: { to: "/members", label: "Open the members" },
    },
  ] satisfies GuideSection[],
  checklist: {
    title: "Getting started",
    progress: (done: number, total: number) => `${done} of ${total} done`,
    hide: "Hide",
    readGuide: "Read the guide",
    steps: {
      income: "Enter this month's income",
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
    "Kwak Finance réunit les dépenses, le budget, le patrimoine et les objectifs de votre foyer, sur votre propre ordinateur. Ce guide parcourt chaque page. Le nom de l'application, en haut à gauche, mène à la vue d'ensemble, le résumé de toute l'application. À côté, « Dépenses », « Patrimoine » et « Objectifs » passent d'un espace à l'autre : les pages du quotidien (lignes, budget, rapports) et le patrimoine (suivi mensuel, analyse), chacun avec ses onglets, et vos objectifs financiers. Les catégories, les membres, les comptes, le journal d'activité, la langue et le thème sont dans le menu à votre nom, à côté de ce guide. Pour installer, lancer ou mettre à jour l'application, voyez « Lancer et arrêter l'application » en bas de chaque page.",
  contents: "Sommaire",
  sections: [
    {
      id: "start",
      title: "Bien démarrer",
      paragraphs: [
        "Quatre étapes mènent d'une application vide à un budget qui fonctionne, et la liste « Bien démarrer » de la vue d'ensemble les coche au fur et à mesure : saisir les revenus du mois, saisir vos premières lignes, ajouter vos dépenses fixes et fixer vos objectifs mensuels ; ensuite, constituer votre épargne de précaution, et inviter le reste du foyer si vous partagez vos finances.",
        "Ensuite, une séance par semaine ou par mois suffit : ouvrez Dépenses, confirmez les dépenses fixes qui attendent en haut du mois, tapez ce que vous avez dépensé depuis la dernière fois (l'en-tête dit où vous vous êtes arrêté) et regardez les chiffres du mois.",
      ],
      link: { to: "/", label: "Ouvrir la vue d'ensemble" },
    },
    {
      id: "lines",
      title: "Saisir les lignes",
      paragraphs: [
        "Les dépenses sont une liste de lignes saisies à la main, au centime : une date, un libellé, un montant et une catégorie, quelle que soit la carte ou le compte qui a payé. « Dépenses » ouvre la grille d'un mois, le mois en cours ; ‹ et › (ou Alt+Page préc. et Alt+Page suiv.) passent au mois précédent et au suivant. Chaque cellule se modifie sur place : Entrée enregistre la ligne, Échap la remet comme elle était. La ligne vide en bas est toujours prête : Tab passe d'une cellule à l'autre, Entrée l'enregistre et en ouvre une nouvelle à la même date. Une nouvelle ligne prend la date de la dernière ligne saisie, sinon aujourd'hui (le dernier jour d'un mois passé).",
        "Tapez une dépense en montant positif. Dans une catégorie d'épargne (l'argent mis de côté, voir Catégories), un montant positif est épargné et un signe moins reprend de l'argent à l'épargne. Les remboursements ne sont pas des lignes : ajoutez-les aux revenus du mois.",
        "La saisie rapide, au-dessus de la grille, prend une ligne entière dans n'importe quel ordre : « boulangerie 12,50 hier », « 45 sncf 13/10 », « carrefour 87,40 #foyer ». Une date est un mot (aujourd'hui, hier, avant-hier), un jour de la semaine ou une date jj/mm ; le montant est le dernier nombre ; « #mot » choisit la catégorie dont le nom commence par ce mot ; le reste est le libellé. Elle montre comment elle a compris la ligne pendant la frappe. Entrée l'enregistre si elle est complète ; sinon elle passe dans la ligne vide, la cellule manquante prête.",
        "Les libellés déjà utilisés sont proposés pendant la frappe, les plus utilisés d'abord, et un libellé connu reprend la catégorie de sa dernière ligne, jamais le montant. Changez la catégorie si besoin : votre dernier choix est celui qui est retenu.",
        "Pour répartir un ticket sur plusieurs catégories, choisissez « Ventiler… » comme catégorie : saisissez chaque part sauf la dernière, qui prend le reste, si bien que les parts tombent toujours juste. Chaque part compte partout dans sa propre catégorie.",
        "L'en-tête donne les revenus, le dépensé, l'épargné et le reste du mois (revenus moins dépensé moins épargné). Les revenus sont un montant pour le mois (salaires, allocations, remboursements) : tapez-le là. Un mois sans revenus reprend ceux du mois précédent, comme l'indique la note en dessous ; le vider y revient. La ligne saisie en dernier est marquée d'un point, et l'en-tête donne sa date et quand elle a été saisie, avec un lien vers son mois. Une ligne supprimée revient avec « Annuler » dans le message qui confirme la suppression.",
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
        "Les catégories de dépenses ont un seul niveau et sont dans le menu à votre nom : les catégories de dépense (logement, courses, transport…) et les catégories d'épargne, pour l'argent mis de côté, qui ne compte jamais comme dépense et réduit le reste du mois. Renommez-les sur place, ajoutez-en, ou supprimez-en une : si elle contient des lignes, des dépenses fixes ou des cibles, choisissez une autre catégorie du même type où les déplacer.",
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
        "Sous les dépenses, les catégories d'épargne ont leur propre section, où les couleurs s'inversent : vert quand vous avez épargné plus de 5 % au-dessus de l'objectif, orange brûlé à plus de 5 % en dessous. Les dernières lignes donnent les revenus, le dépensé, l'épargné et le reste de chaque mois.",
      ],
      link: { to: "/budget", label: "Ouvrir le budget" },
    },
    {
      id: "year",
      title: "L'année",
      paragraphs: [
        "« L'année », sur la page du budget, fait le compte d'une année civile (l'année en cours par défaut ; une année passée est montrée en entier). Pour chaque catégorie : sa cible à date (les cibles de janvier à ce mois, celle du mois en cours comptée en entier, si bien qu'un mois en cours penche vers le dessous), ses dépenses à date, l'écart en euros et en pourcentage avec les mêmes couleurs, combien de mois terminés ont été au-dessus, dans et sous leur cible, et sa cible pour l'année entière. Les objectifs d'épargne suivent. Au-dessus du tableau, des tuiles donnent les revenus, les dépenses, l'épargne, le reste et le taux d'épargne de l'année.",
      ],
      link: { to: "/budget", label: "Ouvrir le budget" },
    },
    {
      id: "overview",
      title: "Vue d'ensemble",
      paragraphs: [
        "La vue d'ensemble résume un mois (le mois en cours par défaut). Dès que votre patrimoine a une ligne, elle s'ouvre sur votre patrimoine net en fin de mois et son évolution depuis le mois précédent ; dès que vous avez un objectif, la pyramide de vos objectifs suit. La vue choisie en haut ne change que ces deux-là : les dépenses sont celles du foyer.",
        "Viennent ensuite les chiffres du mois : les revenus (reportés du mois précédent quand aucun n'est saisi), le dépensé (avec son évolution face au mois dernier et à la moyenne sur 12 mois), l'épargné, le reste et le taux d'épargne (la part des revenus non dépensée).",
        "« Cibles du mois » liste chaque catégorie de dépense qui a une cible ce mois-là, la plus utilisée d'abord : ce qu'elle a dépensé, ce qui reste (ou le dépassement) et une barre. Elle indique « Attention » à partir du seuil d'alerte (80 % de la cible par défaut ; le propriétaire du foyer peut le changer là) et « Dépassé » au-delà de la cible. Pour le mois en cours, un trait sur la barre marque la part du mois écoulée. Les catégories ponctuelles, payées une fois dans le mois, n'ont ni trait ni « Attention ». Cliquez sur une catégorie pour ouvrir ses lignes.",
        "« Dépenses fixes à confirmer » liste celles du mois qui attendent encore, chacune avec « Confirmer », et le reste en fin de mois une fois qu'elles sont payées. Viennent enfin les principales catégories du mois et les dernières lignes saisies.",
      ],
      link: { to: "/", label: "Ouvrir la vue d'ensemble" },
    },
    {
      id: "wealth",
      title: "Patrimoine",
      paragraphs: [
        "L'espace Patrimoine suit ce que vous possédez et devez à la fin de chaque mois, comme un tableur : des catégories (livrets, comptes courants, actions, cryptos, obligations, private equity, or, immobilier, matériels, exotiques, dettes), chacune avec sa couleur, et dans chacune les lignes que vous ajoutez : une par avoir, comme « PEA Fortuneo » ou « Crédit immobilier ». Une ligne est à vous ; choisissez si le foyer la voit, vous seul, ou si c'est un avoir commun du foyer.",
        "Chaque ligne se saisit à la main, comptes courants et livrets compris : ajoutez une ligne par compte (« Livret A », « Compte joint »…) dans sa catégorie, puis saisissez les valeurs une fois par mois avec « Mettre à jour ce mois-ci », qui affiche la dernière valeur de chaque ligne : changez ce qui a bougé et enregistrez. Vous pouvez aussi cliquer sur une valeur du tableau pour changer ce mois-là. Un mois sans valeur reprend la précédente, affichée en gris italique. Une dette se saisit pour ce qui reste dû et compte en moins dans votre patrimoine net.",
        "Dans l'onglet « Suivi mensuel », le tableau défile dans son cadre, les mois restant en haut et les noms des lignes à gauche. Il montre le total de chaque catégorie, l'actif brut, les dettes, le patrimoine net et sa variation d'un mois à l'autre, et la part de chaque catégorie dans ce que vous possédez. Cliquez sur le nom d'une ligne pour la renommer, la déplacer ou la clôturer à partir d'un mois une fois vendue ou remboursée : elle garde son historique. « Gérer les catégories » renomme les catégories, change leur couleur ou leur ordre et en ajoute de nouvelles (un actif ou une dette) ; une catégorie se supprime une fois vide. La vue couvre le foyer, les lignes communes ou seulement les vôtres. Elle s'ouvre sur les 12 derniers mois, au plus tôt à partir du début du patrimoine (page Membres ; sans réglage, le début des analyses) ; choisissez d'autres mois avec « Du » et « Au », et « 12 derniers mois » la ramène.",
        "L'onglet « Analyse » présente en graphiques les mois et le périmètre que vous y choisissez, sous les mêmes tuiles : le patrimoine dans le temps par catégorie ; la répartition d'un mois au choix (le dernier par défaut) en anneaux (les catégories au centre, leurs lignes autour) et en mosaïque, chaque catégorie en tuile aussi grande que sa valeur ; et ce qui a fait bouger le patrimoine du premier mois au dernier, catégorie par catégorie. Pointez un anneau ou une tuile pour le lire, ou ouvrez « Afficher les données » sous chaque graphique. La tuile du patrimoine net donne aussi la variation sur les mois affichés, celle des dettes leur poids dans votre actif brut.",
      ],
      link: { to: "/wealth", label: "Ouvrir votre patrimoine" },
    },
    {
      id: "goals",
      title: "Objectifs",
      paragraphs: [
        "L'espace Objectifs suit les montants que vous voulez réunir pour une date, en pyramide : son socle est votre épargne de précaution, servie en premier ; au-dessus, trois étages donnés par l'éloignement de l'échéance : d'abord le long terme (au-delà de cinq ans : un apport immobilier, les études des enfants) ; puis le moyen terme (plus d'un an, jusqu'à cinq : un voyage, une voiture, un gros achat) ; au sommet le court terme (jusqu'à un an : des vacances, une réparation). Vous ne choisissez jamais l'étage : un objectif change d'étage tout seul quand vous déplacez son échéance, et monte d'un étage à mesure qu'elle approche, jusqu'au sommet. Un objectif peut être « Permanent » : il reste affiché une fois atteint et n'a pas besoin d'échéance (un fonds travaux, par exemple) ; tout autre objectif s'archive de lui-même quand il atteint sa cible. Un objectif peut être votre épargne de précaution (« C'est l'épargne de précaution » dans le formulaire) : mise de côté pour les imprévus, servie en premier, toujours permanente, le socle de la pyramide. Chaque membre peut avoir une épargne de précaution, et le foyer une commune.",
        "Un objectif est financé par vos lignes de patrimoine, chacune lui réservant une enveloppe ; le reste de la ligne reste libre pour autre chose. Pour chaque ligne, indiquez un montant de départ, pris sur ce qui est libre (0 pour partir de rien), et la part de ses hausses qui revient à l'objectif (100 % si la ligne ne sert qu'à lui). L'objectif avance ensuite quand vous mettez votre patrimoine à jour chaque mois, sans autre saisie : une hausse (un versement, des intérêts) remplit son enveloppe jusqu'à sa cible ; un retrait ou une perte est d'abord pris sur la partie libre, et l'objectif ne baisse que si la ligne vaut moins que ce que ses objectifs y réservent, les échéances les plus lointaines d'abord et l'épargne de précaution en dernier. Le formulaire montre ce qui est libre sur chaque ligne, la page Patrimoine ce que les objectifs y réservent. Si une hausse comptée pour un objectif n'était pas pour lui (un versement destiné à autre chose), « Ajuster », dans les Enveloppes de l'objectif, fixe ce que son enveloppe réserve à partir du mois choisi ; elle suit ensuite les hausses et les baisses comme avant, et l'ajustement peut être retiré. Les parts des hausses d'une ligne ne dépassent jamais 100 %, et une ligne privée ne finance qu'un objectif que vous seul voyez. Pour l'épargne de précaution, « Proposer à partir de mes dépenses fixes » multiplie le total mensuel de vos dépenses fixes (loyer, abonnements, assurances…, une trimestrielle ou annuelle comptant pour un tiers ou un douzième) par le nombre de mois choisi (6 par défaut) ; le montant reste fixe une fois enregistré.",
        "Chaque objectif a une jauge avec un repère là où il devrait en être, sur une ligne droite de son début à sa cible à l'échéance, et un statut : en avance, dans les temps ou en retard (à 5 % près), atteint, ou « À combler en priorité » pour une épargne de précaution incomplète. Il donne l'effort requis chaque mois, votre effort réel (le gain moyen des 6 derniers mois) et la date à laquelle il serait atteint à ce rythme, en avance ou en retard. Sa page trace la trajectoire et détaille chaque mois.",
        "« L'effort du mois » répartit ce que vous pouvez épargner (les revenus moins les dépenses du foyer, en moyenne sur les 6 derniers mois complets, ou un montant que le propriétaire du foyer fixe dans les réglages de l'effort) : tant que l'épargne de précaution n'est pas complète, elle reçoit d'abord une part (70 % par défaut, de 50 % à 100 %), les autres objectifs le reste au prorata de l'effort qu'ils demandent, et ce qu'ils laissent revient à la précaution. C'est une recommandation : rien n'est déplacé. Chaque carte a ses actions : « Modifier », « Archiver » quand vous en avez terminé (jamais pour un objectif permanent), « Annuler l'objectif » quand il n'est plus d'actualité. Un objectif archivé ou annulé quitte la pyramide, libère ses lignes et n'apparaît plus sur la page : « Afficher les objectifs archivés et annulés » les liste, et la page d'un objectif permet de le rouvrir (un objectif atteint demande une cible plus haute, ou de devenir permanent).",
      ],
      link: { to: "/goals", label: "Ouvrir vos objectifs" },
    },
    {
      id: "reports",
      title: "Rapports",
      paragraphs: [
        "Les rapports reviennent sur n'importe quelle période de mois entiers : ce mois-ci, le mois dernier, ce trimestre, cette année, l'année dernière, les 12 derniers mois, ou une période libre avec un premier et un dernier mois (10 ans au plus). Une période qui dépasse ce mois-ci s'y arrête (« cette année » veut dire cette année à ce jour) et se compare aux mêmes mois de la période d'avant ; les mois avant votre première ligne ou vos premiers revenus sont laissés de côté, et quand la période d'avant commence avant eux, rien n'est comparé.",
        "Chaque rapport donne les totaux (revenus, dépenses, épargne et reste, face à la période d'avant de même durée, et le taux d'épargne), un tableau par catégorie en deux sections (dépenses et épargne) avec la moyenne par mois, la part de chaque catégorie dans sa section et l'évolution, un graphique des dépenses par catégorie, pour une période de plusieurs mois un graphique mois par mois des dépenses face aux revenus, et les flux d'argent : les revenus à gauche, puis les dépenses par catégorie, l'épargne et le reste non alloué à droite, un manque arrivant comme déficit et l'argent repris à l'épargne comme tel. Les dépenses au-dessus de leurs cibles sur la période sont en orange brûlé, dans leurs cibles (ou sans cible) en ocre ; chaque graphique a son tableau.",
      ],
      link: { to: "/reports", label: "Ouvrir les rapports" },
    },
    {
      id: "members",
      title: "Membres et sécurité",
      paragraphs: [
        "Le propriétaire du foyer invite des membres avec un lien valable une fois et pendant 7 jours ; Kwak Finance n'envoie pas d'e-mail, transmettez-le vous-même.",
        "Chacun se connecte avec un mot de passe et un code d'application d'authentification. Gardez les codes de secours affichés à la configuration : chacun permet de se connecter une fois si vous perdez votre téléphone.",
        "Le journal d'activité, dans le menu à votre nom, garde les actions sensibles : connexions (avec l'adresse d'où elles viennent, et les tentatives refusées), invitations, imports et leur annulation, suppressions, et changements de règles et de catégories. Le propriétaire voit celui de tout le foyer, un membre seulement le sien ; ce qui se passe sur un compte privé n'est montré qu'à son titulaire. Rien ne peut y être modifié ni supprimé.",
        "Sur la même page, le propriétaire peut fixer le début du patrimoine : la page Patrimoine s'ouvre sur les 12 derniers mois à partir de ce mois au plus tôt, pour un historique qui remonte plus loin que celui des dépenses. Sans lui, elle suit le début des analyses, réglé au même endroit ; le budget, la vue d'ensemble et les rapports ne l'utilisent plus : leurs chiffres partent de votre première ligne ou de vos premiers revenus.",
      ],
      link: { to: "/members", label: "Ouvrir les membres" },
    },
  ],
  checklist: {
    title: "Bien démarrer",
    progress: (done, total) => `${done} sur ${total} faites`,
    hide: "Masquer",
    readGuide: "Lire le guide",
    steps: {
      income: "Saisir les revenus du mois",
      line: "Saisir vos premières lignes",
      fixed: "Ajouter vos dépenses fixes",
      plan: "Fixer vos objectifs mensuels",
      goal: "Constituer votre épargne de précaution",
      invite: "Inviter votre foyer (facultatif)",
    },
    done: "Fait",
  },
};
