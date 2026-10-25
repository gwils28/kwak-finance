"""The demo (spec §4.9 F-ADM-5): open it, leave it, reset it. The session then acts as the
demo's owner (or no longer), so every other endpoint shows the demo household."""

from fastapi import APIRouter, HTTPException, status

from kwak_api.auth.routes import CurrentSession, Db, Now, UserOut
from kwak_api.services import demo as service

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/enter")
def enter(user_session: CurrentSession, db: Db, now: Now) -> UserOut:
    """Act as the demo's owner; the demo is generated the first time it is opened."""
    if user_session.acting_user_id is None:
        service.enter(db, user_session, now)
    return UserOut.of_session(user_session)


@router.post("/leave")
def leave(user_session: CurrentSession) -> UserOut:
    service.leave(user_session)
    return UserOut.of_session(user_session)


@router.post("/reset")
def reset(user_session: CurrentSession, db: Db, now: Now) -> UserOut:
    """Generate the demo again, dated from today; what anyone changed in it is lost."""
    if user_session.acting_user_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "open the demo first")
    try:
        service.reset(db, user_session, now)
    except service.ResetTooSoonError:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "the demo was just generated: wait a minute"
        ) from None
    return UserOut.of_session(user_session)
