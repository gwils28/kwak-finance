"""The wealth projection's inputs (spec §4.11, invariants §8.23-29), in `Decimal`.

The assumptions and their defaults, the starting point, the allocation of the savings, the
debts' repayment and the savings month by month, and today's euros. The Monte Carlo engine
(`kwak_analytics.montecarlo`) draws the paths from these, in floating point.

Months are counted from the starting month: month 0 is the start, month t the t-th one after.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

from kwak_core.budget import Month
from kwak_core.money import quantize
from kwak_core.wealth import SAVINGS_PRESET, CategoryInput, LineInput, WealthKind, line_cell

ZERO = Decimal(0)
ONE = Decimal(1)
STEP = Decimal("0.001")
"""Returns, volatilities and the inflation are set to 0.1 % at most: they are uncertain."""
RATE_STEP = Decimal("0.0001")
"""A loan's rate is quoted to 0.01 % (3.25 %)."""

MIN_RETURN = Decimal(-1)
MAX_RETURN = Decimal(1)
MAX_VOLATILITY = Decimal(2)
MIN_INFLATION = Decimal("-0.05")
MAX_INFLATION = Decimal("0.2")
MAX_RATE = Decimal(1)


class ProjectionError(ValueError):
    """An assumption, an allocation or debt terms the projection cannot take."""


# F-SIM-1: assumptions


@dataclass(frozen=True)
class Assumption:
    """A wealth category's expected annual return (the arithmetic mean) and its volatility
    (the standard deviation of the yearly return)."""

    ret: Decimal
    volatility: Decimal


DEFAULT_ASSUMPTIONS: Mapping[str, Assumption] = MappingProxyType(
    {
        "savings": Assumption(Decimal("0.017"), ZERO),
        "current": Assumption(ZERO, ZERO),
        "stocks": Assumption(Decimal("0.07"), Decimal("0.16")),
        "crypto": Assumption(Decimal("0.08"), Decimal("0.6")),
        "bonds": Assumption(Decimal("0.03"), Decimal("0.06")),
        "private-equity": Assumption(Decimal("0.06"), Decimal("0.25")),
        "gold": Assumption(Decimal("0.03"), Decimal("0.15")),
        "real-estate": Assumption(Decimal("0.025"), Decimal("0.08")),
        "equipment": Assumption(Decimal("-0.15"), ZERO),
        "exotic": Assumption(ZERO, Decimal("0.2")),
    }
)
"""F-SIM-1's defaults, nominal, after a low-cost fund's fees and before tax, by the category's
preset (its default colour key, whatever its name or colour become)."""

DEFAULT_INFLATION = Decimal("0.02")


def assumption_of(preset: str | None) -> Assumption:
    """A category added later, without a preset, starts at 0 % ± 0."""
    return (
        DEFAULT_ASSUMPTIONS.get(preset, Assumption(ZERO, ZERO))
        if preset
        else Assumption(ZERO, ZERO)
    )


def _stepped(value: Decimal, what: str, step: Decimal = STEP) -> None:
    if value != value.quantize(step):
        raise ProjectionError(f"{what} is set to {step * 100} % at most")


def check_assumption(a: Assumption) -> None:
    _stepped(a.ret, "a return")
    _stepped(a.volatility, "a volatility")
    if not MIN_RETURN < a.ret <= MAX_RETURN:
        raise ProjectionError("a return is above -100 % and at most +100 % a year")
    if not ZERO <= a.volatility <= MAX_VOLATILITY:
        raise ProjectionError("a volatility is from 0 to 200 %")


def check_inflation(inflation: Decimal) -> None:
    _stepped(inflation, "the inflation")
    if not MIN_INFLATION <= inflation <= MAX_INFLATION:
        raise ProjectionError("the inflation is from -5 % to 20 % a year")


def _log_variance(a: Assumption) -> Decimal:
    """The variance of the annual log-return: ln(1 + sigma^2 / (1 + mu)^2)."""
    return (ONE + a.volatility**2 / (ONE + a.ret) ** 2).ln()


def monthly_params(a: Assumption) -> tuple[Decimal, Decimal]:
    """F-SIM-4: the mean and standard deviation of the normal monthly log-return whose twelve
    months compound to a lognormal annual return of mean 1 + ret and standard deviation
    volatility: sigma_m = sqrt(ln(1 + sigma^2 / (1 + mu)^2) / 12), mu_m = ln(1 + mu) / 12 -
    sigma_m^2 / 2."""
    check_assumption(a)
    variance = _log_variance(a) / 12
    return (ONE + a.ret).ln() / 12 - variance / 2, variance.sqrt()


