/** The retirement page's figures (F-RET-4). Amounts, months and chances arrive formatted. */

export const retirementEn = {
  intro:
    "What standard of living the household could keep once retired: the pensions entered below, and what the wealth can pay each month, against the retirement spending.",
  loading: "Running the plan…",
  problems: {
    no_wealth: "No wealth line in this scope: enter the wealth first.",
    no_member:
      "Enter your birth month, your retirement and your pension below to see the household's retirement.",
    horizon: "The horizon comes before the household retires: raise the horizon age.",
    no_allocation:
      "No category to save into: add Savings accounts or Current accounts to the wealth.",
  },
  sections: "Sections",
  jumpLife: "Timeline",
  jumpIncome: "Income",
  jumpFan: "Net worth",
  jumpInputs: "Inputs",
  tileLiving: (month: string) => `Standard of living from ${month}, 9 in 10`,
  perMonth: (amount: string) => `${amount} a month`,
  splitPensions: (amount: string) => `Pensions ${amount}`,
  splitWithdrawal: (amount: string) => `Withdrawal ${amount}`,
  against: (amount: string) => `Spending ${amount}`,
  living: (
    month: string,
    pensions: string,
    withdrawal: string,
    total: string,
    totalHalf: string,
    spending: string,
    covered: string,
  ) =>
    `From ${month}, pensions of ${pensions} and a sustainable withdrawal of ${withdrawal} a month give ${total} a month in 9 outcomes in 10 (${totalHalf} in half of them), for spending of ${spending}: ${covered} covered.`,
  livingNone: (month: string, pensions: string, spending: string) =>
    `From ${month}, pensions of ${pensions} a month, for spending of ${spending}. In more than one outcome in ten the liquid wealth has already run out by then: nothing can be withdrawn from it.`,
  laterPension:
    "A pension starting after the household's retirement leaves the years before it to the wealth: the chance below counts them, the withdrawal does not.",
  tileCovered: "Spending covered",
  covered: "covered",
  short: "short",
  tileLasts: "The wealth lasts to the horizon",
  lasts: (chance: string, month: string, age: number) =>
    `In ${chance} of the outcomes, the plan runs to ${month} (the youngest ${age} years old) without the liquid wealth running out.`,
  runsOut: (ten: number, half: number) =>
    `The liquid wealth runs out by age ${ten} in 1 outcome in 10, by age ${half} in half of them.`,
  runsOutTen: (ten: number, age: number) =>
    `The liquid wealth runs out by age ${ten} in 1 outcome in 10; in half of them, not before ${age}.`,
  never: (age: number) => `In 9 outcomes in 10, the liquid wealth does not run out before ${age}.`,
  shortfallAfter:
    "From then on, the spending would have to be cut, or financed otherwise (the home, family).",
  model: "9 in 10 in the model, not a guarantee: the real chance is lower (see the limits).",
  chanceLow: "less than 1%",
  chanceHigh: "more than 99%",
  lifeTitle: "Timeline",
  lifeLede: "Who works, who draws a pension, and how far the plan is tested.",
  lifeChart: "Each member's working months, then pension, to the horizon",
  working: (amount: string) => `Works, ${amount}`,
  pensionSegment: (amount: string) => `Pension ${amount}`,
  today: "Today",
  retiresAt: (name: string, age: number) => `${name} retires at ${age}`,
  horizonAt: (name: string, age: number) => `Horizon: ${name} at ${age}`,
  incomeTitle: "Monthly income once retired",
  incomeLede:
    "The pensions plus the sustainable withdrawal (9 in 10), against the retirement spending.",
  incomeChart: "The pensions and the withdrawal against the retirement spending, by month",
  pensions: "Pensions",
  withdrawal: "Sustainable withdrawal (9 in 10)",
  spending: "Retirement spending",
  fanTitle: "Net worth to the horizon",
  fanLede: "Net worth, its median and its range, and the liquid part that pays the withdrawal.",
  fanChart: "Net worth's median and range to the horizon, and the liquid wealth's median",
  median: "Median",
  band2575: "25–75% of outcomes",
  band1090: "10–90% of outcomes",
  liquid: "Liquid wealth (median)",
  retires: "Household retires",
  pensionOf: (name: string) => `${name}'s pension`,
  colMonth: "Month",
  colP10: "10%",
  colMedian: "Median",
  colP90: "90%",
  inputsTitle: "Inputs",
  inputMember: (
    name: string,
    birth: string,
    retirement: string,
    age: number,
    earnings: string,
    pension: string,
    pensionMonth: string,
    pensionAge: number,
  ) =>
    `${name}: born ${birth}, stops working in ${retirement} at ${age} with earnings of ${earnings} stopping then; a pension of ${pension} from ${pensionMonth}, at ${pensionAge}.`,
  inputSpending: (amount: string, how: string) => `Retirement spending: ${amount} a month, ${how}.`,
  howShare: (share: string, base: string, months: number) =>
    `${share} of today's spending outside the loans (${base}, measured over ${months} months)`,
  howAmount: "set by hand",
  inputIndexation: (rate: string) => `Pensions follow inflation ${rate} a year.`,
  inputHorizon: (month: string, age: number) => `Horizon: ${month}, when the youngest is ${age}.`,
  leftOut: (names: string) => `Left out, without a retirement entered: ${names}.`,
  scope: "The wealth counted is the household's lines you see.",
  limitsTitle: "Limits",
  limitsHint: "taxes, long-term care, a death: what the model leaves out",
  limits: [
    "Categories are drawn independently, as if stocks, private equity and crypto never fell together: in a crash they do, so the fan is narrower than reality.",
    "Returns follow a lognormal law: no crash beyond it and no total loss (a failed platform or token).",
    "The inflation is fixed over the whole horizon.",
    "The Shortfall is borrowed at a fixed 8% a year.",
    "Pensions as entered, never revised but by the indexation setting.",
    "No tax on withdrawals: from a PEA, a CTO or an assurance vie, the gains part is taxed, often 5 to 15% of what is withdrawn after many years.",
    "Long-term care not modelled: a nursing home costs about €2,000 to €2,500 a month after aid.",
    "The household's composition is fixed: no death, separation nor inheritance. After a death the survivor keeps a reversion pension (about 54% of a base pension, means-tested, 60% of an Agirc-Arrco one) and spends about two thirds to three quarters of what a couple does.",
    "The home is never sold nor mortgaged.",
  ],
  engine: (paths: string, seed: string, version: string) =>
    `${paths} outcomes, seed ${seed}, engine version ${version}.`,
  disclaimer:
    "An estimate from the assumptions and the pensions you entered, not a forecast and not advice. Pension estimates change with your career and with reforms: check yours on info-retraite.fr. Past returns do not guarantee future ones.",
};

