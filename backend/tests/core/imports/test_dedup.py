from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.imports import ParsedRow, fingerprint_rows, normalize_label, plan_import

D0 = date(2026, 1, 1)


def _row(day: int, amount: str, label: str, line: int = 1) -> ParsedRow:
    return ParsedRow(
        line=line, booked_on=D0 + timedelta(days=day), label=label, amount=Decimal(amount)
    )


rows_strategy = st.lists(
    st.builds(
        _row,
        st.integers(0, 3),
        st.sampled_from(["-1.10", "-4.20", "12.00"]),
        st.sampled_from(["CAFE", "cafe ", "BAKERY", "SALARY"]),
    ),
    max_size=25,
)


def test_labels_are_normalized_for_comparison() -> None:
    assert normalize_label("  Carte  X0000\t13/03 café ") == "CARTE X0000 13/03 CAFÉ"


def test_identical_operations_in_one_file_are_all_kept() -> None:
    coffee = _row(0, "-1.10", "CAFE")
    prints = fingerprint_rows([coffee, coffee])
    assert len(set(prints)) == 2


def test_fingerprints_ignore_label_case_and_spacing() -> None:
    assert fingerprint_rows([_row(0, "-1.10", "Cafe  de la gare")]) == fingerprint_rows(
        [_row(0, "-1.10", "CAFE DE LA GARE")]
    )


@given(rows_strategy)
def test_importing_the_same_file_twice_changes_nothing(rows: list[ParsedRow]) -> None:
    """Invariant §8.4."""
    first = plan_import(rows, existing=set())
    assert len(first.new) == len(rows)
    second = plan_import(rows, existing={p for p, _ in first.new})
    assert second.new == []
    assert len(second.duplicates) == len(rows)


@given(rows_strategy, rows_strategy)
def test_an_overlapping_file_only_adds_what_is_missing(
    old: list[ParsedRow], extra: list[ParsedRow]
) -> None:
    """A later export that repeats the older rows and adds some only imports the additions."""
    stored = {p for p, _ in plan_import(old, existing=set()).new}
    plan = plan_import(old + extra, existing=stored)
    assert len(plan.new) == len(extra)
