from datetime import UTC, date, datetime
from uuid import uuid4

from kwak_core.labels import Use, normalise, remembered_category, suggest

TODAY = date(2026, 10, 21)
GROCERIES, HOME, TRANSPORT = uuid4(), uuid4(), uuid4()


def at(day: int, month: int = 10, year: int = 2026) -> datetime:
    return datetime(year, month, day, 12, tzinfo=UTC)


def use(label: str, category: object, entered: datetime) -> Use:
    return Use(label, category, entered.date(), entered)  # type: ignore[arg-type]


def test_normalise_ignores_case_accents_and_spaces() -> None:
    assert normalise("  Café  de la GARE ") == normalise("cafe de la gare") == "cafe de la gare"


def test_a_known_label_gives_the_category_chosen_last() -> None:
    uses = [
        use("Carrefour", GROCERIES, at(3)),
        use("carrefour", HOME, at(10)),
        use("SNCF", TRANSPORT, at(12)),
    ]
    assert remembered_category("CARREFOUR ", uses) == HOME
    assert remembered_category("Leclerc", uses) is None


def test_latest_is_by_entry_time_not_by_date() -> None:
    late_entry_of_an_old_day = Use("Carrefour", HOME, date(2026, 9, 1), at(15))
    uses = [use("Carrefour", GROCERIES, at(10)), late_entry_of_an_old_day]
    assert remembered_category("carrefour", uses) == HOME


def test_suggestions_start_with_the_text_most_used_over_12_months_first() -> None:
    uses = [
        use("Carrefour", GROCERIES, at(1)),
        use("carrefour", GROCERIES, at(8)),
        use("Carburant", TRANSPORT, at(9)),
        use("Cartes", HOME, at(1, 1, 2025)),  # older than 12 months
        use("Cartes", HOME, at(2, 1, 2025)),
        use("Cartes", HOME, at(3, 1, 2025)),
        use("SNCF", TRANSPORT, at(9)),
    ]
    assert suggest("car", uses, TODAY) == ["carrefour", "Carburant", "Cartes"]


def test_a_tie_goes_to_the_latest_entered_and_the_limit_holds() -> None:
    uses = [use("Pain", GROCERIES, at(1)), use("Pâtes", GROCERIES, at(2))]
    assert suggest("pa", uses, TODAY) == ["Pâtes", "Pain"]
    assert suggest("pa", uses, TODAY, limit=1) == ["Pâtes"]


def test_nothing_typed_suggests_nothing() -> None:
    assert suggest("  ", [use("Pain", GROCERIES, at(1))], TODAY) == []
