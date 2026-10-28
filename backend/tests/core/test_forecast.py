"""The cash-flow forecast's rules (spec §4.14 F-FCT-1 to 5, invariants §8.41 to 44): the series,
the fixed and variable parts, the back-test's cuts and errors, the choice of a model, the bands
and the chances."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month
from kwak_core.categories import CategoryKind
from kwak_core.fixed import FixedExpense, FixedFrequency
from kwak_core.forecast import (
    BASELINE,
    HORIZON,
    MIN_ERRORS,
    Band,
    Errors,
    Piece,
    Risk,
    Series,
    against_objective,
    against_target,
    assemble,
    band,
    build_series,
    chance_above,
    chance_below,
    choose,
    coverage,
    cuts,
    errors,
    history,
    known,
    own_cuts,
    quantiles,
    score,
    sum_errors,
)

D = Decimal
EXPENSE, SAVINGS, INCOME = CategoryKind.EXPENSE, CategoryKind.SAVINGS, CategoryKind.INCOME
GROCERIES, RENT_CAT, SAVED, SALARY = uuid4(), uuid4(), uuid4(), uuid4()
KINDS = {GROCERIES: EXPENSE, RENT_CAT: EXPENSE, SAVED: SAVINGS, SALARY: INCOME}
JAN = Month(2025, 1)
ORDER = (BASELINE, "average_3", "naive", "ets")


def piece(
    category: UUID,
    day: date,
    amount: str,
    label: str = "x",
    *,
    fixed: UUID | None = None,
    split: bool = False,
) -> Piece:
    return Piece(category, day, D(amount), label, fixed, split)


def rent(**kw: object) -> FixedExpense:
    values: dict[str, object] = {
        "id": uuid4(),
        "label": "Rent",
        "category_id": RENT_CAT,
        "amount": D("-800"),
        "frequency": FixedFrequency.MONTHLY,
        "day": 5,
        "first": Month(2025, 6),
    }
    values.update(kw)
    return FixedExpense(**values)  # type: ignore[arg-type]


def months(n: int, start: Month = JAN) -> list[Month]:
    out = [start]
    while len(out) < n:
        out.append(out[-1].next())
    return out


def ds(*values: float | int | str) -> tuple[Decimal, ...]:
    return tuple(D(str(v)) for v in values)


# F-FCT-1: the history


def test_history_runs_from_the_first_line_to_the_origin() -> None:
    assert history(Month(2025, 11), Month(2026, 2)) == months(4, Month(2025, 11))


def test_history_keeps_sixty_months_at_most() -> None:
    got = history(Month(2015, 1), Month(2026, 9))
    assert len(got) == 60
    assert got[0] == Month(2021, 10)
    assert got[-1] == Month(2026, 9)


def test_no_history_without_a_line() -> None:
    assert history(None, Month(2026, 9)) == []


def test_series_are_positive_figures_by_month() -> None:
    pieces = [
        piece(GROCERIES, date(2025, 1, 3), "-40"),
        piece(GROCERIES, date(2025, 1, 20), "-60"),
        piece(SALARY, date(2025, 2, 1), "2500"),
        piece(SAVED, date(2025, 1, 2), "-300"),
        piece(SAVED, date(2025, 2, 2), "100"),  # taken back from savings
    ]
    series = build_series(pieces, KINDS, [], months(2))
    assert series[GROCERIES].total == ds(100, 0)
    assert series[SALARY].total == ds(0, 2500)
    assert series[SAVED].total == ds(300, -100)
    assert series[RENT_CAT].total == ds(0, 0)
    assert series[RENT_CAT].start is None


def test_a_category_starts_at_its_first_line() -> None:
    pieces = [piece(SALARY, date(2025, 2, 1), "2500"), piece(GROCERIES, date(2025, 1, 1), "-1")]
    series = build_series(pieces, KINDS, [], months(3))
    assert series[SALARY].start == 1
    assert series[SALARY].length == 2
    assert series[GROCERIES].start == 0


def test_lines_outside_the_months_are_never_read() -> None:
    """Invariant §8.41: nothing after the origin."""
    pieces = [piece(GROCERIES, date(2025, 3, 1), "-999")]
    assert build_series(pieces, KINDS, [], months(2))[GROCERIES].total == ds(0, 0)


# F-FCT-2: fixed and variable


def test_a_line_created_from_a_fixed_expense_is_fixed() -> None:
    item = rent()
    pieces = [piece(RENT_CAT, date(2025, 6, 5), "-800", "Loyer juin", fixed=item.id)]
    s = build_series(pieces, KINDS, [item], [Month(2025, 6)])[RENT_CAT]
    assert s.fixed == ds(800)
    assert s.variable == ds(0)
    assert s.matched == ds(800)


def test_a_typed_line_matches_the_schedule_extended_back() -> None:
    """Invariant §8.42: before the fixed expense existed too, so it is never also learnt."""
    item = rent(first=Month(2025, 6))
    pieces = [
        piece(RENT_CAT, date(2025, 1, 5), "-790", "  RENT "),
        piece(RENT_CAT, date(2025, 1, 9), "-30", "Plumber"),
    ]
    s = build_series(pieces, KINDS, [item], [JAN])[RENT_CAT]
    assert s.fixed == ds(790)
    assert s.variable == ds(30)
    assert s.matched == ds(800), "the back-test's known part is the current amount"


def test_one_typed_line_per_occurrence_the_closest_in_amount() -> None:
    item = rent()
    pieces = [
        piece(RENT_CAT, date(2025, 1, 5), "-120", "Rent"),
        piece(RENT_CAT, date(2025, 1, 6), "-805", "Rent"),
    ]
    s = build_series(pieces, KINDS, [item], [JAN])[RENT_CAT]
    assert s.fixed == ds(805)
    assert s.variable == ds(120)


def test_a_typed_line_off_the_schedule_stays_variable() -> None:
    yearly = rent(label="Insurance", frequency=FixedFrequency.YEARLY, first=Month(2025, 9))
    pieces = [
        piece(RENT_CAT, date(2024, 9, 5), "-400", "Insurance"),
        piece(RENT_CAT, date(2024, 10, 5), "-50", "Insurance"),
    ]
    s = build_series(pieces, KINDS, [yearly], [Month(2024, 9), Month(2024, 10)])[RENT_CAT]
    assert s.fixed == ds(400, 0)
    assert s.variable == ds(0, 50)


def test_a_typed_line_in_another_category_is_not_matched() -> None:
    pieces = [piece(GROCERIES, date(2025, 1, 5), "-800", "Rent")]
    assert build_series(pieces, KINDS, [rent()], [JAN])[GROCERIES].fixed == ds(0)


def test_a_split_part_is_matched_only_when_created_from_a_fixed_expense() -> None:
    pieces = [piece(RENT_CAT, date(2025, 1, 5), "-800", "Rent", split=True)]
    assert build_series(pieces, KINDS, [rent()], [JAN])[RENT_CAT].fixed == ds(0)


def test_no_typed_line_after_the_last_month() -> None:
    item = rent(first=Month(2024, 1), last=Month(2024, 12))
    pieces = [piece(RENT_CAT, date(2025, 1, 5), "-800", "Rent")]
    assert build_series(pieces, KINDS, [item], [JAN])[RENT_CAT].fixed == ds(0)


def test_known_part_is_the_occurrences_due() -> None:
    monthly = rent(first=Month(2026, 10))
    quarterly = rent(
        category_id=GROCERIES,
        label="Box",
        amount=D("-90"),
        frequency=FixedFrequency.QUARTERLY,
        first=Month(2026, 9),
    )
    paused = rent(label="Gym", paused=True)
    ended = rent(label="Old", last=Month(2026, 10))
    got = known(
        [monthly, quarterly, paused, ended],
        KINDS,
        skipped={(monthly.id, Month(2026, 11))},
        months=months(3, Month(2026, 10)),
    )
    assert got[RENT_CAT] == ds(1600, 0, 800)  # skipped November; "Old" ends in October
    assert got[GROCERIES] == ds(0, 0, 90)
    assert got[SALARY] == ds(0, 0, 0)


# F-FCT-4: cuts and errors


def test_cuts_from_the_thirteenth_month_with_two_years() -> None:
    assert cuts(36) == list(range(13, 36))


def test_cuts_from_the_seventh_month_below_two_years() -> None:
    assert cuts(12) == list(range(7, 12))
    assert cuts(23) == list(range(7, 23))


def test_no_cut_below_twelve_months() -> None:
    assert cuts(11) == []


@given(st.integers(min_value=12, max_value=60))
def test_a_cut_never_forecasts_past_the_origin(n: int) -> None:
    """Invariant §8.41."""
    for c in cuts(n):
        assert 1 <= c < n


def test_a_late_series_has_its_own_cuts() -> None:
    assert own_cuts(36, start=0) == list(range(13, 36))
    assert own_cuts(36, start=20) == list(range(27, 36))  # 16 months: from its 7th
    assert own_cuts(36, start=30) == []


def test_errors_are_actual_minus_forecast_by_cut_and_step() -> None:
    actual = ds(10, 20, 30, 40)
    got = errors(actual, {2: ds(25, 25), 3: ds(35)})
    assert got == {(2, 1): D(5), (2, 2): D(15), (3, 1): D(5)}


def test_errors_stop_at_the_origin() -> None:
    assert set(errors(ds(1, 1, 1, 1), {3: (D(1),) * HORIZON})) == {(3, 1)}


def test_score_scales_errors_by_the_training_months_change() -> None:
    s = score(ds(10, 20, 10, 20, 15), {4: ds(10)})
    # training 10, 20, 10, 20: mean |change| 10; error 5
    assert s is not None
    assert s.mase == D("0.5")
    assert s.rmsse == D("0.5")
    assert s.wape == D(5) / D(15)


def test_no_score_when_a_training_never_changed() -> None:
    assert score(ds(50, 50, 50, 50, 60), {4: ds(50)}) is None


def test_wape_is_none_without_amounts() -> None:
    s = score(ds(0, 5, 0, 0), {3: ds(0)})
    assert s is not None
    assert s.wape is None


# F-FCT-4: the choice

ACTUAL = ds(10, 30, 20, 40)


def bt(**models: tuple[int | str, int | str]) -> dict[str, dict[int, tuple[Decimal, ...]]]:
    """Each model's forecasts at cuts 2 and 3, one month ahead."""
    return {name: {2: ds(a), 3: ds(b)} for name, (a, b) in models.items()}


