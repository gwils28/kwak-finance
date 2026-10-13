const s = (n: number) => (n === 1 ? "" : "s");
const ordinal = (n: number) => {
  const tens = n % 100;
  const suffix = tens >= 11 && tens <= 13 ? "th" : (["th", "st", "nd", "rd"][n % 10] ?? "th");
  return `${n}${suffix}`;
};

export const categoriesEn = {
  title: "Categories",
  intro:
    'Two levels: categories and their subcategories. Deleting one sends its transactions back to "to categorise".',
  spending: "Spending",
  income: "Income",
  savings: "Savings & investments",
  savingsHelp:
    "Money moved to savings or investments the app does not track as an account (a PEA, a life insurance, a PER…). It is never spending nor income, and can have a monthly objective in a budget plan.",
  treeLabel: (title: string) => `${title} categories`,
  newCategory: "New category",
  name: "Name",
  kind: "Kind",
  subcategoriesOf: (name: string) => `Subcategories of ${name}`,
  newSubcategoryOf: (name: string) => `New subcategory of ${name}`,
  addSubcategoryTo: (name: string) => `Add a subcategory to ${name}`,
  subcategory: "+ Subcategory",
  newNameFor: (name: string) => `New name for ${name}`,
  moveTo: (name: string) => `Move ${name} to`,
  renameNamed: (name: string) => `Rename ${name}`,
  rename: "Rename",
  confirmDeleteNamed: (name: string) => `Confirm: delete ${name}`,
  deleteIt: "Delete it",
  deleteNamed: (name: string) => `Delete ${name}`,
  shift: {
    from: (day: number) => `Next month from the ${ordinal(day)}`,
    like: (parent: string, day: number) => `Like ${parent}: next month from the ${ordinal(day)}`,
    never: "Never shifted",
    open: (name: string) => `Budget month of ${name}`,
    help: "Transactions of this category booked on or after this day count for the next month in the budget and the overview, e.g. a salary paid on the 20th for the next month's spending. Their date does not change.",
    mode: "Counts for the next month",
    inherit: (parent: string) => `Like ${parent}`,
    no: "No",
    neverOption: "Never",
    day: "From a day of the month",
    dayLabel: "From day",
    invalidDay: "Enter a day from 1 to 31.",
    preview: "Preview",
    moved: (n: number, months: string) =>
      n === 0
        ? "No transaction changes month."
        : `${n} transaction${s(n)} change${n === 1 ? "s" : ""} month (${months}).`,
    locked: (plans: string) => `Locked plans whose review changes: ${plans}.`,
    save: "Save",
  },
  labelContainsQuoted: (text: string) => `Label contains "${text}"`,
  between: (min: string, max: string) => `from ${min} to ${max}`,
  atLeast: (min: string) => `at least ${min}`,
  atMost: (max: string) => `at most ${max}`,
  onAccount: (name: string) => `on ${name}`,
  anAccount: "an account",
  categorised: (n: number) => `${n} transaction${s(n)} categorised.`,
  rules: "Rules",
  rulesIntro:
    'The first rule that matches sets the category of each import and manual entry. Create rules from a transaction\'s "Rule" button.',
  applyRules: "Apply the rules to past transactions",
  noRules: "No rules yet.",
  rulesOrder: "Rules, in the order they run",
  earlier: (rule: string) => `Run the rule "${rule}" earlier`,
  later: (rule: string) => `Run the rule "${rule}" later`,
  editRule: (rule: string) => `Edit the rule "${rule}"`,
  deleteRule: (rule: string) => `Delete the rule "${rule}"`,
  category: "Category",
  labelContains: "Label contains",
  amountFrom: "From (€, absolute amount)",
  amountTo: "To (€, absolute amount)",
  account: "Account",
  anyAccount: "Any account",
  invalidAmounts: "Enter amounts in euros, e.g. 12.50.",
  restore: {
    title: "Default categories",
    intro:
      "Brings the categories back to the defaults Kwak Finance suggests, named in your language. Defaults you still have keep their transactions, rules and plan targets; the ones you created are deleted.",
    open: "Restore the default categories…",
    loading: "Working out what changes…",
    nothing: "Your categories already match the defaults.",
    warningTitle: "Before you restore",
    toCategorise: (n: number) =>
      `${n} transaction${s(n)} go${n === 1 ? "es" : ""} back to “to categorise”.`,
    rules: (n: number) => `${n} rule${s(n)} ${n === 1 ? "is" : "are"} deleted.`,
    targets: (n: number, locked: number) =>
      `${n} plan target${s(n)} ${n === 1 ? "is" : "are"} deleted${
        locked
          ? `, in ${locked} plan${s(locked)} already locked: ${locked === 1 ? "its" : "their"} review changes`
          : ""
      }.`,
    backup:
      "This cannot be undone from the app. Check that a recent backup exists first (see “How to run the app”).",
    created: (n: number, names: string) => `Created (${n}): ${names}`,
    renamed: (n: number, names: string) => `Renamed (${n}): ${names}`,
    merged: (n: number, names: string) => `Merged (${n}): ${names}`,
    moved: (n: number, names: string) => `Moved back under their category (${n}): ${names}`,
    deleted: (n: number, names: string) => `Deleted (${n}): ${names}`,
    confirm: "Restore now",
    cancel: "Cancel",
    done: "Default categories restored.",
  },
};

const fs = (n: number) => (n > 1 ? "s" : "");

