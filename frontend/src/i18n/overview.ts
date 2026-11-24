/** The overview's spending sections since v1.0; shared words stay in dashboard.ts. */

export const overviewEn = {
  scope: "Wealth and goals",
  scopeHint: "Spending is the household's: the view only changes the wealth and the goals.",
  savedHelp: "Put aside in savings categories",
  rest: "Rest",
  restHelp: "Income minus spent minus saved",
  projectedRest: (amount: string) => `${amount} once the fixed expenses below are paid`,
  notSpent: "Not spent",
  notSpentHelp: (saved: string) => `Share of income not spent · ${saved} put in savings`,
  noTargets: "No category has a monthly target this month.",
  setTargets: "Set them in Budget",
  openLines: (name: string) => `Lines of ${name} this month`,
  savingsTargets: {
    title: "Targets this month: savings",
    titleOf: (month: string) => `Savings targets, ${month}`,
    none: "No savings category has a monthly objective this month.",
    savedOf: (saved: string, objective: string) => `${saved} of ${objective} saved`,
    toGo: (amount: string) => `${amount} to go`,
    beyond: (amount: string) => `${amount} beyond`,
    share: (share: string) => `${share} of the objective`,
    status: { reached: "Reached", in_progress: "In progress" },
  },
  toConfirm: {
    title: "Fixed expenses to confirm",
    none: "Every fixed expense of the month is confirmed or skipped.",
    confirm: (label: string) => `Confirm ${label}`,
  },
  lastLines: {
    title: "Last lines entered",
    order: "Newest entered first",
    none: "No line this month yet.",
    open: "Open the lines",
  },
};

export const overviewFr: typeof overviewEn = {
  scope: "Patrimoine et objectifs",
  scopeHint:
    "Les dépenses sont celles du foyer : la vue ne change que le patrimoine et les objectifs.",
  savedHelp: "Mis de côté dans les catégories d'épargne",
  rest: "Reste",
  restHelp: "Revenus moins dépensé moins épargné",
  projectedRest: (amount) => `${amount} une fois payées les dépenses fixes ci-dessous`,
  notSpent: "Non dépensé",
  notSpentHelp: (saved) => `Part des revenus non dépensée · ${saved} mis en épargne`,
  noTargets: "Aucune catégorie n'a de cible mensuelle ce mois-ci.",
  setTargets: "Les fixer dans Budget",
  openLines: (name) => `Lignes de ${name} ce mois-ci`,
  savingsTargets: {
    title: "Cibles du mois : épargne",
    titleOf: (month) => `Cibles d'épargne, ${month}`,
    none: "Aucune catégorie d'épargne n'a de cible mensuelle ce mois-ci.",
    savedOf: (saved, objective) => `${saved} épargnés sur ${objective}`,
    toGo: (amount) => `reste ${amount}`,
    beyond: (amount) => `${amount} au-delà`,
    share: (share) => `${share} de la cible`,
    status: { reached: "Atteint", in_progress: "En cours" },
  },
  toConfirm: {
    title: "Dépenses fixes à confirmer",
    none: "Toutes les dépenses fixes du mois sont confirmées ou sautées.",
    confirm: (label) => `Confirmer ${label}`,
  },
  lastLines: {
    title: "Dernières lignes saisies",
    order: "Les plus récemment saisies d'abord",
    none: "Aucune ligne ce mois-ci pour l'instant.",
    open: "Ouvrir les lignes",
  },
};
