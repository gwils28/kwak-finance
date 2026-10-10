/**
 * "Using Kwak Finance": one section per feature, and the overview's "Getting started" checklist.
 * Keep it true to the app: a PR that changes what users see updates it, in both languages.
 */

/** The pages a guide section can open. */
export type GuidePage =
  | "/"
  | "/accounts"
  | "/transactions"
  | "/budget"
  | "/budget/review"
  | "/categories"
  | "/members";
export type GuideSection = {
  id: string;
  title: string;
  paragraphs: string[];
  link?: { to: GuidePage; label: string };
};

export const guideEn = {
  title: "Using Kwak Finance",
  intro:
    "Kwak Finance keeps your household's accounts, spending and budget in one place, on your own computer. This guide walks through each page. To install, start or update the app, see “How to run the app” at the bottom of every page.",
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
        "An account is visible to every household member or only to you; only its owner can change that. A closed account keeps its history and can be reopened.",
      ],
      link: { to: "/accounts", label: "Open the accounts" },
    },
    {
      id: "import",
      title: "Importing statements",
      paragraphs: [
        "From an account, “Import” takes the bank's CSV export (Société Générale for now). A preview shows the new operations, the ones already imported and the errors with their line numbers: nothing is saved until you confirm, and importing the same file twice adds nothing.",
        "After the import, the computed balance is compared with the bank's. If they differ, check the account's opening balance and date, or import the missing period. An import can be rolled back from the list of previous imports.",
      ],
      link: { to: "/accounts", label: "Open the accounts" },
    },
    {
      id: "transactions",
      title: "Transactions",
      paragraphs: [
        "Filter by account, category, dates or label. Select several transactions to give them a category at once, or pick it on a single row. “Rule” creates a rule from a transaction's label, so the next imports are categorised for you.",
        "Transfers between your own accounts are detected and offered for linking: linked, they count neither as spending nor as income. “Add a transaction” records cash or anything your bank does not export.",
      ],
      link: { to: "/transactions", label: "Open the transactions" },
    },
    {
      id: "categories",
      title: "Categories and rules",
      paragraphs: [
        "Categories have two levels: a category and its subcategories, for spending or for income. Rename, move or delete them as you like: deleting one sends its transactions back to “to categorise”.",
        "Rules run in order, and the first one that matches sets the category of each import and manual entry. A rule looks at the label (case, spacing and accents ignored), and can also check the amount and the account. They can be applied again to past transactions.",
      ],
      link: { to: "/categories", label: "Open the categories" },
    },
    {
      id: "plans",
      title: "Budget plans",
      paragraphs: [
        "A budget plan holds a monthly target per spending category for a calendar period: a year, a semester or a quarter. A category's envelope is its monthly target times the plan's months, so a cheaper month offsets a dearer one. A parent category without a target of its own takes the sum of its subcategories'.",
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
      ],
      link: { to: "/budget", label: "Open the budget" },
    },
    {
      id: "review",
      title: "Plan review",
      paragraphs: [
        "“See the review” on the budget page tells where a plan stands. While it runs: the share of time elapsed, what was expected by now, and the spending projected at the end of the plan. Completed months count as spent, the others at least at their target, or at your actual pace if it is higher: rent paid on the 1st is not a drift, while spending above the target shows at once.",
        "Categories projected above their envelope are listed as drifting, largest overrun first. Once the plan is over, the review gives the final result with income, savings and the planned savings when the plan has an expected income.",
        "Below: the projected gap per category, the cumulative spending day by day against the envelope line, and a comparison with the previous plan (or any other) on monthly figures. While transactions are left to categorise, the review is marked provisional.",
      ],
      link: { to: "/budget/review", label: "Open the review" },
    },
    {
      id: "overview",
      title: "Overview",
      paragraphs: [
        "The overview sums up a month: spending, income, net and savings rate, compared with the previous month and the 12-month average, then the spending by category, the last 12 months and this month's spending against your budget.",
        "“Household” counts every account you can see, “Only mine” your own accounts.",
      ],
      link: { to: "/", label: "Open the overview" },
    },
    {
      id: "members",
      title: "Members and security",
      paragraphs: [
        "The household owner invites members with a link that works once and expires after 7 days; Kwak Finance sends no email, so send it yourself.",
        "Everyone signs in with a password and a code from an authenticator app. Keep the recovery codes shown at set-up: each lets you sign in once if you lose your phone.",
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
    "Kwak Finance réunit les comptes, les dépenses et le budget de votre foyer, sur votre propre ordinateur. Ce guide parcourt chaque page. Pour installer, lancer ou mettre à jour l'application, voyez « Lancer et arrêter l'application » en bas de chaque page.",
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
        "Un compte est visible de tout le foyer ou de vous seul ; seul son titulaire peut changer cela. Un compte clôturé garde son historique et peut être rouvert.",
      ],
      link: { to: "/accounts", label: "Ouvrir les comptes" },
    },
    {
      id: "import",
      title: "Importer des relevés",
      paragraphs: [
        "Depuis un compte, « Importer » prend l'export CSV de la banque (Société Générale pour l'instant). Un aperçu montre les nouvelles opérations, celles déjà importées et les erreurs avec leur numéro de ligne : rien n'est enregistré avant votre confirmation, et importer deux fois le même fichier n'ajoute rien.",
        "Après l'import, le solde calculé est comparé à celui de la banque. S'ils diffèrent, vérifiez le solde et la date d'ouverture du compte, ou importez la période manquante. Un import peut être annulé depuis la liste des imports précédents.",
      ],
      link: { to: "/accounts", label: "Ouvrir les comptes" },
    },
    {
      id: "transactions",
      title: "Opérations",
      paragraphs: [
        "Filtrez par compte, catégorie, dates ou libellé. Sélectionnez plusieurs opérations pour leur donner une catégorie d'un coup, ou choisissez-la sur une ligne. « Règle » crée une règle à partir du libellé d'une opération, pour que les prochains imports soient catégorisés à votre place.",
        "Les transferts entre vos propres comptes sont détectés et proposés au rapprochement : rapprochés, ils ne comptent ni comme dépense ni comme revenu. « Ajouter une opération » enregistre les espèces ou ce que votre banque n'exporte pas.",
      ],
      link: { to: "/transactions", label: "Ouvrir les opérations" },
    },
    {
      id: "categories",
      title: "Catégories et règles",
      paragraphs: [
        "Les catégories ont deux niveaux : une catégorie et ses sous-catégories, de dépense ou de revenu. Renommez-les, déplacez-les ou supprimez-les à votre guise : en supprimer une renvoie ses opérations « à catégoriser ».",
        "Les règles s'appliquent dans l'ordre, et la première qui correspond fixe la catégorie de chaque import et de chaque saisie. Une règle regarde le libellé (sans tenir compte de la casse, des espaces ni des accents), et peut aussi vérifier le montant et le compte. Elles peuvent être réappliquées aux opérations passées.",
      ],
      link: { to: "/categories", label: "Ouvrir les catégories" },
    },
    {
      id: "plans",
      title: "Plans budgétaires",
      paragraphs: [
        "Un plan budgétaire contient un objectif mensuel par catégorie de dépense pour une période du calendrier : une année, un semestre ou un trimestre. L'enveloppe d'une catégorie est son objectif mensuel multiplié par le nombre de mois du plan : un mois moins cher compense un mois plus cher. Une catégorie parente sans objectif propre prend la somme de ses sous-catégories.",
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
      ],
      link: { to: "/budget", label: "Ouvrir le budget" },
    },
    {
      id: "review",
      title: "Bilan du plan",
      paragraphs: [
        "« Voir le bilan » sur la page Budget indique où en est un plan. Pendant le plan : la part du temps écoulé, ce qui était prévu à ce jour, et la dépense projetée en fin de plan. Les mois terminés comptent tels quels, les autres au moins pour leur objectif, ou à votre rythme réel s'il est plus élevé : un loyer payé le 1er n'est pas une dérive, alors qu'une dépense au-dessus de l'objectif apparaît tout de suite.",
        "Les catégories projetées au-dessus de leur enveloppe sont listées comme dérapant, du plus gros dépassement au plus petit. Une fois le plan terminé, le bilan donne le résultat final avec les revenus, l'épargne et l'épargne prévue quand le plan a un revenu attendu.",
        "Plus bas : l'écart projeté par catégorie, les dépenses cumulées jour après jour face à la ligne d'enveloppe, et une comparaison avec le plan précédent (ou un autre) en chiffres mensuels. Tant que des opérations restent à catégoriser, le bilan est marqué provisoire.",
      ],
      link: { to: "/budget/review", label: "Ouvrir le bilan" },
    },
    {
      id: "overview",
      title: "Vue d'ensemble",
      paragraphs: [
        "La vue d'ensemble résume un mois : dépenses, revenus, solde et taux d'épargne, comparés au mois précédent et à la moyenne sur 12 mois, puis les dépenses par catégorie, les 12 derniers mois et les dépenses du mois face à votre budget.",
        "« Foyer » compte tous les comptes que vous voyez, « Seulement les miens » vos propres comptes.",
      ],
      link: { to: "/", label: "Ouvrir la vue d'ensemble" },
    },
    {
      id: "members",
      title: "Membres et sécurité",
      paragraphs: [
        "Le propriétaire du foyer invite des membres avec un lien valable une fois et pendant 7 jours ; Kwak Finance n'envoie pas d'e-mail, transmettez-le vous-même.",
        "Chacun se connecte avec un mot de passe et un code d'application d'authentification. Gardez les codes de secours affichés à la configuration : chacun permet de se connecter une fois si vous perdez votre téléphone.",
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
