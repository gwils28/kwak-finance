"""Synthetic French household spending, by category and month: the study's data.

Never real data: `data/` and the app's database are out of bounds for the notebooks. A panel of
households is drawn from a fixed seed, each with its own size, income and habits, and every
category is built from known components, so a method's errors can be read against the truth:

- a level that depends on the household (income, size) and drifts slowly (a trend);
- yearly seasonality (December gifts and bonus, July and August holidays, back-to-school);
- intermittent categories (health, home repairs, gifts) with many empty months;
- fixed expenses (rent or mortgage, subscriptions, insurance) that change amount now and then;
- structural breaks (a child starts school, a car is bought, a raise);
- multiplicative, heteroscedastic noise (larger months vary more);
- for some households, an **intervention** of known size: a budget target set on a category
  from a month on, which lowers its variable spending by a known share (notebook 08).

The app's own demo household (`kwak_core.demo`) is loaded the way the app reads it, through
`kwak_core.forecast.build_series`.
"""

from dataclasses import dataclass
from datetime import date
from uuid import NAMESPACE_URL, uuid5

import numpy as np
import pandas as pd
from kwak_core.budget import Month
from kwak_core.categories import DEFAULT_SPENDING_CATEGORIES
from kwak_core.demo import generate
from kwak_core.fixed import FixedExpense
from kwak_core.forecast import Piece, build_series, history
from kwak_core.users import Language

SEED = 20261028
START = pd.Timestamp("2021-01-01")

EXPENSE, SAVINGS, INCOME = "expense", "savings", "income"

# name, kind, base share of net income, yearly seasonal profile (12 multipliers or None),
# probability that a month holds a line (1 = every month), noise (lognormal sigma)
CATEGORIES: tuple[tuple[str, str, float, tuple[float, ...] | None, float, float], ...] = (
    ("Housing", EXPENSE, 0.0, None, 1.0, 0.0),  # fixed only, see below
    ("Groceries", EXPENSE, 0.15, (1, 0.95, 1, 1, 1, 1, 0.9, 0.85, 1, 1, 1.02, 1.2), 1.0, 0.08),
    ("Transport", EXPENSE, 0.07, (1, 1, 1, 1, 1.05, 1.05, 1.25, 1.3, 1, 1, 1, 0.95), 1.0, 0.18),
    ("Children", EXPENSE, 0.04, (1, 1, 1, 1, 1, 1, 0.6, 0.6, 1.9, 1, 1, 1.1), 1.0, 0.15),
    ("Health", EXPENSE, 0.015, None, 0.55, 0.6),
    ("Subscriptions", EXPENSE, 0.0, None, 1.0, 0.0),  # fixed only
    ("Home", EXPENSE, 0.03, (1, 1, 1, 1.3, 1.3, 1.2, 1, 1, 1, 1, 1, 1), 0.6, 0.7),
    ("Leisure", EXPENSE, 0.05, (0.8, 0.8, 0.9, 1, 1, 1.2, 2.6, 2.4, 0.8, 0.9, 0.8, 1.1), 1.0, 0.3),
    ("Shopping", EXPENSE, 0.03, (1.2, 0.9, 0.9, 1, 1, 1.1, 1.2, 0.9, 1, 1, 1.4, 1.5), 0.95, 0.4),
    (
        "Gifts",
        EXPENSE,
        0.012,
        (0.3, 0.3, 0.5, 0.5, 0.8, 0.6, 0.4, 0.3, 0.5, 0.6, 1.2, 6.0),
        0.4,
        0.5,
    ),
    ("Miscellaneous", EXPENSE, 0.02, None, 0.9, 0.5),
    ("Savings", SAVINGS, 0.0, None, 1.0, 0.0),  # transfers, see below
    ("Salaries", INCOME, 1.0, None, 1.0, 0.0),  # see below
)


@dataclass(frozen=True)
class Intervention:
    household: int
    category: str
    month: int
    """Index of the first month it applies to."""
    effect: float
    """The share of the variable spending removed from then on (0.12 = 12 % less)."""


def _profile(values: tuple[float, ...] | None) -> np.ndarray:
    if values is None:
        return np.ones(12)
    p = np.asarray(values, dtype=float)
    return p / p.mean()