def test_the_lowest_mase_wins_when_clearly_below_the_baseline() -> None:
    got = choose(ACTUAL, bt(baseline=(10, 10), ets=(21, 39)), ORDER, cuts=[2, 3])
    assert got.model == "ets"
    assert got.contest


def test_the_baseline_stays_unless_ten_percent_better() -> None:
    """Invariant §8.44: errors 9.2 against 10 on both cuts, 8 % better only."""
    got = choose(ACTUAL, bt(baseline=(10, 30), naive=("10.8", "49.2")), ORDER, cuts=[2, 3])
    assert got.model == BASELINE


def test_ties_go_to_the_simpler() -> None:
    got = choose(ACTUAL, bt(baseline=(10, 10), ets=(20, 40), naive=(20, 40)), ORDER, cuts=[2, 3])
    assert got.model == "naive"


def test_a_candidate_missing_a_cut_is_left_out() -> None:
    models = bt(baseline=(10, 10))
    models["ets"] = {3: ds(40)}
    assert choose(ACTUAL, models, ORDER, cuts=[2, 3]).model == BASELINE


def test_a_sparse_series_keeps_the_baseline_without_contest() -> None:
    got = choose(ds(0, 0, 40, 0), bt(baseline=(10, 10), naive=(40, 0)), ORDER, cuts=[2, 3])
    assert got.model == BASELINE
    assert not got.contest


