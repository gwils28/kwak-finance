"""The quick line (F-ENT-2, invariant §8.21): one spending line typed in any order.

``boulangerie 12,50 hier``: a date (a day word, a weekday or ``dd/mm[/yyyy]``), an amount (the
last number), ``#word`` for the category, and the rest as the label. Every word typed ends up
in exactly one of them.
"""

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from kwak_core.money import quantize
from kwak_core.users import Language

# Day words, each a sequence of words, and how many days before today they mean.
_DAY_WORDS: dict[Language, list[tuple[tuple[str, ...], int]]] = {
    Language.FR: [(("aujourd'hui",), 0), (("hier",), 1), (("avant-hier",), 2)],
    Language.EN: [
        (("the", "day", "before", "yesterday"), 2),
        (("day", "before", "yesterday"), 2),
        (("today",), 0),
        (("yesterday",), 1),
    ],
}
_WEEKDAYS = {
    Language.FR: ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    Language.EN: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
}
_AHEAD_DAYS = 31
_DATE = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?")
_AMOUNT = re.compile(r"€?([+-]?)€?(\d+)(?:[.,](\d{1,2}))?€?")


@dataclass(frozen=True)
class QuickLine:
    day: date | None
    """None: no date typed, the grid's own default applies (F-ENT-1)."""
    amount: Decimal | None
    """As typed: positive is spent or put aside, negative is taken back from savings."""
    category_word: str | None
    """The word after ``#``, to match with :func:`match_category`."""
    label: str
    date_words: tuple[str, ...] = ()
    amount_words: tuple[str, ...] = ()
    category_words: tuple[str, ...] = ()


def fold(text: str) -> str:
    """Case and accents ignored."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _numeric_date(word: str, today: date) -> date | None:
    found = _DATE.fullmatch(word)
    if not found:
        return None
    day, month, year = int(found[1]), int(found[2]), found[3]
    years = [int(year)] if year else [today.year - 1, today.year, today.year + 1]
    candidates = []
    for y in years:
        try:
            candidates.append(date(y, month, day))
        except ValueError:
            continue
    if year:
        return candidates[0] if candidates else None
    # Without a year: the latest such date at most a month ahead (a fixed expense entered early).
    horizon = today + timedelta(days=_AHEAD_DAYS)
    return max((d for d in candidates if d <= horizon), default=None)


def _find_date(words: list[str], today: date, language: Language) -> tuple[date, int, int] | None:
    """The first date in `words`: (day, first index, number of words)."""
    folded = [fold(w) for w in words]
    for i, word in enumerate(folded):
        for phrase, days_ago in _DAY_WORDS[language]:
            if tuple(folded[i : i + len(phrase)]) == phrase:
                return today - timedelta(days=days_ago), i, len(phrase)
        if word in _WEEKDAYS[language]:
            back = (today.weekday() - _WEEKDAYS[language].index(word)) % 7
            return today - timedelta(days=back), i, 1
        numeric = _numeric_date(word, today)
        if numeric is not None:
            return numeric, i, 1
    return None


def _amount(word: str) -> Decimal | None:
    found = _AMOUNT.fullmatch(word)
    if not found or word.count("€") > 1:
        return None
    value = Decimal(f"{found[2]}.{found[3] or 0}")
    return quantize(-value if found[1] == "-" else value)


def parse(text: str, today: date, language: Language) -> QuickLine:
    words = text.split()
    taken: set[int] = set()

    day = None
    date_words: tuple[str, ...] = ()
    found = _find_date(words, today, language)
    if found:
        day, start, length = found
        date_words = tuple(words[start : start + length])
        taken.update(range(start, start + length))

    amount = None
    amount_words: tuple[str, ...] = ()
    for i in reversed(range(len(words))):
        if i in taken:
            continue
        value = _amount(words[i])
        if value is not None:
            amount, end = value, i + 1
            if end < len(words) and words[end] == "€" and end not in taken:
                end += 1  # "12,50 €"
            amount_words = tuple(words[i:end])
            taken.update(range(i, end))
            break

    category_word = None
    category_words: tuple[str, ...] = ()
    for i, word in enumerate(words):
        if i not in taken and word.startswith("#") and len(word) > 1:
            category_word, category_words = word[1:], (word,)
            taken.add(i)
            break

    label = " ".join(w for i, w in enumerate(words) if i not in taken)
    return QuickLine(day, amount, category_word, label, date_words, amount_words, category_words)


def match_category(word: str, names: Mapping[UUID, str]) -> UUID | None:
    """The one category whose name starts with `word` (case and accents ignored), if only one."""
    wanted = fold(word)
    found = [category for category, name in names.items() if fold(name).startswith(wanted)]
    return found[0] if len(found) == 1 else None
