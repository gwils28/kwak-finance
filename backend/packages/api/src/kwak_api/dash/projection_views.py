"""What the Projection page shows (spec §4.11 F-SIM-5), built from the runs: the fan with the
what-ifs' medians and the amount to reach, the median by category, the chance of reaching an
amount, the scenarios compared at the horizon, every chart's table, the assumptions and the
limits. Pure functions: the page's callbacks only gather the inputs."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import plotly.graph_objects as go
from dash import html
from kwak_core.budget import Month
from kwak_core.goals import add_months
from kwak_core.projection import median_growth

from kwak_api.dash import i18n, tokens
from kwak_api.dash.i18n import Language, t
from kwak_api.dash.tokens import Theme
from kwak_api.services import projection

HALF = Decimal("0.5")
NINE_TENTHS = Decimal("0.9")
SHOWN = (90, 75, 50, 25, 10)
"""The percentiles a month's label lists, from the highest outcome to the lowest."""


@dataclass(frozen=True)
class View:
    lang: Language
    theme: Theme


@dataclass(frozen=True)
class Scenario:
    name: str
    run: projection.Run
    what_if: projection.WhatIf


@dataclass(frozen=True)
class Target:
    """An amount to reach, in the euros shown, and a month counted from the start."""

    amount: Decimal
    month: int


def _months(start: Month, count: int) -> list[Month]:
    return [add_months(start, k) for k in range(count + 1)]


def _yearly(count: int) -> list[int]:
    """The rows of a table: the start, each year, and the horizon."""
    rows = list(range(0, count + 1, 12))
    return rows if rows[-1] == count else [*rows, count]


def _layout(figure: go.Figure, view: View, *, y_title: str) -> go.Figure:
    lang, theme = view.lang, view.theme
    grid = tokens.rgb(theme, "chart-grid")
    figure.update_layout(
        paper_bgcolor=tokens.rgb(theme, "bg"),
        plot_bgcolor=tokens.rgb(theme, "bg"),
        font={
            "family": "IBM Plex Sans, ui-sans-serif, sans-serif",
            "color": tokens.rgb(theme, "fg"),
        },
        separators=", " if lang == "fr" else ".,",
        hovermode="x",
        legend={"orientation": "h", "y": -0.15},
        margin={"l": 8, "r": 8, "t": 16, "b": 8},
        xaxis={"gridcolor": grid, "tickformat": "%Y"},
        yaxis={
            "title": {"text": y_title},
            "gridcolor": grid,
            "zerolinecolor": tokens.rgb(theme, "border"),
            "tickformat": ",.0f",
            **({"ticksuffix": " €"} if lang == "fr" else {"tickprefix": "€"}),
        },
    )
    return figure


def _what_if_colour(n: int, theme: Theme) -> str:
    """Spec §7: secondary-500, then neutral-600 (neutral-300 in dark), dashed."""
    if n == 1:
        return tokens.rgb(theme, "secondary-500")
    return tokens.rgb(theme, "neutral-300" if theme == "dark" else "neutral-600")


