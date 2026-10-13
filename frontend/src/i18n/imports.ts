const s = (n: number) => (n === 1 ? "" : "s");

export const importsEn = {
  title: "Import",
  titleInto: (name: string) => `Import into ${name}`,
  back: "← Accounts",
  accountLine: (institution: string, balance: string, opening: string) =>
    `${institution} · balance ${balance} · operations before ${opening} are ignored (opening date)`,
  fileLabel: "Bank export (CSV)",
  fileHelp:
    "Société Générale: account page, “Télécharger”, CSV format. Helios: the monthly statement in CSV. Nothing is saved until you confirm, and importing the same file twice adds nothing.",
  reading: "Reading the file…",
  cannotImport: "This file cannot be imported.",
  tooLarge: "This file is too large (2 MB at most).",
  preview: "Preview",
  period: (from: string, to: string) => `From ${from} to ${to}`,
  bankBalance: (amount: string, on: string) => ` · bank balance ${amount} on ${on}`,
  countNew: (n: number) => `${n} new`,
  countEntered: (n: number) => `${n} already entered by hand`,
  countDuplicate: (n: number) => `${n} already imported`,
  countBeforeOpening: (n: number) => `${n} before the opening date`,
  countErrors: (n: number) => `${n} error${s(n)}`,
  nothingNew: "Nothing new to import",
  importNew: (n: number) => `Import ${n} new operation${s(n)}`,
  importAndMatch: (n: number, m: number) =>
    `Import ${n} new operation${s(n)} and match ${m} entr${m === 1 ? "y" : "ies"}`,
  enteredAs: (date: string, label: string) => `Entered on ${date}: ${label}`,
  notTheSame: "Not the same",
  notTheSameAs: (label: string) => `${label} is not the operation entered by hand`,
  matchHelp:
    "Rows marked “Already entered” take over the operation you entered by hand: it keeps your label and category and takes the bank's date. If a match is wrong, “Not the same” imports the row as a new operation.",
  unmatched: (n: number) =>
    `${n} operation${s(n)} entered by hand in these dates ${n === 1 ? "is" : "are"} not in the file`,
  unmatchedHelp:
    "A typo in the amount or the date, or an operation the bank has not booked yet. They stay as entered.",
  beforeOpening: (n: number, opening: string | null) =>
    `${n} operation${s(n)} ${n === 1 ? "is" : "are"} before the account's opening date${
      opening ? ` (${opening})` : ""
    }: skipped, because the opening balance already includes ${n === 1 ? "it" : "them"}.`,
  openOn: (date: string) => `Open the account on ${date}`,
  openOnHelp: "Then check the opening balance in Accounts: it must be the balance on that day.",
  alreadyImported: (date: string) => `This file was already imported on ${date}.`,
  fileError: "File",
  lineError: (line: number) => `Line ${line}`,
  rowsTable: "Rows in the file",
  date: "Date",
  label: "Label",
  amount: "Amount",
  status: "Status",
  statuses: {
    new: "New",
    already_entered: "Already entered",
    duplicate: "Already imported",
    before_opening: "Before opening date",
  },
  imported: (n: number) => `${n} operation${s(n)} imported.`,
  reconciled: (n: number) =>
    `${n} operation${s(n)} entered by hand matched with the bank's line${s(n)}.`,
  skipped: (parts: string) => `Skipped: ${parts}.`,
  balanceMatches: (amount: string, on: string) =>
    `The balance matches the bank: ${amount} on ${on}.`,
  balanceDiffers: (computed: string, bank: string, gap: string, on: string) =>
    `The computed balance (${computed}) differs from the bank's (${bank}) by ${gap} on ${on}. Check the account's opening balance and date, or import the missing period.`,
  previous: "Previous imports",
  historyLine: (date: string, n: number) => `${date} · ${n} operation${s(n)} imported`,
  rolledBack: (date: string) => ` · Rolled back on ${date}`,
  confirmRollback: (n: number) => `Confirm: delete its ${n} operation${s(n)}`,
  rollbackGivesBack: (n: number) =>
    `The ${n} operation${s(n)} entered by hand go${n === 1 ? "es" : ""} back as entered.`,
  rollBack: "Roll back",
};

const fs = (n: number) => (n > 1 ? "s" : "");

