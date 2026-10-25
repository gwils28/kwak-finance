"""The demo household (spec §4.9 F-ADM-5, invariant §8.40): three years of fictitious data, the
same for the same day and language, to try every feature before the real data has a history.

Everything is named by a key (a member, a fixed expense, a wealth line, a goal) or, for a
category, by its default English name (spending) or colour key (wealth): the API turns them into
rows. The amounts are plausible for a French couple with a child, never anyone's real figures.
"""

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from kwak_core.budget import Month, month_range
from kwak_core.fixed import FixedExpense, FixedFrequency, due_date, is_due
from kwak_core.goals import add_months
from kwak_core.money import quantize
from kwak_core.projection import Assumption
from kwak_core.users import Language
from kwak_core.visibility import Visibility
from kwak_core.wealth import RegulatedType

DEMO_SEED = 20261025
HISTORY_MONTHS = 36
"""Complete months before the current one."""

D = Decimal
ZERO = D(0)
CAMILLE, ALEX = "camille", "alex"
PRIVATE, SHARED, JOINT = Visibility.PRIVATE, Visibility.SHARED, Visibility.JOINT
QUARTERLY, YEARLY = FixedFrequency.QUARTERLY, FixedFrequency.YEARLY

# Months of the history, from 0 (the start) to HISTORY_MONTHS (this month).
RAISE_CAMILLE, RAISE_ALEX = 18, 24
CAR = 8
"""The car is bought: its loan and insurance start, the CEL is emptied and closed."""
PEA = 12
NANNY_LAST = 19
"""Léa starts school the month after: the canteen replaces the childminder."""
REPAIR = 22
"""The clutch: money taken back from the Livret A, its transfer and the PEA's skipped."""
SPOTIFY_LAST = 29
LATE = "internet"
"""The fixed expense whose occurrence this month nobody has confirmed yet."""
ENTERED_NOW = frozenset({"joint_account", "camille_account", "alex_account", "livret_a", "ldds"})
"""The wealth lines already valued this month: the others show their value carried."""

