const s = (n: number) => (n === 1 ? "" : "s");

export const categoriesEn = {
  title: "Categories",
  intro:
    'Two levels: categories and their subcategories. Deleting one sends its transactions back to "to categorise".',
  spending: "Spending",
  income: "Income",
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
  treeLabel: (title) => `Catégories de ${title.toLowerCase()}`,
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
