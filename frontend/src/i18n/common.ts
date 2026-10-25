/** Shared words and every error the API can send, in English then French. */

const minutes = (n: number) => `${n} minute${n === 1 ? "" : "s"}`;

export const commonEn = {
  appName: "Kwak Finance",
  save: "Save",
  cancel: "Cancel",
  delete: "Delete",
  edit: "Edit",
  add: "Add",
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
  "a goal's start is never a month to come": "un objectif ne commence jamais dans un mois à venir",
  "a deadline is never a past month": "une échéance n'est jamais un mois passé",
  "the household already has a joint precaution goal":
    "le foyer a déjà une épargne de précaution commune",
  "this member already has a precaution goal": "ce membre a déjà une épargne de précaution",
  "the proposal counts 1 to 12 months": "la proposition compte de 1 à 12 mois",
  "a debt cannot fund a goal": "une dette ne peut pas financer un objectif",
  "a pension starts with the retirement or later":
    "une pension commence avec la retraite ou plus tard",
  "one retires after being born": "on part à la retraite après sa naissance",
  "one retires before 105 years old": "on part à la retraite avant 105 ans",
  "earnings and pensions are positive, in cents at most":
    "revenus et pensions sont positifs, au centime près",
  "the retirement spending is a whole percentage":
    "les dépenses à la retraite sont un pourcentage entier",
  "the retirement spending is from 50 to 150 % of today's":
    "les dépenses à la retraite vont de 50 à 150 % de celles d'aujourd'hui",
  "the pensions' indexation is set to 0.1 % at most":
    "l'indexation des pensions se règle à 0,1 % près",
  "the pensions' indexation is from -2 % to +1 % a year":
    "l'indexation des pensions va de -2 % à +1 % par an",
  "the horizon is an age from 85 to 105": "l'horizon est un âge de 85 à 105 ans",
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
  "only its owner changes who sees it": "seul son titulaire change qui le voit",
  "only its owner deletes it": "seul son titulaire peut le supprimer",
  "another category has this name": "une autre catégorie porte ce nom",
  "it still holds lines (perhaps a member's private ones): move or delete them first":
    "elle contient encore des lignes (peut-être les lignes privées d'un membre) : déplacez-les ou supprimez-les d'abord",
  "a household already exists": "un foyer existe déjà",
  "an account already uses this email": "un compte utilise déjà cet e-mail",
  "display name is required": "le nom est obligatoire",
  "invalid code": "code invalide",
  "invalid email or password": "e-mail ou mot de passe incorrect",
  "invalid password": "mot de passe incorrect",
  "missing or invalid CSRF token": "jeton de sécurité manquant ou invalide : rechargez la page",
  "no pending invitation with this id": "aucune invitation en attente",
  "not authenticated": "non connecté",
  "no TOTP setup in progress": "aucune configuration de la double authentification en cours",
  "only the household owner can do this": "seul le propriétaire du foyer peut faire cela",
  "second factor required": "double authentification requise",
  "this invitation is invalid or has expired": "cette invitation est invalide ou a expiré",
  "TOTP is already set up": "la double authentification est déjà configurée",
  "TOTP is not set up": "la double authentification n'est pas configurée",
  "unknown category": "catégorie inconnue",
  "it holds lines or fixed expenses: say where to move them":
    "elle contient des lignes ou des dépenses fixes : dites où les déplacer",
  "move them to another category of the same kind":
    "déplacez-les vers une autre catégorie du même type",
  "a line needs a category of the household": "une ligne a besoin d'une catégorie du foyer",
  "every part needs a category of the household": "chaque part a besoin d'une catégorie du foyer",
  "a fixed expense is spent or put aside: a negative amount":
    "une dépense fixe est dépensée ou mise de côté : un montant négatif",
  "its last month cannot come before its first":
    "son dernier mois ne peut pas précéder son premier",
  "only an expense category can be one-off": "seule une catégorie de dépense peut être ponctuelle",
  "no such fixed expense": "dépense fixe inconnue",
  "a part cannot be zero": "une part ne peut pas être nulle",
  "a split needs at least two parts": "une ventilation a besoin d'au moins deux parts",
  "no such line": "ligne inconnue",
  "no such spending category": "catégorie de dépenses inconnue",
  "every part has the sign of the transaction": "chaque part a le signe de la ligne",
  "the rest for the last part must be of the transaction's sign":
    "le reste pour la dernière part doit avoir le signe de la ligne",
  "a line is income or spending, not both": "une ligne est un revenu ou une dépense, pas les deux",
  "an expense is an outflow: a refund is an income line":
    "une dépense est une sortie : un remboursement est une ligne de revenus",
  "an income is an inflow": "un revenu est une entrée",
  "a goal needs a deadline, unless it is permanent":
    "un objectif a besoin d'une échéance, sauf s'il est permanent",
  "a goal closes from a month between its start and the next":
    "un objectif se clôt à partir d'un mois entre son début et le suivant",
  "an income category has no target": "une catégorie de revenus n'a pas de cible",
  "a fixed expense is spent or put aside: not an income category":
    "une dépense fixe est dépensée ou mise de côté : pas une catégorie de revenus",
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
  [
    /^amount must be a whole number of cents: (.*)$/,
    "le montant doit être un nombre entier de centimes : $1",
  ],
];
