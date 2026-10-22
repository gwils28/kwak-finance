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
  "a target is a positive amount in cents": "une cible est un montant positif, en centimes",
  "a medium- or long-term goal needs a deadline":
    "un objectif à moyen ou long terme a besoin d'une échéance",
  "a goal's start is never a month to come": "un objectif ne commence jamais dans un mois à venir",
  "a deadline is never a past month": "une échéance n'est jamais un mois passé",
  "the household already has a joint precaution goal":
    "le foyer a déjà une épargne de précaution commune",
  "this member already has a precaution goal": "ce membre a déjà une épargne de précaution",
  "the proposal counts 1 to 12 months": "la proposition compte de 1 à 12 mois",
  "a debt cannot fund a goal": "une dette ne peut pas financer un objectif",
  "a joint goal uses joint lines only": "un objectif commun n'utilise que des lignes communes",
  "a goal uses its owner's lines and joint ones":
    "un objectif utilise les lignes de son titulaire et les lignes communes",
  "a private line funds a private goal only: it would show its value":
    "une ligne privée ne finance qu'un objectif privé : elle en montrerait la valeur",
  "a share is from 1 to 100 %": "une part va de 1 à 100 %",
  "a line's shares sum to 100 % at most": "les parts d'une ligne font 100 % au plus",
  "the precaution share is from 50 % to 100 %": "la part de la précaution va de 50 % à 100 %",
  "no such goal": "objectif introuvable",
  "a line funds a goal once": "une ligne finance un objectif une seule fois",
  "unknown wealth line": "ligne de patrimoine inconnue",
  "say whether the goal was reached or abandoned": "dites si l'objectif a été atteint ou abandonné",
  "a goal closes from a month between its start and this one":
    "un objectif se clôt à partir d'un mois entre son début et ce mois-ci",
  "only its owner changes who sees it": "seul son titulaire change qui le voit",
  "only its owner deletes it": "seul son titulaire peut le supprimer",
  "another category has this name": "une autre catégorie porte ce nom",
  "it still holds lines (perhaps a member's private ones): move or delete them first":
    "elle contient encore des lignes (peut-être les lignes privées d'un membre) : déplacez-les ou supprimez-les d'abord",
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
  "a plan closes early before its last month":
    "un plan se clôture par anticipation avant son dernier mois",
  "a target cannot be negative": "un objectif ne peut pas être négatif",
  "a transfer has no category: unlink it first":
    "un transfert n'a pas de catégorie : déliez-le d'abord",
  "a transfer is an outflow and an inflow of the same amount":
    "un transfert est une sortie et une entrée du même montant",
  "a transfer moves money between two different accounts":
    "un transfert déplace de l'argent entre deux comptes différents",
  "categories have two levels: a subcategory cannot have children":
    "les catégories ont deux niveaux : une sous-catégorie ne peut pas avoir d'enfants",
  "budget plan not found": "plan budgétaire introuvable",
  "category not found": "catégorie introuvable",
  "display name is required": "le nom est obligatoire",
  "file too large (2 MB at most)": "fichier trop volumineux (2 Mo au plus)",
  "institution name is required": "le nom de l'établissement est obligatoire",
  "invalid code": "code invalide",
  "invalid email or password": "e-mail ou mot de passe incorrect",
  "invalid password": "mot de passe incorrect",
  "missing or invalid CSRF token": "jeton de sécurité manquant ou invalide : rechargez la page",
  "move or delete its subcategories first": "déplacez ou supprimez d'abord ses sous-catégories",
  "no earlier budget plan to compare with": "aucun plan budgétaire antérieur à comparer",
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
  "set a target for this category first": "fixez d'abord un objectif pour cette catégorie",
  "second factor required": "double authentification requise",
  "start is after end": "le début est après la fin",
  "targets are set on expense categories": "les objectifs se fixent sur des catégories de dépense",
  "the amount cannot be zero": "le montant ne peut pas être nul",
  "the cumulative chart is for an expense category":
    "la courbe cumulée porte sur une catégorie de dépense",
  "the date is before the account's opening date": "la date est antérieure à l'ouverture du compte",
  "the minimum amount is above the maximum": "le montant minimum dépasse le maximum",
  "this account is closed": "ce compte est clôturé",
  "this plan can no longer be edited: close it early to change its targets":
    "ce plan n'est plus modifiable : clôturez-le par anticipation pour changer ses objectifs",
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
  "unrecognised file format: export a CSV of the operations from Société Générale or Helios":
    "format de fichier non reconnu : exportez les opérations au format CSV depuis la Société Générale ou Helios",
  "not a Helios export": "ce n'est pas un export Helios",
  "it holds lines or fixed expenses: say where to move them":
    "elle contient des lignes ou des dépenses fixes : dites où les déplacer",
  "move them to another category of the same kind":
    "déplacez-les vers une autre catégorie du même type",
  "an expense is an outflow: refunds go into the month's income":
    "une dépense est une sortie : les remboursements vont dans les revenus du mois",
  "a line needs a category of the household": "une ligne a besoin d'une catégorie du foyer",
  "every part needs a category of the household": "chaque part a besoin d'une catégorie du foyer",
  "a fixed expense is spent or put aside: a negative amount":
    "une dépense fixe est dépensée ou mise de côté : un montant négatif",
  "its last month cannot come before its first":
    "son dernier mois ne peut pas précéder son premier",
  "an income is zero or more": "des revenus valent zéro ou plus",
  "only an expense category can be one-off": "seule une catégorie de dépense peut être ponctuelle",
  "no such fixed expense": "dépense fixe inconnue",
  "a part cannot be zero": "une part ne peut pas être nulle",
  "a split needs at least two parts": "une ventilation a besoin d'au moins deux parts",
  "no such line": "ligne inconnue",
  "no such spending category": "catégorie de dépenses inconnue",
  "every part has the sign of the transaction": "chaque part a le signe de la ligne",
  "the rest for the last part must be of the transaction's sign":
    "le reste pour la dernière part doit avoir le signe de la ligne",
};

/** API messages that carry a value: [English pattern, French replacement]. */
export const API_PATTERNS_FR: [RegExp, string][] = [
  [
    /^(.+) would fund open goals beyond 100 %: (\d+) % of its rises left$/,
    "$1 financerait des objectifs ouverts au-delà de 100 % : il ne reste que $2 % de ses hausses à répartir",
  ],
  [/^it funds a goal: (.+)$/, "elle finance un objectif : $1"],
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
  [/^budget plans overlap: (.*) and (.*)$/, "les plans budgétaires se chevauchent : $1 et $2"],
  [
    /^invalid period (.*), expected YYYY, YYYY-Sn or YYYY-Qn$/,
    "période invalide $1, attendu AAAA, AAAA-Sn ou AAAA-Qn",
  ],
  [/^no such period: (.*)$/, "cette période n'existe pas : $1"],
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
  [
    /^operation not executed yet \((.*)\): import it once it is$/,
    "opération pas encore exécutée ($1) : importez-la une fois exécutée",
  ],
];