export const importsFr: typeof importsEn = {
  title: "Importer",
  titleInto: (name) => `Importer dans ${name}`,
  back: "← Comptes",
  accountLine: (institution, balance, opening) =>
    `${institution} · solde ${balance} · les opérations antérieures au ${opening} sont ignorées (date d'ouverture)`,
  fileLabel: "Export bancaire (CSV)",
  fileHelp:
    "Société Générale : page du compte, « Télécharger », format CSV. Helios : le relevé mensuel au format CSV. Rien n'est enregistré avant votre confirmation, et importer deux fois le même fichier n'ajoute rien.",
  reading: "Lecture du fichier…",
  cannotImport: "Ce fichier ne peut pas être importé.",
  tooLarge: "Ce fichier est trop volumineux (2 Mo au plus).",
  preview: "Aperçu",
  period: (from, to) => `Du ${from} au ${to}`,
  bankBalance: (amount, on) => ` · solde de la banque ${amount} le ${on}`,
  countNew: (n) => `${n} nouvelle${fs(n)}`,
  countEntered: (n) => `${n} déjà saisie${fs(n)} à la main`,
  countDuplicate: (n) => `${n} déjà importée${fs(n)}`,
  countBeforeOpening: (n) => `${n} avant la date d'ouverture`,
  countErrors: (n) => `${n} erreur${fs(n)}`,
  nothingNew: "Rien de nouveau à importer",
  importNew: (n) => `Importer ${n} nouvelle${fs(n)} opération${fs(n)}`,
  importAndMatch: (n, m) =>
    `Importer ${n} nouvelle${fs(n)} opération${fs(n)} et rapprocher ${m} saisie${fs(m)}`,
  enteredAs: (date, label) => `Saisie le ${date} : ${label}`,
  notTheSame: "Pas la même",
  notTheSameAs: (label) => `${label} n'est pas l'opération saisie à la main`,
  matchHelp:
    "Les lignes « Déjà saisie » reprennent l'opération saisie à la main : elle garde votre libellé et votre catégorie, et prend la date de la banque. Si un rapprochement est faux, « Pas la même » importe la ligne comme une nouvelle opération.",
  unmatched: (n) =>
    `${n} opération${fs(n)} saisie${fs(n)} à la main dans ces dates ${n > 1 ? "ne sont pas" : "n'est pas"} dans le fichier`,
  unmatchedHelp:
    "Une faute de frappe dans le montant ou la date, ou une opération que la banque n'a pas encore passée. Elles restent telles que saisies.",
  beforeOpening: (n, opening) =>
    `${n} opération${fs(n)} ${n > 1 ? "sont antérieures" : "est antérieure"} à la date d'ouverture du compte${
      opening ? ` (${opening})` : ""
    } : ${n > 1 ? "ignorées, car le solde d'ouverture les inclut" : "ignorée, car le solde d'ouverture l'inclut"} déjà.`,
  openOn: (date) => `Ouvrir le compte le ${date}`,
  openOnHelp:
    "Vérifiez ensuite le solde d'ouverture dans Comptes : ce doit être le solde de ce jour-là.",
  alreadyImported: (date) => `Ce fichier a déjà été importé le ${date}.`,
  fileError: "Fichier",
  lineError: (line) => `Ligne ${line}`,
  rowsTable: "Lignes du fichier",
  date: "Date",
  label: "Libellé",
  amount: "Montant",
  status: "Statut",
  statuses: {
    new: "Nouvelle",
    already_entered: "Déjà saisie",
    duplicate: "Déjà importée",
    before_opening: "Avant l'ouverture",
  },
  imported: (n) => `${n} opération${fs(n)} importée${fs(n)}.`,
  reconciled: (n) =>
    `${n} opération${fs(n)} saisie${fs(n)} à la main rapprochée${fs(n)} de la ligne de la banque.`,
  skipped: (parts) => `Ignorées : ${parts}.`,
  balanceMatches: (amount, on) => `Le solde correspond à celui de la banque : ${amount} le ${on}.`,
  balanceDiffers: (computed, bank, gap, on) =>
    `Le solde calculé (${computed}) diffère de celui de la banque (${bank}) de ${gap} le ${on}. Vérifiez le solde et la date d'ouverture du compte, ou importez la période manquante.`,
  previous: "Imports précédents",
  historyLine: (date, n) => `${date} · ${n} opération${fs(n)} importée${fs(n)}`,
  rolledBack: (date) => ` · Annulé le ${date}`,
  confirmRollback: (n) => `Confirmer : supprimer ses ${n} opération${fs(n)}`,
  rollbackGivesBack: (n) =>
    `${n > 1 ? `Les ${n} opérations saisies` : "L'opération saisie"} à la main ${n > 1 ? "redeviennent" : "redevient"} telle${fs(n)} que saisie${fs(n)}.`,
  rollBack: "Annuler l'import",
};
