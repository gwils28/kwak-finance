"""What the Projection page shows (spec §4.11 F-SIM-5), built from the runs: the fan with the
what-ifs' medians and the amount to reach, the median by category, the chance of reaching an
amount, the scenarios compared at the horizon, every chart's table, the assumptions and the
limits. Pure functions: the page's callbacks only gather the inputs."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import plotly.graph_objects as go
from dash import dcc, html
from kwak_core.budget import Month
from kwak_core.goals import add_months
from kwak_core.projection import median_growth

from kwak_api.dash import i18n, layout, tokens
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


ROWS_AXIS: dict[str, object] = {
    "gridcolor": "rgba(0,0,0,0)",
    "automargin": True,
    "title": None,
    "tickformat": "",
    "tickprefix": "",
    "ticksuffix": "",
}
"""The y axis of a chart with a row per category: `chart_layout` wrote euros on it."""


def chart_layout(figure: go.Figure, view: View, *, y_title: str) -> go.Figure:
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
        # Plotly's own toolbar and labels in the palette too, not its blue and greys.
        modebar={
            "bgcolor": "rgba(0,0,0,0)",
            "color": tokens.rgb(theme, "muted"),
            "activecolor": tokens.rgb(theme, "primary-400" if theme == "dark" else "primary-600"),
        },
        hoverlabel={
            "bgcolor": tokens.rgb(theme, "surface"),
            "bordercolor": tokens.rgb(theme, "border"),
            "font": {"color": tokens.rgb(theme, "fg")},
        },
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
        reached = [
            k
            for share in (HALF, NINE_TENTHS)
            if (k := base.run.outcome.reached_by(target.amount, share, today=today)) is not None
        ]
        if reached:
            name = t(lang, "reach_marks")
            figure.add_scatter(
                x=[add_months(start, k).first_day() for k in reached],
                y=[float(target.amount)] * len(reached),
                mode="markers",
                marker={
                    "size": 11,
                    "color": tokens.rgb(theme, "surface"),
                    "line": {
                        "width": 2.5,
                        "color": tokens.rgb(theme, "primary-400" if dark else "primary-600"),
                    },
                },
                name=name,
                customdata=[i18n.month(add_months(start, k), lang) for k in reached],
                hovertemplate=f"{name}: %{{customdata}}<extra></extra>",
            )
        figure.add_hline(
            y=float(target.amount),
            line={"dash": "dot", "width": 1.5, "color": tokens.rgb(theme, "neutral-500")},
            annotation_text=t(lang, "amount_line", amount=i18n.money(target.amount, lang)),
            annotation_position="top left",
            annotation_font_color=tokens.rgb(theme, "muted"),
        )
    return chart_layout(figure, view, y_title=t(lang, "net_worth"))


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
    """Each category's own median today and at the horizon, side by side in its colour; the
    debts and the Shortfall below zero, in the debts' colour (F-SIM-5, spec §7)."""
    lang, theme = view.lang, view.theme
    medians = base.outcome.medians_by_category(today=today)
    rows: list[tuple[str, str, Decimal, Decimal]] = [
        (c.name, f"wealth-{c.colour}", medians[0][k], medians[-1][k])
        for k, c in _shown_categories(categories, medians)
    ]
    debts = base.debts(today=today)
    shortfall = base.outcome.shortfall_median(today=today)
    for values, name in ((debts, t(lang, "debts")), (shortfall, t(lang, "shortfall_name"))):
        if any(values):
            rows.append((name, "wealth-debts", -values[0], -values[-1]))
    rows.reverse()  # Plotly draws the first row at the bottom
    names = [r[0] for r in rows]
    figure = go.Figure()
    horizon = i18n.month(add_months(start, len(medians) - 1), lang)
    for label, at, alpha in ((t(lang, "today_bars"), 0, 0.4), (horizon, 1, 1.0)):
        values = [r[3] if at else r[2] for r in rows]
        figure.add_bar(
            orientation="h",
            y=names,
            x=[float(v) for v in values],
            name=label,
            marker={
                "color": [
                    tokens.rgb(theme, r[1]) if alpha == 1 else tokens.rgba(theme, r[1], alpha)
                    for r in rows
                ]
            },
            text=[i18n.money(v, lang) for v in values] if alpha == 1 else None,
            textposition="outside",
            cliponaxis=False,
            customdata=[i18n.money(v, lang) for v in values],
            hovertemplate=f"%{{y}}, {label}: %{{customdata}}<extra></extra>",
        )
    chart_layout(figure, view, y_title="")
    figure.update_layout(
        barmode="group",
        bargap=0.3,
        bargroupgap=0.1,
        hovermode="closest",
        height=56 * len(rows) + 80,
        margin={"l": 8, "r": 64, "t": 8, "b": 8},
        legend={"orientation": "h", "y": -0.12, "traceorder": "normal"},
        xaxis={
            "tickformat": "~s",
            "zeroline": True,
            "zerolinecolor": tokens.rgb(theme, "fg"),
        },
        yaxis=ROWS_AXIS,
    )
    return figure