_TEXT: Mapping[str, tuple[str, str]] = {
    "household": ("The Martins (demo)", "Famille Martin (démo)"),
    # Fixed expenses.
    "mortgage": ("Mortgage", "Prêt immobilier"),
    "condo": ("Condo fees", "Charges de copropriété"),
    "property_tax": ("Property tax", "Taxe foncière"),
    "home_insurance": ("Home insurance", "Assurance habitation"),
    "electricity": ("Electricity", "Électricité"),
    "internet": ("Internet box", "Box internet"),
    "phones": ("Mobile plans", "Forfaits mobiles"),
    "netflix": ("Netflix", "Netflix"),
    "spotify": ("Spotify Family", "Spotify Family"),
    "gym": ("Gym", "Salle de sport"),
    "car_insurance": ("Car insurance", "Assurance auto"),
    "car_loan": ("Car loan", "Prêt auto"),
    "nanny": ("Childminder", "Assistante maternelle"),
    "canteen": ("School canteen", "Cantine et périscolaire"),
    "to_livret_a": ("Transfer to Livret A", "Virement Livret A"),
    "to_ldds": ("Transfer to LDDS", "Virement LDDS"),
    "to_joint": ("Transfer to joint savings", "Virement livret joint"),
    "to_insurance": ("Life insurance payment", "Versement assurance-vie"),
    "to_pea": ("PEA payment", "Versement PEA"),
    # Lines.
    "salary_camille": ("Salary Camille", "Salaire Camille"),
    "salary_alex": ("Salary Alex", "Salaire Alex"),
    "bonus": ("Year-end bonus", "Prime de fin d'année"),
    "sale": ("Leboncoin sale", "Vente Leboncoin"),
    "bakery": ("Bakery", "Boulangerie"),
    "market": ("Market", "Marché"),
    "fuel": ("Fuel", "Carburant"),
    "pharmacy": ("Pharmacy", "Pharmacie"),
    "doctor": ("Doctor", "Médecin"),
    "refund": ("Health insurance refund", "Remboursement Ameli"),
    "cinema": ("Cinema", "Cinéma"),
    "clothes": ("Clothes", "Vêtements"),
    "christmas": ("Christmas gifts", "Cadeaux de Noël"),
    "birthday": ("Birthday gift", "Cadeau d'anniversaire"),
    "hairdresser": ("Hairdresser", "Coiffeur"),
    "post": ("Post office", "La Poste"),
    "lea_clothes": ("Clothes for Léa", "Vêtements Léa"),
    "swimming": ("Swimming lessons Léa", "Cours de natation Léa"),
    "holidays_paid": ("Summer holidays", "Vacances d'été"),
    "from_cel": ("Withdrawal CEL", "Retrait CEL"),
    "car_down": ("Car down payment", "Apport voiture"),
    "clutch": ("Garage - clutch", "Garage - embrayage"),
    "from_livret_a": ("Withdrawal Livret A", "Retrait Livret A"),
    # Wealth lines.
    "joint_account": ("Joint account", "Compte joint"),
    "camille_account": ("Camille's account", "Compte courant Camille"),
    "alex_account": ("Alex's account", "Compte courant Alex"),
    "livret_a": ("Livret A Camille", "Livret A Camille"),
    "ldds": ("LDDS Alex", "LDDS Alex"),
    "joint_savings": ("Joint savings account", "Livret joint"),
    "pel": ("PEL Alex", "PEL Alex"),
    "cel": ("CEL Alex", "CEL Alex"),
    "life_insurance": ("Life insurance (euro fund)", "Assurance-vie (fonds euros)"),
    "pea": ("PEA Camille", "PEA Camille"),
    "brokerage": ("Brokerage account Alex", "CTO Alex"),
    "bitcoin": ("Bitcoin", "Bitcoin"),
    "home": ("Home", "Résidence principale"),
    "car": ("Car", "Voiture"),
    "mortgage_debt": ("Mortgage", "Crédit immobilier"),
    "car_debt": ("Car loan", "Prêt auto"),
    # Goals.
    "precaution": ("Emergency fund", "Épargne de précaution"),
    "holidays": ("Holidays in Portugal", "Vacances au Portugal"),
    "motorbike": ("Motorbike", "Moto"),
    "studies": ("Léa's studies", "Études de Léa"),
    "spa": ("Spa weekend", "Week-end spa"),
    "guitar": ("Vintage guitar", "Guitare vintage"),
    "sofa": ("New sofa", "Nouveau canapé"),
}
"""The texts of the demo in each language, by key; a shop's name reads the same in both."""


@dataclass(frozen=True)
class DemoMember:
    key: str
    name: str
    owner: bool
    birth: Month
    retirement: Month
    earnings: Decimal
    """The net salary that stops at retirement: the latest one entered."""
    pension_month: Month
    pension: Decimal


@dataclass(frozen=True)
class DemoFixed:
    key: str
    label: str
    category: str
    amount: Decimal
    """Signed as a line."""
    frequency: FixedFrequency
    day: int
    first: Month
    last: Month | None = None
    skips: tuple[Month, ...] = ()


@dataclass(frozen=True)
class DemoPart:
    category: str
    amount: Decimal


@dataclass(frozen=True)
class DemoLine:
    day: date
    label: str
    amount: Decimal
    """Signed: negative is spent or put aside."""
    category: str | None
    """None for a split line."""
    entered_by: str
    entered_on: date
    """When it was entered: the Sunday after its date, as a weekly session would."""
    parts: tuple[DemoPart, ...] = ()
    fixed: str | None = None
    """The fixed expense it was confirmed from."""


@dataclass(frozen=True)
class DemoTarget:
    category: str
    start: Month
    amount: Decimal | None


