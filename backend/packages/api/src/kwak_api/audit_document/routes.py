"""The audit document (spec §4.15): built on demand from what the viewer sees, nothing stored;
printing, copying or downloading it is logged without a figure (F-AUD-1)."""

from fastapi import APIRouter, HTTPException, status
from kwak_core.audit import AuditAction
from kwak_core.audit_document import Audience, AuditError, Privacy, check_period, default_privacy
from kwak_core.budget import Month

from kwak_api.audit_document.schemas import AuditIn, AuditIssuedIn, AuditOut, AuditPrivacyIn
from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.services import audit
from kwak_api.services import audit_document as service

router = APIRouter(prefix="/api/audit-document", tags=["audit-document"])


@router.get("/privacy/{audience}")
def audit_privacy_defaults(audience: Audience, user_session: CurrentSession) -> AuditPrivacyIn:
    """The audience's privacy defaults, which the form starts from (F-AUD-4)."""
    p: Privacy = default_privacy(audience)
    return AuditPrivacyIn(
        named_members=p.named_members, named_lines=p.named_lines, exact_amounts=p.exact_amounts
    )


@router.post("")
def audit_document(body: AuditIn, db: Db, user_session: CurrentSession, now: Now) -> AuditOut:
    """Rebuilt as the form changes: writes nothing, not even to the activity log."""
    try:
        return service.build(db, user_session.user, body, now)
    except AuditError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None


@router.post("/issued", status_code=status.HTTP_204_NO_CONTENT)
def audit_document_issued(
    body: AuditIssuedIn, db: Db, user_session: CurrentSession, now: Now
) -> None:
    try:
        check_period(Month.parse(body.start), Month.parse(body.end), current=Month.of(now.date()))
    except AuditError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    audit.record(
        db,
        user_session.user,
        AuditAction.AUDIT_DOCUMENT_ISSUED,
        now,
        audience=body.audience.value,
        scope=body.scope.value,
        start=body.start,
        end=body.end,
        how=body.how,
    )
