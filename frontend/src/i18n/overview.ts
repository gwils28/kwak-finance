/** The overview's spending sections since v1.0; shared words stay in dashboard.ts. */

export const overviewEn = {
  scope: "Wealth and goals",
  scopeHint: "Spending is the household's: the view only changes the wealth and the goals.",
  savedHelp: "Put aside in savings categories",
  rest: "Rest",
  restHelp: "Income minus spent minus saved",
  projectedRest: (amount: string) => `${amount} once the fixed expenses below are paid`,
  savingsRateHelp: "Share of income not spent",
  noTargets: "No category has a monthly target this month.",
  setTargets: "Set them in Budget",
  openLines: (name: string) => `Lines of ${name} this month`,
  toConfirm: {
    title: "Fixed expenses to confirm",
    none: "Every fixed expense of the month is confirmed or skipped.",
    confirm: (label: string) => `Confirm ${label}`,
    projected: (amount: string) => `Rest at the end of the month: ${amount}`,
  },
  lastLines: {
    title: "Last lines entered",
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
  savingsRateHelp: "Part des revenus non dépensée",
  noTargets: "Aucune catégorie n'a de cible mensuelle ce mois-ci.",
  setTargets: "Les fixer dans Budget",
  openLines: (name) => `Lignes de ${name} ce mois-ci`,
  toConfirm: {
    title: "Dépenses fixes à confirmer",
    none: "Toutes les dépenses fixes du mois sont confirmées ou sautées.",
    confirm: (label) => `Confirmer ${label}`,
    projected: (amount) => `Reste en fin de mois : ${amount}`,
  },
  lastLines: {
    title: "Dernières lignes saisies",
    none: "Aucune ligne ce mois-ci pour l'instant.",
    open: "Ouvrir les lignes",
  },
};
