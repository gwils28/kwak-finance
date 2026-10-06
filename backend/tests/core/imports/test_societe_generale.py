from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from kwak_core.imports import Balance, detect_format, parse_statement
from kwak_core.imports.societe_generale import SG_CHECKING, SG_SAVINGS

FIXTURES = Path(__file__).parents[2] / "fixtures" / "import" / "societe_generale"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_formats_are_detected_from_the_header() -> None:
    assert detect_format(_read("checking.csv")) is SG_CHECKING
    assert detect_format(_read("savings.csv")) is SG_SAVINGS
    assert detect_format(b"date,amount\n2026-01-01,1\n") is None
    assert detect_format(b"") is None


def test_checking_export() -> None:
    statement = parse_statement(SG_CHECKING, _read("checking.csv"))

    assert statement.errors == []
    assert len(statement.rows) == 14
    first = statement.rows[0]
    assert first.line == 4
    assert first.booked_on == date(2026, 3, 14)
    assert first.amount == Decimal("-4.20")
    assert first.label == "CARTE X0000 13/03 BOULANGERIE DU PARC 100000000000001IOPD"
    assert statement.balance == Balance(on=date(2026, 3, 14), amount=Decimal("1234.56"))
    assert statement.period == (date(2026, 3, 1), date(2026, 3, 14))


def test_checking_export_keeps_accents_and_credits() -> None:
    rows = parse_statement(SG_CHECKING, _read("checking.csv")).rows
    salary = next(r for r in rows if "SALAIRE" in r.label)
    assert salary.amount == Decimal("2480.15")
    assert any("PHARMACIE DE L'ÉGLISE" in r.label for r in rows)


def test_savings_export() -> None:
    statement = parse_statement(SG_SAVINGS, _read("savings.csv"))

    assert statement.errors == []
    assert [r.amount for r in statement.rows] == [
        Decimal("300.00"),
        Decimal("-1500.00"),
        Decimal("-200.00"),
        Decimal("2000.00"),
        Decimal("-750.50"),
        Decimal("45.67"),
    ]
    assert statement.rows[-1].label == "INTERETS CREDITEURS"
    assert statement.rows[-1].line == 8
    assert statement.balance is None
    assert statement.period == (date(2026, 1, 1), date(2026, 9, 30))


CHECKING_HEAD = (
    "00000000000;01/03/2026;14/03/2026;{count};14/03/2026;10.00 EUR\r\n\r\n"
    "Date de l'opération;Libellé;Détail de l'écriture;Montant de l'opération;Devise\r\n"
)


def _checking(*rows: str, count: int | None = None) -> bytes:
    head = CHECKING_HEAD.format(count=len(rows) if count is None else count)
    return (head + "".join(f"{r}\r\n" for r in rows)).encode("iso-8859-1")


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("32/03/2026;A;A;-1,00;EUR", "date"),
        ("14/03/2026;A;A;-1,0x;EUR", "amount"),
        ("14/03/2026;A;A;-1,00;USD", "currency"),
        ("14/03/2026;A;-1,00;EUR", "5 fields"),
    ],
)
def test_a_bad_row_is_reported_with_its_line_and_the_others_are_kept(
    row: str, message: str
) -> None:
    statement = parse_statement(SG_CHECKING, _checking("14/03/2026;OK;OK;-2,00;EUR", row))

    assert [r.label for r in statement.rows] == ["OK"]
    assert len(statement.errors) == 1
    assert statement.errors[0].line == 5
    assert message in statement.errors[0].message


def test_the_detail_falls_back_to_the_short_label() -> None:
    statement = parse_statement(SG_CHECKING, _checking("14/03/2026;SHORT;   ;-2,00;EUR"))
    assert statement.rows[0].label == "SHORT"


def test_a_row_count_that_disagrees_with_the_summary_is_reported() -> None:
    statement = parse_statement(SG_CHECKING, _checking("14/03/2026;A;A;-2,00;EUR", count=3))
    assert [e.message for e in statement.errors] == [
        "the file announces 3 operations but contains 1"
    ]


def test_a_file_without_the_expected_header_is_rejected() -> None:
    statement = parse_statement(SG_CHECKING, _read("savings.csv"))
    assert statement.rows == []
    assert statement.errors[0].message.startswith("not a Société Générale checking export")
