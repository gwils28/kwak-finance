from collections import Counter
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.quickline import match_category, parse
from kwak_core.users import Language

D = Decimal
TODAY = date(2026, 10, 21)  # a Wednesday
FR, EN = Language.FR, Language.EN


def test_amount_label_and_day_word_in_any_order() -> None:
    line = parse("boulangerie 12,50 hier", TODAY, FR)
    assert (line.day, line.amount, line.label) == (date(2026, 10, 20), D("12.50"), "boulangerie")
    assert parse("hier 12,50 boulangerie", TODAY, FR) == line


def test_without_a_date_the_day_is_left_to_the_grid() -> None:
    line = parse("sncf 45", TODAY, FR)
    assert (line.day, line.amount, line.label) == (None, D("45.00"), "sncf")


@pytest.mark.parametrize(
    ("text", "language", "day"),
    [
        ("aujourd'hui", FR, date(2026, 10, 21)),
        ("hier", FR, date(2026, 10, 20)),
        ("avant-hier", FR, date(2026, 10, 19)),
        ("today", EN, date(2026, 10, 21)),
        ("yesterday", EN, date(2026, 10, 20)),
        ("the day before yesterday", EN, date(2026, 10, 19)),
        ("lundi", FR, date(2026, 10, 19)),
        ("Mercredi", FR, date(2026, 10, 21)),  # today is a Wednesday
        ("jeudi", FR, date(2026, 10, 15)),  # the latest Thursday up to today
        ("sunday", EN, date(2026, 10, 18)),
        ("13/10", FR, date(2026, 10, 13)),
        ("3/9/2026", FR, date(2026, 9, 3)),
        ("28/12", FR, date(2025, 12, 28)),  # no later than a month ahead
        ("02/11", FR, date(2026, 11, 2)),  # a fixed expense entered ahead
    ],
)
def test_dates(text: str, language: Language, day: date) -> None:
    assert parse(f"pain 2 {text}", TODAY, language).day == day


def test_day_words_follow_the_language() -> None:
    line = parse("hier 3", TODAY, EN)
    assert (line.day, line.label) == (None, "hier")


def test_an_impossible_date_stays_in_the_label() -> None:
    line = parse("31/02 cadeau 20", TODAY, FR)
    assert (line.day, line.label) == (None, "31/02 cadeau")


def test_only_the_first_date_counts() -> None:
    line = parse("hier concert 13/10 30", TODAY, FR)
    assert (line.day, line.label) == (date(2026, 10, 20), "concert 13/10")


@pytest.mark.parametrize(
    ("text", "amount", "label"),
    [
        ("carrefour 87.40", D("87.40"), "carrefour"),
        ("carrefour 87,4", D("87.40"), "carrefour"),
        ("carrefour 87,40€", D("87.40"), "carrefour"),
        ("carrefour 87,40 €", D("87.40"), "carrefour"),
        ("carrefour €87", D("87.00"), "carrefour"),
        ("leclerc 2 15", D("15.00"), "leclerc 2"),  # the last number is the amount
        ("livret -200", D("-200.00"), "livret"),  # a savings withdrawal
        ("cinema", None, "cinema"),
    ],
)
def test_amounts(text: str, amount: Decimal | None, label: str) -> None:
    line = parse(text, TODAY, FR)
    assert (line.amount, line.label) == (amount, label)


def test_a_hash_word_forces_the_category() -> None:
    line = parse("carrefour 87.40 #foyer", TODAY, FR)
    assert (line.category_word, line.label) == ("foyer", "carrefour")


def test_only_the_first_hash_word_counts_and_a_lone_hash_is_label() -> None:
    line = parse("# fête #cad #loisirs 30", TODAY, FR)
    assert (line.category_word, line.label) == ("cad", "# fête #loisirs")


def test_spaces_are_collapsed() -> None:
    assert parse("  la   poste  4 ", TODAY, FR).label == "la poste"


HOME, HEALTH, HOBBIES = uuid4(), uuid4(), uuid4()
NAMES = {HOME: "Foyer", HEALTH: "Santé", HOBBIES: "Loisirs"}


@pytest.mark.parametrize(
    ("word", "expected"),
    [("foyer", HOME), ("FO", HOME), ("sante", HEALTH), ("l", HOBBIES), ("x", None)],
)
def test_a_category_word_matches_the_one_name_it_starts(word: str, expected: object) -> None:
    assert match_category(word, NAMES) == expected


def test_an_ambiguous_category_word_matches_nothing() -> None:
    assert match_category("s", {HOME: "Santé", HEALTH: "Shopping"}) is None


words = st.text(
    alphabet=st.sampled_from("abcé0123456789,.-/#€'"), min_size=1, max_size=8
) | st.sampled_from(["hier", "lundi", "12,50", "#foyer", "€", "13/10", "avant-hier", "-4"])


@given(st.lists(words, max_size=8), st.sampled_from([FR, EN]))
def test_invariant_21_no_word_is_lost(typed: list[str], language: Language) -> None:
    text = " ".join(typed)
    line = parse(text, TODAY, language)
    found = [*line.date_words, *line.amount_words, *line.category_words, *line.label.split()]
    assert Counter(found) == Counter(text.split())
