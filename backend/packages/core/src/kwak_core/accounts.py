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
    SHARED = "shared"  # every household member


def can_view(*, owner_id: UUID, visibility: Visibility, viewer_id: UUID) -> bool:
    """Within one household: the owner sees everything, others see shared accounts."""
    return owner_id == viewer_id or visibility is Visibility.SHARED
