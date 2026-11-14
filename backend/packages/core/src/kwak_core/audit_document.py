"""The audit document for a chosen reader (§4.15, F-AUD, invariants §8.47 to §8.49).

The rules the document is built from: its period, its privacy (pseudonyms and rounding), the
facts it sums up and the debt ratio, and the property project a banker reads. The document
itself is assembled by the API from these, with nothing stored.
"""

import enum
from collections.abc import Collection, Hashable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from types import MappingProxyType
from uuid import UUID

from kwak_core.budget import Month, month_range
from kwak_core.goals import add_months
from kwak_core.money import quantize
from kwak_core.projection import DebtTerms, amortise, debt_grows
from kwak_core.spending import MonthFigures

ZERO = Decimal(0)
ONE = Decimal(1)


class AuditError(ValueError):
    """A setting the document cannot be built with."""


class Audience(enum.StrEnum):
    BANKER = "banker"
    """A mortgage application."""
    ADVISOR = "advisor"
    """A wealth-management advisor (CGP)."""
    NOTARY = "notary"
    """An accountant or a notary."""
    AI = "ai"
    """An AI chat asked for an audit and advice, as Markdown."""


# F-AUD-1: the period

DEFAULT_MONTHS = 12
MAX_MONTHS = 60


@dataclass(frozen=True)
class AuditPeriod:
    start: Month
    end: Month
    shortened: bool
    """The history is shorter than the default twelve months: the document says so."""


def default_period(*, current: Month, since: Month | None) -> AuditPeriod:
    """The last complete month and the eleven before, or from the first month holding a line
    (`since`) when the history is shorter; at least the last complete month."""
    end = current.previous()
    start = add_months(end, 1 - DEFAULT_MONTHS)
    if since is not None and since > start:
        return AuditPeriod(min(since, end), end, shortened=True)
    return AuditPeriod(start, end, shortened=False)


def check_period(start: Month, end: Month, *, current: Month) -> None:
    """Complete months only, 1 to 60 of them."""
    if end >= current:
        raise AuditError("the period ends with the last complete month at the latest")
    if end < start:
        raise AuditError("the period ends before it starts")
    if len(month_range(start, end)) > MAX_MONTHS:
        raise AuditError(f"the period covers {MAX_MONTHS} months at most")


# F-AUD-4: privacy


@dataclass(frozen=True)
class Privacy:
    named_members: bool
    """Else Member A, Member B, the household never by its name and goals by tier."""
    named_lines: bool
    """Else each wealth line by its envelope or its category, numbered."""
    exact_amounts: bool
    """Else monthly amounts to €10, wealth and debts to €1,000."""


def default_privacy(audience: Audience) -> Privacy:
    if audience is Audience.AI:
        return Privacy(named_members=False, named_lines=False, exact_amounts=True)
    return Privacy(named_members=True, named_lines=True, exact_amounts=True)


def member_letter(index: int) -> str:
    """A, B, ..., Z, AA, AB, ...: the member's letter from its place, from 0."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def number_within(items: Sequence[tuple[UUID, Hashable]]) -> dict[UUID, int]:
    """Each item's number within its group (an envelope, a category, a tier), from 1, in the
    order given: PEA 1, PEA 2, Savings account 1."""
    seen: dict[Hashable, int] = {}
    out: dict[UUID, int] = {}
    for item_id, group in items:
        seen[group] = seen.get(group, 0) + 1
        out[item_id] = seen[group]
    return out


MONTHLY_STEP = Decimal(10)
WEALTH_STEP = Decimal(1000)


def rounded(amount: Decimal, step: Decimal) -> Decimal:
    """To the nearest step, half away from zero."""
    return (amount / step).quantize(ONE, rounding=ROUND_HALF_UP) * step


def rounded_parts[K: Hashable](parts: Mapping[K, Decimal], step: Decimal) -> dict[K, Decimal]:
    """Each part to a step, so that they add up to their rounded total (invariant §8.48): each
    part rounded down, then a step more to the largest remainders, the first of equals first."""
    floors = {k: (v / step).quantize(ONE, rounding=ROUND_FLOOR) * step for k, v in parts.items()}
    total = rounded(sum(parts.values(), ZERO), step)
    extra = int((total - sum(floors.values(), ZERO)) / step)
    order = sorted(parts, key=lambda k: parts[k] - floors[k], reverse=True)
    for k in order[:extra]:
        floors[k] += step
    return floors


@dataclass(frozen=True)
class RoundedWealth:
    assets: dict[UUID, Decimal]
    debts: dict[UUID, Decimal]
    gross: Decimal
    owed: Decimal

    @property
    def net(self) -> Decimal:
        return self.gross - self.owed


def rounded_wealth(
    assets: Mapping[UUID, Decimal], debts: Mapping[UUID, Decimal], step: Decimal
) -> RoundedWealth:
    """Assets and debts each rounded by part, net worth their difference, never rounded on
    its own (invariant §8.48): 1,600 of assets and 400 of debts show 2,000 - 0 = 2,000."""
    a = rounded_parts(assets, step)
    d = rounded_parts(debts, step)
    return RoundedWealth(a, d, sum(a.values(), ZERO), sum(d.values(), ZERO))


def percent(ratio: Decimal) -> Decimal:
    """A ratio as shown, a percentage to one decimal; compare the exact ratio, not this."""
    return (ratio * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


# F-AUD-2: the facts


@dataclass(frozen=True)
class Spread:
    total: Decimal
    average: Decimal
    """A month, to the cent."""
    lowest: tuple[Month, Decimal]
    highest: tuple[Month, Decimal]
    """The first of equal months."""


def spread(values: Sequence[tuple[Month, Decimal]]) -> Spread:
    """One measure (income, spent, saved or the rest) over the period's months."""
    if not values:
        raise AuditError("a period has a month at least")
    total = sum((v for _, v in values), ZERO)
    lowest = min(values, key=lambda mv: mv[1])
    highest = max(values, key=lambda mv: mv[1])
    return Spread(total, quantize(total / len(values)), lowest, highest)