def fan(
    scenarios: Sequence[Scenario],
    start: Month,
    *,
    today: bool,
    view: View,
    target: Target | None = None,
) -> go.Figure:
    """The base's median net worth and its 25-75 % and 10-90 % bands; each what-if's median,
    dashed; the amount to reach, dotted."""
    lang, theme = view.lang, view.theme
    dark = theme == "dark"
    base, *others = scenarios
    rows = base.run.outcome.percentiles(today=today)
    months = _months(start, len(rows) - 1)
    x = [m.first_day() for m in months]
    labels = [i18n.month(m, lang) for m in months]

    def series(p: int) -> list[float]:
        return [float(r[p]) for r in rows]

    figure = go.Figure()
    for low, high, colour, name in (
        (10, 90, "primary-800" if dark else "primary-200", t(lang, "band_10_90")),
        (25, 75, "primary-700" if dark else "primary-300", t(lang, "band_25_75")),
    ):
        figure.add_scatter(
            x=x,
            y=series(low),
            mode="lines",
            line={"width": 0},
            showlegend=False,
            legendgroup=name,
            hoverinfo="skip",
        )
        figure.add_scatter(
            x=x,
            y=series(high),
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor=tokens.rgb(theme, colour),
            legendgroup=name,
            name=name,
            hoverinfo="skip",
        )
    median = t(lang, "median")
    lines = [
        f"{median if p == 50 else i18n.percent(Decimal(p) / 100, lang)}: %{{customdata[{k + 1}]}}"
        for k, p in enumerate(SHOWN)
    ]
    figure.add_scatter(
        x=x,
        y=series(50),
        mode="lines",
        line={"width": 3, "color": tokens.rgb(theme, "primary-400" if dark else "primary-600")},
        name=f"{median} ({base.name})" if others else median,
        # One label for the month, from the highest outcome to the lowest.
        customdata=[
            [label, *(i18n.money(r[p], lang) for p in SHOWN)]
            for label, r in zip(labels, rows, strict=True)
        ],
        hovertemplate="<b>%{customdata[0]}</b><br>" + "<br>".join(lines) + "<extra></extra>",
    )
    for n, other in enumerate(others, start=1):
        values = [r[50] for r in other.run.outcome.percentiles(today=today)]
        figure.add_scatter(
            x=x,
            y=[float(v) for v in values],
            mode="lines",
            line={"width": 2, "dash": "dash", "color": _what_if_colour(n, theme)},
            name=f"{median} ({other.name})",
            customdata=[i18n.money(v, lang) for v in values],
            hovertemplate=f"{other.name}: %{{customdata}}<extra></extra>",
        )
    if target is not None:
        figure.add_hline(
            y=float(target.amount),
            line={"dash": "dot", "width": 1.5, "color": tokens.rgb(theme, "neutral-500")},
            annotation_text=t(lang, "amount_line", amount=i18n.money(target.amount, lang)),
            annotation_position="top left",
            annotation_font_color=tokens.rgb(theme, "muted"),
        )
    return _layout(figure, view, y_title=t(lang, "net_worth"))


@dataclass(frozen=True)
class CategoryInfo:
    id: UUID
    name: str
    colour: str


def _shown_categories(
    categories: Sequence[CategoryInfo], medians: list[list[Decimal]]
) -> list[tuple[int, CategoryInfo]]:
    """The categories holding something at some point of the median."""
    return [(k, c) for k, c in enumerate(categories) if any(row[k] for row in medians)]


def by_category(
    base: projection.Run,
    categories: Sequence[CategoryInfo],
    start: Month,
    *,
    today: bool,
    view: View,
) -> go.Figure:
    """Each category's own median, stacked in its colour; the debts and the Shortfall below
    zero, in the debts' colour (spec §7)."""
    lang, theme = view.lang, view.theme
    medians = base.outcome.medians_by_category(today=today)
    months = _months(start, len(medians) - 1)
    x = [m.first_day() for m in months]
    figure = go.Figure()
    for k, category in _shown_categories(categories, medians):
        values = [row[k] for row in medians]
        figure.add_scatter(
            x=x,
            y=[float(v) for v in values],
            mode="lines",
            stackgroup="assets",
            line={"width": 0.5, "color": tokens.rgb(theme, f"wealth-{category.colour}")},
            fillcolor=tokens.rgb(theme, f"wealth-{category.colour}"),
            name=category.name,
            customdata=[i18n.money(v, lang) for v in values],
            hovertemplate=f"{category.name}: %{{customdata}}<extra></extra>",
        )
    debts = base.debts(today=today)
    shortfall = base.outcome.shortfall_median(today=today)
    for values, name, pattern in (
        (debts, t(lang, "debts"), None),
        (shortfall, t(lang, "shortfall_name"), {"shape": "/"}),
    ):
        if not any(values):
            continue
        figure.add_scatter(
            x=x,
            y=[-float(v) for v in values],
            mode="lines",
            stackgroup="debts",
            line={"width": 0.5, "color": tokens.rgb(theme, "wealth-debts")},
            fillcolor=tokens.rgb(theme, "wealth-debts"),
            fillpattern=pattern,
            name=name,
            customdata=[i18n.money(-v, lang) for v in values],
            hovertemplate=f"{name}: %{{customdata}}<extra></extra>",
        )
    return _layout(figure, view, y_title=t(lang, "median"))


