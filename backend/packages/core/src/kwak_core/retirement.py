"""Retirement (spec §4.13, invariants §8.37-39), in `Decimal`: each member's months and
amounts, the household's settings, and the plan's savings month by month, which the Monte
Carlo engine (`kwak_analytics.montecarlo`) draws the paths from.

Amounts entered are in today's euros; the plan's savings are in current euros, as the
projection's (`kwak_core.projection.savings_path`). Months are counted from this month: month 0
is now, month t the t-th one after.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import Month
from kwak_core.goals import add_months, months_between
from kwak_core.money import quantize
from kwak_core.projection import DebtTerms, ProjectionError, amortise

ZERO = Decimal(0)
ONE = Decimal(1)

# F-RET-2: the household's settings

DEFAULT_SPENDING_SHARE = Decimal("0.8")
"""One spends less on work and on the children, more on health and leisure."""
MIN_SPENDING_SHARE = Decimal("0.5")
MAX_SPENDING_SHARE = Decimal("1.5")
SHARE_STEP = Decimal("0.01")

DEFAULT_INDEXATION = Decimal("-0.003")
"""Pensions against inflation: base pensions follow prices by law, supplementary ones have
often been raised by less (frozen from 2015 to 2018 and in November 2025)."""
MIN_INDEXATION = Decimal("-0.02")
MAX_INDEXATION = Decimal("0.01")
INDEXATION_STEP = Decimal("0.001")

DEFAULT_HORIZON_AGE = 95
"""The youngest member's age at which the plan ends: a margin, not a ceiling."""
MIN_HORIZON_AGE = 85
MAX_HORIZON_AGE = 105
MAX_YEARS = 80
"""The plan never runs more than 80 years from now."""


def check_spending_share(share: Decimal) -> None:
    if share != share.quantize(SHARE_STEP):
        raise ProjectionError("the retirement spending is a whole percentage")
    if not MIN_SPENDING_SHARE <= share <= MAX_SPENDING_SHARE:
        raise ProjectionError("the retirement spending is from 50 to 150 % of today's")


def check_indexation(rate: Decimal) -> None:
    if rate != rate.quantize(INDEXATION_STEP):
        raise ProjectionError("the pensions' indexation is set to 0.1 % at most")
    if not MIN_INDEXATION <= rate <= MAX_INDEXATION:
        raise ProjectionError("the pensions' indexation is from -2 % to +1 % a year")


def check_horizon_age(years: int) -> None:
    if not MIN_HORIZON_AGE <= years <= MAX_HORIZON_AGE:
        raise ProjectionError("the horizon is an age from 85 to 105")


# F-RET-1: the members


@dataclass(frozen=True)
class Member:
    id: UUID
    birth: Month | None
    """None: the member is left out of the plan, and the page names them."""
    retirement: Month
    """When the member stops working; a past month for one already retired."""
    earnings: Decimal
    """Net monthly earnings that stop then, as they reach the account, in today's euros."""
    pension_month: Month
    """From when the pension is received: the retirement month or later."""
    pension: Decimal
    """Net monthly pension as it would reach the account, in today's euros."""


def _amount(value: Decimal) -> None:
    if value < 0 or value != quantize(value):
        raise ProjectionError("earnings and pensions are positive, in cents at most")


def check_member(member: Member) -> None:
    _amount(member.earnings)
    _amount(member.pension)
    if member.pension_month < member.retirement:
        raise ProjectionError("a pension starts with the retirement or later")
    if member.birth is not None and member.birth >= member.retirement:
        raise ProjectionError("one retires after being born")


def age(birth: Month, month: Month) -> int:
    """Whole years in `month`, counted from the birth month."""
    return months_between(birth, month) // 12


def counted(members: Sequence[Member]) -> list[Member]:
    """The members the plan counts: those with a birth month."""
    return [m for m in members if m.birth is not None]


