"""Admin command line: `kwak migrate`, `kwak create-owner`, `kwak generate-key`, `kwak openapi`."""

import argparse
import base64
import getpass
import json
import secrets
import sys
from collections.abc import Callable, Sequence

from alembic import command
from kwak_core.users import Language
from sqlalchemy.orm import Session

from kwak_api.db import make_engine
from kwak_api.migrate import alembic_config
from kwak_api.services.households import HouseholdAlreadyExistsError, create_household
from kwak_api.settings import Settings


def _default_session() -> Session:
    return Session(make_engine(Settings().database_url))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kwak", description="Kwak Finance administration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="apply database migrations")
    commands.add_parser("generate-key", help="print a new KWAK_SECRET_KEY")
    commands.add_parser("openapi", help="print the OpenAPI schema (input of the TS client)")
    owner = commands.add_parser("create-owner", help="create the household and its owner")
    owner.add_argument("--household", required=True, help="household name")
    owner.add_argument("--email", required=True)
    owner.add_argument("--name", required=True, help="owner display name")
    owner.add_argument(
        "--language",
        choices=[language.value for language in Language],
        default=Language.EN.value,
        help="interface language, also used to name the default categories (default: en)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory: Callable[[], Session] = _default_session,
    read_password: Callable[[str], str] = getpass.getpass,
) -> int:
    args = _parser().parse_args(argv)

    if args.command == "generate-key":
        print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        return 0

    if args.command == "openapi":
        # Lazy: importing kwak_api.main builds the app, which needs a full configuration.
        from kwak_api.main import create_app

        print(json.dumps(create_app().openapi(), indent=2, sort_keys=True))
        return 0

    if args.command == "migrate":
        command.upgrade(alembic_config(Settings().database_url), "head")
        print("database is up to date")
        return 0

    password = read_password("Password: ")
    if read_password("Repeat password: ") != password:
        print("error: passwords do not match", file=sys.stderr)
        return 1
    with session_factory() as session:
        try:
            owner = create_household(
                session,
                household_name=args.household,
                email=args.email,
                display_name=args.name,
                password=password,
                language=Language(args.language),
            )
        except (ValueError, HouseholdAlreadyExistsError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        session.commit()
        print(f"created owner {owner.email} of household {owner.household.name!r}")
    return 0


def run() -> None:
    sys.exit(main())