def _table(
    header: Sequence[str], rows: Sequence[Sequence[str]], lang: Language, *, open_: bool = False
) -> html.Details:
    cell = {"padding": "0.25rem 0.75rem", "textAlign": "right", "whiteSpace": "nowrap"}
    return html.Details(
        [
            html.Summary(t(lang, "show_data")),
            html.Div(
                html.Table(
                    [
                        html.Thead(html.Tr([html.Th(h, style=cell) for h in header])),
                        html.Tbody(
                            [html.Tr([html.Td(v, style=cell) for v in row]) for row in rows]
                        ),
                    ],
                    style={"borderCollapse": "collapse", "fontSize": "0.85rem"},
                ),
                style={"overflowX": "auto"},
            ),
        ],
        open=open_,
    )


def fan_table(
    scenarios: Sequence[Scenario], start: Month, *, today: bool, lang: Language
) -> html.Details:
    base, *others = scenarios
    rows = base.run.outcome.percentiles(today=today)
    medians = [o.run.outcome.percentiles(today=today) for o in others]
    header = [
        t(lang, "col_month"),
        *(t(lang, "median") if p == 50 else i18n.percent(Decimal(p) / 100, lang) for p in SHOWN),
        *(f"{t(lang, 'median')} ({o.name})" for o in others),
    ]
    body = [
        [
            i18n.month(add_months(start, k), lang),
            *(i18n.money(rows[k][p], lang) for p in SHOWN),
            *(i18n.money(m[k][50], lang) for m in medians),
        ]
        for k in _yearly(len(rows) - 1)
    ]
    return _table(header, body, lang)


def category_table(
    base: projection.Run,
    categories: Sequence[CategoryInfo],
    start: Month,
    *,
    today: bool,
    lang: Language,
) -> html.Details:
    medians = base.outcome.medians_by_category(today=today)
    shown = _shown_categories(categories, medians)
    debts = base.debts(today=today)
    shortfall = base.outcome.shortfall_median(today=today)
    header = [
        t(lang, "col_month"),
        *(c.name for _, c in shown),
        t(lang, "debts"),
        t(lang, "shortfall_name"),
    ]
    body = [
        [
            i18n.month(add_months(start, m), lang),
            *(i18n.money(medians[m][k], lang) for k, _ in shown),
            i18n.money(-debts[m], lang),
            i18n.money(-shortfall[m], lang),
        ]
        for m in _yearly(len(medians) - 1)
    ]
    return _table(header, body, lang)


def reach(
    base: projection.Run, target: Target, start: Month, *, today: bool, lang: Language
) -> list[html.P]:
    """The chance that net worth is at least the amount in the month, and the months by
    which half and nine tenths of the outcomes have reached it once (F-SIM-5)."""
    outcome = base.outcome
    month = i18n.month(add_months(start, target.month), lang)
    amount = i18n.money(target.amount, lang)
    out: list[html.P] = []
    if target.month > outcome.months:
        out.append(html.P(t(lang, "after_horizon", month=month)))
    else:
        chance = outcome.chance(target.amount, target.month, today=today)
        out.append(
            html.P(
                t(
                    lang,
                    "reach_chance",
                    chance=i18n.chance(chance, lang),
                    amount=amount,
                    month=month,
                )
            )
        )

    def by(share: Decimal) -> str:
        k = outcome.reached_by(target.amount, share, today=today)
        return t(lang, "not_within") if k is None else i18n.month(add_months(start, k), lang)

    out.append(html.P(t(lang, "reach_dates", half=by(HALF), ninety=by(NINE_TENTHS))))
    return out


def shortfall_note(base: projection.Run, lang: Language) -> html.P | None:
    share = base.outcome.shortfall_share()
    return html.P(t(lang, "shortfall", share=i18n.chance(share, lang))) if share else None


