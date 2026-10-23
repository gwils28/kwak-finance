import type { Severity } from "../api/generated";

export const goalAnalysisEn = {
  title: "Goals analysis",
  intro:
    "Your goals seen together: against what you can save each month, on a timeline and month by month, with the points worth a look.",
  loadFailed: "Could not load the analysis.",
  empty: "No goal yet: the analysis starts with your first goal.",
  reference: (month: string) =>
    `Judged at ${month}, the last month whose funding lines all have a value entered: the efforts are those of that month, so they can differ from the Pyramid's, worked out this month.`,
  noReference:
    "No funding line has a value entered yet: the goals are judged on what is known this month.",
  householdCapacity:
    "The capacity is the household's, so this chart compares it with the household's goals.",
  capacityShort: (n: number) =>
    `Capacity measured over ${n === 1 ? "1 month" : `${n} months`}: too short to judge. The chart waits for 3 complete months of spending, or a capacity set in the effort settings.`,
  irregular:
    "Measured over fewer than 12 months, it misses the year's irregular costs (taxes, insurance, holidays).",
  // Points to look at (F-ANA-8)
  points: "Points to look at",
  pointsLink: (n: number) => (n === 1 ? "1 point to look at" : `${n} points to look at`),
  noPoint: "Nothing to look at: your goals are in order.",
  more: (n: number) => (n === 1 ? "1 more point" : `${n} more points`),
  fewer: "Show fewer",
  snooze: "Remind me next month",
  dismiss: "Hide until it worsens",
  showHidden: "Show hidden points again",
  hideFailed: "Could not hide this point.",
  severity: {
    warning: "Warning",
    info: "Information",
    good: "Good news",
  } satisfies Record<Severity, string>,
  disclaimer:
    "Rule-based observations computed from your entries and the Projection assumptions. Not personalised investment advice nor a recommendation to buy or sell any product; for a decision that matters, ask a licensed adviser.",
  data: {
    lines: (month: string, names: string) => `No value entered for ${month} on: ${names}.`,
    linesWhy:
      "The analysis waits for every funding line, so a month not yet entered never looks like a month without savings.",
    capacity: (n: number) =>
      n === 0
        ? "Your savings capacity has no complete month of spending to be measured on yet."
        : `Your savings capacity is measured over ${n === 1 ? "1 month" : `${n} months`}: too short to judge.`,
    capacityWhy:
      "The points that compare your goals with the capacity wait for 3 complete months of spending.",
    update: "Update your wealth",
    spending: "Enter your spending",
  },
  precautionNone: "You have no emergency fund yet.",
  precautionNoneWhy:
    "It comes before every other goal: a few months of your fixed expenses, kept apart for the unexpected.",
  precautionNoneAction: "Create it",
  precautionLow: (goal: string, months: string, monthly: string) =>
    `${goal} covers ${months} months of your fixed expenses (${monthly} a month).`,
  precautionLowWarning: (missing: string) => `Below 3 months: ${missing} more would bring it to 3.`,
  precautionLowInfo: (missing: string) => `Below 6 months: ${missing} more would bring it to 6.`,
  precautionLowWhy:
    "Fixed expenses leave out groceries and day-to-day spending; a single income or a self-employed one may want more.",
  precautionRisky: (goal: string, amount: string) =>
    `${amount} of ${goal} sits on volatile or illiquid lines.`,
  precautionRiskyWhy:
    "An emergency fund must be there, whole, on the day it is needed. One option is to keep it on savings accounts.",
  precautionCurrent: (goal: string, amount: string) =>
    `${amount} of ${goal} sits on a current account.`,
  precautionCurrentWhy:
    "It is available and guaranteed, but earns nothing and mixes with your spending. One option is a savings account.",
  unfunded: (goal: string) => `${goal} has no funding line: it can never progress.`,
  unfundedAction: "Choose its lines",
  overcommitted: (excess: string, capacity: string) =>
    `Your goals need ${excess} a month more than your capacity (${capacity} a month).`,
  overcommittedFilling: (months: number) =>
    `Only while the emergency fund fills: in ${months === 1 ? "1 month" : `${months} months`}, the other goals fit again.`,
  postpone: (goal: string, months: number, deadline: string) =>
    `Consider postponing ${goal} by ${months === 1 ? "1 month" : `${months} months`}, to ${deadline}`,
  movesTo: (tier: string) => ` (it would move to the ${tier.toLowerCase()})`,
  orLower: (amount: string) => `, or lowering its target by ${amount}.`,
  otherOptions: (list: string) => `Other options: ${list}`,
  postponeOther: (goal: string, months: number) =>
    `${goal}: ${months === 1 ? "1 month" : `${months} months`} later`,
  noPostponement: (excess: string) =>
    `Postponing one goal is not enough: ${excess} a month is missing.`,
  behind: (goal: string, amount: string) =>
    `${goal} has been behind for three months: ${amount} under where it should stand.`,
  behindExtra: (extra: string) => `+${extra} a month keeps the date`,
  behindDate: (month: string) => `or the date moves to ${month}`,
  behindTarget: (target: string) => `or the target to ${target}`,
  behindNever: "At this pace it is never reached.",
  behindMarket: "Part of this gap may come from market moves on its lines.",
  noGain: (goal: string) => `${goal} has not gained anything in six months.`,
  noGainOptions: (required: string | null) =>
    required
      ? `One option is to relaunch it (${required} a month keeps the date), to postpone it or to cancel it.`
      : "One option is to relaunch it, to postpone it or to cancel it.",
  openGoal: "Open the goal",
  // Required effort against capacity (F-ANA-2)
  forward: "Required effort against capacity",
  forwardHelp:
    "What each goal needs every month to reach its target on time, stacked, against what you can save. Required efforts leave out the lines' returns, so they are prudent for long goals.",
  capacity: "Capacity",
  capacityIs: (amount: string, how: string) => `Capacity: ${amount} a month (${how}).`,
  capacityMeasured: (n: number) => `measured over ${n === 1 ? "1 month" : `${n} months`}`,
  capacitySet: "set by hand",
  horizon: "Months shown",
  over: (months: number, peak: string) =>
    months === 0
      ? "Every month fits within the capacity."
      : `Over-committed for ${months === 1 ? "1 month" : `${months} months`}, by up to ${peak} a month.`,
  overArea: "Over-committed",
  forwardTable: "Required effort by month",
  month: "Month",
  total: "Total",
  noBand: "No goal with a deadline needs an effort.",
  // Timeline (F-ANA-3)
  timeline: "Timeline",
  timelineHelp:
    "Each goal from its start to its deadline: ● where it lands at its actual pace (dashed: too little history to tell), ◇ where it lands at the plan's effort, → beyond the chart.",
  timelineLabel: "Timeline of the goals",
  timelineTable: "Goals' dates",
  goal: "Goal",
  start: "Start",
  deadline: "Deadline",
  atPace: "At its pace",
  atPlan: "At the plan",
  never: "never at this pace",
  notEnough: "not enough history",
  noDeadline: "none",
  beyond: "Beyond the chart: see the table",
  // Status by month (F-ANA-6)
  statuses: "Status by month",
  statusesHelp: "Each goal's status at the end of each month, with today's target and deadline.",
  statusesTable: "Goals' status by month",
};