def median_growth(a: Assumption) -> Decimal:
    """The annual growth of the median path, below the mean when there is volatility: (1 + mu)
    / sqrt(1 + sigma^2 / (1 + mu)^2) - 1."""
    check_assumption(a)
    return (ONE + a.ret) / (ONE + a.volatility**2 / (ONE + a.ret) ** 2).sqrt() - ONE


# F-SIM-2: the starting point


@dataclass(frozen=True)
class Start:
    month: Month
    assets: dict[UUID, Decimal]
    """Each asset category holding a line that month: its total."""
    debts: dict[UUID, Decimal]
    """Each debt line that month: what is still owed."""

    @property
    def net(self) -> Decimal:
        return sum(self.assets.values(), ZERO) - sum(self.debts.values(), ZERO)


def starting_point(
    categories: Sequence[CategoryInput], lines: Sequence[LineInput], month: Month
) -> Start:
    """The scope's wealth in `month`, values carried forward, nothing after it read (invariant
    §8.23); `lines` are in scope."""
    kinds = {c.id: c.kind for c in categories}
    assets: dict[UUID, Decimal] = {}
    debts: dict[UUID, Decimal] = {}
    for line in lines:
        before = {m: v for m, v in line.values.items() if m <= month}
        cell = line_cell(before, month, closed_from=line.closed_from)
        if cell is None:
            continue
        if kinds[line.category_id] is WealthKind.DEBT:
            debts[line.id] = cell.amount
        else:
            assets[line.category_id] = assets.get(line.category_id, ZERO) + cell.amount
    return Start(month, assets, debts)


# F-SIM-3: the allocation of the savings

SHARE = Decimal("1e-12")
"""Shares are kept to 12 decimals, so that they add up to exactly 1."""

NOT_ALLOCATED = frozenset({"current", "real-estate", "equipment", "private-equity", "exotic"})
"""A working balance stays on a current account, and monthly savings buy neither a home,
equipment, locked-in private equity nor exotic holdings (wine, art, watches) unless a
scenario's allocation says so."""

FIRST_TAKEN = ("current", "savings")
"""Negative savings are taken from current accounts, then savings accounts, then the other
categories in proportion to what they hold."""
NEVER_TAKEN = frozenset({"real-estate", "equipment", "private-equity", "exotic"})
"""The illiquid categories (as F-ANA-1 judges them) are not sold to pay a month's spending."""
SHORTFALL_RATE = Decimal("0.08")
"""What is missing once the liquid holdings are spent is borrowed: an overdraft or a consumer
loan costs several percent a year (up to about 20 %, the usury rate); 8 % a year, a month at a
time, is a middle estimate the page states."""


def default_allocation(
    assets: Mapping[UUID, Decimal], presets: Mapping[UUID, str | None]
) -> dict[UUID, Decimal]:
    """The categories' shares of today's gross assets, current accounts, real estate,
    equipment, private equity and exotic holdings left out; the shares sum to exactly 1, the
    largest taking the rounding. With nothing left to share by, the savings go to Savings
    accounts, else to Current accounts; without either, the scenario must set its own.
    `presets`: every asset category of the household."""
    kept = {c: v for c, v in assets.items() if v > 0 and presets.get(c) not in NOT_ALLOCATED}
    total = sum(kept.values(), ZERO)
    if total > 0:
        shares = {c: (v / total).quantize(SHARE) for c, v in kept.items()}
        largest = max(shares, key=lambda c: shares[c])
        shares[largest] = ONE - sum((v for c, v in shares.items() if c != largest), ZERO)
        return shares
    for wanted in (SAVINGS_PRESET, "current"):
        found = next((c for c, p in presets.items() if p == wanted), None)
        if found is not None:
            return {found: ONE}
    raise ProjectionError("no category to save into: add Savings accounts, or set an allocation")


def check_allocation(percentages: Mapping[UUID, int]) -> None:
    """A scenario's own allocation: whole percentages summing to 100."""
    if any(not 0 <= p <= 100 for p in percentages.values()):
        raise ProjectionError("each share is from 0 to 100 %")
    if sum(percentages.values()) != 100:
        raise ProjectionError("the shares sum to 100 %")


# F-SIM-3: the debts


@dataclass(frozen=True)
class DebtTerms:
    payment: Decimal | None
    """A month, in current euros; None: not set, the debt stays as owed."""
    rate: Decimal = ZERO
    """The annual nominal rate (not the APR)."""
    insurance: Decimal = ZERO
    """The borrower insurance a month, in current euros: it repays nothing, and stops with the
    loan."""


