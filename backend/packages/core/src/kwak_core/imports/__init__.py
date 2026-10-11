"""Bank file parsing and deduplication (pure: bytes in, rows out)."""

import re

from kwak_core.imports.dedup import ImportPlan, fingerprint_rows, normalize_label, plan_import
from kwak_core.imports.helios import HELIOS
from kwak_core.imports.model import Balance, BankFormat, ParsedRow, RowError, Statement
from kwak_core.imports.societe_generale import SG_CHECKING, SG_SAVINGS

FORMATS: tuple[BankFormat, ...] = (SG_CHECKING, SG_SAVINGS, HELIOS)


def _lines(data: bytes, encoding: str) -> list[str]:
    # Not str.splitlines(): it also breaks on \x85 and other controls a label may contain.
    lines = re.split(r"\r?\n", data.decode(encoding))
    return lines[:-1] if lines and lines[-1] == "" else lines


def _matches(bank_format: BankFormat, data: bytes) -> bool:
    try:
        return bank_format.matches(_lines(data, bank_format.encoding))
    except UnicodeDecodeError:  # another bank's encoding
        return False


def detect_format(data: bytes) -> BankFormat | None:
    return next((f for f in FORMATS if _matches(f, data)), None)


def parse_statement(bank_format: BankFormat, data: bytes) -> Statement:
    return bank_format.parse(_lines(data, bank_format.encoding))


__all__ = [
    "FORMATS",
    "Balance",
    "BankFormat",
    "ImportPlan",
    "ParsedRow",
    "RowError",
    "Statement",
    "detect_format",
    "fingerprint_rows",
    "normalize_label",
    "parse_statement",
    "plan_import",
]
