"""The activity log of sensitive actions (F-ADM-3): what is recorded, by kind.

Who sees an entry is a query (kwak_api.services.audit): the owner the household's entries, a
member their own, and an entry about a private wealth line or goal only its owner.
"""

import enum


class AuditKind(enum.StrEnum):
    SIGN_IN = "sign_in"
    HOUSEHOLD = "household"
    DELETION = "deletion"


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
    WEALTH_LINE_DELETED = "wealth_line_deleted", AuditKind.DELETION
    WEALTH_CATEGORY_DELETED = "wealth_category_deleted", AuditKind.DELETION
    GOAL_DELETED = "goal_deleted", AuditKind.DELETION
    SPENDING_LINE_DELETED = "spending_line_deleted", AuditKind.DELETION
    SPENDING_CATEGORY_DELETED = "spending_category_deleted", AuditKind.DELETION
    FIXED_EXPENSE_DELETED = "fixed_expense_deleted", AuditKind.DELETION
    CATEGORIES_RESTORED = "categories_restored", AuditKind.HOUSEHOLD