def check_debt_terms(terms: DebtTerms) -> None:
    for amount in (terms.payment, terms.insurance):
        if amount is not None and (amount < 0 or amount != quantize(amount)):
            raise ProjectionError("a payment or an insurance is positive, in cents at most")
    _stepped(terms.rate, "a rate", RATE_STEP)
    if not ZERO <= terms.rate <= MAX_RATE:
        raise ProjectionError("a rate is from 0 to 100 % a year")


def debt_grows(owed: Decimal, terms: DebtTerms) -> bool:
    """A payment at or below the month's interest: the debt grows (a total deferral, or more
    often a mistyped entry, which the form warns of)."""
    return (
        owed > 0 and terms.payment is not None and terms.payment <= quantize(owed * terms.rate / 12)
    )


@dataclass(frozen=True)
class DebtPath:
    owed: list[Decimal]
    """At the end of months 1 to n."""
    freed: list[Decimal]
    """What joins the savings in months 1 to n: in the month it is repaid, what its payment
    did not need; from the month after, all of it with the insurance. A debt already repaid at
    the start frees nothing: its payment is no longer spent, so the capacity already counts
    it."""


def amortise(owed: Decimal, terms: DebtTerms, *, months: int) -> DebtPath:
    """Each month the debt accrues its interest (rate / 12 of what is owed, to the cent) and
    falls by its payment, never below zero (invariant §8.27)."""
    out: list[Decimal] = []
    freed: list[Decimal] = []
    repaid = False
    for _ in range(months):
        if repaid and terms.payment:
            freed.append(terms.payment + terms.insurance)
        elif owed > 0 and terms.payment is not None:
            due = owed + quantize(owed * terms.rate / 12)
            owed = max(ZERO, due - terms.payment)
            repaid = owed == 0
            freed.append(terms.payment - due if repaid else ZERO)
        else:
            freed.append(ZERO)
        out.append(owed)
    return DebtPath(out, freed)


# F-SIM-3 and 4: savings, today's euros


def savings_path(
    monthly: Decimal, *, months: int, inflation: Decimal, freed: Sequence[Decimal] = ()
) -> list[Decimal]:
    """The savings of months 1 to n in current euros: `monthly`, in today's euros, grows with
    the inflation as an income keeping pace with prices; the debts' freed payments, already in
    current euros, join it."""
    return [
        quantize(monthly * (ONE + inflation) ** (Decimal(t) / 12))
        + (freed[t - 1] if t <= len(freed) else ZERO)
        for t in range(1, months + 1)
    ]


def to_today(amount: Decimal, month: int, inflation: Decimal) -> Decimal:
    """An amount of month `month` in today's euros (invariant §8.28), unrounded: the engine
    works on it; money shown goes through `quantize`."""
    return amount / (ONE + inflation) ** (Decimal(month) / 12) if month else amount


# F-SIM-3: the monthly contributions

MIN_CONTRIBUTION = Decimal(1)
MAX_CONTRIBUTION = Decimal(100_000)


@dataclass(frozen=True)
class Contribution:
    """What the household invests each month in one asset category."""

    category_id: UUID
    amount: Decimal
    """A month, today's euros if indexed, else current euros."""
    indexed: bool = True
    """Follows the inflation, as an income keeping pace with prices; else a fixed amount, as a
    standing order usually is."""


def check_contributions(contributions: Sequence[Contribution]) -> None:
    """At most one per category, each from €1 to €100,000 a month, in cents."""
    ids = [c.category_id for c in contributions]
    if len(set(ids)) != len(ids):
        raise ProjectionError("one contribution per category at most")
    for c in contributions:
        if c.amount != quantize(c.amount):
            raise ProjectionError("a contribution is in cents at most")
        if not MIN_CONTRIBUTION <= c.amount <= MAX_CONTRIBUTION:
            raise ProjectionError("a contribution is from €1 to €100,000 a month")


@dataclass(frozen=True)
class ContributionPlan:
    put_in: list[Decimal]
    """The contributions of months 1 to n, current euros."""
    savings: list[Decimal]
    """The savings of months 1 to n, current euros: the contributions plus the debts' freed
    payments (`savings_path`)."""
    split: list[dict[UUID, Decimal]]
    """Each month's allocation: each contribution over their sum, summing to exactly 1 (the
    largest takes the rounding). It moves when indexed and fixed contributions mix, so each
    category receives its own contribution only."""