export const categoriesFr: typeof categoriesEn = {
  title: "Catégories",
  intro:
    "Deux niveaux : les catégories et leurs sous-catégories. En supprimer une renvoie ses opérations dans « à catégoriser ».",
  spending: "Dépenses",
  income: "Revenus",
  savings: "Épargne et placements",
  savingsHelp:
    "L'argent mis de côté ou placé sur des supports que l'app ne suit pas comme un compte (un PEA, une assurance-vie, un PER…). Ce n'est jamais une dépense ni un revenu, et une catégorie d'épargne peut avoir un objectif mensuel dans un plan budgétaire.",
  // "de dépenses", "de revenus", but "d'épargne et placements".
  treeLabel: (title) =>
    `Catégories ${/^[aeiouyéè]/i.test(title) ? "d'" : "de "}${title.toLowerCase()}`,
  newCategory: "Nouvelle catégorie",
  name: "Nom",
  kind: "Type",
  subcategoriesOf: (name) => `Sous-catégories de ${name}`,
  newSubcategoryOf: (name) => `Nouvelle sous-catégorie de ${name}`,
  addSubcategoryTo: (name) => `Ajouter une sous-catégorie à ${name}`,
  subcategory: "+ Sous-catégorie",
  newNameFor: (name) => `Nouveau nom pour ${name}`,
  moveTo: (name) => `Déplacer ${name} vers`,
  renameNamed: (name) => `Renommer ${name}`,
  rename: "Renommer",
  confirmDeleteNamed: (name) => `Confirmer : supprimer ${name}`,
  deleteIt: "La supprimer",
  deleteNamed: (name) => `Supprimer ${name}`,
  shift: {
    from: (day) => `Mois suivant à partir du ${day === 1 ? "1er" : day}`,
    like: (parent, day) => `Comme ${parent} : mois suivant à partir du ${day === 1 ? "1er" : day}`,
    never: "Jamais décalée",
    open: (name) => `Mois budgétaire de ${name}`,
    help: "Les opérations de cette catégorie datées de ce jour ou après comptent pour le mois suivant dans le budget et la vue d'ensemble, par ex. un salaire versé le 20 pour les dépenses du mois suivant. Leur date ne change pas.",
    mode: "Compte pour le mois suivant",
    inherit: (parent) => `Comme ${parent}`,
    no: "Non",
    neverOption: "Jamais",
    day: "À partir d'un jour du mois",
    dayLabel: "À partir du jour",
    invalidDay: "Saisissez un jour de 1 à 31.",
    preview: "Aperçu",
    moved: (n, months) =>
      n === 0
        ? "Aucune opération ne change de mois."
        : `${n} opération${fs(n)} change${n > 1 ? "nt" : ""} de mois (${months}).`,
    locked: (plans) => `Plans verrouillés dont le bilan change : ${plans}.`,
    save: "Enregistrer",
  },
  labelContainsQuoted: (text) => `Le libellé contient « ${text} »`,
  between: (min, max) => `de ${min} à ${max}`,
  atLeast: (min) => `au moins ${min}`,
  atMost: (max) => `au plus ${max}`,
  onAccount: (name) => `sur ${name}`,
  anAccount: "un compte",
  categorised: (n) => `${n} opération${fs(n)} catégorisée${fs(n)}.`,
  rules: "Règles",
  rulesIntro:
    "La première règle qui correspond fixe la catégorie de chaque opération importée ou saisie. Créez des règles avec le bouton « Règle » d'une opération.",
  applyRules: "Appliquer les règles aux opérations passées",
  noRules: "Aucune règle pour l'instant.",
  rulesOrder: "Règles, dans leur ordre d'exécution",
  earlier: (rule) => `Exécuter la règle « ${rule} » plus tôt`,
  later: (rule) => `Exécuter la règle « ${rule} » plus tard`,
  editRule: (rule) => `Modifier la règle « ${rule} »`,
  deleteRule: (rule) => `Supprimer la règle « ${rule} »`,
  category: "Catégorie",
  labelContains: "Le libellé contient",
  amountFrom: "De (€, montant absolu)",
  amountTo: "À (€, montant absolu)",
  account: "Compte",
  anyAccount: "N'importe quel compte",
  invalidAmounts: "Saisissez des montants en euros, par ex. 12,50.",
  restore: {
    title: "Catégories par défaut",
    intro:
      "Ramène les catégories à celles que propose Kwak Finance, nommées dans votre langue. Les catégories par défaut que vous avez encore gardent leurs opérations, règles et objectifs de plans ; celles que vous avez créées sont supprimées.",
    open: "Rétablir les catégories par défaut…",
    loading: "Calcul de ce qui change…",
    nothing: "Vos catégories correspondent déjà à celles par défaut.",
    warningTitle: "Avant de rétablir",
    toCategorise: (n) => `${n} opération${fs(n)} repasse${n > 1 ? "nt" : ""} « à catégoriser ».`,
    rules: (n) => `${n} règle${fs(n)} ${n > 1 ? "sont supprimées" : "est supprimée"}.`,
    targets: (n, locked) =>
      `${n} objectif${fs(n)} de plan ${n > 1 ? "sont supprimés" : "est supprimé"}${
        locked
          ? `, dans ${locked} plan${fs(locked)} déjà verrouillé${fs(locked)} : ${locked > 1 ? "leur" : "son"} bilan change`
          : ""
      }.`,
    backup:
      "Cette action ne peut pas être annulée depuis l'application. Vérifiez d'abord qu'une sauvegarde récente existe (voir « Lancer et arrêter l'application »).",
    created: (n, names) => `Créées (${n}) : ${names}`,
    renamed: (n, names) => `Renommées (${n}) : ${names}`,
    merged: (n, names) => `Fusionnées (${n}) : ${names}`,
    moved: (n, names) => `Replacées sous leur catégorie (${n}) : ${names}`,
    deleted: (n, names) => `Supprimées (${n}) : ${names}`,
    confirm: "Rétablir maintenant",
    cancel: "Annuler",
    done: "Catégories par défaut rétablies.",
  },
};
