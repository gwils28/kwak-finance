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
    "band_25_75": "25–75% of outcomes",
    "band_10_90": "10–90% of outcomes",
    "net_worth": "Net worth",
    "caption": (
        "An estimate from the assumptions below, not a forecast and not advice. One outcome in "
        "five lies outside the 10–90% band, and the real spread is wider (see the limits). The "
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
    "reach_title": "Reaching an amount",
    "amount": "Amount",
    "reach_month": "Month",
    "reach_year": "Year",
    "reach_chance": "In {chance} of the outcomes, net worth is at least {amount} in {month}.",
    "reach_dates": "Half of the outcomes have reached it once by {half}, nine tenths by {ninety}.",
    "not_within": "not within the horizon",
    "after_horizon": "{month} is after the horizon: lengthen it to see the chance then.",
    "amount_missing": "Enter an amount to see the chance of reaching it.",
    "chance_low": "less than 1%",
    "chance_high": "more than 99%",
    "shortfall": (
        "In {share} of the outcomes the liquid holdings run out: the net worth still counts the "
        "home and locked-in funds, but the spending would have to be borrowed."
    ),
    "amount_line": "Amount to reach: {amount}",
    "by_category_title": "Median by category",
    "by_category_note": (
        "Each category's own median: together they need not add up to the median net worth."
    ),
    "debts": "Debts",
    "shortfall_name": "Shortfall",
    "show_data": "Show the data",
    "col_month": "Month",
    "base": "Base",
    "whatifs_title": "What-ifs",
    "whatifs_intro": (
        "Change the savings, the inflation, a category's return or the allocation, for this "
        "visit only: nothing is saved. Every scenario uses the same draws."
    ),
    "whatif": "What-if {n}",
    "whatif_on": "Compare what-if {n}",
    "wi_savings": "Monthly savings (€)",
    "wi_inflation": "Inflation (% a year)",
    "wi_category": "Category",
    "wi_return": "Return (% a year)",
    "wi_volatility": "Volatility (%)",
    "wi_allocation": "Allocation of the savings (%)",
    "wi_allocation_hint": "Leave empty to keep the current one; the shares sum to 100.",
    "wi_invalid": "What-if {n} is not compared: {reason}.",
    "reason_allocation": "the shares of the allocation sum to 100%",
    "reason_assumption": (
        "a return is above −100% and at most +100%, a volatility from 0 to 200%, to 0.1%"
    ),
    "reason_inflation": "the inflation is from −5% to 20%, to 0.1%",
    "reason_savings": "the savings are an amount in euros",
    "compare_title": "Scenarios at the horizon, {month}",
    "col_scenario": "Scenario",
    "col_median": "Median",
    "col_chance": "Chance of {amount} in {month}",
    "assumptions_title": "Assumptions",
    "assumption_line": "{category}: {ret} a year ± {vol}, a median growth of {median} a year",
    "inflation_line": "Inflation: {rate} a year.",
    "allocation_line": "Savings go to: {shares}.",
    "assumptions_where": "The base uses the household's assumptions, set under the charts.",
    "changes_line": "What-if {n}: {changes}.",
    "change_savings": "savings of {amount} a month",
    "change_inflation": "inflation of {rate}",
    "change_assumption": "{category} at {ret} ± {vol}",
    "change_allocation": "allocation {shares}",
    "no_change": "no change",
    "limits_title": "Limits",
    "limit_independent": (
        "Categories are drawn independently, as if stocks, private equity and crypto never fell "
        "together: in a crash they do, so the fan is narrower than reality."
    ),
    "limit_crashes": (
        "Returns follow a lognormal law: no crash beyond it and no total loss (a failed "
        "platform or token)."
    ),
    "limit_inflation": "The inflation is fixed over the whole horizon.",
    "limit_shortfall": "The Shortfall is borrowed at a fixed 8% a year.",
    "limit_tax": (
        "Returns are after a low-cost fund's fees and before tax: the wealth is what the "
        "holdings would be worth, not what selling them would bring after tax on the gains."
    ),
    "limit_ceilings": (
        "Savings accounts' ceilings (€22,950 on a Livret A, €12,000 on an LDDS) are not modelled."
    ),
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
    "band_25_75": "25–75\u202f% des résultats",
    "band_10_90": "10–90\u202f% des résultats",
    "net_worth": "Patrimoine net",
    "caption": (
        "Une estimation tirée des hypothèses ci-dessous, ni une prévision ni un conseil. Un "
        "résultat sur cinq sort de la bande 10–90\u202f%, et l'écart réel est plus large (voir les "
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
    "reach_title": "Atteindre un montant",
    "amount": "Montant",
    "reach_month": "Mois",
    "reach_year": "Année",
    "reach_chance": (
        "Dans {chance} des résultats, le patrimoine net atteint au moins {amount} en {month}."
    ),
    "reach_dates": (
        "La moitié des résultats l'ont atteint une fois en {half}, neuf sur dix en {ninety}."
    ),
    "not_within": "pas dans l'horizon",
    "after_horizon": "{month} est après l'horizon : allongez-le pour voir la chance à ce mois.",
    "amount_missing": "Saisissez un montant pour voir la chance de l'atteindre.",
    "chance_low": "moins de 1\u202f%",
    "chance_high": "plus de 99\u202f%",
    "shortfall": (
        "Dans {share} des résultats, les avoirs liquides s'épuisent : le patrimoine net compte "
        "encore le logement et les fonds bloqués, mais les dépenses devraient être empruntées."
    ),
    "amount_line": "Montant à atteindre : {amount}",
    "by_category_title": "Médiane par catégorie",
    "by_category_note": (
        "La médiane propre à chaque catégorie : ensemble, elles ne font pas forcément la médiane "
        "du patrimoine net."
    ),
    "debts": "Dettes",
    "shortfall_name": "Découvert",
    "show_data": "Afficher les données",
    "col_month": "Mois",
    "base": "Base",
    "whatifs_title": "Et si",
    "whatifs_intro": (
        "Changez l'épargne, l'inflation, le rendement d'une catégorie ou l'allocation, pour "
        "cette visite seulement : rien n'est enregistré. Chaque scénario utilise les mêmes "
        "tirages."
    ),
    "whatif": "Et si {n}",
    "whatif_on": "Comparer l'« et si » {n}",
    "wi_savings": "Épargne mensuelle (€)",
    "wi_inflation": "Inflation (% par an)",
    "wi_category": "Catégorie",
    "wi_return": "Rendement (% par an)",
    "wi_volatility": "Volatilité (%)",
    "wi_allocation": "Allocation de l'épargne (%)",
    "wi_allocation_hint": "Laissez vide pour garder l'actuelle ; les parts font 100 au total.",
    "wi_invalid": "L'« et si » {n} n'est pas comparé : {reason}.",
    "reason_allocation": "les parts de l'allocation font 100\u202f% au total",
    "reason_assumption": (
        "un rendement est au-dessus de −100\u202f% et au plus de +100\u202f%, "
        "une volatilité de 0 à 200\u202f%, à 0,1\u202f% près"
    ),
    "reason_inflation": "l'inflation va de −5\u202f% à 20\u202f%, à 0,1\u202f% près",
    "reason_savings": "l'épargne est un montant en euros",
    "compare_title": "Les scénarios à l'horizon, {month}",
    "col_scenario": "Scénario",
    "col_median": "Médiane",
    "col_chance": "Chance de {amount} en {month}",
    "assumptions_title": "Hypothèses",
    "assumption_line": (
        "{category} : {ret} par an ± {vol}, une croissance médiane de {median} par an"
    ),
    "inflation_line": "Inflation : {rate} par an.",
    "allocation_line": "L'épargne va à : {shares}.",
    "assumptions_where": "La base utilise les hypothèses du foyer, réglées sous les graphiques.",
    "changes_line": "Et si {n} : {changes}.",
    "change_savings": "épargne de {amount} par mois",
    "change_inflation": "inflation de {rate}",
    "change_assumption": "{category} à {ret} ± {vol}",
    "change_allocation": "allocation {shares}",
    "no_change": "aucun changement",
    "limits_title": "Limites",
    "limit_independent": (
        "Les catégories sont tirées indépendamment, comme si actions, private equity et crypto "
        "ne chutaient jamais ensemble : dans un krach, elles le font, l'éventail est donc plus "
        "étroit que la réalité."
    ),
    "limit_crashes": (
        "Les rendements suivent une loi lognormale : pas de krach au-delà, ni de perte totale "
        "(une plateforme ou un jeton qui fait faillite)."
    ),
    "limit_inflation": "L'inflation est fixe sur tout l'horizon.",
    "limit_shortfall": "Le découvert est emprunté à 8\u202f% par an, fixe.",
    "limit_tax": (
        "Les rendements sont après les frais d'un fonds peu cher et avant impôts : le patrimoine "
        "est ce que vaudraient les avoirs, pas ce que leur vente rapporterait après l'impôt sur "
        "les plus-values."
    ),
    "limit_ceilings": (
        "Les plafonds des livrets (22 950 € pour un Livret A, 12 000 € pour un LDDS) ne sont pas "
        "modélisés."
    ),
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


def percent(share: Decimal, lang: Language, *, places: int = 1) -> str:
    """A share as a percentage, to `places` decimals at most: 6.5% or 6,5 %."""
    value = (share * HUNDRED).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    text = f"{value.normalize():f}" if value else "0"
    if lang == "fr":
        return text.replace(".", ",").replace("-", "−") + "\u202f%"
    return text.replace("-", "−") + "%"


def chance(share: Decimal, lang: Language) -> str:
    """To the whole percent, never 0 nor 100 (F-SIM-5)."""
    if share < Decimal("0.01"):
        return t(lang, "chance_low")
    if share > Decimal("0.99"):
        return t(lang, "chance_high")
    return percent(share, lang, places=0)


def month(m: Month, lang: Language) -> str:
    return f"{MONTHS[lang][m.month - 1]} {m.year}"
