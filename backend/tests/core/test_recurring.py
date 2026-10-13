from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.recurring import (
    LATE_WINDOW,
    TOLERANCE,
    Booked,
    Frequency,
    Item,
    Occurrence,
    OccurrenceStatus,
    RecurringError,
    check_item,
    detect,
    due_dates,
    entry_date,
    estimate,
    occurrences,
    projected_balance,
    upcoming,
)

D = Decimal
ACCOUNT = uuid4()


def item(**changes: object) -> Item:
    fields: dict[str, object] = {
        "id": uuid4(),
        "account_id": ACCOUNT,
        "label": "Loyer",
        "amount": D("-950.00"),
        "frequency": Frequency.MONTHLY,
        "day": 3,
        "start": date(2026, 1, 1),
    }
    fields.update(changes)
    return Item(**fields)  # type: ignore[arg-type]


def booked(day: date, amount: str, label: str = "LOYER OCTOBRE", account: UUID = ACCOUNT) -> Booked:
    return Booked(uuid4(), account, day, D(amount), label)


# Definition.


def test_a_valid_item_passes() -> None:
    check_item(item())
    check_item(item(frequency=Frequency.WEEKLY, day=0))


@pytest.mark.parametrize(
    "changes",
    [
        {"label": "  "},
        {"amount": D("0.00")},
        {"frequency": Frequency.WEEKLY, "day": 7},
        {"day": 0},
        {"day": 32},
        {"start": date(2026, 5, 1), "end": date(2026, 4, 30)},
    ],
)
def test_an_invalid_item_is_refused(changes: dict[str, object]) -> None:
    with pytest.raises(RecurringError):
        check_item(item(**changes))


# Due dates.


def test_a_monthly_item_is_due_on_its_day_and_the_last_day_stands_in_for_a_missing_one() -> None:
    rent = item(day=31)
    assert due_dates(rent, date(2026, 1, 1), date(2026, 4, 30)) == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
    ]


def test_a_weekly_item_is_due_on_its_weekday() -> None:
    market = item(frequency=Frequency.WEEKLY, day=5, start=date(2026, 10, 1))  # Saturdays
    assert due_dates(market, date(2026, 10, 1), date(2026, 10, 20)) == [
        date(2026, 10, 3),
        date(2026, 10, 10),
        date(2026, 10, 17),
    ]


def test_quarterly_and_yearly_items_count_from_their_first_month() -> None:
    water = item(frequency=Frequency.QUARTERLY, day=15, start=date(2026, 2, 1))
    assert due_dates(water, date(2026, 1, 1), date(2026, 12, 31)) == [
        date(2026, 2, 15),
        date(2026, 5, 15),
        date(2026, 8, 15),
        date(2026, 11, 15),
    ]
    insurance = item(frequency=Frequency.YEARLY, day=10, start=date(2025, 3, 1))
    assert due_dates(insurance, date(2026, 1, 1), date(2027, 12, 31)) == [
        date(2026, 3, 10),
        date(2027, 3, 10),
    ]


def test_nothing_is_due_before_the_start_nor_after_the_end() -> None:
    gym = item(day=5, start=date(2026, 3, 10), end=date(2026, 6, 30))
    assert due_dates(gym, date(2026, 1, 1), date(2026, 12, 31)) == [
        date(2026, 4, 5),
        date(2026, 5, 5),
        date(2026, 6, 5),
    ]


def test_a_paused_item_has_no_due_dates() -> None:
    assert due_dates(item(paused=True), date(2026, 1, 1), date(2026, 12, 31)) == []


# Occurrences.


def test_a_transaction_fulfils_an_occurrence_within_tolerance() -> None:
    assert TOLERANCE == 5
    rent = item()
    paid = booked(date(2026, 10, 6), "-960.00")  # 3 days late, 1 % more
    (october,) = occurrences(
        [rent], [paid], date(2026, 10, 1), date(2026, 10, 31), today=date(2026, 10, 13)
    )
    assert october.status is OccurrenceStatus.FULFILLED
    assert october.transaction_id == paid.id


@pytest.mark.parametrize(
    ("day", "amount", "label", "account"),
    [
        (date(2026, 10, 9), "-950.00", "LOYER", ACCOUNT),  # 6 days late
        (date(2026, 10, 3), "-1046.00", "LOYER", ACCOUNT),  # 10.1 % more
        (date(2026, 10, 3), "950.00", "LOYER", ACCOUNT),  # a refund, not the rent
        (date(2026, 10, 3), "-950.00", "EDF", ACCOUNT),
        (date(2026, 10, 3), "-950.00", "LOYER", uuid4()),
    ],
)
def test_other_transactions_do_not_fulfil_it(
    day: date, amount: str, label: str, account: UUID
) -> None:
    (october,) = occurrences(
        [item()],
        [booked(day, amount, label, account)],
        date(2026, 10, 1),
        date(2026, 10, 31),
        today=date(2026, 10, 20),
    )
    assert october.status is OccurrenceStatus.LATE
    assert october.transaction_id is None