def comparison(
    scenarios: Sequence[Scenario],
    start: Month,
    *,
    today: bool,
    lang: Language,
    target: Target | None,
) -> html.Div:
    """The scenarios at the horizon: median, 10 % and 90 %, and the chance of the amount."""
    last = scenarios[0].run.outcome.months
    horizon = i18n.month(add_months(start, last), lang)
    reachable = target is not None and target.month <= last
    header = [
        t(lang, "col_scenario"),
        t(lang, "col_median"),
        i18n.percent(Decimal("0.1"), lang),
        i18n.percent(Decimal("0.9"), lang),
    ]
    if reachable and target is not None:
        header.append(
            t(
                lang,
                "col_chance",
                amount=i18n.money(target.amount, lang),
                month=i18n.month(add_months(start, target.month), lang),
            )
        )
    body = []
    for s in scenarios:
        at = s.run.outcome.percentiles(today=today)[-1]
        row = [s.name, *(i18n.money(at[p], lang) for p in (50, 10, 90))]
        if reachable and target is not None:
            chance = s.run.outcome.chance(target.amount, target.month, today=today)
            row.append(i18n.chance(chance, lang))
        body.append(row)
    table = _table(header, body, lang, open_=True)
    return html.Div([html.H3(t(lang, "compare_title", month=horizon)), table])


def _shares(shares: dict[UUID, Decimal], names: dict[UUID, str], lang: Language) -> str:
    return ", ".join(
        f"{names[k]} {i18n.percent(v, lang, places=0)}"
        for k, v in sorted(shares.items(), key=lambda kv: -kv[1])
        if v
    )


def assumptions(b: projection.Basis, scenarios: Sequence[Scenario], lang: Language) -> html.Div:
    """The base's assumptions, and what each what-if changes (F-SIM-5)."""
    names = {c.id: c.name for c in b.categories}
    items = [
        html.Li(
            t(
                lang,
                "assumption_line",
                category=c.name,
                ret=i18n.percent(b.assumptions[c.id].ret, lang),
                vol=i18n.percent(b.assumptions[c.id].volatility, lang),
                median=i18n.percent(median_growth(b.assumptions[c.id]), lang),
            )
        )
        for c in b.categories
    ]
    items.append(html.Li(t(lang, "inflation_line", rate=i18n.percent(b.inflation, lang))))
    if b.allocation:
        items.append(html.Li(t(lang, "allocation_line", shares=_shares(b.allocation, names, lang))))
    for n, s in enumerate(scenarios[1:], start=1):
        w = s.what_if
        changes = []
        if w.savings is not None:
            changes.append(t(lang, "change_savings", amount=i18n.money(w.savings, lang)))
        if w.inflation is not None:
            changes.append(t(lang, "change_inflation", rate=i18n.percent(w.inflation, lang)))
        for k, a in w.assumptions.items():
            changes.append(
                t(
                    lang,
                    "change_assumption",
                    category=names[k],
                    ret=i18n.percent(a.ret, lang),
                    vol=i18n.percent(a.volatility, lang),
                )
            )
        if w.allocation is not None:
            shares = {k: Decimal(p) / 100 for k, p in w.allocation.items()}
            changes.append(t(lang, "change_allocation", shares=_shares(shares, names, lang)))
        items.append(
            html.Li(
                t(
                    lang,
                    "changes_line",
                    n=n,
                    changes=", ".join(changes) if changes else t(lang, "no_change"),
                )
            )
        )
    return html.Div(
        [
            html.H3(t(lang, "assumptions_title")),
            html.P(t(lang, "assumptions_where")),
            html.Ul(items),
        ]
    )


LIMITS = (
    "limit_independent",
    "limit_crashes",
    "limit_inflation",
    "limit_shortfall",
    "limit_tax",
    "limit_ceilings",
)


def limits(lang: Language) -> html.Div:
    return html.Div(
        [html.H3(t(lang, "limits_title")), html.Ul([html.Li(t(lang, k)) for k in LIMITS])]
    )
