"""Helios CSV exports (UTF-8 with a BOM, `; `-separated, in no particular order).

    Effectué le; Compte émetteur; Libellé; Type; Catégorie; Sous-catégorie; Montant; Note
    28/09/2026; Boulangerie du Parc; Boulangerie du Parc;  exécuté; Alimentation & …; -4.2; null

"Compte émetteur" is the counterparty, "Libellé" the wording (often the same, sometimes
empty). Helios' own categories are ignored: Kwak Finance's rules categorise. No period nor
balance is given.
"""

from datetime import date, datetime

from kwak_core.imports.model import BankFormat, ParsedRow, RowError, Statement
from kwak_core.money import parse_amount

HEADER = [
    "Effectué le",
    "Compte émetteur",
    "Libellé",
    "Type",
    "Catégorie",
    "Sous-catégorie",
    "Montant",
    "Note",
]
EXECUTED = "exécuté"


def _fields(line: str) -> list[str]:
    return [part.strip() for part in line.split(";")]


def _date(text: str) -> date:
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()  # noqa: DTZ007 (a calendar date)
    except ValueError:
        raise ValueError(f"invalid date {text!r}, expected DD/MM/YYYY") from None


def _label(counterparty: str, wording: str) -> str:
    if not wording or wording == counterparty:
        return counterparty
    return f"{counterparty} · {wording}" if counterparty else wording


def _row(line: int, fields: list[str]) -> ParsedRow:
    booked, counterparty, wording, kind, _category, _subcategory, amount_text, _note = fields
    if kind != EXECUTED:
        raise ValueError(f"operation not executed yet ({kind!r}): import it once it is")
    booked_on = _date(booked)
    try:
        amount = parse_amount(amount_text, decimal_separator=".")
    except ValueError:
        raise ValueError(f"invalid amount {amount_text!r}") from None
    return ParsedRow(line, booked_on, _label(counterparty, wording), amount)


def _parse(lines: list[str]) -> Statement:
    statement = Statement()
    if not lines or _fields(lines[0]) != HEADER:
        statement.errors.append(RowError(0, "not a Helios export"))
        return statement
    for index, text in enumerate(lines[1:], start=2):
        if not text.strip():
            continue
        fields = _fields(text)
        if len(fields) != len(HEADER):
            statement.errors.append(
                RowError(index, f"expected {len(HEADER)} fields, found {len(fields)}")
            )
            continue
        try:
            statement.rows.append(_row(index, fields))
        except ValueError as exc:
            statement.errors.append(RowError(index, str(exc)))
    return statement


HELIOS = BankFormat(
    key="helios",
    label="Helios (CSV)",
    matches=lambda lines: bool(lines) and _fields(lines[0]) == HEADER,
    parse=_parse,
    encoding="utf-8-sig",
)