@dataclass(frozen=True)
class DemoWealthLine:
    key: str
    name: str
    category: str
    owner: str
    visibility: Visibility
    values: Mapping[Month, Decimal]
    regulated: RegulatedType | None = None
    closed_from: Month | None = None
    debt_payment: Decimal | None = None
    debt_rate: Decimal = ZERO
    debt_insurance: Decimal = ZERO


@dataclass(frozen=True)
class DemoFunding:
    line: str
    share: int
    opening: Decimal = ZERO


@dataclass(frozen=True)
class DemoGoal:
    key: str
    name: str
    target: Decimal
    start: Month
    owner: str
    visibility: Visibility
    fundings: tuple[DemoFunding, ...]
    deadline: Month | None = None
    precaution: bool = False
    permanent: bool = False
    pleasure: bool = False
    closed_from: Month | None = None
    closed_as: Literal["archived", "cancelled"] | None = None


@dataclass(frozen=True)
class Demo:
    today: date
    language: Language
    household: str
    start: Month
    """The first month with lines and values."""
    this_month: Month
    wealth_start: Month
    members: tuple[DemoMember, ...]
    fixed: tuple[DemoFixed, ...]
    lines: tuple[DemoLine, ...]
    """By date, then in the order entered."""
    targets: tuple[DemoTarget, ...]
    wealth_lines: tuple[DemoWealthLine, ...]
    goals: tuple[DemoGoal, ...]
    assumptions: Mapping[str, Assumption]
    """By wealth category colour key; the others keep the defaults."""


def _cents(rng: random.Random, low: int, high: int) -> Decimal:
    """An amount from `low` to `high` euros, to the cent."""
    return D(rng.randint(low * 100, high * 100)).scaleb(-2)