def household_retirement(members: Sequence[Member]) -> Month | None:
    """The household retires with its last member."""
    return max((m.retirement for m in members), default=None)


def horizon(members: Sequence[Member], horizon_age: int, this_month: Month) -> Month:
    """When the youngest member reaches `horizon_age`, at most 80 years from now."""
    youngest = max(m.birth for m in members if m.birth is not None)
    return min(add_months(youngest, horizon_age * 12), add_months(this_month, MAX_YEARS * 12))


# F-RET-2: the retirement spending


def spending_base(average_spending: Decimal, debt_payments: Decimal) -> Decimal:
    """Today's average monthly spending outside the debts' payments and borrower insurance,
    which are spending lines: the plan spends them apart, until each loan is repaid."""
    return max(ZERO, average_spending - debt_payments)


def retirement_spending(
    base: Decimal, *, share: Decimal | None = None, amount: Decimal | None = None
) -> Decimal:
    """A share of the base, or an amount entered by hand, in today's euros."""
    if amount is not None:
        return amount
    return quantize(base * (share if share is not None else DEFAULT_SPENDING_SHARE))


# F-RET-3: the plan's savings


@dataclass(frozen=True)
class Debt:
    owed: Decimal
    """What it owes at the start."""
    terms: DebtTerms


def _grown(amount: Decimal, rate: Decimal, t: int) -> Decimal:
    """An amount of today's euros in month t, growing by `rate` a year."""
    return quantize(amount * (ONE + rate) ** (Decimal(t) / 12))


def _paid(debt: Debt, months: int) -> list[Decimal]:
    """What a debt costs each month, payment and insurance, until it is repaid."""
    owed = [debt.owed, *amortise(debt.owed, debt.terms, months=months).owed]
    payment = debt.terms.payment
    out: list[Decimal] = []
    for t in range(1, months + 1):
        before = owed[t - 1]
        if before <= 0 or payment is None:
            out.append(ZERO)
            continue
        interest = quantize(before * debt.terms.rate / 12)
        out.append(before + interest - owed[t] + debt.terms.insurance)
    return out


def plan_savings(
    members: Sequence[Member],
    *,
    capacity: Decimal,
    spending: Decimal,
    debts: Sequence[Debt],
    inflation: Decimal,
    indexation: Decimal,
    this_month: Month,
    months: int,
) -> list[Decimal]:
    """The savings of months 1 to n in current euros (negative: withdrawn). `members` are the
    counted ones. Before the household retires: the capacity, less the earnings of members who
    retire, plus their pensions as they start (one already received is in the capacity), and
    the debts' freed payments, as in the projection (invariant §8.37). From then on: the
    pensions, indexed to inflation plus `indexation`, less the retirement spending, indexed to
    inflation, less what the debts still cost; a repaid debt then frees nothing."""
    retired = household_retirement(members)
    freed = [ZERO] * months
    cost = [ZERO] * months
    for debt in debts:
        freed = [
            a + b
            for a, b in zip(
                freed, amortise(debt.owed, debt.terms, months=months).freed, strict=True
            )
        ]
        cost = [a + b for a, b in zip(cost, _paid(debt, months), strict=True)]
    pension_rate = inflation + indexation
    out: list[Decimal] = []
    for t in range(1, months + 1):
        month = add_months(this_month, t)
        pensions = sum(
            (_grown(m.pension, pension_rate, t) for m in members if m.pension_month <= month),
            ZERO,
        )
        if retired is None or month < retired:
            lost = sum(
                (
                    _grown(m.earnings, inflation, t)
                    for m in members
                    if this_month < m.retirement <= month
                ),
                ZERO,
            )
            started = sum(
                (
                    _grown(m.pension, pension_rate, t)
                    for m in members
                    if this_month < m.pension_month <= month
                ),
                ZERO,
            )
            out.append(_grown(capacity, inflation, t) - lost + started + freed[t - 1])
        else:
            out.append(pensions - _grown(spending, inflation, t) - cost[t - 1])
    return out
