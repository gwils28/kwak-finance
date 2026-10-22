import type { AuditAction } from "../api/generated";

/** The details of an entry, already formatted (amounts, dates, percentages) by the page. */
type D = Record<string, string | undefined>;
/** One sentence per action, in the past tense. */
type Sentences = Record<AuditAction, (d: D) => string>;
const sentences = (all: Sentences): Sentences => all;

export const activityEn = {
  title: "Activity log",
  introOwner:
    "Sensitive actions in the household: sign-ins, deletions and household changes. Entries about a member's private wealth line or goal are only shown to them.",
  introMember: "Your sensitive actions: sign-ins, deletions and changes.",
  loadFailed: "Could not load the activity log.",
  kind: "Kind",
  allKinds: "Everything",
  kinds: {
    sign_in: "Sign-ins",
    household: "Household",
    deletion: "Deletions",
  },
  member: "Member",
  allMembers: "Everyone",
  when: "When",
  who: "Who",
  what: "What",
  address: "Address",
  removedMember: "A former member",
  empty: "Nothing logged yet.",
  previous: "Newer",
  next: "Older",
  page: (first: number, last: number, total: number) => `${first}–${last} of ${total}`,
  actions: sentences({
    signed_in: (d) =>
      d.method === "recovery_code" ? "Signed in with a recovery code" : "Signed in",
    sign_in_failed: (d) =>
      d.step === "code" ? "Failed sign-in: wrong code" : "Failed sign-in: wrong password",
    signed_out: () => "Signed out",
    recovery_codes_renewed: () => "Renewed the recovery codes",
    invite_created: (d) => `Invited ${d.email}`,
    invite_revoked: (d) => `Revoked the invitation of ${d.email}`,
    member_joined: (d) => `Joined the household (${d.email})`,
    settings_changed: (d) =>
      d.precaution_share !== undefined
        ? `Set the precaution share of the goals' effort to ${d.precaution_share}`
        : d.goal_capacity !== undefined
          ? d.goal_capacity
            ? `Set the goals' monthly capacity to ${d.goal_capacity}`
            : "Set the goals' capacity to follow the income minus spending"
          : d.wealth_start !== undefined
            ? d.wealth_start
              ? `Set the wealth to start in ${d.wealth_start}`
              : "Cleared the wealth start"
            : d.analysis_start === undefined
              ? `Set the budget warning threshold to ${d.warn_at}`
              : d.analysis_start
                ? `Set the analyses to start in ${d.analysis_start}`
                : "Set the analyses to count every month",
    wealth_line_deleted: (d) => `Deleted the wealth line ${d.name} (${d.category})`,
    wealth_category_deleted: (d) => `Deleted the wealth category ${d.name}`,
    goal_deleted: (d) => `Deleted the goal ${d.name}`,
    spending_line_deleted: (d) => `Deleted the line “${d.label}” (${d.amount}, ${d.date})`,
    spending_category_deleted: (d) =>
      d.moved_to
        ? `Deleted the category ${d.name}, its lines moved to ${d.moved_to}`
        : `Deleted the category ${d.name}`,
    fixed_expense_deleted: (d) => `Deleted the fixed expense “${d.label}” (${d.amount})`,
    categories_restored: (d) =>
      d.count !== undefined
        ? `Restored the default categories: ${d.count} added back`
        : `Restored the default categories: ${d.created} created, ${d.merged} merged, ${d.deleted} deleted`,
  }),
};

export const activityFr: typeof activityEn = {
  title: "Journal d'activité",
  introOwner:
    "Les actions sensibles du foyer : connexions, suppressions et changements du foyer. Ce qui touche à une ligne de patrimoine ou à un objectif privés d'un membre n'est montré qu'à lui.",
  introMember: "Vos actions sensibles : connexions, suppressions et changements.",
  loadFailed: "Impossible de charger le journal d'activité.",
  kind: "Type",
  allKinds: "Tout",
  kinds: {
    sign_in: "Connexions",
    household: "Foyer",
    deletion: "Suppressions",
  },
  member: "Membre",
  allMembers: "Tout le monde",
  when: "Quand",
  who: "Qui",
  what: "Quoi",
  address: "Adresse",
  removedMember: "Un ancien membre",
  empty: "Rien n'est encore enregistré.",
  previous: "Plus récentes",
  next: "Plus anciennes",
  page: (first, last, total) => `${first}–${last} sur ${total}`,
  actions: {
    signed_in: (d) =>
      d.method === "recovery_code" ? "Connexion avec un code de secours" : "Connexion",
    sign_in_failed: (d) =>
      d.step === "code"
        ? "Connexion refusée : code erroné"
        : "Connexion refusée : mot de passe erroné",
    signed_out: () => "Déconnexion",
    recovery_codes_renewed: () => "Codes de secours renouvelés",
    invite_created: (d) => `Invitation envoyée à ${d.email}`,
    invite_revoked: (d) => `Invitation de ${d.email} annulée`,
    member_joined: (d) => `A rejoint le foyer (${d.email})`,
    settings_changed: (d) =>
      d.precaution_share !== undefined
        ? `Part de l'effort réservée à la précaution réglée à ${d.precaution_share}`
        : d.goal_capacity !== undefined
          ? d.goal_capacity
            ? `Capacité mensuelle des objectifs fixée à ${d.goal_capacity}`
            : "La capacité des objectifs suit de nouveau les revenus moins les dépenses"
          : d.wealth_start !== undefined
            ? d.wealth_start
              ? `Début du patrimoine fixé à ${d.wealth_start}`
              : "Début du patrimoine retiré"
            : d.analysis_start === undefined
              ? `Seuil d'alerte du budget réglé à ${d.warn_at}`
              : d.analysis_start
                ? `Début des analyses fixé à ${d.analysis_start}`
                : "Les analyses comptent de nouveau tous les mois",
    wealth_line_deleted: (d) => `Ligne de patrimoine ${d.name} (${d.category}) supprimée`,
    wealth_category_deleted: (d) => `Catégorie de patrimoine ${d.name} supprimée`,
    goal_deleted: (d) => `Objectif ${d.name} supprimé`,
    spending_line_deleted: (d) => `Ligne « ${d.label} » supprimée (${d.amount}, ${d.date})`,
    spending_category_deleted: (d) =>
      d.moved_to
        ? `Catégorie ${d.name} supprimée, ses lignes déplacées vers ${d.moved_to}`
        : `Catégorie ${d.name} supprimée`,
    fixed_expense_deleted: (d) => `Dépense fixe « ${d.label} » supprimée (${d.amount})`,
    categories_restored: (d) =>
      d.count !== undefined
        ? `Catégories par défaut restaurées : ${d.count} rajoutée(s)`
        : `Catégories par défaut restaurées : ${d.created} créées, ${d.merged} fusionnées, ${d.deleted} supprimées`,
  },
};