def generate(today: date, language: Language, seed: int = DEMO_SEED) -> Demo:
    """The demo household as of `today`, its texts in `language`."""

    def t(key: str) -> str:
        en, fr = _TEXT.get(key, (key, key))
        return fr if language is Language.FR else en

    rng = random.Random(seed)  # noqa: S311 - fictitious amounts, nothing secret
    this_month = Month.of(today)
    start = add_months(this_month, -HISTORY_MONTHS)
    months = month_range(start, this_month)

    def at(i: int) -> Month:
        return add_months(start, i)

    def first_in(calendar_months: set[int]) -> Month:
        """The first month of the history that falls in one of `calendar_months`."""
        month = start
        while month.month not in calendar_months:
            month = month.next()
        return month

    def fx(
        key: str,
        category: str,
        amount: str,
        day: int,
        first: Month,
        frequency: FixedFrequency = FixedFrequency.MONTHLY,
        *,
        last: Month | None = None,
        skips: tuple[Month, ...] = (),
    ) -> DemoFixed:
        return DemoFixed(key, t(key), category, D(amount), frequency, day, first, last, skips)

    augusts = tuple(m for m in months if m.month == 8)
    fixed = (
        fx("mortgage", "Housing", "-1088.00", 5, start),
        fx("condo", "Housing", "-420.00", 1, first_in({1, 4, 7, 10}), QUARTERLY),
        fx("property_tax", "Housing", "-1240.00", 15, first_in({10}), YEARLY),
        fx("home_insurance", "Housing", "-264.00", 20, first_in({3}), YEARLY),
        fx("electricity", "Home", "-98.00", 8, start),
        fx("internet", "Subscriptions", "-39.99", 1, start),
        fx("phones", "Subscriptions", "-31.98", 12, start),
        fx("netflix", "Subscriptions", "-13.49", 17, start),
        fx("spotify", "Subscriptions", "-17.99", 3, start, last=at(SPOTIFY_LAST)),
        fx("gym", "Leisure", "-34.90", 4, start, skips=augusts),
        fx("car_insurance", "Transport", "-61.00", 6, at(CAR)),
        fx("car_loan", "Transport", "-263.00", 6, at(CAR)),
        fx("nanny", "Children", "-690.00", 5, start, last=at(NANNY_LAST)),
        fx("canteen", "Children", "-145.00", 10, at(NANNY_LAST + 1)),
        fx("to_livret_a", "Savings", "-300.00", 2, start, skips=(at(REPAIR),)),
        fx("to_ldds", "Savings", "-100.00", 2, start),
        fx("to_joint", "Savings", "-250.00", 2, start),
        fx("to_insurance", "Savings", "-150.00", 15, start),
        fx("to_pea", "Savings", "-200.00", 10, at(PEA), skips=(at(REPAIR),)),
    )

    lines: list[DemoLine] = []

    def add(
        day: date,
        key: str,
        amount: Decimal | str,
        category: str | None,
        by: str,
        *,
        parts: tuple[DemoPart, ...] = (),
        fixed_key: str | None = None,
    ) -> None:
        """A line entered the Sunday after its date; none after today."""
        if day <= today:
            entered = min(day + timedelta(days=6 - day.weekday()), today)
            lines.append(DemoLine(day, t(key), D(amount), category, by, entered, parts, fixed_key))

    def anyone() -> str:
        return rng.choice((CAMILLE, ALEX))

    def spend(month: Month, key: str, category: str, low: int, high: int) -> None:
        """An expense on a day of the month, from `low` to `high` euros."""
        day = date(month.year, month.month, rng.randint(1, 28))
        add(day, key, -_cents(rng, low, high), category, anyone())

    def split(day: date, key: str, *parts: tuple[str, Decimal], by: str = "") -> None:
        total = sum((-a for _, a in parts), ZERO)
        add(day, key, total, None, by or anyone(), parts=tuple(DemoPart(c, -a) for c, a in parts))

    items = [
        (
            f,
            FixedExpense(
                uuid5(NAMESPACE_URL, f.key),
                f.label,
                uuid5(NAMESPACE_URL, f.category),
                f.amount,
                f.frequency,
                f.day,
                f.first,
                f.last,
            ),
        )
        for f in fixed
    ]
    salary_camille = salary_alex = ZERO
    for i, month in enumerate(months):

        def on(day: int, month: Month = month) -> date:
            return date(month.year, month.month, day)

        # Fixed expenses, confirmed from the grid.
        for f, item in items:
            late = month == this_month and f.key == LATE
            if is_due(item, month) and month not in f.skips and not late:
                add(due_date(item, month), f.key, f.amount, f.category, CAMILLE, fixed_key=f.key)

        # Income.
        salary_camille = D("2960.00") if i >= RAISE_CAMILLE else D("2780.00")
        salary_alex = D("2590.00") if i >= RAISE_ALEX else D("2420.00")
        add(on(28), "salary_camille", salary_camille, "Salaries", CAMILLE)
        add(on(27), "salary_alex", salary_alex, "Salaries", ALEX)
        if month.month == 12:
            add(on(18), "bonus", "1800.00", "Salaries", ALEX)
        if i <= NANNY_LAST:
            add(on(5), "CAF - PAJE", "184.81", "Benefits", CAMILLE)
            add(on(7), "CAF - CMG", "384.00", "Benefits", CAMILLE)
        if i % 7 == 3:
            add(on(rng.randint(1, 28)), "sale", _cents(rng, 40, 220), "Other income", ALEX)

        # Groceries, one of the supermarket runs split with the home.
        add(on(1), "bakery", -_cents(rng, 8, 15), "Groceries", anyone())
        for week in range(4):
            if week == 1:
                food, home = _cents(rng, 70, 110), _cents(rng, 15, 40)
                split(on(3 + 7 * week), "Carrefour", ("Groceries", food), ("Home", home))
            else:
                add(on(3 + 7 * week), "Carrefour", -_cents(rng, 90, 160), "Groceries", anyone())
        for _ in range(2):
            spend(month, "Lidl", "Groceries", 40, 70)
        spend(month, "market", "Groceries", 25, 45)

        # Transport.
        for _ in range(2 if i >= CAR else 1):
            spend(month, "fuel", "Transport", 55, 75)
        spend(month, "Parking", "Transport", 8, 20)
        if i % 3 == 1:
            spend(month, "SNCF", "Transport", 60, 140)

        # Health, and what the health insurance pays back.
        spend(month, "pharmacy", "Health", 8, 35)
        if rng.random() < 0.6:
            day = on(rng.randint(1, 20))
            add(day, "doctor", "-30.00", "Health", anyone())
            add(day + timedelta(days=5), "refund", "21.00", "Refunds", CAMILLE)

        # Home, leisure, shopping, gifts, the rest.
        if i % 2 == 0:
            spend(month, rng.choice(("IKEA", "Leroy Merlin")), "Home", 30, 180)
        for _ in range(2):
            spend(month, "Restaurant", "Leisure", 35, 80)
        spend(month, "cinema", "Leisure", 20, 35)
        spend(month, "Fnac", "Leisure", 15, 40)
        spend(month, "clothes", "Shopping", 40, 120)
        if i % 3 == 2:
            book, toy = _cents(rng, 15, 40), _cents(rng, 10, 35)
            split(on(rng.randint(1, 28)), "Amazon", ("Shopping", book), ("Children", toy))
        else:
            spend(month, "Amazon", "Shopping", 20, 80)
        if month.month == 12:
            spend(month, "christmas", "Gifts", 350, 500)
        elif i % 2 == 1:
            spend(month, "birthday", "Gifts", 30, 70)
        spend(month, "hairdresser", "Miscellaneous", 25, 45)
        if i % 4 == 0:
            spend(month, "post", "Miscellaneous", 5, 15)
        if i % 2 == 1:
            spend(month, "lea_clothes", "Children", 30, 60)
        if month.month == 9 and i > NANNY_LAST:
            add(on(14), "swimming", "-180.00", "Children", CAMILLE)

        # The months out of the ordinary.
        if month.month == 7:
            leisure, transport = ("Leisure", D(1100)), ("Transport", D(250))
            split(on(20), "holidays_paid", leisure, transport, by=CAMILLE)
        if i == CAR:
            add(on(3), "from_cel", "2500.00", "Savings", ALEX)
            add(on(4), "car_down", "-7000.00", "Transport", ALEX)
        if i == REPAIR:
            add(on(11), "clutch", "-1480.00", "Transport", ALEX)
            add(on(12), "from_livret_a", "1000.00", "Savings", CAMILLE)

    def target(category: str, *steps: tuple[int, str | None]) -> list[DemoTarget]:
        return [DemoTarget(category, at(i), D(a) if a else None) for i, a in steps]

    targets = (
        *target("Housing", (0, "1350"), (12, "1400")),
        *target("Groceries", (0, "650"), (18, "700")),
        *target("Transport", (0, "220"), (CAR, "520")),
        *target("Children", (0, "780"), (NANNY_LAST + 1, "260")),
        *target("Health", (0, "50")),
        *target("Subscriptions", (0, "110"), (SPOTIFY_LAST + 1, "95")),
        *target("Home", (0, "160")),
        *target("Leisure", (0, "220"), (24, "260")),
        *target("Shopping", (0, "150")),
        *target("Gifts", (0, "70")),
        *target("Miscellaneous", (0, "60"), (24, None)),
        *target("Savings", (0, "800"), (PEA, "1000")),
    )

    def member(key: str, owner: bool, age: int, salary: Decimal, pension: str) -> DemoMember:
        """Born `age` years and a few months ago, retiring at 64 with the pension then."""
        birth = add_months(this_month, -(age * 12 + (6 if owner else 1)))
        retires = Month(birth.year + 64, birth.month)
        return DemoMember(key, key.title(), owner, birth, retires, salary, retires, D(pension))

    return Demo(
        today=today,
        language=language,
        household=t("household"),
        start=start,
        this_month=this_month,
        wealth_start=start,
        members=(
            member(CAMILLE, True, 38, salary_camille, "1980.00"),
            member(ALEX, False, 40, salary_alex, "1720.00"),
        ),
        fixed=fixed,
        lines=tuple(sorted(lines, key=lambda line: line.day)),
        targets=targets,
        wealth_lines=_wealth(rng, months, t),
        goals=_goals(at, this_month, t),
        assumptions={
            "bonds": Assumption(D("0.025"), D("0.01")),
            "stocks": Assumption(D("0.065"), D("0.16")),
        },
    )


