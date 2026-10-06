/** Shared words and every error the API can send, in English then French. */

const minutes = (n: number) => `${n} minute${n === 1 ? "" : "s"}`;

export const commonEn = {
  appName: "Kwak Finance",
  save: "Save",
  cancel: "Cancel",
  delete: "Delete",
  edit: "Edit",
  add: "Add",
  apply: "Apply",
  clear: "Clear",
  loading: "Loading…",
  copied: "Copied",
  confirm: "Confirm",
  showData: "Show the data",
  language: "Language",
  lightTheme: "Light theme",
  darkTheme: "Dark theme",
  signOut: "Sign out",
};

export const commonFr: typeof commonEn = {
  appName: "Kwak Finance",
  save: "Enregistrer",
  cancel: "Annuler",
  delete: "Supprimer",
  edit: "Modifier",
  add: "Ajouter",
  apply: "Appliquer",
  clear: "Effacer",
  loading: "Chargement…",
  copied: "Copié",
  confirm: "Confirmer",
  showData: "Afficher les données",
  language: "Langue",
  lightTheme: "Thème clair",
  darkTheme: "Thème sombre",
  signOut: "Se déconnecter",
};

export const errorsEn = {
  generic: "Something went wrong. Please try again.",
  tooManyAttempts: (waitMinutes: number | null) =>
    `Too many failed attempts. Try again ${waitMinutes === null ? "later" : `in ${minutes(waitMinutes)}`}.`,
  checkForm: "Check the form.",
};

export const errorsFr: typeof errorsEn = {
  generic: "Une erreur s'est produite. Réessayez.",
  tooManyAttempts: (waitMinutes) =>
    `Trop de tentatives échouées. Réessayez ${
      waitMinutes === null ? "plus tard" : `dans ${waitMinutes} minute${waitMinutes > 1 ? "s" : ""}`
    }.`,
  checkForm: "Vérifiez le formulaire.",
};

/**
 * French for the API's English `detail` messages (kwak_api), keyed by the exact text. An
 * unknown message is shown in English rather than hidden. Messages with values go to
 * API_PATTERNS below.
 */
