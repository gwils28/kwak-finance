import json
from collections.abc import Iterator

import pytest
from kwak_api.cli import main
from kwak_api.models import Category, User
from kwak_api.settings import Settings
from kwak_core.users import Language
from sqlalchemy import select
from sqlalchemy.orm import Session


def _passwords(*values: str) -> Iterator[str]:
    return iter(values)


def _run(session: Session, argv: list[str], passwords: Iterator[str]) -> int:
    return main(
        argv, session_factory=lambda: session, read_password=lambda _prompt: next(passwords)
    )


def test_create_owner(session: Session, capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["create-owner", "--household", "Home", "--email", "o@example.com", "--name", "Owner"]
    code = _run(session, argv, _passwords("correct horse battery", "correct horse battery"))

    assert code == 0
    assert session.scalars(select(User.email)).all() == ["o@example.com"]
    assert "o@example.com" in capsys.readouterr().out


def test_create_owner_in_french_names_the_default_categories_in_french(
    session: Session,
) -> None:
    argv = ["create-owner", "--household", "Home", "--email", "o@example.com", "--name", "Owner"]
    code = _run(
        session,
        [*argv, "--language", "fr"],
        _passwords("correct horse battery", "correct horse battery"),
    )

    assert code == 0
    owner = session.scalars(select(User)).one()
    assert owner.language == Language.FR
    names = set(session.scalars(select(Category.name)))
    assert {"Alimentation", "Courses", "Revenus"} <= names
    assert "Groceries" not in names


def test_create_owner_fails_when_the_passwords_differ(
    session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["create-owner", "--household", "Home", "--email", "o@example.com", "--name", "Owner"]
    code = _run(session, argv, _passwords("correct horse battery", "correct horse batterY"))

    assert code == 1
    assert session.scalars(select(User)).all() == []
    assert "do not match" in capsys.readouterr().err


def test_create_owner_reports_a_rule_violation(
    session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["create-owner", "--household", "Home", "--email", "o@example.com", "--name", "Owner"]
    code = _run(session, argv, _passwords("short", "short"))

    assert code == 1
    assert "password" in capsys.readouterr().err


def test_generate_key_prints_a_valid_secret_key(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["generate-key"]) == 0
    key = capsys.readouterr().out.strip()
    assert len(Settings(secret_key=key).encryption_key) == 32


def test_openapi_prints_the_schema(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["openapi"]) == 0
    assert json.loads(capsys.readouterr().out)["info"]["title"] == "Kwak Finance API"