def test_a_flat_training_keeps_the_baseline_without_contest() -> None:
    got = choose(ds(5, 5, 5, 9), bt(baseline=(5, 5), naive=(5, 9)), ORDER, cuts=[2, 3])
    assert got.model == BASELINE
    assert not got.contest


def test_no_cut_keeps_the_baseline() -> None:
    assert not choose(ACTUAL, bt(baseline=(10, 10)), ORDER, cuts=[]).contest


# F-FCT-5: bands and chances

NINE = [D(v) for v in (-40, -30, -20, -10, 0, 10, 20, 30, 40)]


def test_quantiles_take_the_conformal_ranks() -> None:
    """Of 9 errors, the 1st and the 9th; of 19, the 2nd and the 18th."""
    assert quantiles(NINE) == (D(-40), D(40))
    nineteen = [D(v) for v in range(19)]
    assert quantiles(nineteen) == (D(1), D(17))


def test_no_quantiles_below_nine_errors() -> None:
    assert quantiles(NINE[:8]) is None


def test_band_adds_the_error_quantiles() -> None:
    assert band(D(100), NINE, floor=False) == Band(D(60), D(100), D(140))


def test_a_band_always_holds_its_forecast() -> None:
    """A biased model's errors all of one sign widen the band on one side only."""
    errs = [D(v) for v in range(10, 100, 10)]
    assert band(D(100), errs, floor=False) == Band(D(100), D(100), D(190))


