"""Import fingerprints: re-importing a file, or a later overlapping export, adds nothing twice.

A fingerprint is (date, amount, normalised label, occurrence). The occurrence is the rank of
the row among identical rows of the same file: two real coffees at the same price on the same
day stay two transactions, while importing the same file again matches them one for one.
Fingerprints are unique per account, so the account is not part of them.
"""

import hashlib
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from kwak_core.imports.model import ParsedRow


def normalize_label(label: str) -> str:
    return " ".join(unicodedata.normalize("NFC", label).upper().split())


def fingerprint_rows(rows: list[ParsedRow]) -> list[str]:
    seen: Counter[tuple[str, str, str]] = Counter()
    prints = []
    for row in rows:
        key = (row.booked_on.isoformat(), str(row.amount), normalize_label(row.label))
        occurrence = seen[key]
        seen[key] += 1
        prints.append(hashlib.sha256("|".join((*key, str(occurrence))).encode()).hexdigest())
    return prints


@dataclass
class ImportPlan:
    new: list[tuple[str, ParsedRow]] = field(default_factory=list)
    duplicates: list[tuple[str, ParsedRow]] = field(default_factory=list)


def plan_import(rows: list[ParsedRow], *, existing: set[str]) -> ImportPlan:
    """Split rows into new ones and ones already stored (by fingerprint)."""
    plan = ImportPlan()
    for fp, row in zip(fingerprint_rows(rows), rows, strict=True):
        (plan.duplicates if fp in existing else plan.new).append((fp, row))
    return plan
