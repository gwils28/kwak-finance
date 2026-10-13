from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.imports.model import ParsedRow
from kwak_core.imports.reconcile import MATCH_DAYS, Entry, reconcile

D = Decimal
T0 = datetime(2026, 10, 1, tzinfo=UTC)


def row(line: int, day: int, amount: str, label: str = "CB CARREFOUR") -> ParsedRow:
    return ParsedRow(line, date(2026, 10, day), label, D(amount))


def entry(day: int, amount: str, minute: int = 0) -> Entry:
    return Entry(uuid4(), date(2026, 10, day), D(amount), T0 + timedelta(minutes=minute))


def test_a_row_matches_an_entry_with_the_same_amount_within_five_days() -> None:
    assert MATCH_DAYS == 5
    groceries = entry(8, "-52.30")
    result = reconcile([row(1, 10, "-52.30")], [groceries])
    assert result.matches == {1: groceries.id}
    assert result.unmatched == []


def test_the_amount_must_be_exactly_the_same() -> None:
    result = reconcile([row(1, 10, "-52.31")], [entry(10, "-52.30")])
    assert result.matches == {}


def test_six_days_apart_is_too_far() -> None:
    late = entry(4, "-52.30")
    result = reconcile([row(1, 10, "-52.30"), row(2, 3, "-9.00")], [late])
    assert result.matches == {}
    assert result.unmatched == [late]  # within the statement's dates, matched by no row


def test_each_row_takes_the_closest_entry_then_the_earliest_entered() -> None:
    far, near, near_later = entry(6, "-20.00", 0), entry(9, "-20.00", 5), entry(11, "-20.00", 9)
    october = (date(2026, 10, 1), date(2026, 10, 31))
    result = reconcile([row(1, 10, "-20.00")], [far, near_later, near], period=october)
    assert result.matches == {1: near.id}
    assert sorted(e.booked_on for e in result.unmatched) == [date(2026, 10, 6), date(2026, 10, 11)]


def test_two_identical_coffees_match_two_entries_one_for_one() -> None:
    first, second = entry(5, "-2.10", 0), entry(5, "-2.10", 1)
    result = reconcile([row(1, 6, "-2.10"), row(2, 6, "-2.10")], [second, first])
    assert result.matches == {1: first.id, 2: second.id}


def test_a_match_the_user_undid_is_not_made_again() -> None:
    groceries = entry(10, "-52.30")
    result = reconcile([row(1, 10, "-52.30")], [groceries], refused={(1, groceries.id)})
    assert result.matches == {}
    assert result.unmatched == [groceries]


def test_entries_outside_the_statement_dates_are_not_reported() -> None:
    before = entry(1, "-5.00")
    result = reconcile([row(1, 10, "-52.30"), row(2, 20, "-8.00")], [before])
    assert result.unmatched == []


# Invariant §8.17: every bank row ends up as one transaction, the entries that match none stay.
amounts = st.sampled_from(["-2.10", "-9.99", "-52.30", "1200.00", "-850.00"])


@st.composite
def statement(draw: st.DrawFn) -> tuple[list[ParsedRow], list[Entry]]:
    rows = [
        ParsedRow(i + 1, date(2026, 10, draw(st.integers(1, 28))), "X", D(draw(amounts)))
        for i in range(draw(st.integers(0, 12)))
    ]
    entries = []
    for i, r in enumerate(rows):
        if draw(st.booleans()):  # entered by hand, a few days off
            shift = timedelta(days=draw(st.integers(-MATCH_DAYS, MATCH_DAYS)))
            entries.append(Entry(uuid4(), r.booked_on + shift, r.amount, T0 + timedelta(i)))
    extra = draw(st.lists(st.tuples(st.integers(1, 28), amounts), max_size=4))
    entries += [Entry(uuid4(), date(2026, 10, d), D(a), T0) for d, a in extra]
    return rows, entries


@given(statement())
def test_every_row_becomes_one_transaction_and_unmatched_entries_stay(
    data: tuple[list[ParsedRow], list[Entry]],
) -> None:
    rows, entries = data
    result = reconcile(rows, entries)
    by_id: dict[UUID, Entry] = {e.id: e for e in entries}
    by_line = {r.line: r for r in rows}

    assert len(set(result.matches.values())) == len(result.matches)  # one-to-one
    for line, entry_id in result.matches.items():
        r, e = by_line[line], by_id[entry_id]
        assert r.amount == e.amount
        assert abs(r.booked_on - e.booked_on) <= timedelta(days=MATCH_DAYS)
    matched = set(result.matches.values())
    left = [e for e in entries if e.id not in matched]
    assert set(result.unmatched) <= set(left)
    # After the import: one transaction per row, plus the entries no row took.
    balance = sum((r.amount for r in rows), D(0)) + sum((e.amount for e in left), D(0))
    assert balance == sum((e.amount for e in entries), D(0)) + sum(
        (r.amount for r in rows if r.line not in result.matches), D(0)
    )
    # A row that can still take a free entry was not left unmatched.
    for r in rows:
        if r.line not in result.matches:
            assert not any(
                e.amount == r.amount
                and abs(e.booked_on - r.booked_on) <= timedelta(days=MATCH_DAYS)
                for e in left
            )