def largest_first[K: Hashable](
    amounts: Mapping[K, Decimal], *, limit: int
) -> tuple[list[tuple[K, Decimal]], Decimal]:
    """The `limit` largest positive amounts, largest first, and the rest added up."""
    ranked = sorted(((k, v) for k, v in amounts.items() if v > 0), key=lambda kv: -kv[1])
    return ranked[:limit], sum((v for _, v in ranked[limit:]), ZERO)


@dataclass(frozen=True)
class YearTotals:
    year: int
    figures: MonthFigures
    months: int
    """How many of its months the period covers."""

    @property
    def partial(self) -> bool:
        return self.months < 12


def by_year(figures: Sequence[tuple[Month, MonthFigures]]) -> list[YearTotals]:
    """The notary's totals by calendar year, partial years marked."""
    years: dict[int, tuple[MonthFigures, int]] = {}
    for month, f in figures:
        total, count = years.get(month.year, (MonthFigures.zero(), 0))
        years[month.year] = (total + f, count + 1)
    return [YearTotals(y, total, count) for y, (total, count) in sorted(years.items())]


RATIO_LEFT_OUT = frozenset({"refunds"})
"""The default income categories a debt ratio leaves out: a bank does not count refunds."""


def counted_by_default(presets: Mapping[UUID, str | None]) -> set[UUID]:
    """The income categories (with their preset) a ratio counts unless the form says else."""
    return {c for c, preset in presets.items() if preset not in RATIO_LEFT_OUT}


def ratio_income(
    totals: Mapping[UUID, Decimal], *, counted: Collection[UUID], months: int
) -> Decimal:
    """The period's average monthly income of the counted categories, after tax withheld."""
    return quantize(sum((v for c, v in totals.items() if c in counted), ZERO) / months)


DEBT_CEILING = Decimal("0.35")
"""The HCSF ceiling (D-HCSF-2021-7), insurance included, on net income before tax."""


def debt_ratio(payments: Decimal, income: Decimal) -> Decimal | None:
    """The monthly payments and insurance over the ratio income; none without income."""
    return payments / income if income > 0 else None


MAX_WITHHOLDING = Decimal("0.45")


def check_withholding(rate: Decimal) -> None:
    """0 to 45 %, to the tenth of a percent."""
    if rate != rate.quantize(Decimal("0.001")) or not ZERO <= rate <= MAX_WITHHOLDING:
        raise AuditError("a withholding rate is from 0 to 45 %, to the tenth")


def before_tax(income: Decimal, withholding: Decimal) -> Decimal:
    """The estimated net income before tax, from what is left after withholding."""
    return income / (ONE - withholding)


def months_of(amount: Decimal, monthly: Decimal) -> Decimal | None:
    """How many months of `monthly` an amount covers (the precaution in fixed expenses)."""
    return amount / monthly if monthly > 0 else None


DEBT_HORIZON = 600
"""How far ahead a debt's end is looked for: 50 years."""


def debt_end(owed: Decimal, terms: DebtTerms, *, last: Month) -> Month | None:
    """The month a running debt is repaid, from what is owed at the end of `last` (F-SIM-3):
    pass the month the value was entered, not a later one it is carried to, or the end comes
    late; None without a payment, when it grows or ends beyond 50 years, or is repaid."""
    if owed <= 0 or terms.payment is None or debt_grows(owed, terms):
        return None
    path = amortise(owed, terms, months=DEBT_HORIZON)
    for i, left in enumerate(path.owed):
        if left == 0:
            return add_months(last, i + 1)
    return None


# F-AUD-5: the property project


class PropertyAge(enum.StrEnum):
    OLD = "old"
    NEW = "new"


NOTARY_RATES: Mapping[PropertyAge, Decimal] = MappingProxyType(
    {PropertyAge.OLD: Decimal("0.08"), PropertyAge.NEW: Decimal("0.025")}
)
"""Indicative: they depend on the department and on a first-time buyer."""


