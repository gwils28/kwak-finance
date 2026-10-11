from datetime import date
from decimal import Decimal
from pathlib import Path

from kwak_core.imports import detect_format, parse_statement
from kwak_core.imports.helios import HELIOS
from kwak_core.imports.societe_generale import SG_CHECKING

FIXTURES = Path(__file__).parents[2] / "fixtures" / "import"
STATEMENT = (FIXTURES / "helios" / "statement.csv").read_bytes()


def test_a_helios_export_is_detected_and_sg_ones_still_are() -> None:
    assert detect_format(STATEMENT) is HELIOS
    sg = (FIXTURES / "societe_generale" / "checking.csv").read_bytes()
    assert detect_format(sg) is SG_CHECKING


def test_rows_keep_their_date_amount_and_accents() -> None:
    statement = parse_statement(HELIOS, STATEMENT)

    assert statement.errors == []
    assert len(statement.rows) == 8
    first = statement.rows[0]
    assert (first.line, first.booked_on, first.amount) == (2, date(2026, 9, 28), Decimal("-4.20"))
    assert first.label == "Boulangerie du Parc"
    assert statement.rows[3].label == "Électricité Exemple"
    assert statement.rows[6].amount == Decimal("1300.55")
    assert statement.period is None
    assert statement.balance is None


def test_the_label_adds_the_wording_when_it_says_more_than_the_counterparty() -> None:
    rows = parse_statement(HELIOS, STATEMENT).rows
    assert rows[4].label == "Agence Immobilière Exemple · Loyer septembre"
    assert rows[5].label == "A. Exemple · Virement mensuel"


def test_an_operation_not_executed_yet_is_reported_and_left_out() -> None:
    pending = STATEMENT.replace("exécuté; Santé".encode(), "en attente; Santé".encode())
    statement = parse_statement(HELIOS, pending)
    assert len(statement.rows) == 7
    assert [(e.line, e.message) for e in statement.errors] == [
        (9, "operation not executed yet ('en attente'): import it once it is")
    ]


def test_a_bad_row_is_reported_with_its_line() -> None:
    broken = STATEMENT.replace(b"-86.35", b"-86,35").replace(b"25/09/2026", b"2026-09-25")
    errors = parse_statement(HELIOS, broken).errors
    assert [(e.line, e.message) for e in errors] == [
        (3, "invalid amount '-86,35'"),
        (4, "invalid date '2026-09-25', expected DD/MM/YYYY"),
    ]