def test_band_never_below_zero_for_spending() -> None:
    errs = [D(-200)] * 5 + [D(0)] * 4
    got = band(D(50), errs, floor=True)
    assert got.low == D(0)
    assert got.point == D(50)


def test_a_negative_point_is_floored_for_spending() -> None:
    assert band(D(-5), None, floor=True) == Band(D(0), D(0), D(0))


def test_no_band_without_errors() -> None:
    assert band(D(50), None, floor=True) == Band(D(50), D(50), D(50))


def test_chance_above_is_conformal() -> None:
    """(k + 1) / (n + 1): 2 of 9 errors carry 100 above 125."""
    assert chance_above(D(100), NINE, D(125)) == D(3) / D(10)
    assert chance_above(D(100), NINE, D(500)) == D(1) / D(10)


def test_chance_below_mirrors_it() -> None:
    assert chance_below(D(100), NINE, D(75)) == D(3) / D(10)


@given(
    st.lists(st.integers(-500, 500), min_size=MIN_ERRORS, max_size=30),
    st.integers(-100, 1000),
    st.integers(0, 1000),
    st.integers(0, 1000),
)
def test_bands_hold_their_forecast_and_chances_are_monotone(
    raw: list[int], point: int, a: int, b: int
) -> None:
    """Invariant §8.43."""
    errs = [D(v) for v in raw]
    got = band(D(point), errs, floor=True)
    assert D(0) <= got.low <= got.point <= got.high
    low, high = sorted((a, b))
    assert chance_above(D(point), errs, D(high)) <= chance_above(D(point), errs, D(low))


def test_errors_widen_past_the_longest_step_with_enough() -> None:
    errs = {(c, k): D(9) for c in range(1, 12) for k in range(1, 4) if c + k <= 12}
    # step 1: 11 errors, step 2: 10, step 3: 9; steps 4 and up: none
    got = Errors.of(errs)
    assert got.widened_from == 4
    assert got.at(3) == [D(9)] * 9
    assert got.at(12) == [D(18)] * 9  # √(12 / 3) = 2


def test_errors_none_without_nine_one_month_ahead() -> None:
    got = Errors.of({(c, 1): D(1) for c in range(1, 9)})
    assert got.at(1) is None
    assert got.widened_from == 1


def test_sum_errors_add_each_cut_s_months() -> None:
    errs = {(c, k): D(k) for c in range(1, 20) for k in range(1, 4) if c + k <= 20}
    got = sum_errors(errs, 3)
    assert got == [D(6)] * 17
    assert sum_errors(errs, 4) is None


