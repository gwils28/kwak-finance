from kwak_core.audit import AuditAction, AuditKind


def test_every_action_belongs_to_one_kind() -> None:
    assert AuditAction.SIGNED_IN.kind is AuditKind.SIGN_IN
    assert AuditAction.SIGN_IN_FAILED.kind is AuditKind.SIGN_IN
    assert AuditAction.INVITE_CREATED.kind is AuditKind.HOUSEHOLD
    assert AuditAction.CATEGORIES_RESTORED.kind is AuditKind.HOUSEHOLD
    assert AuditAction.SPENDING_LINE_DELETED.kind is AuditKind.DELETION
    assert {a.kind for a in AuditAction} == set(AuditKind)
