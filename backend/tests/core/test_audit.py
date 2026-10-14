from kwak_core.audit import AuditAction, AuditKind


def test_every_action_belongs_to_one_kind() -> None:
    assert AuditAction.SIGNED_IN.kind is AuditKind.SIGN_IN
    assert AuditAction.SIGN_IN_FAILED.kind is AuditKind.SIGN_IN
    assert AuditAction.INVITE_CREATED.kind is AuditKind.HOUSEHOLD
    assert AuditAction.IMPORTED.kind is AuditKind.IMPORT
    assert AuditAction.TRANSACTION_DELETED.kind is AuditKind.DELETION
    assert AuditAction.RULE_UPDATED.kind is AuditKind.RULES
    assert {a.kind for a in AuditAction} == set(AuditKind)