def contribution_plan(
    contributions: Sequence[Contribution],
    *,
    months: int,
    inflation: Decimal,
    freed: Sequence[Decimal] = (),
    scale: Decimal = ONE,
) -> ContributionPlan:
    """F-SIM-3: with contributions, the savings are their sum and the allocation their split;
    a freed debt payment joins the savings and is split the same way. `scale` multiplies every
    contribution, for a what-if changing their total (F-SIM-5)."""
    check_contributions(contributions)
    if not contributions:
        raise ProjectionError("no contribution to plan")
    if scale <= 0:
        raise ProjectionError("a plan's contributions stay above zero")
    put_in: list[Decimal] = []
    savings: list[Decimal] = []
    split: list[dict[UUID, Decimal]] = []
    for t in range(1, months + 1):
        growth = (ONE + inflation) ** (Decimal(t) / 12)
        own = {
            c.category_id: quantize(c.amount * scale * (growth if c.indexed else ONE))
            for c in contributions
        }
        total = sum(own.values(), ZERO)
        shares = {k: (v / total).quantize(SHARE) for k, v in own.items()}
        largest = max(shares, key=lambda k: shares[k])
        shares[largest] = ONE - sum((v for k, v in shares.items() if k != largest), ZERO)
        put_in.append(total)
        savings.append(total + (freed[t - 1] if t <= len(freed) else ZERO))
        split.append(shares)
    return ContributionPlan(put_in, savings, split)


# F-SIM-5: where the money comes from


@dataclass(frozen=True)
class Parts:
    """What makes up a month's median net worth, in the euros shown."""

    today: Decimal
    contributed: Decimal
    """The savings added up, freed debt payments included (withdrawals subtracted)."""
    repaid: Decimal
    """The capital the debt lines repaid from the income, the Shortfall left out."""
    gains: Decimal
    """The rest: after inflation in today's euros, negative as losses."""


def breakdown(
    *,
    start_net: Decimal,
    savings: Sequence[Decimal],
    start_debts: Decimal,
    owed: Sequence[Decimal],
    medians: Sequence[Decimal],
    inflation: Decimal,
    today: bool,
) -> list[Parts]:
    """Months 0 to n (invariant §8.46). `savings` and `owed` (months 1 to n) are in current
    euros, `medians` (months 0 to n) in the euros shown. In today's euros each amount counts
    at its value when it was added, so the gains are after inflation; in current euros, the
    amounts as paid. Today's net worth, the savings and the debts are the same on every path,
    so the gains are exactly the median of the paths' gains."""
    if not len(savings) == len(owed) == len(medians) - 1:
        raise ValueError("savings and debts cover months 1 to n, the medians 0 to n")
    out = [Parts(quantize(start_net), ZERO, ZERO, quantize(medians[0]) - quantize(start_net))]
    contributed = repaid = ZERO
    before = start_debts
    for t in range(1, len(medians)):
        unit = (ONE + inflation) ** (Decimal(t) / 12) if today else ONE
        contributed += savings[t - 1] / unit
        repaid += (before - owed[t - 1]) / unit
        before = owed[t - 1]
        start, added, paid = quantize(start_net), quantize(contributed), quantize(repaid)
        out.append(Parts(start, added, paid, quantize(medians[t]) - start - added - paid))
    return out


# F-SIM-5: an income at a withdrawal rate, the regulated ceilings

DEFAULT_WITHDRAWAL = Decimal("0.04")
MIN_WITHDRAWAL, MAX_WITHDRAWAL = Decimal("0.02"), Decimal("0.05")
"""A rule of thumb from US history (Bengen, Trinity), for holdings mostly in shares paying out
over about 30 years; beyond 5 %, such drawdowns often failed."""
REGULATED_CEILINGS = Decimal("34950")
"""A full Livret A (€22,950) and LDDS (€12,000), a member, in current euros."""


def check_withdrawal_rate(rate: Decimal) -> None:
    _stepped(rate, "a withdrawal rate")
    if not MIN_WITHDRAWAL <= rate <= MAX_WITHDRAWAL:
        raise ProjectionError("a withdrawal rate is from 2 to 5 % a year")


def withdrawal_income(liquid: Decimal, rate: Decimal) -> Decimal:
    """A month: the liquid holdings (a home pays no income) times the rate, over 12."""
    check_withdrawal_rate(rate)
    return quantize(liquid * rate / 12)


def beyond_ceilings(savings_accounts: Decimal, *, members: int) -> bool:
    """Savings accounts above a full Livret A and LDDS a member: beyond, the 1.7 % rate is not
    available (F-SIM-3). Compared in current euros, as the ceilings are not indexed."""
    return savings_accounts > REGULATED_CEILINGS * max(members, 1)