def data_table(
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
    return data_table(header, body, lang)


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
    return data_table(header, body, lang)


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
    view: View,
    target: Target | None,
) -> html.Div:
    """The scenarios at the horizon: median, 10 % and 90 %, and the chance of the amount."""
    lang = view.lang
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
    table = data_table(header, body, lang)
    return html.Div(
        [
            html.P(html.B(t(lang, "compare_title", month=horizon))),
            dcc.Graph(
                id="compare-chart",
                figure=scenarios_chart(scenarios, today=today, view=view),
                config={"displayModeBar": False},
            ),
            table,
        ]
    )


def scenarios_chart(scenarios: Sequence[Scenario], *, today: bool, view: View) -> go.Figure:
    """Each scenario at the horizon: its median a point on its 10-90 % range, the base on top."""
    lang, theme = view.lang, view.theme
    rows = list(reversed(scenarios))
    ends = [s.run.outcome.percentiles(today=today)[-1] for s in rows]
    hues = [
        tokens.rgb(theme, "primary-400" if theme == "dark" else "primary-600")
        if s is scenarios[0]
        else _what_if_colour(scenarios.index(s), theme)
        for s in rows
    ]
    names = [s.name for s in rows]
    figure = go.Figure()
    figure.add_bar(
        orientation="h",
        y=names,
        base=[float(e[10]) for e in ends],
        x=[float(e[90] - e[10]) for e in ends],
        marker={"color": [h.replace("rgb(", "rgba(").replace(")", ",0.25)") for h in hues]},
        width=0.4,
        hoverinfo="skip",
    )
    figure.add_scatter(
        mode="markers+text",
        y=names,
        x=[float(e[50]) for e in ends],
        marker={
            "size": 12,
            "color": hues,
            "line": {"color": tokens.rgb(theme, "surface"), "width": 2},
        },
        text=[i18n.money(e[50], lang) for e in ends],
        textposition="top center",
        customdata=[[i18n.money(e[10], lang), i18n.money(e[90], lang)] for e in ends],
        hovertemplate=(
            f"%{{y}}: %{{text}}<br>{i18n.percent(Decimal('0.1'), lang)} %{{customdata[0]}}, "
            f"{i18n.percent(Decimal('0.9'), lang)} %{{customdata[1]}}<extra></extra>"
        ),
    )
    chart_layout(figure, view, y_title="")
    figure.update_layout(
        showlegend=False,
        hovermode="closest",
        height=70 * len(rows) + 60,
        xaxis={"tickformat": "~s"},
        yaxis=ROWS_AXIS,
    )
    return figure


def _shares(shares: dict[UUID, Decimal], names: dict[UUID, str], lang: Language) -> str:
    return ", ".join(
        f"{names[k]} {i18n.percent(v, lang, places=0)}"
        for k, v in sorted(shares.items(), key=lambda kv: -kv[1])
        if v
    )


