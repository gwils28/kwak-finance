"""The Dash pages' strings (the one exception to `frontend/src/i18n/`, CLAUDE.md): `EN` and
`FR` hold the same keys, which a test checks. Amounts and months follow the language."""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from kwak_core.budget import Month

type Language = Literal["en", "fr"]

EN: Mapping[str, str] = {
    "title": "Projection",
    "intro": (
        "Where the wealth could be in 1 to 40 years, from what it holds today, what the "
        "household saves each month and what each kind of holding may earn: a fan of outcomes "
        "rather than one line, since returns are uncertain."
    ),
    "scope": "Scope",
    "scope_household": "Household",
    "scope_mine": "Only mine",
    "scope_joint": "Joint",
    "horizon": "Horizon",
    "years": "{n} years",
    "euros": "Amounts",
    "euros_today": "Today's euros",
    "euros_current": "Current euros",
    "median": "Median",
    "band_25_75": "25–75 % of outcomes",
    "band_10_90": "10–90 % of outcomes",
    "net_worth": "Net worth",
    "caption": (
        "An estimate from the assumptions below, not a forecast and not advice. One outcome in "
        "five lies outside the 10–90 % band, and the real spread is wider (see the limits). The "
        "median line is not one path: no single outcome follows it. Past returns do not "
        "guarantee future ones."
    ),
    "savings_measured": "Monthly savings: {amount}, the goals' capacity measured over {n} months.",
    "savings_set": "Monthly savings: {amount}, the goals' capacity set by hand.",
    "savings_short": (
        "Fewer than 12 months miss the year's irregular costs (taxes, insurance, holidays)."
    ),
    "savings_household": (
        "In this scope it is still the whole household's capacity, which may be too much."
    ),
    "engine": "{paths} outcomes, seed {seed}, engine version {version}.",
    "no_wealth": "No wealth line in this scope: enter the wealth first.",
    "no_allocation": (
        "No category to save into: add Savings accounts or Current accounts to the wealth."
    ),
    "not_signed_in": "Sign in to Kwak Finance to see this page.",
    "not_found": "No such page.",
}

FR: Mapping[str, str] = {
    "title": "Projection",
    "intro": (
        "Où pourrait en être le patrimoine dans 1 à 40 ans, d'après ce qu'il contient "
        "aujourd'hui, ce que le foyer épargne chaque mois et ce que chaque type de placement "
        "peut rapporter : un éventail de résultats plutôt qu'une ligne, car les rendements sont "
        "incertains."
    ),
    "scope": "Périmètre",
    "scope_household": "Foyer",
    "scope_mine": "Seulement les miens",
    "scope_joint": "En commun",
    "horizon": "Horizon",
    "years": "{n} ans",
    "euros": "Montants",
    "euros_today": "Euros d'aujourd'hui",
    "euros_current": "Euros courants",
    "median": "Médiane",
    "band_25_75": "25–75 % des résultats",
    "band_10_90": "10–90 % des résultats",
    "net_worth": "Patrimoine net",
    "caption": (
        "Une estimation tirée des hypothèses ci-dessous, ni une prévision ni un conseil. Un "
        "résultat sur cinq sort de la bande 10–90 %, et l'écart réel est plus large (voir les "
        "limites). La médiane n'est pas un chemin : aucun résultat ne la suit. Les rendements "
        "passés ne présagent pas des rendements futurs."
    ),
    "savings_measured": (
        "Épargne mensuelle : {amount}, la capacité des objectifs mesurée sur {n} mois."
    ),
    "savings_set": "Épargne mensuelle : {amount}, la capacité des objectifs saisie à la main.",
    "savings_short": (
        "Moins de 12 mois oublient les dépenses irrégulières de l'année (impôts, assurances, "
        "vacances)."
    ),
    "savings_household": (
        "Dans ce périmètre, c'est toujours la capacité de tout le foyer, peut-être trop élevée."
    ),
    "engine": "{paths} résultats, graine {seed}, version du moteur {version}.",
    "no_wealth": "Aucune ligne de patrimoine dans ce périmètre : saisissez d'abord le patrimoine.",
    "no_allocation": (
        "Aucune catégorie où épargner : ajoutez des Livrets ou des Comptes courants au patrimoine."
    ),
    "not_signed_in": "Connectez-vous à Kwak Finance pour voir cette page.",
    "not_found": "Cette page n'existe pas.",
}

MESSAGES: Mapping[Language, Mapping[str, str]] = {"en": EN, "fr": FR}

MONTHS: Mapping[Language, tuple[str, ...]] = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "fr": (
        "janv.",
        "févr.",
        "mars",
        "avr.",
        "mai",
        "juin",
        "juil.",
        "août",
        "sept.",
        "oct.",
        "nov.",
        "déc.",
    ),
}

HUNDRED = Decimal(100)


def language(value: str | None) -> Language:
    return "fr" if value == "fr" else "en"


def t(lang: Language, key: str, **values: object) -> str:
    return MESSAGES[lang][key].format(**values)


def number(value: int, lang: Language) -> str:
    """Grouped by thousands: 12,300 or 12 300 (a narrow no-break space, as the app's)."""
    grouped = f"{value:,}"
    return grouped.replace(",", "\u202f") if lang == "fr" else grouped


def money(amount: Decimal, lang: Language) -> str:
    """To the nearest €100, as the projection's amounts (F-SIM-5)."""
    rounded = int((amount / HUNDRED).quantize(Decimal(1), rounding=ROUND_HALF_UP) * HUNDRED)
    sign = "-" if rounded < 0 else ""
    digits = number(abs(rounded), lang)
    return f"{sign}{digits}\u00a0€" if lang == "fr" else f"{sign}€{digits}"


def month(m: Month, lang: Language) -> str:
    return f"{MONTHS[lang][m.month - 1]} {m.year}"