Step = Callable[[int, Decimal], Decimal]
"""A line's value in month i from its value the month before."""


def _wealth(
    rng: random.Random, months: list[Month], t: Callable[[str], str]
) -> tuple[DemoWealthLine, ...]:
    """Each line's monthly values, from the same events as the spending: the transfers, the
    withdrawals, the car, the loans' payments."""
    n = len(months)

    def series(first: int, v0: int, step: Step) -> dict[int, Decimal]:
        out, v = {first: D(v0)}, D(v0)
        for i in range(first + 1, n):
            v = max(ZERO, quantize(step(i, v)))
            out[i] = v
        return out

    def saved(monthly: int, yearly_rate: str) -> Step:
        """A transfer a month, and the year's interest paid at the start of January."""
        return lambda i, v: v * (1 + (D(yearly_rate) if months[i].month == 1 else ZERO)) + monthly

    def market(bp_low: int, bp_high: int, monthly: int = 0) -> Step:
        """A month's return, the sum of two draws in basis points, then a payment."""

        def step(i: int, v: Decimal) -> Decimal:
            r = D(rng.randint(bp_low, bp_high) + rng.randint(bp_low, bp_high)).scaleb(-4)
            return v * (1 + r) + (0 if i == REPAIR else monthly)

        return step

    def around(mid: int, spread: int) -> Step:
        return lambda i, v: D(mid + rng.randint(-spread, spread))

    def amortised(rate: str, payment: str) -> Step:
        return lambda i, v: v - (D(payment) - v * D(rate) / 12)

    def livret_a(i: int, v: Decimal) -> Decimal:
        return v - 1000 if i == REPAIR else saved(300, "0.024")(i, v)

    def line(
        key: str,
        category: str,
        owner: str,
        visibility: Visibility,
        values: dict[int, Decimal],
        *,
        regulated: RegulatedType | None = None,
        closed_from: int | None = None,
        debt: tuple[str, str, str] | None = None,
    ) -> DemoWealthLine:
        """`debt`: the monthly payment, the yearly rate and the insurance."""
        kept = {
            months[i]: v
            for i, v in values.items()
            if (i < n - 1 or key in ENTERED_NOW)
            # Real estate is valued once a year, in January, and carried in between.
            and (category != "real-estate" or i == 0 or months[i].month == 1)
        }
        payment, rate, insurance = debt or (None, "0", "0")
        return DemoWealthLine(
            key,
            t(key),
            category,
            owner,
            visibility,
            kept,
            regulated,
            months[closed_from] if closed_from is not None and closed_from < n else None,
            D(payment) if payment else None,
            D(rate),
            D(insurance),
        )

    cel = {i: D(2500) if i < CAR else ZERO for i in range(min(CAR + 1, n))}
    return (
        line("joint_account", "current", CAMILLE, JOINT, series(0, 2400, around(2600, 900))),
        line("camille_account", "current", CAMILLE, PRIVATE, series(0, 950, around(1100, 450))),
        line("alex_account", "current", ALEX, SHARED, series(0, 700, around(850, 400))),
        line(
            "livret_a",
            "savings",
            CAMILLE,
            SHARED,
            series(0, 10500, livret_a),
            regulated=RegulatedType.LIVRET_A,
        ),
        line(
            "ldds",
            "savings",
            ALEX,
            SHARED,
            series(0, 4000, saved(100, "0.024")),
            regulated=RegulatedType.LDDS,
        ),
        line("joint_savings", "savings", CAMILLE, JOINT, series(0, 2000, saved(250, "0.015"))),
        line(
            "pel",
            "savings",
            ALEX,
            PRIVATE,
            series(0, 9000, saved(0, "0.02")),
            regulated=RegulatedType.PEL,
        ),
        line("cel", "savings", ALEX, SHARED, cel, closed_from=CAR + 1),
        line(
            "life_insurance",
            "bonds",
            CAMILLE,
            SHARED,
            series(0, 18000, lambda i, v: v * (1 + D("0.025") / 12) + 150),
        ),
        line("pea", "stocks", CAMILLE, SHARED, series(PEA, 200, market(-220, 280, 200))),
        line("brokerage", "stocks", ALEX, PRIVATE, series(0, 5000, market(-220, 280))),
        line("bitcoin", "crypto", ALEX, PRIVATE, series(0, 1200, market(-850, 950))),
        line("home", "real-estate", CAMILLE, JOINT, series(0, 310000, saved(0, "0.025"))),
        line(
            "car",
            "equipment",
            ALEX,
            JOINT,
            series(CAR, 21000, lambda i, v: v * (1 - D("0.15") / 12)),
        ),
        line(
            "mortgage_debt",
            "debts",
            CAMILLE,
            JOINT,
            series(0, 228000, amortised("0.0145", "1050")),
            debt=("1050.00", "0.0145", "38.00"),
        ),
        line(
            "car_debt",
            "debts",
            ALEX,
            JOINT,
            series(CAR, 14000, amortised("0.049", "263")),
            debt=("263.00", "0.049", "0"),
        ),
    )