def test_the_label_matches_like_a_rule() -> None:
    (october,) = occurrences(
        [item(label="loyer")],
        [booked(date(2026, 10, 3), "-950.00", "Prlv Loyer Sci")],
        date(2026, 10, 1),
        date(2026, 10, 31),
        today=date(2026, 10, 3),
    )
    assert october.status is OccurrenceStatus.FULFILLED


def test_an_occurrence_is_upcoming_then_late_five_days_after_its_date() -> None:
    rent = item()

    def status(today: date) -> OccurrenceStatus:
        (o,) = occurrences([rent], [], date(2026, 10, 1), date(2026, 10, 31), today=today)
        return o.status

    assert status(date(2026, 10, 1)) is OccurrenceStatus.UPCOMING
    assert status(date(2026, 10, 8)) is OccurrenceStatus.UPCOMING
    assert status(date(2026, 10, 9)) is OccurrenceStatus.LATE


def test_a_skipped_occurrence_is_not_expected() -> None:
    rent = item()
    (october,) = occurrences(
        [rent],
        [],
        date(2026, 10, 1),
        date(2026, 10, 31),
        today=date(2026, 10, 20),
        skipped={(rent.id, date(2026, 10, 3))},
    )
    assert october.status is OccurrenceStatus.SKIPPED


def test_each_transaction_fulfils_one_occurrence_the_closest() -> None:
    coffee = item(
        label="CAFE", amount=D("-2.00"), frequency=Frequency.WEEKLY, day=0, start=date(2026, 10, 1)
    )
    one = booked(date(2026, 10, 6), "-2.00", "CAFE")
    result = occurrences(
        [coffee], [one], date(2026, 10, 1), date(2026, 10, 14), today=date(2026, 10, 14)
    )
    assert [(o.due, o.status) for o in result] == [
        (date(2026, 10, 5), OccurrenceStatus.FULFILLED),
        (date(2026, 10, 12), OccurrenceStatus.UPCOMING),
    ]


def test_an_estimated_amount_is_the_average_of_the_last_three() -> None:
    assert estimate([D("-200.00"), D("-80.00"), D("-90.00"), D("-85.00")]) == D("-85.00")
    assert estimate([D("-10.00"), D("-10.01")]) == D("-10.01")  # half up, in cents
    assert estimate([]) is None


def test_an_estimated_item_expects_its_recent_average() -> None:
    edf = item(label="EDF", amount=D("-80.00"), estimated=True, day=5)
    history = [
        booked(date(2026, m, 5), a, "EDF") for m, a in [(7, "-80.00"), (8, "-90.00"), (9, "-85.00")]
    ]
    result = occurrences(
        [edf], history, date(2026, 7, 1), date(2026, 10, 31), today=date(2026, 10, 1)
    )
    assert result[-1].expected == D("-85.00")


def test_enter_it_dates_the_entry_on_the_expected_day_or_today_if_that_is_later() -> None:
    today = date(2026, 10, 13)
    assert entry_date(date(2026, 10, 9), today) == date(2026, 10, 9)
    assert entry_date(date(2026, 10, 28), today) == today


def test_upcoming_lists_the_open_occurrences_to_the_month_end_late_ones_first() -> None:
    assert LATE_WINDOW == 31
    rent, salary, gym = item(), item(label="SALAIRE", amount=D("2500.00"), day=28), item(day=12)
    today = date(2026, 10, 13)

    def occ(i: Item, due: date, status: OccurrenceStatus) -> Occurrence:
        return Occurrence(i.id, due, i.amount, status)

    old = occ(rent, date(2026, 9, 3), OccurrenceStatus.LATE)  # 40 days ago: dropped
    late = occ(rent, date(2026, 10, 3), OccurrenceStatus.LATE)
    soon = occ(gym, date(2026, 10, 12), OccurrenceStatus.UPCOMING)
    paid = occ(gym, date(2026, 9, 12), OccurrenceStatus.FULFILLED)
    pay = occ(salary, date(2026, 10, 28), OccurrenceStatus.UPCOMING)
    next_month = occ(rent, date(2026, 11, 3), OccurrenceStatus.UPCOMING)
    assert upcoming([pay, next_month, soon, paid, late, old], today=today) == [late, soon, pay]


