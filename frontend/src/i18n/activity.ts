import type { AuditAction } from "../api/generated";

/** The details of an entry, already formatted (amounts, dates, percentages) by the page. */
type D = Record<string, string | undefined>;
/** One sentence per action, in the past tense. */
type Sentences = Record<AuditAction, (d: D) => string>;
const sentences = (all: Sentences): Sentences => all;

const ruleEn = (d: D) =>
  [
    d.label ? `“${d.label}”` : null,
    d.min || d.max ? `${d.min ?? "…"} to ${d.max ?? "…"}` : null,
    d.account ? `on ${d.account}` : null,
  ]
    .filter(Boolean)
    .join(", ") || "any transaction";

const ruleFr = (d: D) =>
  [
    d.label ? `« ${d.label} »` : null,
    d.min || d.max ? `de ${d.min ?? "…"} à ${d.max ?? "…"}` : null,
    d.account ? `sur ${d.account}` : null,
  ]
    .filter(Boolean)
    .join(", ") || "toute opération";

export const activityEn = {
  title: "Activity log",
  introOwner:
    "Sensitive actions in the household: sign-ins, imports, deletions, rule and household changes. Entries about a member's private account are only shown to them.",
  introMember: "Your sensitive actions: sign-ins, imports, deletions and rule changes.",
  loadFailed: "Could not load the activity log.",
  kind: "Kind",
  allKinds: "Everything",
  kinds: {
    sign_in: "Sign-ins",
    household: "Household",
    import: "Imports",
    deletion: "Deletions",
    rules: "Rules and categories",
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
            : "Set the goals' capacity to follow the net cash flow"
          : d.wealth_start !== undefined
            ? d.wealth_start
              ? `Set the wealth to start in ${d.wealth_start}`
              : "Set the wealth to follow the analyses start"
            : d.analysis_start === undefined
              ? `Set the budget warning threshold to ${d.warn_at}`
              : d.analysis_start
                ? `Set the analyses to start in ${d.analysis_start}`
                : "Set the analyses to count every month",
    imported: (d) => `Imported ${d.file} into ${d.account}: ${d.added} transactions added`,
    import_rolled_back: (d) => `Rolled back the import of ${d.file} on ${d.account}`,
    transaction_deleted: (d) => `Deleted “${d.label}” (${d.amount}, ${d.date}) on ${d.account}`,
    category_deleted: (d) => `Deleted the category ${d.name}`,
    plan_deleted: (d) => `Deleted the budget plan ${d.period}`,
    wealth_line_deleted: (d) => `Deleted the wealth line ${d.name} (${d.category})`,
    wealth_category_deleted: (d) => `Deleted the wealth category ${d.name}`,
    goal_deleted: (d) => `Deleted the goal ${d.name}`,
    recurring_deleted: (d) =>
      `Deleted the recurring item ${d.label ? `“${d.label}” ` : ""}(${d.amount}) on ${d.account}`,
    rule_created: (d) => `Created a rule: ${ruleEn(d)} → ${d.category}`,
    rule_updated: (d) => `Changed a rule: ${ruleEn(d)} → ${d.category}`,
    rule_deleted: (d) => `Deleted a rule: ${ruleEn(d)} → ${d.category}`,
    rules_applied: (d) => `Applied the rules: ${d.updated} transactions categorised`,
    categories_restored: (d) =>
      `Restored the default categories: ${d.created} created, ${d.merged} merged, ${d.deleted} deleted`,
  }),
};

export const activityFr: typeof activityEn = {
  title: "Journal d'activité",
  introOwner:
    "Les actions sensibles du foyer : connexions, imports, suppressions, changements de règles et du foyer. Ce qui touche au compte privé d'un membre n'est montré qu'à lui.",
  introMember:
    "Vos actions sensibles : connexions, imports, suppressions et changements de règles.",
  loadFailed: "Impossible de charger le journal d'activité.",
  kind: "Type",
  allKinds: "Tout",
  kinds: {
    sign_in: "Connexions",
    household: "Foyer",
    import: "Imports",
    deletion: "Suppressions",
    rules: "Règles et catégories",
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
            : "La capacité des objectifs suit de nouveau le solde net"
          : d.wealth_start !== undefined
            ? d.wealth_start
              ? `Début du patrimoine fixé à ${d.wealth_start}`
              : "Le patrimoine suit de nouveau le début des analyses"
            : d.analysis_start === undefined
              ? `Seuil d'alerte du budget réglé à ${d.warn_at}`
              : d.analysis_start
                ? `Début des analyses fixé à ${d.analysis_start}`
                : "Les analyses comptent de nouveau tous les mois",
    imported: (d) => `Import de ${d.file} dans ${d.account} : ${d.added} opérations ajoutées`,
    import_rolled_back: (d) => `Import de ${d.file} sur ${d.account} annulé`,
    transaction_deleted: (d) =>
      `« ${d.label} » supprimée (${d.amount}, ${d.date}) sur ${d.account}`,
    category_deleted: (d) => `Catégorie ${d.name} supprimée`,
    plan_deleted: (d) => `Plan de budget ${d.period} supprimé`,
    wealth_line_deleted: (d) => `Ligne de patrimoine ${d.name} (${d.category}) supprimée`,
    wealth_category_deleted: (d) => `Catégorie de patrimoine ${d.name} supprimée`,
    goal_deleted: (d) => `Objectif ${d.name} supprimé`,
    recurring_deleted: (d) =>
      `Échéance ${d.label ? `« ${d.label} » ` : ""}(${d.amount}) supprimée sur ${d.account}`,
    rule_created: (d) => `Règle créée : ${ruleFr(d)} → ${d.category}`,
    rule_updated: (d) => `Règle modifiée : ${ruleFr(d)} → ${d.category}`,
    rule_deleted: (d) => `Règle supprimée : ${ruleFr(d)} → ${d.category}`,
    rules_applied: (d) => `Règles appliquées : ${d.updated} opérations catégorisées`,
    categories_restored: (d) =>
      `Catégories par défaut restaurées : ${d.created} créées, ${d.merged} fusionnées, ${d.deleted} supprimées`,
  },
};
