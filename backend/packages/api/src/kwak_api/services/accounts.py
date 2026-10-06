"""Accounts and institutions, with per-account visibility (docs/SPECIFICATIONS.md §3)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TypedDict
from uuid import UUID

from kwak_core.accounts import AccountType, Visibility, can_view
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from kwak_api.models import Account, Institution, User


class DuplicateAccountError(Exception):
    """This institution already has an account with this name."""


@dataclass
class AccountInput:
    name: str
    institution_name: str
    type: AccountType
    visibility: Visibility
    opening_balance: Decimal
    opening_date: date


class AccountChanges(TypedDict, total=False):
    name: str
    institution_name: str
    type: AccountType
    visibility: Visibility
    opening_balance: Decimal
    opening_date: date
    closed_on: date | None


def _visible(account: Account, viewer: User) -> bool:
    return can_view(owner_id=account.owner_id, visibility=account.visibility, viewer_id=viewer.id)


def institution_named(db: Session, household_id: UUID, name: str) -> Institution:
    """The household's institution with this name (any case), created if needed."""
    name = " ".join(name.split())
    if not name:
        raise ValueError("institution name is required")
    institution = db.scalar(
        select(Institution).where(
            Institution.household_id == household_id, func.lower(Institution.name) == name.lower()
        )
    )
    if institution is None:
        institution = Institution(household_id=household_id, name=name)
        db.add(institution)
        db.flush()
    return institution


def institution_names(db: Session, household_id: UUID) -> list[str]:
    return list(
        db.scalars(
            select(Institution.name)
            .where(Institution.household_id == household_id)
            .order_by(func.lower(Institution.name))
        )
    )


def visible_accounts(db: Session, viewer: User, *, include_closed: bool) -> list[Account]:
    query = (
        select(Account)
        .where(Account.household_id == viewer.household_id)
        .options(joinedload(Account.institution), joinedload(Account.owner))
    )
    if not include_closed:
        query = query.where(Account.closed_on.is_(None))
    accounts = [a for a in db.scalars(query) if _visible(a, viewer)]
    return sorted(accounts, key=lambda a: (a.institution.name.lower(), a.name.lower()))


def find_visible_account(db: Session, viewer: User, account_id: UUID) -> Account | None:
    account = db.get(Account, account_id)
    if account is None or account.household_id != viewer.household_id:
        return None
    return account if _visible(account, viewer) else None


def _flush_unique(db: Session, account: Account) -> None:
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as exc:
        if "uq_account_institution_name" in str(exc.orig):
            raise DuplicateAccountError(account.name) from None
        raise


def create_account(db: Session, owner: User, data: AccountInput) -> Account:
    name = data.name.strip()
    if not name:
        raise ValueError("account name is required")
    account = Account(
        household_id=owner.household_id,
        institution=institution_named(db, owner.household_id, data.institution_name),
        owner=owner,
        name=name,
        type=data.type,
        visibility=data.visibility,
        opening_balance=data.opening_balance,
        opening_date=data.opening_date,
    )
    db.add(account)
    _flush_unique(db, account)
    return account


def update_account(db: Session, editor: User, account: Account, changes: AccountChanges) -> None:
    """Apply the given fields. Any member may edit a shared account; only its owner changes
    who can see it.
    """
    visibility = changes.get("visibility", account.visibility)
    if visibility != account.visibility and account.owner_id != editor.id:
        raise PermissionError("only the account owner can change its visibility")
    if "institution_name" in changes:
        account.institution = institution_named(
            db, account.household_id, changes["institution_name"]
        )
    if "name" in changes:
        if not changes["name"].strip():
            raise ValueError("account name is required")
        account.name = changes["name"].strip()
    account.visibility = visibility
    account.type = changes.get("type", account.type)
    account.opening_balance = changes.get("opening_balance", account.opening_balance)
    account.opening_date = changes.get("opening_date", account.opening_date)
    if "closed_on" in changes:
        account.closed_on = changes["closed_on"]
    if account.closed_on is not None and account.closed_on < account.opening_date:
        raise ValueError("an account cannot close before it opened")
    _flush_unique(db, account)