# Projection (invariant §8.16).


def test_the_projected_balance_adds_what_is_still_expected() -> None:
    rent, salary = item(), item(label="SALAIRE", amount=D("2500.00"), day=28)
    paid = booked(date(2026, 10, 3), "-950.00")
    result = occurrences(
        [rent, salary], [paid], date(2026, 10, 1), date(2026, 10, 31), today=date(2026, 10, 13)
    )
    assert projected_balance(D("1200.00"), result) == D("3700.00")


fixed_amounts = st.sampled_from(["-950.00", "-15.99", "2500.00", "-42.10"])


@given(
    st.lists(st.tuples(st.integers(1, 31), fixed_amounts), max_size=6),
    st.lists(st.tuples(st.integers(1, 31), fixed_amounts), max_size=10),
    st.integers(1, 31),
)
def test_matches_are_one_to_one_and_the_projection_adds_the_rest(
    plans: list[tuple[int, str]], paid: list[tuple[int, str]], today: int
) -> None:
    items = [item(label=f"ITEM {a}", amount=D(a), day=d) for d, a in plans]
    txns = [booked(date(2026, 10, d), a, f"ITEM {a}") for d, a in paid]
    result = occurrences(
        items, txns, date(2026, 10, 1), date(2026, 10, 31), today=date(2026, 10, today)
    )
    used = [o.transaction_id for o in result if o.transaction_id]
    assert len(used) == len(set(used))
    by_id = {t.id: t for t in txns}
    for o in result:
        if o.transaction_id:
            t = by_id[o.transaction_id]
            assert abs(t.booked_on - o.due) <= timedelta(days=TOLERANCE)
    open_ = [o for o in result if o.status in (OccurrenceStatus.UPCOMING, OccurrenceStatus.LATE)]
    assert projected_balance(D(0), result) == sum((o.expected for o in open_), D(0))


# Detection.


def test_three_monthly_payments_of_the_same_label_are_suggested() -> None:
    history = [
        booked(date(2026, m, d), "-15.99", "NETFLIX") for m, d in [(7, 4), (8, 5), (9, 3), (10, 4)]
    ]
    (netflix,) = detect(history, today=date(2026, 10, 13))
    assert (netflix.label, netflix.frequency, netflix.day) == ("NETFLIX", Frequency.MONTHLY, 4)
    assert (netflix.amount, netflix.estimated) == (D("-15.99"), False)
    assert netflix.account_id == ACCOUNT
    assert len(netflix.transaction_ids) == 4


def test_a_varying_amount_is_suggested_as_an_estimate() -> None:
    history = [
        booked(date(2026, m, 5), a, "EDF")
        for m, a in [(8, "-80.00"), (9, "-86.00"), (10, "-83.00")]
    ]
    (edf,) = detect(history, today=date(2026, 10, 13))
    assert (edf.amount, edf.estimated) == (D("-83.00"), True)


def test_a_weekly_series_is_suggested_on_its_weekday() -> None:
    history = [booked(date(2026, 9, 19) + timedelta(weeks=w), "-30.00", "MARCHE") for w in range(4)]
    (market,) = detect(history, today=date(2026, 10, 13))
    assert (market.frequency, market.day) == (Frequency.WEEKLY, 5)


@pytest.mark.parametrize(
    "days",
    [
        [(7, 4), (8, 5)],  # two are not a series
        [(7, 4), (8, 20), (9, 3)],  # irregular
        [(1, 4), (2, 4), (3, 4)],  # older than 6 months
    ],
)
def test_no_suggestion_without_a_regular_recent_series(days: list[tuple[int, int]]) -> None:
    history = [booked(date(2026, m, d), "-15.99", "NETFLIX") for m, d in days]
    assert detect(history, today=date(2026, 10, 13)) == []


def test_amounts_varying_by_ten_percent_or_more_are_not_a_series() -> None:
    history = [
        booked(date(2026, m, 5), a, "COURSES")
        for m, a in [(8, "-80.00"), (9, "-95.00"), (10, "-83.00")]
    ]
    assert detect(history, today=date(2026, 10, 13)) == []


def test_dismissed_and_known_series_are_not_suggested_again() -> None:
    history = [booked(date(2026, m, 4), "-15.99", "NETFLIX") for m in (7, 8, 9)]
    assert detect(history, today=date(2026, 10, 13), dismissed={(ACCOUNT, "NETFLIX")}) == []
    assert detect(history, today=date(2026, 10, 13), known={h.id for h in history}) == []