export const retirementFr: typeof retirementEn = {
  intro:
    "Le niveau de vie que le foyer pourrait garder une fois retraité : les pensions saisies plus bas, et ce que le patrimoine peut verser chaque mois, face aux dépenses de retraite.",
  loading: "Calcul du plan…",
  problems: {
    no_wealth: "Aucune ligne de patrimoine dans ce périmètre : saisissez d'abord le patrimoine.",
    no_member:
      "Saisissez votre mois de naissance, votre départ et votre pension plus bas pour voir la retraite du foyer.",
    horizon: "L'horizon arrive avant la retraite du foyer : relevez l'âge de l'horizon.",
    no_allocation:
      "Aucune catégorie où épargner : ajoutez des Livrets ou des Comptes courants au patrimoine.",
  },
  sections: "Sections",
  jumpLife: "Le parcours",
  jumpIncome: "Revenus",
  jumpFan: "Patrimoine",
  jumpInputs: "Données",
  tileLiving: (month) => `Niveau de vie dès ${month}, 9 fois sur 10`,
  perMonth: (amount) => `${amount} par mois`,
  splitPensions: (amount) => `Pensions ${amount}`,
  splitWithdrawal: (amount) => `Retrait ${amount}`,
  against: (amount) => `Dépenses ${amount}`,
  living: (month, pensions, withdrawal, total, totalHalf, spending, covered) =>
    `À partir de ${month}, des pensions de ${pensions} et un retrait soutenable de ${withdrawal} par mois donnent ${total} par mois dans 9 cas sur 10 (${totalHalf} dans la moitié des cas), pour des dépenses de ${spending}, couvertes à ${covered}.`,
  livingNone: (month, pensions, spending) =>
    `À partir de ${month}, des pensions de ${pensions} par mois, pour des dépenses de ${spending}. Dans plus d'un cas sur dix, le patrimoine liquide est déjà épuisé : rien ne peut en être retiré.`,
  laterPension:
    "Une pension qui démarre après la retraite du foyer laisse les années d'avant au patrimoine : la chance ci-dessous les compte, le retrait non.",
  tileCovered: "Dépenses couvertes",
  covered: "couvertes",
  short: "insuffisant",
  tileLasts: "Le patrimoine tient jusqu'à l'horizon",
  lasts: (chance, month, age) =>
    `Dans ${chance} des résultats, le plan tient jusqu'en ${month} (le plus jeune a ${age} ans) sans que le patrimoine liquide s'épuise.`,
  runsOut: (ten, half) =>
    `Le patrimoine liquide s'épuise vers ${ten} ans dans 1 cas sur 10, vers ${half} ans dans la moitié des cas.`,
  runsOutTen: (ten, age) =>
    `Le patrimoine liquide s'épuise vers ${ten} ans dans 1 cas sur 10 ; dans la moitié des cas, pas avant ${age} ans.`,
  never: (age) => `Dans 9 cas sur 10, le patrimoine liquide ne s'épuise pas avant ${age} ans.`,
  shortfallAfter:
    "Dès lors, il faudrait réduire les dépenses ou les financer autrement (le logement, la famille).",
  model:
    "9 sur 10 dans le modèle, pas une garantie : la chance réelle est plus faible (voir les limites).",
  chanceLow: "moins de 1 %",
  chanceHigh: "plus de 99 %",
  lifeTitle: "Le parcours",
  lifeLede: "Qui travaille, qui touche sa pension, et jusqu'où le plan est testé.",
  lifeChart: "Les mois de travail puis la pension de chaque membre, jusqu'à l'horizon",
  working: (amount) => `Travaille, ${amount}`,
  pensionSegment: (amount) => `Pension ${amount}`,
  today: "Aujourd'hui",
  retiresAt: (name, age) => `${name} part à ${age} ans`,
  horizonAt: (name, age) => `Horizon : ${name} à ${age} ans`,
  incomeTitle: "Les revenus mensuels une fois retraité",
  incomeLede:
    "Les pensions plus le retrait soutenable (9 fois sur 10), face aux dépenses de retraite.",
  incomeChart: "Les pensions et le retrait face aux dépenses de retraite, par mois",
  pensions: "Pensions",
  withdrawal: "Retrait soutenable (9 sur 10)",
  spending: "Dépenses de retraite",
  fanTitle: "Le patrimoine net jusqu'à l'horizon",
  fanLede: "Le patrimoine net, sa médiane et son éventail, et la part liquide qui paie le retrait.",
  fanChart:
    "La médiane et l'éventail du patrimoine net jusqu'à l'horizon, et la médiane du patrimoine liquide",
  median: "Médiane",
  band2575: "25–75 % des résultats",
  band1090: "10–90 % des résultats",
  liquid: "Patrimoine liquide (médiane)",
  retires: "Retraite du foyer",
  pensionOf: (name) => `Pension de ${name}`,
  colMonth: "Mois",
  colP10: "10 %",
  colMedian: "Médiane",
  colP90: "90 %",
  inputsTitle: "Données utilisées",
  inputMember: (name, birth, retirement, age, earnings, pension, pensionMonth, pensionAge) =>
    `${name} : né(e) en ${birth}, arrête de travailler en ${retirement} à ${age} ans avec un revenu de ${earnings} qui s'arrête alors ; une pension de ${pension} à partir de ${pensionMonth}, à ${pensionAge} ans.`,
  inputSpending: (amount, how) => `Dépenses de retraite : ${amount} par mois, ${how}.`,
  howShare: (share, base, months) =>
    `${share} des dépenses d'aujourd'hui hors prêts (${base}, mesurées sur ${months} mois)`,
  howAmount: "saisies à la main",
  inputIndexation: (rate) => `Les pensions suivent l'inflation ${rate} par an.`,
  inputHorizon: (month, age) => `Horizon : ${month}, quand le plus jeune a ${age} ans.`,
  leftOut: (names) => `Non compté, sans retraite saisie : ${names}.`,
  scope: "Le patrimoine compté est celui des lignes du foyer que vous voyez.",
  limitsTitle: "Limites",
  limitsHint: "impôts, dépendance, décès : ce que le modèle laisse de côté",
  limits: [
    "Les catégories sont tirées indépendamment, comme si actions, private equity et crypto ne chutaient jamais ensemble : dans un krach, elles le font, l'éventail est donc plus étroit que la réalité.",
    "Les rendements suivent une loi lognormale : pas de krach au-delà, ni de perte totale (une plateforme ou un jeton qui fait faillite).",
    "L'inflation est fixe sur tout l'horizon.",
    "Le découvert est emprunté à 8 % par an, fixe.",
    "Pensions telles que saisies, jamais révisées sauf par le réglage d'indexation.",
    "Pas d'impôt sur les retraits : d'un PEA, d'un CTO ou d'une assurance vie, la part de plus-value est imposée, souvent 5 à 15 % de ce qui est retiré après de longues années.",
    "La dépendance n'est pas modélisée : un Ehpad coûte environ 2 000 à 2 500 € par mois après aides.",
    "La composition du foyer est fixe : ni décès, ni séparation, ni héritage. Après un décès, le survivant garde une pension de réversion (environ 54 % d'une pension de base, sous conditions de ressources, 60 % d'une pension Agirc-Arrco) et dépense environ les deux tiers à trois quarts de ce que dépense un couple.",
    "Le logement n'est jamais vendu ni hypothéqué.",
  ],
  engine: (paths, seed, version) =>
    `${paths} résultats, graine ${seed}, version du moteur ${version}.`,
  disclaimer:
    "Une estimation tirée des hypothèses et des pensions saisies, ni une prévision ni un conseil. Les estimations de pension changent avec la carrière et les réformes : vérifiez la vôtre sur info-retraite.fr. Les rendements passés ne présagent pas des rendements futurs.",
};
