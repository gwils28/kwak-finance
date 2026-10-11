"""Account kinds and who may see an account (docs/SPECIFICATIONS.md §3, §4.2)."""

import enum
from uuid import UUID


class AccountType(enum.StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"  # livret A, LDDS, PEL…
    BROKERAGE = "brokerage"  # PEA, CTO
    LIFE_INSURANCE = "life_insurance"
    EMPLOYEE_SAVINGS = "employee_savings"  # PEE/PEG, PERCOL, PER
    CRYPTO = "crypto"
    LOAN = "loan"
    REAL_ESTATE = "real_estate"
    USE_ASSET = "use_asset"
    OTHER = "other"


# Accounts whose balance is the sum of their transactions (F-WLT-1): the budget's scope.
CASH_TYPES = frozenset({AccountType.CHECKING, AccountType.SAVINGS})


class Visibility(enum.StrEnum):
    PRIVATE = "private"  # its owner only
    SHARED = "shared"  # every household member, still one member's account
    JOINT = "joint"  # the household's common account: every member, nobody's own


def can_view(*, owner_id: UUID, visibility: Visibility, viewer_id: UUID) -> bool:
    """Within one household: the owner sees everything, others all but private accounts."""
    return owner_id == viewer_id or visibility is not Visibility.PRIVATE


class Scope(enum.StrEnum):
    """Which accounts an aggregated view (budget, dashboard) covers (F-BUD-3)."""

    HOUSEHOLD = "household"
    """Every account the viewer can see."""
    MINE = "mine"
    """The viewer's own accounts, without the joint ones even if the viewer created them."""
    JOINT = "joint"
    """The household's joint accounts, whoever created them."""


def in_scope(scope: Scope, *, owner_id: UUID, visibility: Visibility, viewer_id: UUID) -> bool:
    if scope is Scope.MINE:
        return owner_id == viewer_id and visibility is not Visibility.JOINT
    if scope is Scope.JOINT:
        return visibility is Visibility.JOINT
    return can_view(owner_id=owner_id, visibility=visibility, viewer_id=viewer_id)
