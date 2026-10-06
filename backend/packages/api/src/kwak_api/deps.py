"""FastAPI dependencies shared by the routers."""

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from kwak_api.settings import Settings


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Iterator[Session]:
    """One database session per request, committed when the handler succeeds."""
    factory: sessionmaker[Session] = request.app.state.sessionmaker
    with factory() as session, session.begin():
        yield session


def get_now() -> datetime:
    return datetime.now(UTC)