def assumptions_chart(b: projection.Basis, view: View) -> go.Figure:
    """Each category's expected return a point, its volatility on either side."""
    lang, theme = view.lang, view.theme
    rows = sorted(b.categories, key=lambda c: b.assumptions[c.id].ret)
    figure = go.Figure()
    figure.add_scatter(
        mode="markers",
        y=[c.name for c in rows],
        x=[float(100 * b.assumptions[c.id].ret) for c in rows],
        marker={
            "size": 11,
            "color": [tokens.rgb(theme, f"wealth-{c.colour}") for c in rows],
            "line": {"color": tokens.rgb(theme, "surface"), "width": 2},
        },
        error_x={
            "type": "data",
            "array": [float(100 * b.assumptions[c.id].volatility) for c in rows],
            "color": tokens.rgb(theme, "muted"),
            "thickness": 1.5,
            "width": 0,
        },
        customdata=[
            [
                i18n.percent(b.assumptions[c.id].ret, lang),
                i18n.percent(b.assumptions[c.id].volatility, lang),
            ]
            for c in rows
        ],
        hovertemplate="%{y}: %{customdata[0]} ± %{customdata[1]}<extra></extra>",
    )
    chart_layout(figure, view, y_title="")
    figure.update_layout(
        showlegend=False,
        hovermode="closest",
        height=30 * len(rows) + 60,
        xaxis={
            "ticksuffix": " %",
            "tickprefix": "",
            "tickformat": "",
            "zeroline": True,
            "zerolinecolor": tokens.rgb(theme, "fg"),
            "title": {"text": t(lang, "return_axis")},
        },
        yaxis=ROWS_AXIS,
    )
    return figure


def allocation_bar(b: projection.Basis, lang: Language, theme: Theme) -> html.Div | None:
    """Where the monthly savings go, as one bar in the categories' colours."""
    if not b.allocation:
        return None
    by_id = {c.id: c for c in b.categories}
    parts = sorted(((v, by_id[k]) for k, v in b.allocation.items() if v), key=lambda p: -p[0])
    return html.Div(
        [
            html.Div(
                f"{c.name} {i18n.percent(v, lang, places=0)}",
                title=f"{c.name} {i18n.percent(v, lang, places=0)}",
                style={
                    "flex": f"{v} 1 0",
                    "background": tokens.rgb(theme, f"wealth-{c.colour}"),
                },
            )
            for v, c in parts
        ],
        className="kw-split",
    )


def assumptions(b: projection.Basis, scenarios: Sequence[Scenario], view: View) -> html.Div:
    """The base's assumptions drawn, then what each what-if changes (F-SIM-5)."""
    lang = view.lang
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
    lines, what_ifs = items[: len(b.categories)], items[len(b.categories) :]
    bar = allocation_bar(b, lang, view.theme)
    return html.Div(
        [
            html.P(t(lang, "assumptions_where"), className="kw-lede"),
            dcc.Graph(
                id="assumptions-chart",
                figure=assumptions_chart(b, view),
                config={"displayModeBar": False},
            ),
            *([bar] if bar is not None else []),
            html.Ul(what_ifs),
            html.Details([html.Summary(t(lang, "show_data")), html.Ul(lines)]),
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


def limits(lang: Language) -> html.Details:
    return layout.fold(
        t(lang, "limits_title"),
        t(lang, "limits_hint"),
        html.Ul([html.Li(t(lang, k)) for k in LIMITS]),
    )


def tiles(
    b: projection.Basis,
    base: projection.Run,
    target: Target | None,
    start: Month,
    *,
    today: bool,
    lang: Language,
) -> html.Div:
    """The answer first (spec §7): net worth today, the median at the horizon, the amount."""
    outcome = base.outcome
    end = outcome.percentiles(today=today)[-1]
    horizon = i18n.month(add_months(start, outcome.months), lang)
    items = [
        layout.tile(
            t(lang, "tile_today"),
            i18n.money(b.start.net, lang),
            note=t(lang, "tile_savings", amount=i18n.money(b.savings, lang)),
        ),
        layout.tile(
            t(lang, "tile_median", month=horizon),
            i18n.money(end[50], lang),
            note=t(
                lang,
                "tile_range",
                low=i18n.money(end[10], lang),
                high=i18n.money(end[90], lang),
            ),
            wide=True,
        ),
    ]
    if target is not None and target.month <= outcome.months:
        month = i18n.month(add_months(start, target.month), lang)
        half = outcome.reached_by(target.amount, HALF, today=today)
        items.append(
            layout.tile(
                t(lang, "tile_amount", amount=i18n.money(target.amount, lang), month=month),
                i18n.chance(outcome.chance(target.amount, target.month, today=today), lang),
                note=t(lang, "not_within")
                if half is None
                else t(lang, "tile_half", month=i18n.month(add_months(start, half), lang)),
                anchor="prj-goal-tile",
            )
        )
    return layout.tiles(*items)
