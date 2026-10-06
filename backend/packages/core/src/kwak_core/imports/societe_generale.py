"""Société Générale CSV exports (ISO-8859-1, `;`-separated, newest operation first).

Two layouts exist. Checking accounts:

    00000000000;01/03/2026;14/03/2026;14;14/03/2026;1234.56 EUR  <- account, period, count,
                                                                 balance, then an empty line
    Date de l'opération;Libellé;Détail de l'écriture;Montant de l'opération;Devise
    14/03/2026;CARTE X0000 13/03 ;CARTE X0000 13/03 SHOP 1000IOPD;-4,20;EUR

Savings accounts (Livret A, LDDS), a newer layout with a trailing `;`:

    ="0000000000000000";01/01/2026;30/09/2026;
    date_comptabilisation;libellé_complet_operation;montant_operation;devise;
    12/09/2026;VIR RECU 0000000000011;300,00;EUR;
"""

from datetime import date, datetime

from kwak_core.imports.model import Balance, BankFormat, ParsedRow, RowError, Statement
from kwak_core.money import parse_amount

CHECKING_HEADER = "Date de l'opération;Libellé;Détail de l'écriture;Montant de l'opération;Devise"
SAVINGS_HEADER = "date_comptabilisation;libellé_complet_operation;montant_operation;devise;"


def _date(text: str) -> date:
    try:
        return datetime.strptime(text.strip(), "%d/%m/%Y").date()  # noqa: DTZ007 (a calendar date)
    except ValueError:
        raise ValueError(f"invalid date {text!r}, expected DD/MM/YYYY") from None


def _row(line: int, date_text: str, label: str, amount_text: str, currency: str) -> ParsedRow:
    if currency.strip() != "EUR":
        raise ValueError(
            f"unsupported currency {currency.strip()!r}: only EUR accounts are handled"
        )
    try:
        amount = parse_amount(amount_text, decimal_separator=",")
    except ValueError:
        raise ValueError(f"invalid amount {amount_text!r}") from None
    return ParsedRow(line=line, booked_on=_date(date_text), label=label.strip(), amount=amount)


def _parse_rows(
    lines: list[str], start: int, fields: int, pick: tuple[int, int, int, int], statement: Statement
) -> None:
    """Rows from `start` (0-based index); `pick` gives the date, label, amount, currency fields."""
    for index in range(start, len(lines)):
        text = lines[index]
        if not text.strip():
            continue
        line = index + 1
        parts = text.split(";")
        if len(parts) != fields:
            statement.errors.append(RowError(line, f"expected {fields} fields, found {len(parts)}"))
            continue
        d, label, amount, currency = (parts[i] for i in pick)
        try:
            statement.rows.append(_row(line, d, label, amount, currency))
        except ValueError as exc:
            statement.errors.append(RowError(line, str(exc)))


def _parse_checking(lines: list[str]) -> Statement:
    statement = Statement()
    if len(lines) < 3 or lines[2] != CHECKING_HEADER:
        statement.errors.append(RowError(0, "not a Société Générale checking export"))
        return statement
    summary = lines[0].split(";")
    announced: int | None = None
    try:
        statement.period = (_date(summary[1]), _date(summary[2]))
        announced = int(summary[3])
        statement.balance = Balance(
            on=_date(summary[4]), amount=parse_amount(summary[5], decimal_separator=".")
        )
    except (IndexError, ValueError):
        statement.errors.append(RowError(1, "unreadable summary line"))
    # The detail field is the full label; the short one is its first 18 characters.
    _parse_rows(lines, 3, 5, (0, 2, 3, 4), statement)
    for i, row in enumerate(statement.rows):
        if not row.label:
            short = lines[row.line - 1].split(";")[1].strip()
            statement.rows[i] = ParsedRow(row.line, row.booked_on, short, row.amount)
    found = len(statement.rows) + sum(1 for e in statement.errors if e.line > 3)
    if announced is not None and announced != found:
        statement.errors.append(
            RowError(0, f"the file announces {announced} operations but contains {found}")
        )
    return statement


def _parse_savings(lines: list[str]) -> Statement:
    statement = Statement()
    if len(lines) < 2 or lines[1] != SAVINGS_HEADER:
        statement.errors.append(RowError(0, "not a Société Générale savings export"))
        return statement
    summary = lines[0].split(";")
    try:
        statement.period = (_date(summary[1]), _date(summary[2]))
    except (IndexError, ValueError):
        statement.errors.append(RowError(1, "unreadable summary line"))
    # Every line ends with ";", hence an empty 5th field.
    _parse_rows(lines, 2, 5, (0, 1, 2, 3), statement)
    return statement


SG_CHECKING = BankFormat(
    key="societe_generale_checking",
    label="Société Générale — checking account (CSV)",
    matches=lambda lines: len(lines) > 2 and lines[2] == CHECKING_HEADER,
    parse=_parse_checking,
)

SG_SAVINGS = BankFormat(
    key="societe_generale_savings",
    label="Société Générale — savings account (CSV)",
    matches=lambda lines: len(lines) > 1 and lines[1] == SAVINGS_HEADER,
    parse=_parse_savings,
)