def test_coverage_uses_only_errors_known_at_each_cut() -> None:
    zeros = {(c, 1): D(0) for c in range(1, 10)}
    # cut 10's band is built from cuts 1 to 9 (known by then); its error falls outside.
    assert coverage(zeros | {(10, 1): D(100)}) == D(0)
    assert coverage(zeros | {(10, 1): D(0)}) == D(1)


def test_no_coverage_without_enough_errors() -> None:
    assert coverage({(c, 1): D(0) for c in range(1, 10)}) is None


# Assembling (invariants §8.42, 43)


def _series(
    total: list[int], fixed: list[int] | None = None, kind: CategoryKind = EXPENSE
) -> Series:
    t = tuple(D(v) for v in total)
    f = tuple(D(v) for v in fixed) if fixed else (D(0),) * len(t)
    return Series(kind, t, f, f, 0)


def _flat_backtests(s: Series, n: int) -> dict[str, dict[int, tuple[Decimal, ...]]]:
    """The baseline forecasting each cut's last variable month."""
    return {
        BASELINE: {c: (s.variable[c - 1],) * min(HORIZON, n - c) for c in range(1, n)},
    }


def test_a_constant_series_is_forecast_at_its_amount_with_no_width() -> None:
    n = 24
    s = _series([50] * n)
    got = assemble(
        {GROCERIES: s},
        {},
        {GROCERIES: _flat_backtests(s, n)},
        {GROCERIES: {BASELINE: (D(50),) * HORIZON}},
        ORDER,
    )
    cf = got.categories[GROCERIES]
    assert all(b == Band(D(50), D(50), D(50)) for b in cf.bands)
    assert got.year(GROCERIES, 3) == Band(D(150), D(150), D(150))


def test_forecasts_add_up() -> None:
    """Invariant §8.42: known plus variable, totals the sums, rest = income - spent - saved."""
    n = 24
    s = {
        GROCERIES: _series([100 + (i % 3) * 10 for i in range(n)]),
        RENT_CAT: _series([800] * n, [800] * n),
        SAVED: _series([200] * n, kind=SAVINGS),
        SALARY: _series([3000] * n, kind=INCOME),
    }
    backtests = {k: _flat_backtests(v, n) for k, v in s.items()}
    futures = {k: {BASELINE: (v.variable[-1],) * HORIZON} for k, v in s.items()}
    got = assemble(s, {RENT_CAT: (D(800),) * HORIZON}, backtests, futures, ORDER)
    cats = got.categories
    for step in range(HORIZON):
        assert cats[RENT_CAT].bands[step].point == D(800)
        spent = cats[GROCERIES].bands[step].point + cats[RENT_CAT].bands[step].point
        assert got.spent[step].point == spent
        assert got.income[step].point == D(3000)
        assert got.saved[step].point == D(200)
        assert got.rest[step].point == D(3000) - spent - D(200)


def test_a_category_without_lines_is_forecast_at_zero() -> None:
    s = {GROCERIES: Series(EXPENSE, (D(0),) * 14, (D(0),) * 14, (D(0),) * 14, None)}
    got = assemble(s, {}, {}, {}, ORDER)
    assert got.categories[GROCERIES].choice is None
    assert got.categories[GROCERIES].bands[0] == Band(D(0), D(0), D(0))


# F-FCT-6: against the targets


def test_likely_over_from_one_chance_in_two() -> None:
    risk, chance = against_target(D(510), NINE, D(500))
    assert risk is Risk.LIKELY
    assert chance == D(6) / D(10)


def test_may_go_over_from_a_fifth() -> None:
    risk, chance = against_target(D(475), NINE, D(500))
    assert risk is Risk.POSSIBLE
    assert chance == D(3) / D(10)


def test_unlikely_below_a_fifth() -> None:
    risk, _ = against_target(D(400), NINE, D(500))
    assert risk is Risk.UNLIKELY


def test_no_risk_without_errors() -> None:
    assert against_target(D(510), None, D(500)) == (Risk.LIKELY, None)
    assert against_target(D(490), None, D(500)) == (Risk.UNLIKELY, None)


