/**
 * "Using Kwak Finance": one section per feature, and the overview's "Getting started" checklist.
 * Keep it true to the app: a PR that changes what users see updates it, in both languages.
 */

/** The pages a guide section can open. */
export type GuidePage =
  | "/"
  | "/accounts"
  | "/transactions"
  | "/recurring"
  | "/budget"
  | "/budget/review"
  | "/wealth"
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
    "Kwak Finance keeps your household's accounts, spending, budget and wealth in one place, on your own computer. This guide walks through each page. The tabs at the top lead to the everyday pages; categories, members, the activity log, language and theme are in the menu under your name, next to this guide. To install, start or update the app, see “How to run the app” at the bottom of every page.",
  contents: "Contents",
  sections: [
    {
      id: "start",
      title: "Getting started",
      paragraphs: [
        "Five steps take you from an empty app to a working budget, and the “Getting started” list on the overview ticks them off as you go: add your bank accounts, import a statement for each, categorise the transactions, set your monthly targets in a budget plan, and invite the rest of the household if you share your finances.",
        "After that, a monthly routine is enough: import the new statements, categorise what the rules did not, then look at the plan review.",
      ],
      link: { to: "/", label: "Open the overview" },
    },
    {
      id: "accounts",
      title: "Accounts",
      paragraphs: [
        "Add each bank account with its institution and type (checking, savings…). Its opening date is the first day of the first statement you will import, and its opening balance the balance on that day, before its first operation: operations dated earlier are ignored.",
        "An account is visible only to you, to every household member, or is the household's joint account (the one shared expenses are paid from: rent, childminder, groceries…); only the member who created it can change that. Keep the same categories on every account: the account tells who pays, the category what for. A closed account keeps its history and can be reopened.",
      ],
      link: { to: "/accounts", label: "Open the accounts" },
    },
    {
      id: "import",
      title: "Importing statements",
      paragraphs: [
        "From an account, “Import” takes the bank's CSV export (Société Générale or Helios for now). A preview shows the new operations, the ones already imported and the errors with their line numbers: nothing is saved until you confirm, and importing the same file twice adds nothing.",
        "Operations you entered by hand during the month are not added twice: a statement line with the same amount, on the same account and at most 5 days from an entry is marked “Already entered” and takes that entry over. The entry keeps your label and category and takes the bank's date (the bank's label shows when you point at it in Transactions). If a match is wrong, “Not the same” imports the line as a new operation. The preview also lists what you entered within the statement's dates that is not in it: a typo, or an operation the bank has not booked yet. Rolling the import back gives the entries back as you entered them.",
        "After the import, the computed balance is compared with the bank's. If they differ, check the account's opening balance and date, or import the missing period. An import can be rolled back from the list of previous imports.",
      ],
      link: { to: "/accounts", label: "Open the accounts" },
    },
    {
      id: "transactions",
      title: "Transactions",
      paragraphs: [
        "Filter by account, category, dates or label. Select several transactions to give them a category at once, or pick it on a single row. “Rule” creates a rule from a transaction's label, so the next imports are categorised for you.",
        "Each transaction keeps its real date and also counts for a budget month: its date's month, or the next one when its category says so; the list says “counted in …” under the date when it differs. Click that note (or the calendar icon next to the date) to set it by hand (the date's month, the one before or the one after), e.g. for a salary paid early; “Automatic” goes back to the category's rule. Transfers between your accounts stay in their month. The “Budget month” filter shows what a budget cell counts.",
        "Transfers between your own accounts are detected and offered for linking (the same amount, at most 3 days apart): linked, they count neither as spending nor as income. When the detection misses one, “Link to…” on a row lists the transactions of the same amount the other way on your other accounts, within 31 days, to pick the other side.",
        "“Add a transaction” records cash or anything your bank does not export; pick its category there, or leave it to the rules. Choose “Transfer” to move money from one of your accounts to another, e.g. your share paid into the joint account: both sides are entered at once, already linked, labelled “Transfer to …” and “Transfer from …” unless you give a label. Change the amount or the date of one side and the other follows; delete one and both go. Once a side comes from a statement, its amount is the bank's: the other side's amount can no longer change.",
        "“Details” on a row adds a note (searched with the label) and splits the transaction over several categories, e.g. a supermarket receipt with groceries, household supplies and the pharmacy: enter each part but the last, which takes the rest, so the parts always add up. Each part counts in its category in the budget, the overview and the review; the transaction counts in the month its first part's category gives. Rules and bulk categorisation leave a split transaction as it is; “Remove the split” brings it back to categorise.",
      ],
      link: { to: "/transactions", label: "Open the transactions" },
    },
    {
      id: "recurring",
      title: "Recurring items",
      paragraphs: [
        "“Recurring”, at the top of the transactions, lists what comes back regularly: salary, rent, subscriptions, a weekly market. Each item has an account, a label found in the transactions' labels (like a rule), an amount, a frequency (weekly, monthly, quarterly or yearly), a day and a category. Tick “Variable amount” for a bill that changes, such as electricity: Kwak then expects the average of its last 3 payments, shown “≈”.",
        "Kwak never enters anything by itself. A transaction of the item's account whose label matches, within 10 % of the amount (any amount for a variable one) and 5 days of the date, counts as that occurrence. Without one, the occurrence is late 5 days after its date: “Enter it” opens a new transaction filled in with the item's account, label, category and amount, on the expected date (today if that is still to come), for you to check and save. “Skip” tells Kwak an occurrence will not happen (a subscription paused for a month); “History” shows the past ones and restores a skipped one. Pause an item, or give it an end date, when it stops.",
        "Suggestions list the series found in the last 6 months: at least 3 transactions of one account with the same label, every week or every month, the amounts within 10 %. “Follow” opens the form filled in to check and save; “Dismiss” stops suggesting it. Quarterly and yearly items are too rare to detect: add them by hand.",
        "A recurring item can also be a “Transfer”, such as a monthly share paid into the joint account: pick the account it leaves and the account it reaches, with no category. Any transfer between those two accounts counts as that occurrence, whatever its label, and “Enter it” opens a transfer to enter. Transfers are never suggested: add them by hand.",
      ],
      link: { to: "/recurring", label: "Open the recurring items" },
    },
    {
      id: "categories",
      title: "Categories and rules",
      paragraphs: [
        "Categories have two levels: a category and its subcategories, for spending or for income. Rename, move or delete them as you like: deleting one sends its transactions back to “to categorise”.",
        "A third kind, “Savings & investments”, holds the money you move to savings or investments the app does not track as an account (a PEA, a life insurance, a PER, a savings account you do not import). It is never spending nor income: it stays in the net and the savings rate, as a transfer to one of your savings accounts does. A transfer between two accounts of the app stays a transfer, whatever its category. A savings rule catches both outflows and money brought back.",
        "Click the calendar icon next to a category's name (or its “Next month from …” note) to shift it to the next month from a day of the month: a salary paid on the 20th (or the 28th) for the next month's spending then counts for that month in the budget, the overview and the reviews, and the net is no longer negative while waiting for payday. A subcategory follows its parent unless it has a setting of its own (or “Never”). The setting applies to past transactions too: “Preview” says how many change month and which locked plans see their review change. For a full first month, import the previous month's statement too.",
        "The same panel says whether an expense category is paid once in the month (rent, a subscription, an insurance premium): its target on the overview is then not compared with the pace of the month, and paying it in full is not a warning. Housing and Subscriptions are set so by default, and a subcategory follows its parent unless it says otherwise.",
        "Rules run in order, and the first one that matches sets the category of each import and manual entry. A rule looks at the label (case, spacing and accents ignored), and can also check the amount and the account. They can be applied again to past transactions.",
        "The household owner can restore the default categories, named in their language: defaults still there keep their transactions, rules and plan targets, copies merge into them, missing ones come back, and every other category is deleted. A preview lists what goes and what it implies before anything changes.",
      ],
      link: { to: "/categories", label: "Open the categories" },
    },
    {
      id: "plans",
      title: "Budget plans",
      paragraphs: [
        "A budget plan holds a monthly target per spending category for a calendar period: a year, a semester or a quarter. A category's envelope is its monthly target times the plan's months, so a cheaper month offsets a dearer one. A parent category without a target of its own takes the sum of its subcategories'. With a joint account, say under each target who pays it, the joint account or personal ones (even once the plan is locked): the “Joint accounts” and “Only mine” views then judge only their own targets, while “Household” keeps them all.",
        "A savings category can have a monthly objective in the plan, set like a target. An objective is a minimum: saving more is good.",
        "A new plan starts with the targets of the latest one. You can change its targets and its expected income until the end of its first month; the note can change at any time.",
        "When life changes (a new job, a raise, a new recurring expense), close the plan early: it keeps its targets and is reviewed over its months, and a replacement plan, pre-filled with the same targets, covers the rest of the period. Change the targets there.",
      ],
      link: { to: "/budget", label: "Open the budget" },
    },
    {
      id: "matrix",
      title: "The budget table",
      paragraphs: [
        "The budget page shows your spending per category and month next to the monthly target of the plan covering each month. A cell is green when spending is more than the margin (5 % by default) below the target, grey within it, burnt orange above it; without a target it has no colour.",
        "Click a cell to see its transactions. The “to categorise” row is always shown, so totals are never silently wrong.",
        "Savings categories have their own section below the spending, with their objective and their own total, never counted in the spending total. There the colours turn round: green when you saved more than the margin above the objective, burnt orange when you saved more than the margin below it.",
      ],
      link: { to: "/budget", label: "Open the budget" },
    },
    {
      id: "review",
      title: "Plan review",
      paragraphs: [
        "“See the review” on the budget page tells where a plan stands. While it runs: the share of time elapsed, what was expected by now, and the spending projected at the end of the plan. Completed months count as spent, the others at least at their target, or at your actual pace if it is higher: rent paid on the 1st is not a drift, while spending above the target shows at once.",
        "Categories projected above their envelope, or savings categories projected below their objective, are listed as drifting, largest gap first. Once the plan is over, the review gives the final result with income, savings and the planned savings when the plan has an expected income, next to the sum of your savings objectives. The table by category and the comparison show the savings categories in a section of their own.",
        "Below: the money flows (where the income went: spending, savings, what is left unallocated; tick the box to detail the subcategories; money in is blue, spending ochre within its target and burnt orange over it, savings green when they meet their objectives and pale green below them, the rest grey), the projected gap per category, the cumulative spending day by day against the envelope line, and a comparison with the previous plan (or any other) on monthly figures. While transactions are left to categorise, the review is marked provisional.",
      ],
      link: { to: "/budget/review", label: "Open the review" },
    },
    {
      id: "overview",
      title: "Overview",
      paragraphs: [
        "The overview sums up a month: spending, income, net (with the part put in savings categories) and savings rate, compared with the previous month and the 12-month average, then the month's top categories and its spending against your budget. The overview stays on one month: “See the month's report” opens its report, and the reports tab looks back over longer periods.",
        "“Targets this month” lists each category with a monthly target in the plan covering the month, the most used first: what it spent, what is left (or the overrun) and a bar. It says “Watch” from the warning threshold (80 % of the target by default; the household owner can change it there) and “Over” beyond the target. For the current month, a line on the bar marks how much of the month has gone by: spending ahead of that line is going faster than the calendar. One-off categories, paid once in the month, have no line and no “Watch”: paid as planned, they stay on track. Click a category to see its transactions.",
        "“Still expected this month” lists the recurring items still to come by the end of the month, late ones (up to a month back) first, each with “Enter it” and “Skip”, and the projected balance at the end of the month: today's balance of the cash accounts in view plus everything listed. It uses real dates, not budget months: a salary expected on the 28th counts this month. A recurring transfer counts as money leaving one account and reaching the other: in a view holding both, it changes nothing.",
        "“Household” counts every account you can see, “Joint accounts” only the household's joint accounts (offered once there is one), “Only mine” your own accounts without the joint ones. In those two, a transfer with an account left out shows in the net: what you pay into the joint account is paid out of yours and paid into it, so each view's savings stay right.",
      ],
      link: { to: "/", label: "Open the overview" },
    },
    {
      id: "wealth",
      title: "Wealth",
      paragraphs: [
        "The wealth tab follows what you own and owe at the end of each month, like a spreadsheet: categories (savings accounts, current accounts, stocks, crypto, bonds, private equity, gold, real estate, equipment, exotic, debts), each with its colour, and in each the lines you add: one per holding, such as “PEA Fortuneo” or “Crédit immobilier”. A line is yours; choose whether the household sees it, only you, or whether it is the household's joint holding.",
        "Every line is entered by hand, your current accounts and savings accounts too: add one line per account (“Livret A”, “Compte joint”…) in its category, then enter the values once a month with “Update this month”, which shows each line's last value: change what moved and save. You can also click any value in the table to change that month. A month without a value carries the previous one, shown in grey italics. A debt is entered as what is still owed and counts against your net worth.",
        "The table shows each category's total, gross assets, debts, net worth and its change month by month, and each category's share of what you own. Click a line's name to rename it, move it, or close it from a month once sold or repaid: it keeps its history. The view covers the household, the joint lines or only yours. It opens on the last 12 months, from the wealth start at the earliest (on the members page; without one, the analyses start); choose any other months with “From” and “To”, and “Last 12 months” brings it back.",
        "Below the table, charts cover the same months: net worth over time by category; the allocation of the last month as rings (categories inside, their lines outside); who holds what, each category's column as wide as its share and split between you, the other members and the joint holding; and what moved net worth from the first month to the last, category by category. Point at a ring or a column to read it, or open “Show the data” under each chart. The net worth tile also gives the change over the months shown, the debts tile the share of your gross assets they weigh.",
      ],
      link: { to: "/wealth", label: "Open your wealth" },
    },
    {
      id: "reports",
      title: "Reports",
      paragraphs: [
        "Reports look back over any period of budget months: this month, last month, this quarter, this year, last year, the last 12 months, or a custom period with a first and a last month (10 years at most). They follow the overview's rules: budget months, split transactions by part, transfers between your accounts left out. Once the household owner has set when analyses start (on the members page), a report begins no earlier.",
        "Each report compares the period with the one just before, of the same length: a year with the year before, a quarter with the quarter before. It gives the totals (income, spending, net, the part saved and the savings rate), a table by category in three sections (income, spending, savings) with the subcategories, the monthly average, each category's share of its section and the change, a month-by-month chart, and the money flows of the period, drawn as on the plan review but without targets.",
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
        "On the same page, the owner can set when analyses start: the first month your history is complete. The overview, the reports and the detection of recurring items leave earlier months out; transactions, balances and budget plans stay as they are. The wealth has its own start, for a history that goes back further than your spending's: the wealth page opens from it.",
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
      account: "Add your bank accounts",
      import: "Import a statement",
      categorise: "Categorise your transactions",
      plan: "Set your monthly targets",
      invite: "Invite your household (optional)",
    },
    done: "Done",
  },
};