export const goalAnalysisFr: typeof goalAnalysisEn = {
  title: "Analyse des objectifs",
  intro:
    "Vos objectifs vus ensemble : face à ce que vous pouvez épargner chaque mois, sur une frise et mois par mois, avec les points qui méritent un coup d'œil.",
  loadFailed: "Impossible de charger l'analyse.",
  empty: "Pas encore d'objectif : l'analyse commence avec votre premier objectif.",
  reference: (month) =>
    `Jugé à ${month}, le dernier mois où toutes les lignes de financement ont une valeur saisie : les efforts sont ceux de ce mois-là, et peuvent différer de ceux de la Pyramide, calculés ce mois-ci.`,
  noReference:
    "Aucune ligne de financement n'a encore de valeur saisie : les objectifs sont jugés sur ce que l'on sait ce mois-ci.",
  householdCapacity:
    "La capacité est celle du foyer : ce graphique la compare donc aux objectifs du foyer.",
  capacityShort: (n) =>
    `Capacité mesurée sur ${n === 1 ? "1 mois" : `${n} mois`} : trop peu pour juger. Le graphique attend 3 mois complets de dépenses, ou une capacité fixée dans les réglages de l'effort.`,
  irregular:
    "Mesurée sur moins de 12 mois, elle ne voit pas les dépenses irrégulières de l'année (impôts, assurances, vacances).",
  points: "Points d'attention",
  pointsLink: (n) => (n === 1 ? "1 point d'attention" : `${n} points d'attention`),
  noPoint: "Rien à signaler : vos objectifs sont en ordre.",
  more: (n) => (n === 1 ? "1 autre point" : `${n} autres points`),
  fewer: "Afficher moins",
  snooze: "Me le rappeler le mois prochain",
  dismiss: "Masquer jusqu'à ce que ça empire",
  showHidden: "Réafficher les points masqués",
  hideFailed: "Impossible de masquer ce point.",
  severity: {
    warning: "Attention",
    info: "Information",
    good: "Bonne nouvelle",
  },
  disclaimer:
    "Observations calculées par des règles à partir de vos saisies et des hypothèses de la page Projection. Ni un conseil en investissement personnalisé, ni une recommandation d'acheter ou de vendre un produit ; pour une décision importante, consultez un conseiller agréé.",
  data: {
    lines: (month, names) => `Aucune valeur saisie pour ${month} sur : ${names}.`,
    linesWhy:
      "L'analyse attend toutes les lignes de financement : un mois pas encore saisi ne passe jamais pour un mois sans épargne.",
    capacity: (n) =>
      n === 0
        ? "Votre capacité d'épargne n'a encore aucun mois complet de dépenses pour être mesurée."
        : `Votre capacité d'épargne est mesurée sur ${n === 1 ? "1 mois" : `${n} mois`} : trop peu pour juger.`,
    capacityWhy:
      "Les points qui comparent vos objectifs à la capacité attendent 3 mois complets de dépenses.",
    update: "Mettre à jour le patrimoine",
    spending: "Saisir vos dépenses",
  },
  precautionNone: "Vous n'avez pas encore d'épargne de précaution.",
  precautionNoneWhy:
    "Elle passe avant tout autre objectif : quelques mois de vos charges fixes, mis de côté pour les imprévus.",
  precautionNoneAction: "La créer",
  precautionLow: (goal, months, monthly) =>
    `${goal} couvre ${months} mois de vos charges fixes (${monthly} par mois).`,
  precautionLowWarning: (missing) => `Moins de 3 mois : ${missing} de plus la porteraient à 3.`,
  precautionLowInfo: (missing) => `Moins de 6 mois : ${missing} de plus la porteraient à 6.`,
  precautionLowWhy:
    "Les charges fixes laissent de côté les courses et le quotidien ; avec un seul revenu ou un revenu d'indépendant, on peut vouloir davantage.",
  precautionRisky: (goal, amount) =>
    `${amount} de ${goal} sont sur des lignes volatiles ou peu liquides.`,
  precautionRiskyWhy:
    "Une épargne de précaution doit être là, entière, le jour où on en a besoin. Une option est de la garder sur des livrets.",
  precautionCurrent: (goal, amount) => `${amount} de ${goal} sont sur un compte courant.`,
  precautionCurrentWhy:
    "Ils sont disponibles et garantis, mais ne rapportent rien et se mêlent à vos dépenses. Une option est un livret.",
  unfunded: (goal) => `${goal} n'a aucune ligne de financement : il ne peut jamais avancer.`,
  unfundedAction: "Choisir ses lignes",
  overcommitted: (excess, capacity) =>
    `Vos objectifs demandent ${excess} par mois de plus que votre capacité (${capacity} par mois).`,
  overcommittedFilling: (months) =>
    `Seulement le temps de remplir l'épargne de précaution : dans ${months === 1 ? "1 mois" : `${months} mois`}, les autres objectifs tiennent à nouveau.`,
  postpone: (goal, months, deadline) =>
    `Envisager de repousser ${goal} de ${months === 1 ? "1 mois" : `${months} mois`}, à ${deadline}`,
  movesTo: (tier) => ` (il passerait au ${tier.toLowerCase()})`,
  orLower: (amount) => `, ou de baisser sa cible de ${amount}.`,
  otherOptions: (list) => `Autres options : ${list}`,
  postponeOther: (goal, months) =>
    `${goal} : ${months === 1 ? "1 mois" : `${months} mois`} plus tard`,
  noPostponement: (excess) =>
    `Repousser un seul objectif ne suffit pas : il manque ${excess} par mois.`,
  behind: (goal, amount) =>
    `${goal} est en retard depuis trois mois : ${amount} de moins que prévu à ce stade.`,
  behindExtra: (extra) => `+${extra} par mois permettent de tenir la date`,
  behindDate: (month) => `ou la date passe à ${month}`,
  behindTarget: (target) => `ou la cible à ${target}`,
  behindNever: "À ce rythme, il n'est jamais atteint.",
  behindMarket: "Une partie de cet écart peut venir des mouvements de marché sur ses lignes.",
  noGain: (goal) => `${goal} n'a rien gagné depuis six mois.`,
  noGainOptions: (required) =>
    required
      ? `Une option est de le relancer (${required} par mois permettent de tenir la date), de le repousser ou de l'annuler.`
      : "Une option est de le relancer, de le repousser ou de l'annuler.",
  openGoal: "Ouvrir l'objectif",
  forward: "Effort requis face à la capacité",
  forwardHelp:
    "Ce que chaque objectif demande chaque mois pour atteindre sa cible à temps, empilé, face à ce que vous pouvez épargner. Les efforts requis ne comptent pas les rendements des lignes : ils sont prudents pour les objectifs lointains.",
  capacity: "Capacité",
  capacityIs: (amount, how) => `Capacité : ${amount} par mois (${how}).`,
  capacityMeasured: (n) => `mesurée sur ${n === 1 ? "1 mois" : `${n} mois`}`,
  capacitySet: "fixée à la main",
  horizon: "Mois affichés",
  over: (months, peak) =>
    months === 0
      ? "Chaque mois tient dans la capacité."
      : `Surengagé pendant ${months === 1 ? "1 mois" : `${months} mois`}, jusqu'à ${peak} par mois.`,
  overArea: "Surengagé",
  forwardTable: "Effort requis par mois",
  month: "Mois",
  total: "Total",
  noBand: "Aucun objectif avec une échéance ne demande d'effort.",
  timeline: "Frise",
  timelineHelp:
    "Chaque objectif de son début à son échéance : ● où il arrive à son rythme réel (en pointillé : trop peu d'historique pour le dire), ◇ où il arrive à l'effort du plan, → au-delà du graphique.",
  timelineLabel: "Frise des objectifs",
  timelineTable: "Dates des objectifs",
  goal: "Objectif",
  start: "Début",
  deadline: "Échéance",
  atPace: "À son rythme",
  atPlan: "Selon le plan",
  never: "jamais à ce rythme",
  notEnough: "pas assez d'historique",
  noDeadline: "aucune",
  beyond: "Au-delà du graphique : voir le tableau",
  statuses: "Statut par mois",
  statusesHelp:
    "Le statut de chaque objectif à la fin de chaque mois, avec la cible et l'échéance d'aujourd'hui.",
  statusesTable: "Statut des objectifs par mois",
};