export const API_MESSAGES_FR: Record<string, string> = {
  "a category cannot be its own parent": "une catégorie ne peut pas être sa propre parente",
  "a category name is required": "un nom de catégorie est obligatoire",
  "account name is required": "le nom du compte est obligatoire",
  "account not found": "compte introuvable",
  "a household already exists": "un foyer existe déjà",
  "a label is required": "un libellé est obligatoire",
  "already part of a transfer": "fait déjà partie d'un transfert",
  "amount bounds are positive: they apply to the absolute amount":
    "les bornes de montant sont positives : elles portent sur la valeur absolue",
  "an account already uses this email": "un compte utilise déjà cet e-mail",
  "an account cannot close before it opened":
    "un compte ne peut pas être clôturé avant son ouverture",
  "a rule needs at least one condition": "une règle a besoin d'au moins une condition",
  "a sibling category already has this name": "une catégorie voisine porte déjà ce nom",
  "a subcategory has the same kind as its parent":
    "une sous-catégorie a le même type que sa parente",
  "a target cannot be negative": "un objectif ne peut pas être négatif",
  "a transfer has no category: unlink it first":
    "un transfert n'a pas de catégorie : déliez-le d'abord",
  "a transfer is an outflow and an inflow of the same amount":
    "un transfert est une sortie et une entrée du même montant",
  "a transfer moves money between two different accounts":
    "un transfert déplace de l'argent entre deux comptes différents",
  "categories have two levels: a subcategory cannot have children":
    "les catégories ont deux niveaux : une sous-catégorie ne peut pas avoir d'enfants",
  "category not found": "catégorie introuvable",
  "display name is required": "le nom est obligatoire",
  "file too large (2 MB at most)": "fichier trop volumineux (2 Mo au plus)",
  "institution name is required": "le nom de l'établissement est obligatoire",
  "invalid code": "code invalide",
  "invalid email or password": "e-mail ou mot de passe incorrect",
  "invalid password": "mot de passe incorrect",
  "missing or invalid CSRF token": "jeton de sécurité manquant ou invalide : rechargez la page",
  "move or delete its subcategories first": "déplacez ou supprimez d'abord ses sous-catégories",
  "no import to roll back with this id": "aucun import à annuler",
  "no pending invitation with this id": "aucune invitation en attente",
  "not authenticated": "non connecté",
  "no TOTP setup in progress": "aucune configuration de la double authentification en cours",
  "only checking and savings accounts take bank statements":
    "seuls les comptes courants et les livrets acceptent des relevés",
  "only the account owner can change its visibility":
    "seul le titulaire du compte peut changer sa visibilité",
  "only the household owner can do this": "seul le propriétaire du foyer peut faire cela",
  "rule not found": "règle introuvable",
  "second factor required": "double authentification requise",
  "start is after end": "le début est après la fin",
  "targets are set on expense categories": "les objectifs se fixent sur des catégories de dépense",
  "the amount cannot be zero": "le montant ne peut pas être nul",
  "the date is before the account's opening date": "la date est antérieure à l'ouverture du compte",
  "the minimum amount is above the maximum": "le montant minimum dépasse le maximum",
  "this account is closed": "ce compte est clôturé",
  "this account is closed: reopen it to import": "ce compte est clôturé : rouvrez-le pour importer",
  "this institution already has an account with this name":
    "cet établissement a déjà un compte de ce nom",
  "this invitation is invalid or has expired": "cette invitation est invalide ou a expiré",
  "TOTP is already set up": "la double authentification est déjà configurée",
  "TOTP is not set up": "la double authentification n'est pas configurée",
  "transaction not found": "opération introuvable",
  "transactions can only be entered on checking and savings accounts":
    "les opérations ne se saisissent que sur les comptes courants et les livrets",
  "transfer not found": "transfert introuvable",
  "unknown account": "compte inconnu",
  "unknown category": "catégorie inconnue",
  "unknown parent category": "catégorie parente inconnue",
  "unrecognised file format: export a CSV of the operations from Société Générale":
    "format de fichier non reconnu : exportez les opérations au format CSV depuis la Société Générale",
};

/** API messages that carry a value: [English pattern, French replacement]. */
export const API_PATTERNS_FR: [RegExp, string][] = [
  [
    /^password must be at least (\d+) characters$/,
    "le mot de passe doit faire au moins $1 caractères",
  ],
  [
    /^password must be at most (\d+) characters$/,
    "le mot de passe doit faire au plus $1 caractères",
  ],
  [/^invalid email address: (.*)$/, "adresse e-mail invalide : $1"],
  [/^invalid month (.*), expected YYYY-MM$/, "mois invalide $1, attendu AAAA-MM"],
  [
    /^amount must be a whole number of cents: (.*)$/,
    "le montant doit être un nombre entier de centimes : $1",
  ],
  [/^invalid date (.*), expected DD\/MM\/YYYY$/, "date invalide $1, attendu JJ/MM/AAAA"],
  [/^invalid amount (.*)$/, "montant invalide $1"],
  [
    /^unsupported currency (.*): only EUR accounts are handled$/,
    "devise $1 non prise en charge : seuls les comptes en euros sont gérés",
  ],
  [/^expected (\d+) fields, found (\d+)$/, "$1 colonnes attendues, $2 trouvées"],
  [
    /^the file announces (\d+) operations but contains (\d+)$/,
    "le fichier annonce $1 opérations mais en contient $2",
  ],
  [
    /^not a Société Générale (checking|savings) export$/,
    "ce n'est pas un export Société Générale du bon type de compte",
  ],
  [/^unreadable summary line$/, "ligne de synthèse illisible"],
];