def test_savings_objective_counts_the_chance_of_falling_below() -> None:
    risk, chance = against_objective(D(310), NINE, D(300))
    assert risk is Risk.POSSIBLE
    assert chance == D(4) / D(10)


# Review fixes


def test_a_split_line_from_a_fixed_expense_shares_its_known_amount() -> None:
    """Invariant §8.42: one occurrence, counted once, spread over the parts."""
    item = rent(amount=D("-100"))
    pieces = [
        piece(GROCERIES, date(2025, 1, 5), "-60", "Rent", fixed=item.id, split=True),
        piece(RENT_CAT, date(2025, 1, 5), "-40", "Rent", fixed=item.id, split=True),
    ]
    series = build_series(pieces, KINDS, [item], [JAN])
    assert series[GROCERIES].matched == ds(60)
    assert series[RENT_CAT].matched == ds(40)


def test_a_late_series_is_scaled_on_its_own_months() -> None:
    """A constant amount since its first line never changed: no MASE."""
    actual = ds(0, 0, 30, 30, 30, 31)
    assert score(actual, {5: ds(30)}, start=2) is None


def test_coverage_counts_the_band_shown_which_holds_the_forecast() -> None:
    errs = {(c, 1): D(10) for c in range(1, 10)} | {(10, 1): D(0)}
    assert coverage(errs) == D(1)


def test_a_category_s_errors_come_from_its_chosen_model_only() -> None:
    n = 36
    start = 10
    values = [D(0)] * start + [D(100 + (i % 2) * 40) for i in range(n - start)]
    s = Series(EXPENSE, tuple(values), (D(0),) * n, (D(0),) * n, start)
    exact = {c: tuple(values[c : min(c + HORIZON, n)]) for c in range(start + 13, n)}
    base = {c: (D(500),) * min(HORIZON, n - c) for c in range(start + 1, n)}
    got = assemble(
        {GROCERIES: s},
        {},
        {GROCERIES: {BASELINE: base, "naive": exact}},
        {GROCERIES: {BASELINE: (D(120),) * HORIZON, "naive": (D(120),) * HORIZON}},
        ORDER,
    )
    cf = got.categories[GROCERIES]
    assert cf.choice is not None
    assert cf.choice.model == "naive"
    assert all(e == 0 for (c, _), e in cf.errors.items() if c > start)


def test_a_category_without_lines_is_forecast_at_its_fixed_expenses() -> None:
    s = {RENT_CAT: Series(EXPENSE, (D(0),) * 14, (D(0),) * 14, (D(0),) * 14, None)}
    got = assemble(s, {RENT_CAT: (D(800),) * HORIZON}, {}, {}, ORDER)
    assert got.categories[RENT_CAT].choice is None
    assert got.spent[0].point == D(800)


def test_below_two_years_every_candidate_competes_but_last_year_s_month() -> None:
    """Invariant §8.44: the seasonal naive needs 24 months of the series."""
    n = 20
    values = [D(100 + (i % 2) * 40) for i in range(n)]
    s = Series(EXPENSE, tuple(values), (D(0),) * n, (D(0),) * n, 0)
    exact = {c: tuple(values[c : min(c + HORIZON, n)]) for c in range(13, n)}
    base = {c: (D(500),) * min(HORIZON, n - c) for c in range(1, n)}
    futures = {BASELINE: (D(1),) * HORIZON, "naive": (D(2),) * HORIZON}
    got = assemble(
        {GROCERIES: s},
        {},
        {GROCERIES: {BASELINE: base, "naive": exact}},
        {GROCERIES: futures},
        ORDER,
    )
    assert got.categories[GROCERIES].choice.model == "naive"  # type: ignore[union-attr]
    seasonal = {GROCERIES: {BASELINE: base, "seasonal_naive": exact}}
    order = (BASELINE, "seasonal_naive")
    got = assemble({GROCERIES: s}, {}, seasonal, {GROCERIES: {BASELINE: (D(1),) * HORIZON}}, order)
    assert got.categories[GROCERIES].choice.model == BASELINE  # type: ignore[union-attr]