export const guideFr: typeof guideEn = {
  title: "Utiliser Kwak Finance",
  intro:
    "Kwak Finance réunit les comptes, les dépenses, le budget et le patrimoine de votre foyer, sur votre propre ordinateur. Ce guide parcourt chaque page. Les onglets du haut mènent aux pages du quotidien ; les catégories, les membres, le journal d'activité, la langue et le thème sont dans le menu à votre nom, à côté de ce guide. Pour installer, lancer ou mettre à jour l'application, voyez « Lancer et arrêter l'application » en bas de chaque page.",
  contents: "Sommaire",
  sections: [
    {
      id: "start",
      title: "Bien démarrer",
      paragraphs: [
        "Cinq étapes mènent d'une application vide à un budget qui fonctionne, et la liste « Bien démarrer » de la vue d'ensemble les coche au fur et à mesure : ajouter vos comptes bancaires, importer un relevé pour chacun, catégoriser les opérations, fixer vos objectifs mensuels dans un plan budgétaire, et inviter le reste du foyer si vous partagez vos finances.",
        "Ensuite, une routine mensuelle suffit : importer les nouveaux relevés, catégoriser ce que les règles n'ont pas fait, puis consulter le bilan du plan.",
      ],
      link: { to: "/", label: "Ouvrir la vue d'ensemble" },
    },
    {
      id: "accounts",
      title: "Comptes",
      paragraphs: [
        "Ajoutez chaque compte bancaire avec son établissement et son type (courant, livret…). Sa date d'ouverture est le premier jour du premier relevé que vous importerez, et son solde d'ouverture le solde ce jour-là, avant sa première opération : les opérations antérieures sont ignorées.",
        "Un compte est visible de vous seul, de tout le foyer, ou c'est le compte commun du foyer (celui qui paie les dépenses partagées : loyer, assistante maternelle, courses…) ; seul le membre qui l'a créé peut changer cela. Gardez les mêmes catégories sur tous les comptes : le compte dit qui paie, la catégorie pour quoi. Un compte clôturé garde son historique et peut être rouvert.",
      ],
      link: { to: "/accounts", label: "Ouvrir les comptes" },
    },
    {
      id: "import",
      title: "Importer des relevés",
      paragraphs: [
        "Depuis un compte, « Importer » prend l'export CSV de la banque (Société Générale ou Helios pour l'instant). Un aperçu montre les nouvelles opérations, celles déjà importées et les erreurs avec leur numéro de ligne : rien n'est enregistré avant votre confirmation, et importer deux fois le même fichier n'ajoute rien.",
        "Les opérations saisies à la main pendant le mois ne sont pas ajoutées deux fois : une ligne du relevé de même montant, sur le même compte et à 5 jours au plus d'une saisie est marquée « Déjà saisie » et reprend cette saisie. La saisie garde votre libellé et votre catégorie, et prend la date de la banque (le libellé de la banque s'affiche au survol dans Opérations). Si un rapprochement est faux, « Pas la même » importe la ligne comme une nouvelle opération. L'aperçu liste aussi ce que vous avez saisi dans les dates du relevé et qui n'y figure pas : une faute de frappe, ou une opération que la banque n'a pas encore passée. Annuler l'import rend les saisies telles que vous les aviez entrées.",
        "Après l'import, le solde calculé est comparé à celui de la banque. S'ils diffèrent, vérifiez le solde et la date d'ouverture du compte, ou importez la période manquante. Un import peut être annulé depuis la liste des imports précédents.",
      ],
      link: { to: "/accounts", label: "Ouvrir les comptes" },
    },
    {
      id: "transactions",
      title: "Opérations",
      paragraphs: [
        "Filtrez par compte, catégorie, dates ou libellé. Sélectionnez plusieurs opérations pour leur donner une catégorie d'un coup, ou choisissez-la sur une ligne. « Règle » crée une règle à partir du libellé d'une opération, pour que les prochains imports soient catégorisés à votre place.",
        "Chaque opération garde sa vraie date, et compte aussi pour un mois budgétaire : celui de sa date, ou le suivant si sa catégorie le prévoit ; la liste indique « compté en … » sous la date quand il diffère. Cliquez sur cette mention (ou sur l'icône calendrier à côté de la date) pour le fixer à la main (le mois de la date, celui d'avant ou celui d'après), par ex. pour un salaire versé en avance ; « Automatique » revient à la règle de la catégorie. Les virements entre vos comptes restent dans leur mois. Le filtre « Mois budgétaire » montre ce qu'une case du budget compte.",
        "Les transferts entre vos propres comptes sont détectés et proposés au rapprochement (même montant, 3 jours d'écart au plus) : rapprochés, ils ne comptent ni comme dépense ni comme revenu. Quand la détection en manque un, « Lier à… » sur une ligne liste les opérations du même montant dans l'autre sens sur vos autres comptes, à 31 jours près, pour choisir l'autre côté.",
        "« Ajouter une opération » enregistre les espèces ou ce que votre banque n'exporte pas ; choisissez-y sa catégorie, ou laissez faire les règles. Choisissez « Virement » pour passer de l'argent d'un de vos comptes à un autre, par exemple votre quote-part versée sur le compte commun : les deux côtés sont saisis d'un coup, déjà liés, avec pour libellés « Virement vers … » et « Virement depuis … » sauf si vous en donnez un. Changez le montant ou la date d'un côté et l'autre suit ; supprimez-en un et les deux partent. Dès qu'un côté vient d'un relevé, son montant est celui de la banque : celui de l'autre côté ne peut plus changer.",
        "« Détails » sur une ligne ajoute une note (cherchée avec le libellé) et ventile l'opération sur plusieurs catégories, par exemple un ticket de supermarché avec les courses, l'entretien de la maison et la pharmacie : saisissez chaque partie sauf la dernière, qui prend le reste, si bien que les parties tombent toujours juste. Chaque partie compte dans sa catégorie, dans le budget, la vue d'ensemble et la revue ; l'opération compte dans le mois que donne la catégorie de sa première partie. Les règles et la catégorisation en lot laissent une opération ventilée telle quelle ; « Annuler la ventilation » la remet à catégoriser.",
      ],
      link: { to: "/transactions", label: "Ouvrir les opérations" },
    },
    {
      id: "recurring",
      title: "Récurrences",
      paragraphs: [
        "« Récurrences », en haut des opérations, liste ce qui revient régulièrement : salaire, loyer, abonnements, un marché chaque semaine. Chaque récurrence a un compte, un libellé cherché dans celui des opérations (comme une règle), un montant, une fréquence (hebdomadaire, mensuelle, trimestrielle ou annuelle), un jour et une catégorie. Cochez « Montant variable » pour une facture qui change, comme l'électricité : Kwak attend alors la moyenne de ses 3 derniers paiements, affichée « ≈ ».",
        "Kwak ne saisit jamais rien tout seul. Une opération du compte de la récurrence dont le libellé correspond, à 10 % près du montant (n'importe quel montant pour une récurrence variable) et à 5 jours près de la date, compte pour cette échéance. Sans elle, l'échéance passe en retard 5 jours après sa date : « La saisir » ouvre une nouvelle opération remplie avec le compte, le libellé, la catégorie et le montant, à la date prévue (aujourd'hui si elle est encore à venir), à vérifier puis enregistrer. « Sauter » indique qu'une échéance n'aura pas lieu (un abonnement suspendu un mois) ; « Historique » montre les échéances passées et rétablit une échéance sautée. Mettez une récurrence en pause, ou donnez-lui une date de fin, quand elle s'arrête.",
        "Les suggestions listent les séries trouvées sur les 6 derniers mois : au moins 3 opérations d'un même compte avec le même libellé, chaque semaine ou chaque mois, les montants à 10 % près. « Suivre » ouvre le formulaire rempli, à vérifier puis enregistrer ; « Ignorer » ne la propose plus. Les récurrences trimestrielles et annuelles sont trop rares pour être détectées : ajoutez-les à la main.",
        "Une récurrence peut aussi être un « Virement », comme une quote-part mensuelle versée sur le compte commun : choisissez le compte qu'il quitte et celui qu'il rejoint, sans catégorie. Tout virement entre ces deux comptes compte pour l'échéance, quel que soit son libellé, et « La saisir » ouvre un virement à saisir. Les virements ne sont jamais suggérés : ajoutez-les à la main.",
      ],
      link: { to: "/recurring", label: "Ouvrir les récurrences" },
    },
    {
      id: "categories",
      title: "Catégories et règles",
      paragraphs: [
        "Les catégories ont deux niveaux : une catégorie et ses sous-catégories, de dépense ou de revenu. Renommez-les, déplacez-les ou supprimez-les à votre guise : en supprimer une renvoie ses opérations « à catégoriser ».",
        "Un troisième type, « Épargne et placements », reçoit l'argent mis de côté ou placé sur des supports que l'app ne suit pas comme un compte (un PEA, une assurance-vie, un PER, un livret que vous n'importez pas). Ce n'est jamais une dépense ni un revenu : il reste dans le solde net et le taux d'épargne, comme un virement vers un de vos livrets. Un virement entre deux comptes de l'app reste un virement, quelle que soit sa catégorie. Une règle d'épargne prend à la fois les sorties et l'argent rapatrié.",
        "Cliquez sur l'icône calendrier à côté du nom d'une catégorie (ou sur sa mention « Mois suivant à partir du … ») pour la décaler au mois suivant à partir d'un jour du mois : un salaire versé le 20 (ou le 28) pour les dépenses du mois suivant compte alors pour ce mois-là dans le budget, la vue d'ensemble et les bilans, et le solde net n'est plus négatif en attendant la paie. Une sous-catégorie suit sa catégorie parente, sauf si elle a son propre réglage (ou « Jamais »). Le réglage vaut aussi pour les opérations passées : « Aperçu » dit combien changent de mois et quels plans verrouillés voient leur bilan changer. Pour un premier mois complet, importez aussi le relevé du mois précédent.",
        "Le même panneau indique si une catégorie de dépense est payée une fois dans le mois (loyer, abonnement, prime d'assurance) : son objectif sur la vue d'ensemble n'est alors pas comparé au rythme du mois, et la payer en entier ne déclenche pas d'alerte. Logement et Abonnements le sont par défaut, et une sous-catégorie suit sa catégorie parente sauf si elle dit autrement.",
        "Les règles s'appliquent dans l'ordre, et la première qui correspond fixe la catégorie de chaque import et de chaque saisie. Une règle regarde le libellé (sans tenir compte de la casse, des espaces ni des accents), et peut aussi vérifier le montant et le compte. Elles peuvent être réappliquées aux opérations passées.",
        "Le propriétaire du foyer peut rétablir les catégories par défaut, nommées dans sa langue : celles encore présentes gardent leurs opérations, règles et objectifs de plans, les doublons sont fusionnés avec elles, celles qui manquent reviennent, et toutes les autres sont supprimées. Un aperçu liste ce qui part et ce que cela implique avant tout changement.",
      ],
      link: { to: "/categories", label: "Ouvrir les catégories" },
    },
    {
      id: "plans",
      title: "Plans budgétaires",
      paragraphs: [
        "Un plan budgétaire contient un objectif mensuel par catégorie de dépense pour une période du calendrier : une année, un semestre ou un trimestre. L'enveloppe d'une catégorie est son objectif mensuel multiplié par le nombre de mois du plan : un mois moins cher compense un mois plus cher. Une catégorie parente sans objectif propre prend la somme de ses sous-catégories. Avec un compte commun, indiquez sous chaque objectif qui le paie, le compte commun ou les comptes perso (même une fois le plan verrouillé) : les vues « Comptes communs » et « Seulement les miens » ne jugent alors que leurs propres objectifs, « Foyer » les garde tous.",
        "Une catégorie d'épargne peut avoir un objectif mensuel dans le plan, saisi comme un objectif de dépense. C'est un minimum : épargner davantage est une bonne chose.",
        "Un nouveau plan reprend les objectifs du plan le plus récent. Ses objectifs et son revenu attendu se modifient jusqu'à la fin de son premier mois ; la note se modifie à tout moment.",
        "Quand la vie change (nouvel emploi, augmentation, nouvelle dépense récurrente), clôturez le plan par anticipation : il garde ses objectifs et sera évalué sur ses mois, et un plan de remplacement, pré-rempli avec les mêmes objectifs, couvre le reste de la période. Modifiez les objectifs là.",
      ],
      link: { to: "/budget", label: "Ouvrir le budget" },
    },
    {
      id: "matrix",
      title: "Le tableau du budget",
      paragraphs: [
        "La page Budget montre vos dépenses par catégorie et par mois à côté de l'objectif mensuel du plan qui couvre chaque mois. Une case est verte quand la dépense est sous l'objectif de plus que la marge (5 % par défaut), grise dans la marge, terre brûlée au-dessus ; sans objectif, elle n'a pas de couleur.",
        "Cliquez sur une case pour voir ses opérations. La ligne « à catégoriser » est toujours affichée, pour que les totaux ne soient jamais faux en silence.",
        "Les catégories d'épargne ont leur propre section sous les dépenses, avec leur objectif et leur propre total, jamais compté dans le total des dépenses. Les couleurs s'y inversent : vert quand vous avez épargné plus que la marge au-dessus de l'objectif, terre brûlée quand vous êtes en dessous de plus que la marge.",
      ],
      link: { to: "/budget", label: "Ouvrir le budget" },
    },
    {
      id: "review",
      title: "Bilan du plan",
      paragraphs: [
        "« Voir le bilan » sur la page Budget indique où en est un plan. Pendant le plan : la part du temps écoulé, ce qui était prévu à ce jour, et la dépense projetée en fin de plan. Les mois terminés comptent tels quels, les autres au moins pour leur objectif, ou à votre rythme réel s'il est plus élevé : un loyer payé le 1er n'est pas une dérive, alors qu'une dépense au-dessus de l'objectif apparaît tout de suite.",
        "Les catégories projetées au-dessus de leur enveloppe, ou les catégories d'épargne projetées sous leur objectif, sont listées comme dérapant, du plus gros écart au plus petit. Une fois le plan terminé, le bilan donne le résultat final avec les revenus, l'épargne et l'épargne prévue quand le plan a un revenu attendu, à côté de la somme de vos objectifs d'épargne. Le tableau par catégorie et la comparaison montrent les catégories d'épargne dans une section à part.",
        "Plus bas : les flux du plan (où sont allés les revenus : dépenses, épargne, restant non alloué ; cochez la case pour détailler les sous-catégories ; les entrées sont en bleu, les dépenses en ocre dans l'objectif et en terre brûlée au-dessus, l'épargne en vert quand elle atteint ses objectifs et en vert pâle en dessous, le reste en gris), l'écart projeté par catégorie, les dépenses cumulées jour après jour face à la ligne d'enveloppe, et une comparaison avec le plan précédent (ou un autre) en chiffres mensuels. Tant que des opérations restent à catégoriser, le bilan est marqué provisoire.",
      ],
      link: { to: "/budget/review", label: "Ouvrir le bilan" },
    },
    {
      id: "overview",
      title: "Vue d'ensemble",
      paragraphs: [
        "La vue d'ensemble résume un mois : dépenses, revenus, solde (avec la part mise en épargne et placements) et taux d'épargne, comparés au mois précédent et à la moyenne sur 12 mois, puis les principales catégories du mois et ses dépenses face à votre budget. La vue d'ensemble reste sur un mois : « Voir le rapport du mois » ouvre son rapport, et l'onglet Rapports revient sur des périodes plus longues.",
        "« Objectifs du mois » liste chaque catégorie qui a un objectif mensuel dans le plan du mois, la plus avancée d'abord : ce qu'elle a dépensé, ce qui reste (ou le dépassement) et une barre. Elle indique « Attention » à partir du seuil d'alerte (80 % de l'objectif par défaut ; le propriétaire du foyer peut le changer ici) et « Dépassé » au-delà de l'objectif. Pour le mois en cours, un trait sur la barre marque la part du mois écoulée : une dépense en avance sur ce trait va plus vite que le calendrier. Les catégories ponctuelles, payées une fois dans le mois, n'ont ni trait ni « Attention » : payées comme prévu, elles restent dans les clous. Cliquez sur une catégorie pour voir ses opérations.",
        "« Encore attendu ce mois-ci » liste les récurrences encore à venir d'ici la fin du mois, les retards (jusqu'à un mois en arrière) d'abord, chacune avec « La saisir » et « Sauter », et le solde prévu en fin de mois : le solde d'aujourd'hui des comptes courants et d'épargne de la vue, plus tout ce qui est listé. Il suit les vraies dates, pas les mois budgétaires : un salaire attendu le 28 compte ce mois-ci. Un virement récurrent compte comme de l'argent qui quitte un compte et en rejoint un autre : dans une vue qui contient les deux, il ne change rien.",
        "« Foyer » compte tous les comptes que vous voyez, « Comptes communs » seulement les comptes communs du foyer (proposé dès qu'il y en a un), « Seulement les miens » vos propres comptes, sans les comptes communs. Dans ces deux vues, un virement avec un compte laissé de côté compte dans le solde net : ce que vous versez au compte commun sort de vos comptes et y entre, donc l'épargne de chaque vue reste juste.",
      ],
      link: { to: "/", label: "Ouvrir la vue d'ensemble" },
    },
    {
      id: "wealth",
      title: "Patrimoine",
      paragraphs: [
        "L'onglet Patrimoine suit ce que vous possédez et devez à la fin de chaque mois, comme un tableur : des catégories (livrets, comptes courants, actions, cryptos, obligations, private equity, or, immobilier, matériels, exotiques, dettes), chacune avec sa couleur, et dans chacune les lignes que vous ajoutez : une par avoir, comme « PEA Fortuneo » ou « Crédit immobilier ». Une ligne est à vous ; choisissez si le foyer la voit, vous seul, ou si c'est un avoir commun du foyer.",
        "Chaque ligne se saisit à la main, comptes courants et livrets compris : ajoutez une ligne par compte (« Livret A », « Compte joint »…) dans sa catégorie, puis saisissez les valeurs une fois par mois avec « Mettre à jour ce mois-ci », qui affiche la dernière valeur de chaque ligne : changez ce qui a bougé et enregistrez. Vous pouvez aussi cliquer sur une valeur du tableau pour changer ce mois-là. Un mois sans valeur reprend la précédente, affichée en gris italique. Une dette se saisit pour ce qui reste dû et compte en moins dans votre patrimoine net.",
        "Le tableau montre le total de chaque catégorie, l'actif brut, les dettes, le patrimoine net et sa variation d'un mois à l'autre, et la part de chaque catégorie dans ce que vous possédez. Cliquez sur le nom d'une ligne pour la renommer, la déplacer ou la clôturer à partir d'un mois une fois vendue ou remboursée : elle garde son historique. La vue couvre le foyer, les lignes communes ou seulement les vôtres. Elle s'ouvre sur les 12 derniers mois, au plus tôt à partir du début du patrimoine (page Membres ; sans réglage, le début des analyses) ; choisissez d'autres mois avec « Du » et « Au », et « 12 derniers mois » la ramène.",
        "Sous le tableau, des graphiques couvrent les mêmes mois : le patrimoine dans le temps par catégorie ; la répartition du dernier mois en anneaux (les catégories au centre, leurs lignes autour) ; qui détient quoi, chaque catégorie en colonne aussi large que sa part et partagée entre vous, les autres membres et l'avoir commun ; et ce qui a fait bouger le patrimoine du premier mois au dernier, catégorie par catégorie. Pointez un anneau ou une colonne pour le lire, ou ouvrez « Afficher les données » sous chaque graphique. La tuile du patrimoine net donne aussi la variation sur les mois affichés, celle des dettes leur poids dans votre actif brut.",
      ],
      link: { to: "/wealth", label: "Ouvrir votre patrimoine" },
    },
    {
      id: "reports",
      title: "Rapports",
      paragraphs: [
        "Les rapports reviennent sur n'importe quelle période de mois budgétaires : ce mois-ci, le mois dernier, ce trimestre, cette année, l'année dernière, les 12 derniers mois, ou une période libre avec un premier et un dernier mois (10 ans au plus). Ils suivent les règles de la vue d'ensemble : mois budgétaires, opérations ventilées comptées par partie, virements entre vos comptes laissés de côté. Si le propriétaire du foyer a fixé le début des analyses (page Membres), un rapport ne commence pas avant.",
        "Chaque rapport compare la période à celle juste avant, de même durée : une année à l'année d'avant, un trimestre au trimestre d'avant. Il donne les totaux (revenus, dépenses, solde, la part épargnée et le taux d'épargne), un tableau par catégorie en trois sections (revenus, dépenses, épargne) avec les sous-catégories, la moyenne par mois, la part de chaque catégorie dans sa section et l'évolution, un graphique mois par mois, et les flux de la période, dessinés comme dans le bilan du plan mais sans objectifs.",
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
        "Sur la même page, le propriétaire peut fixer le début des analyses : le premier mois où votre historique est complet. La vue d'ensemble, les rapports et la détection des récurrences laissent de côté les mois précédents ; les opérations, les soldes et les plans de budget restent tels quels. Le patrimoine a son propre début, pour un historique qui remonte plus loin que celui des dépenses : la page Patrimoine s'ouvre à partir de lui.",
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
      account: "Ajouter vos comptes bancaires",
      import: "Importer un relevé",
      categorise: "Catégoriser vos opérations",
      plan: "Fixer vos objectifs mensuels",
      invite: "Inviter votre foyer (facultatif)",
    },
    done: "Fait",
  },
};
