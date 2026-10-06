from datetime import date
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.imports import parse_statement
from kwak_core.imports.societe_generale import CHECKING_HEADER, SG_CHECKING

# Characters a SG label can hold: ISO-8859-1 printable, never the ";" separator.
label_text = (
    st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=255, exclude_characters=";\x7f"),
        min_size=1,
        max_size=60,
    )
    .map(str.strip)
    .filter(bool)
)
cents = st.integers(min_value=-(10**9), max_value=10**9).map(lambda c: Decimal(c) / 100)
operations = st.lists(
    st.tuples(st.dates(date(2000, 1, 1), date(2099, 12, 31)), label_text, cents), max_size=30
)


def _export(ops: list[tuple[date, str, Decimal]]) -> bytes:
    lines = [
        f"00000000000;01/01/2000;31/12/2099;{len(ops)};31/12/2099;0.00 EUR",
        "",
        CHECKING_HEADER,
    ]
    for day, label, amount in ops:
        text = f"{amount:.2f}".replace(".", ",")
        lines.append(f"{day:%d/%m/%Y};{label[:18]};{label};{text};EUR")
    return ("\r\n".join(lines) + "\r\n").encode("iso-8859-1")


@given(operations)
def test_whatever_sg_writes_is_read_back_exactly(ops: list[tuple[date, str, Decimal]]) -> None:
    statement = parse_statement(SG_CHECKING, _export(ops))

    assert statement.errors == []
    assert [(r.booked_on, r.label, r.amount) for r in statement.rows] == ops
