"""The activity log of sensitive actions (F-ADM-3): what is recorded, by kind.

Who sees an entry is a query (kwak_api.services.audit): the owner the household's entries, a
member their own, and an entry about a private account only that account's owner.
"""

import enum


class AuditKind(enum.StrEnum):
    SIGN_IN = "sign_in"
    HOUSEHOLD = "household"
    IMPORT = "import"
    DELETION = "deletion"
    RULES = "rules"


class AuditAction(enum.StrEnum):
    kind: AuditKind

    def __new__(cls, value: str, kind: AuditKind) -> "AuditAction":
        member = str.__new__(cls, value)
        member._value_ = value
        member.kind = kind
        return member

    SIGNED_IN = "signed_in", AuditKind.SIGN_IN
    SIGN_IN_FAILED = "sign_in_failed", AuditKind.SIGN_IN
    SIGNED_OUT = "signed_out", AuditKind.SIGN_IN
    RECOVERY_CODES_RENEWED = "recovery_codes_renewed", AuditKind.SIGN_IN
    INVITE_CREATED = "invite_created", AuditKind.HOUSEHOLD
    INVITE_REVOKED = "invite_revoked", AuditKind.HOUSEHOLD
    MEMBER_JOINED = "member_joined", AuditKind.HOUSEHOLD
    SETTINGS_CHANGED = "settings_changed", AuditKind.HOUSEHOLD
    IMPORTED = "imported", AuditKind.IMPORT
    IMPORT_ROLLED_BACK = "import_rolled_back", AuditKind.IMPORT
    TRANSACTION_DELETED = "transaction_deleted", AuditKind.DELETION
    CATEGORY_DELETED = "category_deleted", AuditKind.DELETION
    PLAN_DELETED = "plan_deleted", AuditKind.DELETION
    RECURRING_DELETED = "recurring_deleted", AuditKind.DELETION
    WEALTH_LINE_DELETED = "wealth_line_deleted", AuditKind.DELETION
    WEALTH_CATEGORY_DELETED = "wealth_category_deleted", AuditKind.DELETION
    GOAL_DELETED = "goal_deleted", AuditKind.DELETION
    RULE_CREATED = "rule_created", AuditKind.RULES
    RULE_UPDATED = "rule_updated", AuditKind.RULES
    RULE_DELETED = "rule_deleted", AuditKind.RULES
    RULES_APPLIED = "rules_applied", AuditKind.RULES
    CATEGORIES_RESTORED = "categories_restored", AuditKind.RULES
