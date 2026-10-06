from datetime import timedelta

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey
from sqlalchemy import Connection, MetaData, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session


class _TestBase(DeclarativeBase):
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)


class Widget(UUIDPrimaryKey, Timestamps, _TestBase):
    __tablename__ = "widget"
    name: Mapped[str]


def _create_table(connection: Connection) -> None:
    _TestBase.metadata.create_all(connection)


def test_new_rows_get_a_uuid7_and_utc_timestamps(connection: Connection, session: Session) -> None:
    _create_table(connection)
    widget = Widget(name="a")
    session.add(widget)
    session.flush()
    session.refresh(widget)

    assert widget.id.version == 7
    assert widget.created_at.utcoffset() == timedelta(0)
    assert widget.updated_at == widget.created_at


def test_updated_at_changes_on_update(connection: Connection, session: Session) -> None:
    _create_table(connection)
    widget = Widget(name="a")
    session.add(widget)
    session.flush()
    # now() is frozen within a transaction, so age the row instead of waiting.
    session.execute(text("UPDATE widget SET updated_at = updated_at - interval '1 day'"))
    session.refresh(widget)
    aged = widget.updated_at

    widget.name = "b"
    session.flush()
    session.refresh(widget)

    assert widget.updated_at > aged