def _goals(
    at: Callable[[int], Month], this_month: Month, t: Callable[[str], str]
) -> tuple[DemoGoal, ...]:
    """A pyramid with every tier: Camille's precaution reached and her goals ahead unlock her
    pleasure goal; Alex, without a precaution and behind on the motorbike, keeps his locked."""

    def goal(
        key: str,
        target: int,
        start: Month,
        owner: str,
        visibility: Visibility,
        line: str,
        share: int,
        opening: int = 0,
        *,
        deadline: Month | None = None,
        precaution: bool = False,
        pleasure: bool = False,
        closed_from: Month | None = None,
    ) -> DemoGoal:
        """Funded by one line: `share` % of its rises and `opening` taken at the start."""
        return DemoGoal(
            key,
            t(key),
            D(target),
            start,
            owner,
            visibility,
            (DemoFunding(line, share, D(opening)),),
            deadline,
            precaution,
            permanent=precaution,
            pleasure=pleasure,
            closed_from=closed_from,
            closed_as="archived" if closed_from else None,
        )

    def months(n: int) -> Month:
        return add_months(this_month, n)

    return (
        goal("precaution", 12000, at(0), CAMILLE, SHARED, "livret_a", 60, 9000, precaution=True),
        goal(
            "holidays",
            3000,
            months(-8),
            CAMILLE,
            JOINT,
            "joint_savings",
            80,
            1200,
            deadline=months(4),
        ),
        goal("motorbike", 9000, at(6), ALEX, SHARED, "ldds", 80, 2000, deadline=months(20)),
        goal(
            "studies",
            30000,
            at(0),
            CAMILLE,
            SHARED,
            "life_insurance",
            100,
            12000,
            deadline=months(144),
        ),
        goal("spa", 1500, at(20), CAMILLE, SHARED, "livret_a", 20, pleasure=True),
        goal("guitar", 2000, at(PEA), ALEX, SHARED, "ldds", 20, 500, pleasure=True),
        goal(
            "sofa",
            1500,
            at(4),
            CAMILLE,
            JOINT,
            "joint_savings",
            30,
            300,
            deadline=at(14),
            closed_from=at(14),
        ),
    )