def household(
    rng: np.random.Generator, h: int, n: int
) -> tuple[list[dict[str, object]], Intervention | None]:
    """One household's rows over n months, and its intervention if it has one."""
    size = int(rng.choice([1, 2, 3, 4], p=[0.25, 0.3, 0.25, 0.2]))
    net = rng.lognormal(np.log(2600 + 900 * min(size, 2)), 0.3)  # net monthly income
    thirteenth = rng.random() < 0.45  # a 13th month paid in December
    raise_at = int(rng.integers(6, n)) if rng.random() < 0.6 else None
    raise_by = rng.uniform(0.03, 0.12)
    owner = rng.random() < 0.55
    housing = net * rng.uniform(0.22, 0.33)
    housing_change = int(rng.integers(6, n)) if rng.random() < 0.5 else None  # rent indexation
    subscriptions = rng.uniform(40, 160)
    sub_change = int(rng.integers(6, n)) if rng.random() < 0.4 else None
    car_at = int(rng.integers(6, n)) if rng.random() < 0.25 else None  # transport jumps
    school_at = int(rng.integers(6, n)) if size >= 3 and rng.random() < 0.5 else None
    saving = net * rng.uniform(0.05, 0.2)
    trend = rng.normal(0.0015, 0.002)  # monthly drift of variable spending (inflation, habits)
    month0 = int(rng.integers(0, 12))
    intervention = None
    if rng.random() < 0.3 and n >= 30:
        intervention = Intervention(
            h,
            str(rng.choice(["Groceries", "Leisure", "Shopping"])),
            int(rng.integers(n - 14, n - 6)),
            float(rng.uniform(0.08, 0.25)),
        )
    rows: list[dict[str, object]] = []
    for name, kind, share, seasonal, p_line, sigma in CATEGORIES:
        profile = _profile(seasonal)
        base = net * share * (0.6 + 0.2 * size)
        for t in range(n):
            moy = (month0 + t) % 12
            fixed = 0.0
            variable = 0.0
            if name == "Housing":
                fixed = housing * (
                    1.03 if housing_change is not None and t >= housing_change else 1
                )
                if owner and moy == 9:
                    variable = rng.lognormal(np.log(net * 0.35), 0.1)  # property tax, typed by hand
            elif name == "Subscriptions":
                fixed = subscriptions + (12 if sub_change is not None and t >= sub_change else 0)
            elif name == "Savings":
                fixed = saving
                if rng.random() < 0.06:
                    variable = -rng.uniform(0.3, 1.5) * saving  # money taken back
            elif name == "Salaries":
                pay = net * (1 + raise_by if raise_at is not None and t >= raise_at else 1)
                variable = pay * rng.lognormal(0, 0.015)
                if thirteenth and moy == 11:
                    variable += pay
            else:
                level = base * (1 + trend) ** t
                if name == "Transport" and car_at is not None and t >= car_at:
                    level *= 1.35
                if name == "Children" and school_at is not None and t >= school_at:
                    level *= 0.7
                if intervention and intervention.category == name and t >= intervention.month:
                    level *= 1 - intervention.effect
                if rng.random() < p_line:
                    # heteroscedastic: the noise grows with the seasonal peak
                    variable = (
                        level
                        * profile[moy]
                        * rng.lognormal(
                            -0.5 * sigma**2, sigma * (0.8 + 0.4 * profile[moy] / profile.max())
                        )
                    )
            rows.append(
                {
                    "household": h,
                    "category": name,
                    "kind": kind,
                    "t": t,
                    "month_of_year": moy + 1,
                    "fixed": round(fixed, 2),
                    "variable": round(variable, 2),
                }
            )
    return rows, intervention


def panel(
    households: int = 200, *, seed: int = SEED, min_months: int = 36, max_months: int = 60
) -> tuple[pd.DataFrame, list[Intervention]]:
    """The panel, long: one row per household, category and month, with `unique_id`, `ds`
    (month starts, every household ending on the same last month), `y` = fixed + variable."""
    rng = np.random.default_rng(seed)
    frames, interventions = [], []
    last = START + pd.DateOffset(months=max_months - 1)
    for h in range(households):
        n = int(rng.integers(min_months, max_months + 1))
        rows, intervention = household(rng, h, n)
        df = pd.DataFrame(rows)
        first = last - pd.DateOffset(months=n - 1)
        df["ds"] = [first + pd.DateOffset(months=int(t)) for t in df["t"]]
        frames.append(df)
        if intervention:
            interventions.append(intervention)
    out = pd.concat(frames, ignore_index=True)
    out["month_of_year"] = out["ds"].dt.month
    out["y"] = (out["fixed"] + out["variable"]).round(2)
    out["unique_id"] = out["household"].astype(str).str.zfill(3) + "/" + out["category"]
    return out, interventions


def variable_series(df: pd.DataFrame) -> pd.DataFrame:
    """What the models forecast: each series' variable part (the app adds the fixed part, known
    in advance), in Nixtla's long format. Series that are fixed only are left out."""
    v = df[["unique_id", "household", "category", "kind", "ds", "variable"]].rename(
        columns={"variable": "y"}
    )
    keep = v.groupby("unique_id")["y"].transform(lambda s: (s != 0).sum() >= 3)
    return v[keep].reset_index(drop=True)


def demo_household(today: date = date(2026, 10, 28)) -> pd.DataFrame:
    """The app's demo household (F-ADM-5), its series built as the app builds them."""
    demo = generate(today, Language.EN)
    names = {c.name(Language.EN): c for c in DEFAULT_SPENDING_CATEGORIES}
    ids = {name: uuid5(NAMESPACE_URL, f"demo/{name}") for name in names}
    kinds = {ids[n]: c.kind for n, c in names.items()}
    fixed_ids = {f.key: uuid5(NAMESPACE_URL, f"fixed/{f.key}") for f in demo.fixed}
    items = [
        FixedExpense(
            fixed_ids[f.key],
            f.label,
            ids[f.category],
            f.amount,
            f.frequency,
            f.day,
            f.first,
            f.last,
        )
        for f in demo.fixed
    ]
    pieces = []
    for line in demo.lines:
        fx = fixed_ids.get(line.fixed) if line.fixed else None
        if line.parts:
            for part in line.parts:
                pieces.append(
                    Piece(ids[part.category], line.day, part.amount, line.label, fx, True)
                )
        else:
            assert line.category is not None
            pieces.append(Piece(ids[line.category], line.day, line.amount, line.label, fx))
    origin = Month.of(today).previous()
    first = min(Month.of(p.day) for p in pieces)
    months = history(first, origin)
    series = build_series(pieces, kinds, items, months)
    rows = []
    by_id = {v: k for k, v in ids.items()}
    for key, s in series.items():
        for i, m in enumerate(months):
            rows.append(
                {
                    "unique_id": f"demo/{by_id[key]}",
                    "category": by_id[key],
                    "kind": str(s.kind),
                    "ds": pd.Timestamp(m.first_day()),
                    "y": float(s.total[i]),
                    "fixed": float(s.fixed[i]),
                    "variable": float(s.total[i] - s.fixed[i]),
                }
            )
    return pd.DataFrame(rows)