def notary_fees(price: Decimal, age: PropertyAge) -> Decimal:
    return quantize(price * NOTARY_RATES[age])


MAX_YEARS = 25
MAX_YEARS_DEFERRED = 27
"""For a new build or major works with a deferred start of up to two years."""
MAX_LOAN_YEARS = 30
MAX_LOAN_RATE = Decimal("0.2")


class Duration(enum.StrEnum):
    WITHIN = "within"
    DEFERRED_ONLY = "deferred_only"
    """Within the 27 years of a new build or major works only."""
    ABOVE = "above"


def duration_check(years: int) -> Duration:
    if years <= MAX_YEARS:
        return Duration.WITHIN
    return Duration.DEFERRED_ONLY if years <= MAX_YEARS_DEFERRED else Duration.ABOVE


def monthly_payment(amount: Decimal, yearly_rate: Decimal, years: int) -> Decimal:
    """Capital and interest, constant and amortised, at the proportional monthly rate:
    amount * r / (1 - (1 + r)^-n), r = rate / 12, n = years * 12; amount / n at a zero rate."""
    n = years * 12
    if yearly_rate == 0:
        return quantize(amount / n)
    r = yearly_rate / 12
    return quantize(amount * r / (ONE - (ONE + r) ** -n))


@dataclass(frozen=True)
class Project:
    price: Decimal
    notary_fees: Decimal
    agency_fees: Decimal
    guarantee_fees: Decimal
    down_payment: Decimal
    loan: Decimal | None
    """None: price + fees - down payment."""
    years: int
    rate: Decimal
    """The yearly nominal rate."""
    insurance: Decimal
    """The borrower insurance a month."""
    rent: Decimal
    """The current rent a month (0 without one)."""
    rent_stops: bool

    @property
    def cost(self) -> Decimal:
        return self.price + self.notary_fees + self.agency_fees + self.guarantee_fees

    @property
    def loan_amount(self) -> Decimal:
        return self.loan if self.loan is not None else self.cost - self.down_payment


def _cents(amount: Decimal) -> bool:
    return amount.is_finite() and amount >= 0 and amount == quantize(amount)


def check_project(p: Project) -> None:
    amounts = (p.price, p.notary_fees, p.agency_fees, p.guarantee_fees, p.down_payment)
    if not all(_cents(a) for a in (*amounts, p.insurance, p.rent)):
        raise AuditError("the project's amounts are positive, in cents at most")
    if p.price <= 0:
        raise AuditError("a property has a price")
    if p.loan is not None and not _cents(p.loan):
        raise AuditError("a loan amount is positive, in cents at most")
    if p.down_payment > p.cost:
        raise AuditError("the down payment is at most the price and fees")
    if p.loan_amount <= 0:
        raise AuditError("the project borrows something")
    if not 1 <= p.years <= MAX_LOAN_YEARS:
        raise AuditError(f"a loan lasts 1 to {MAX_LOAN_YEARS} years")
    if (
        not p.rate.is_finite()
        or p.rate != p.rate.quantize(Decimal("0.0001"))
        or not ZERO <= p.rate <= MAX_LOAN_RATE
    ):
        raise AuditError("a loan's rate is from 0 to 20 %")


@dataclass(frozen=True)
class ProjectFigures:
    cost: Decimal
    """Price and fees."""
    loan: Decimal
    payment: Decimal
    """Capital and interest, without the insurance."""
    ratio_after: Decimal | None
    """The running loans that go on, the new payment and its insurance over the ratio
    income; rent is never in it."""
    remaining_after_housing: Decimal
    """The ratio income less those payments, less the rent if it goes on."""
    housing_change: Decimal
    """The new payment and insurance less the rent that stops."""
    down_share: Decimal
    """Of price and fees."""
    liquid_left: Decimal
    """The liquid wealth after the down payment."""

    @property
    def above_ceiling(self) -> bool:
        return self.ratio_after is not None and self.ratio_after > DEBT_CEILING


def project_figures(
    p: Project, *, ratio_income: Decimal, running_payments: Decimal, liquid: Decimal
) -> ProjectFigures:
    """`running_payments`: the running loans' payments and insurance that go on. The ratio is
    after tax withheld: with a withholding rate, the API also divides the same payments by
    `before_tax(ratio_income, rate)` (F-AUD-2)."""
    loan = p.loan_amount
    payment = monthly_payment(loan, p.rate, p.years)
    housing = payment + p.insurance
    stopped_rent = p.rent if p.rent_stops else ZERO
    ongoing_rent = ZERO if p.rent_stops else p.rent
    cost = p.cost
    return ProjectFigures(
        cost=cost,
        loan=loan,
        payment=payment,
        ratio_after=debt_ratio(running_payments + housing, ratio_income),
        remaining_after_housing=ratio_income - running_payments - housing - ongoing_rent,
        housing_change=housing - stopped_rent,
        down_share=p.down_payment / cost,
        liquid_left=liquid - p.down_payment,
    )
