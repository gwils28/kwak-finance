"""FastAPI dependencies shared by the routers."""

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from kwak_api.auth.crypto import SecretBox
from kwak_api.settings import Settings


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def request_scope(session: Session) -> Iterator[Session]:
    """Commit when the handler succeeds, roll back when it raises.

    Handlers may commit earlier themselves, e.g. to keep a record of a failed login
    that the error response would otherwise roll back.
    """
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    session.commit()


def get_db(request: Request) -> Iterator[Session]:
    """One database session per request."""
    factory: sessionmaker[Session] = request.app.state.sessionmaker
    with factory() as session:
        yield from request_scope(session)


def get_now() -> datetime:
    return datetime.now(UTC)


def get_secret_box(request: Request) -> SecretBox:
    return SecretBox(get_settings(request).encryption_key)
