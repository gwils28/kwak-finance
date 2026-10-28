"""The Spending space's Forecast tab (spec §4.14 F-FCT-6): the next twelve months by category
with their bands, against the targets, what each forecast rests on and the back-test, their
tables, the disclaimer and the limits. Nothing is set here: the page only reads."""

from collections.abc import Callable, Sequence
from decimal import Decimal
from uuid import UUID

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html
from dash.development.base_component import Component
from kwak_analytics.forecast import TREES
from kwak_core import forecast as core
from kwak_core.budget import Month, month_range, target_for
from kwak_core.categories import CategoryKind
from kwak_core.forecast import BASELINE, Band, Risk

from kwak_api.dash import i18n, tokens
from kwak_api.dash import projection_views as views
from kwak_api.dash.app import Context
from kwak_api.dash.i18n import Language, t
from kwak_api.dash.projection import GRAPH, dash_colours, view_of
from kwak_api.dash.projection_views import View
from kwak_api.services import forecast as service

ZERO = Decimal(0)
SHOWN_HISTORY = 24
"""Months entered shown before the forecast."""
LIMITS = (
    "fct_limit_fixed",
    "fct_limit_bands",
    "fct_limit_change",
    "fct_limit_yearly",
    "fct_limit_euros",
)
TOTALS = ("income", "spent", "saved", "rest")
KIND_TOTAL = {
    CategoryKind.INCOME: "income",
    CategoryKind.EXPENSE: "spent",
    CategoryKind.SAVINGS: "saved",
}
OVER = {
    Risk.LIKELY: "fct_likely_over",
    Risk.POSSIBLE: "fct_may_go_over",
    Risk.UNLIKELY: "fct_within",
}
SHORT = {
    Risk.LIKELY: "fct_likely_short",
    Risk.POSSIBLE: "fct_may_fall_short",
    Risk.UNLIKELY: "fct_on_track",
}


def _token(theme: tokens.Theme, total: str) -> str:
    """Spec §7: income money in, spent ochre, saved green, the rest the text colour."""
    dark = theme == "dark"
    return {
        "income": "flow-in",
        "spent": "secondary-400" if dark else "secondary-600",
        "fixed": "secondary-700" if dark else "secondary-300",
        "saved": "primary-400" if dark else "primary-600",
        "rest": "fg",
    }[total]


def colour(theme: tokens.Theme, total: str) -> str:
    return tokens.rgb(theme, _token(theme, total))


def _band_text(b: Band, lang: Language) -> str:
    if b.low == b.high:
        return "—"
    return t(lang, "fct_range", low=i18n.euros(b.low, lang), high=i18n.euros(b.high, lang))


def _chance(chance: Decimal | None, lang: Language) -> str:
    return "—" if chance is None else i18n.chance_5(chance, lang)


# Totals, entered and forecast


def history_totals(r: service.Result) -> dict[str, list[Decimal]]:
    """Each month of the history's income, spent and saved, its fixed spending and rest."""
    n = len(r.history)
    out = {name: [ZERO] * n for name in ("income", "spent", "saved", "fixed")}
    for c in r.categories:
        s = r.forecast.categories[c.id].series
        name = KIND_TOTAL[c.kind]
        for i in range(n):
            out[name][i] += s.total[i]
            if c.kind is CategoryKind.EXPENSE:
                out["fixed"][i] += s.fixed[i]
    out["rest"] = [out["income"][i] - out["spent"][i] - out["saved"][i] for i in range(n)]
    return out


def forecast_bands(r: service.Result, name: str) -> tuple[Band, ...]:
    bands: tuple[Band, ...] = getattr(r.forecast, name)
    return bands


def known_spent(r: service.Result) -> list[Decimal]:
    out = [ZERO] * core.HORIZON
    for c in r.categories:
        if c.kind is CategoryKind.EXPENSE:
            for k, v in enumerate(r.forecast.categories[c.id].known):
                out[k] += v
    return out


def summary(r: service.Result, lang: Language) -> list[html.P]:
    f = r.forecast
    over = {name: f.total_over(name, core.HORIZON) for name in TOTALS}
    rest = over["rest"]
    has_band = core.sum_errors(f.total_errors["rest"], core.HORIZON) is not None
    values = {
        "first": i18n.month(r.ahead[0], lang),
        "last": i18n.month(r.ahead[-1], lang),
        "income": i18n.euros(over["income"].point, lang),
        "spent": i18n.euros(over["spent"].point, lang),
        "saved": i18n.euros(over["saved"].point, lang),
        "rest": i18n.euros(rest.point, lang),
    }
    text = (
        t(
            lang,
            "fct_summary",
            low=i18n.euros(rest.low, lang),
            high=i18n.euros(rest.high, lang),
            **values,
        )
        if has_band
        else t(lang, "fct_summary_no_band", **values)
    )
    entered = sum(
        (r.entered.get(c.id, ZERO) for c in r.categories if c.kind is CategoryKind.EXPENSE), ZERO
    )
    now = f.spent[0]
    month = i18n.month(r.ahead[0], lang)
    if now.high > now.point and entered > now.high:
        current = t(
            lang,
            "fct_now_above",
            entered=i18n.euros(entered, lang),
            month=month,
            high=i18n.euros(now.high, lang),
        )
    else:
        current = t(
            lang,
            "fct_now",
            entered=i18n.euros(entered, lang),
            month=month,
            expected=i18n.euros(now.point, lang),
        )
    return [html.P(text, style={"fontSize": "1.1rem", "fontWeight": 600}), html.P(current)]


def _x(months: Sequence[Month]) -> list[object]:
    return [m.first_day() for m in months]


def _origin(figure: go.Figure, month: Month, view: View) -> None:
    x = month.first_day()
    figure.add_shape(
        type="line",
        x0=x,
        x1=x,
        y0=0,
        y1=1,
        yref="paper",
        line={"dash": "dot", "width": 1.5, "color": tokens.rgb(view.theme, "neutral-500")},
    )
    figure.add_annotation(
        x=x,
        y=1,
        yref="paper",
        text=t(view.lang, "fct_origin"),
        showarrow=False,
        xanchor="right",
        yanchor="top",
        font={"color": tokens.rgb(view.theme, "muted")},
    )


def _series(
    figure: go.Figure,
    r: service.Result,
    view: View,
    key: str,
    entered: Sequence[Decimal],
    bands: Sequence[Band],
    *,
    colour_name: str,
    width: float = 2,
) -> None:
    """Months entered solid, the forecast dashed from the origin, its band in the same hue."""
    lang, theme = view.lang, view.theme
    name = t(lang, key)
    hue = colour(theme, colour_name)
    start = max(0, len(r.history) - SHOWN_HISTORY)
    past = r.history[start:]
    shown = list(entered[start:])
    figure.add_scatter(
        x=_x(past),
        y=[float(v) for v in shown],
        mode="lines",
        name=name,
        line={"width": width, "color": hue},
        legendgroup=key,
        customdata=[i18n.euros(v, lang) for v in shown],
        hovertemplate=f"{name}: %{{customdata}}<extra></extra>",
    )
    if any(b.low != b.high for b in bands):
        months = _x(r.ahead)
        figure.add_scatter(
            x=months,
            y=[float(b.high) for b in bands],
            mode="lines",
            line={"width": 0},
            showlegend=False,
            hoverinfo="skip",
            legendgroup=key,
        )
        figure.add_scatter(
            x=months,
            y=[float(b.low) for b in bands],
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor=tokens.rgba(theme, _token(theme, colour_name), 0.18),
            name=t(lang, "fct_band", name=name),
            legendgroup=key,
            customdata=[_band_text(b, lang) for b in bands],
            hovertemplate=f"{t(lang, 'fct_band', name=name)}: %{{customdata}}<extra></extra>",
        )
    points = [shown[-1] if shown else ZERO, *(b.point for b in bands)]
    figure.add_scatter(
        x=_x([r.origin, *r.ahead]),
        y=[float(v) for v in points],
        mode="lines",
        name=t(lang, "fct_forecast_of", name=name),
        legendgroup=key,
        line={"width": width, "color": hue, "dash": "dash"},
        customdata=[i18n.euros(v, lang) for v in points],
        hovertemplate=f"{t(lang, 'fct_forecast_of', name=name)}: %{{customdata}}<extra></extra>",
    )


def _layout(figure: go.Figure, view: View, months: Sequence[Month]) -> go.Figure:
    """Month ticks in the page's language, every third month (Plotly's own are English)."""
    views.chart_layout(figure, view, y_title=t(view.lang, "fct_axis"))
    ticks = [m for m in months if m.month % 3 == 1]
    figure.update_layout(
        hovermode="x unified",
        xaxis={
            "tickmode": "array",
            "tickvals": _x(ticks),
            "ticktext": [i18n.month(m, view.lang) for m in ticks],
        },
    )
    return figure


def ratio(value: Decimal, lang: Language) -> str:
    """A MASE or RMSSE, two decimals, the decimal sign of the language."""
    text = f"{value:.2f}"
    return text.replace(".", ",") if lang == "fr" else text


def _shown(r: service.Result) -> list[Month]:
    return [*r.history[max(0, len(r.history) - SHOWN_HISTORY) :], *r.ahead]


def months_chart(r: service.Result, view: View) -> go.Figure:
    figure = go.Figure()
    h = history_totals(r)
    fixed = [Band(v, v, v) for v in known_spent(r)]
    _series(
        figure,
        r,
        view,
        "fct_income",
        h["income"],
        forecast_bands(r, "income"),
        colour_name="income",
    )
    _series(
        figure, r, view, "fct_spent", h["spent"], forecast_bands(r, "spent"), colour_name="spent"
    )
    _series(figure, r, view, "fct_spent_fixed", h["fixed"], fixed, colour_name="fixed", width=1.5)
    _series(
        figure, r, view, "fct_saved", h["saved"], forecast_bands(r, "saved"), colour_name="saved"
    )
    _origin(figure, r.origin, view)
    return _layout(figure, view, _shown(r))


def rest_chart(r: service.Result, view: View) -> go.Figure:
    figure = go.Figure()
    _series(
        figure,
        r,
        view,
        "fct_rest",
        history_totals(r)["rest"],
        forecast_bands(r, "rest"),
        colour_name="rest",
    )
    _origin(figure, r.origin, view)
    return _layout(figure, view, _shown(r))


def months_table(r: service.Result, lang: Language, names: Sequence[str]) -> html.Details:
    h = history_totals(r)
    start = max(0, len(r.history) - SHOWN_HISTORY)
    rows = [
        [i18n.month(m, lang), *(i18n.euros(h[n][start + i], lang) for n in names)]
        for i, m in enumerate(r.history[start:])
    ]
    for k, m in enumerate(r.ahead):
        cells = []
        for n in names:
            b = forecast_bands(r, n)[k]
            band = _band_text(b, lang)
            cells.append(i18n.euros(b.point, lang) + ("" if band == "—" else f" ({band})"))
        rows.append([f"{i18n.month(m, lang)} *", *cells])
    header = [t(lang, "col_month"), *(t(lang, f"fct_{n}") for n in names)]
    return views.data_table(header, rows, lang)


def band_note(r: service.Result, lang: Language) -> html.P | None:
    steps = core.Errors.of(r.forecast.total_errors["spent"])
    if steps.widened_from == 1:
        return html.P(t(lang, "fct_no_band"))
    if steps.widened_from is not None:
        return html.P(
            t(lang, "fct_widened", month=i18n.month(r.ahead[steps.widened_from - 1], lang))
        )
    return None


# Against the targets


def _table(header: Sequence[str], rows: Sequence[Sequence[str]], *, text: int = 1) -> html.Div:
    """The first `text` columns hold words, left-aligned and wrapping; the others figures."""
    cell = {"padding": "0.25rem 0.75rem", "textAlign": "right", "whiteSpace": "nowrap"}
    words = {**cell, "textAlign": "left", "whiteSpace": "normal", "minWidth": "8rem"}
    return html.Div(
        html.Table(
            [
                html.Thead(
                    html.Tr(
                        [
                            html.Th(h, style=words if i < text else cell)
                            for i, h in enumerate(header)
                        ]
                    )
                ),
                html.Tbody(
                    [
                        html.Tr(
                            [
                                html.Td(v, style=words if i < text else cell)
                                for i, v in enumerate(row)
                            ]
                        )
                        for row in rows
                    ]
                ),
            ],
            style={"borderCollapse": "collapse", "fontSize": "0.9rem"},
        ),
        style={"overflowX": "auto"},
    )


def _ranked(risk: Risk, chance: Decimal | None) -> tuple[int, Decimal]:
    order = {Risk.LIKELY: 0, Risk.POSSIBLE: 1, Risk.UNLIKELY: 2}
    return order[risk], -(chance or ZERO)


def targets(r: service.Result, lang: Language) -> list[Component]:
    month = r.ahead[0]
    rows = []
    for c in r.categories:
        target = r.target(c.id, month) if c.kind is CategoryKind.EXPENSE else None
        if target is None:
            continue
        cf = r.forecast.categories[c.id]
        b = cf.bands[0]
        risk, chance = core.against_target(b.point, cf.steps.at(1), target)
        rows.append(
            (
                _ranked(risk, chance),
                [
                    c.name,
                    i18n.euros(b.point, lang),
                    _band_text(b, lang),
                    i18n.euros(target, lang),
                    _chance(chance, lang),
                    t(lang, OVER[risk]),
                ],
            )
        )
    out: list[Component] = [
        html.H3(t(lang, "fct_targets_title")),
        html.P(t(lang, "fct_targets_intro", month=i18n.month(month, lang))),
    ]
    if not rows:
        return [*out, html.P(t(lang, "fct_no_target"))]
    header = [
        t(lang, k)
        for k in (
            "col_category",
            "col_forecast",
            "col_band",
            "col_target",
            "col_odds",
            "col_status",
        )
    ]
    out.append(_table(header, [row for _, row in sorted(rows, key=lambda p: p[0])]))
    return out


def year(r: service.Result, lang: Language) -> list[Component]:
    first = r.ahead[0]
    left = 12 - first.month + 1
    year_months = month_range(Month(first.year, 1), Month(first.year, 12))
    rows = []
    for c in r.categories:
        if c.kind is CategoryKind.INCOME:
            continue
        history = r.targets.get(c.id, [])
        in_force = [v for m in year_months if (v := target_for(history, m)) is not None]
        if not in_force:
            continue
        full = sum(in_force, ZERO)
        cf = r.forecast.categories[c.id]
        to_date = sum(
            (v for m, v in zip(r.history, cf.series.total, strict=True) if m.year == first.year),
            ZERO,
        )
        rest = r.forecast.year(c.id, left)
        point = to_date + rest.point
        whole = Band(to_date + rest.low, point, to_date + rest.high)
        errs = core.sum_errors(cf.errors, left)
        if c.kind is CategoryKind.SAVINGS:
            risk, chance = core.against_objective(point, errs, full)
            word = SHORT[risk]
        else:
            risk, chance = core.against_target(point, errs, full)
            word = OVER[risk]
        rows.append(
            (
                _ranked(risk, chance),
                [
                    c.name,
                    i18n.euros(to_date, lang),
                    i18n.euros(rest.point, lang),
                    i18n.euros(point, lang),
                    _band_text(whole, lang),
                    i18n.euros(full, lang),
                    _chance(chance, lang),
                    t(lang, word),
                ],
            )
        )
    if not rows:
        return []
    header = [
        t(lang, k)
        for k in (
            "col_category",
            "col_to_date",
            "col_to_december",
            "col_year",
            "col_band",
            "col_year_target",
            "col_odds",
            "col_status",
        )
    ]
    return [
        html.H3(t(lang, "fct_year_title", year=first.year)),
        html.P(t(lang, "fct_year_intro", origin=i18n.month(r.origin, lang))),
        _table(header, [row for _, row in sorted(rows, key=lambda p: p[0])]),
    ]


def savings(r: service.Result, lang: Language) -> list[Component]:
    month = r.ahead[0]
    rows = []
    for c in r.categories:
        objective = r.target(c.id, month) if c.kind is CategoryKind.SAVINGS else None
        if objective is None:
            continue
        cf = r.forecast.categories[c.id]
        b = cf.bands[0]
        risk, chance = core.against_objective(b.point, cf.steps.at(1), objective)
        rows.append(
            (
                _ranked(risk, chance),
                [
                    c.name,
                    i18n.euros(b.point, lang),
                    _band_text(b, lang),
                    i18n.euros(objective, lang),
                    _chance(chance, lang),
                    t(lang, SHORT[risk]),
                ],
            )
        )
    if not rows:
        return []
    header = [
        t(lang, k)
        for k in (
            "col_category",
            "col_forecast",
            "col_band",
            "col_objective",
            "col_odds",
            "col_status",
        )
    ]
    return [
        html.H3(t(lang, "fct_savings_title")),
        html.P(t(lang, "fct_savings_intro", month=i18n.month(month, lang))),
        _table(header, [row for _, row in sorted(rows, key=lambda p: p[0])]),
    ]


def income(r: service.Result, lang: Language) -> list[Component]:
    rows = []
    for c in r.categories:
        if c.kind is not CategoryKind.INCOME:
            continue
        b = r.forecast.categories[c.id].bands[0]
        rows.append([c.name, i18n.euros(b.point, lang), _band_text(b, lang)])
    if not rows:
        return []
    header = [t(lang, k) for k in ("col_category", "col_forecast", "col_band")]
    return [
        html.H3(t(lang, "fct_income_title")),
        html.P(i18n.month(r.ahead[0], lang)),
        _table(header, rows),
    ]


# What it rests on, and the back-test


def method(r: service.Result, category: UUID, lang: Language) -> str:
    choice = r.forecast.categories[category].choice
    if choice is None:
        return t(lang, "fct_m_none")
    words = t(lang, f"fct_m_{choice.model}")
    if not choice.contest:
        return t(lang, "fct_no_contest", method=words)
    if choice.model == TREES and (shares := r.contributions.get(category)):
        features = ", ".join(t(lang, f"fct_f_{name}") for name, _ in shares[:3])
        return t(lang, "fct_mostly", method=words, features=features)
    return words


def rests_on(r: service.Result, lang: Language) -> list[Component]:
    rows = []
    for c in r.categories:
        cf = r.forecast.categories[c.id]
        choice = cf.choice
        score = choice.scores.get(choice.model) if choice else None
        gain = choice.gains.get(choice.model) if choice else None
        if gain is not None and choice is not None and choice.model != BASELINE:
            versus = t(lang, "fct_better", share=i18n.percent(1 - gain, lang, places=0))
        else:
            versus = t(lang, "fct_same") if choice else "—"
        rows.append(
            [
                c.name,
                method(r, c.id, lang),
                i18n.euros(sum(cf.known, ZERO), lang),
                ratio(score.mase, lang) if score else "—",
                i18n.percent(score.wape, lang, places=0)
                if score and score.wape is not None
                else "—",
                versus,
                i18n.percent(cf.coverage, lang, places=0) if cf.coverage is not None else "—",
            ]
        )
    header = [
        t(lang, k)
        for k in (
            "col_category",
            "col_method",
            "col_known",
            "col_mase",
            "col_wape",
            "col_vs_baseline",
            "col_coverage",
        )
    ]
    return [
        html.H3(t(lang, "fct_rests_title")),
        html.P(t(lang, "fct_rests_intro")),
        _table(header, rows, text=2),
    ]


def one_ahead(r: service.Result, name: str) -> tuple[list[int], list[Decimal], list[Decimal]]:
    """The cuts, what was entered the month after each, and the total forecast for it."""
    actual = history_totals(r)[name]
    errs = r.forecast.total_errors[name]
    cuts = [c for c in core.cuts(len(r.history)) if (c, 1) in errs]
    return cuts, [actual[c] for c in cuts], [actual[c] - errs[(c, 1)] for c in cuts]


def backtest(r: service.Result, view: View) -> list[Component]:
    lang, theme = view.lang, view.theme
    figure = go.Figure()
    for name in ("income", "spent"):
        cuts, entered, forecast = one_ahead(r, name)
        x = [r.history[c].first_day() for c in cuts]
        label = t(lang, f"fct_{name}")
        hue = colour(theme, name)
        figure.add_scatter(
            x=x,
            y=[float(v) for v in entered],
            mode="lines",
            name=t(lang, "fct_entered", name=label),
            line={"width": 2, "color": hue},
            customdata=[i18n.euros(v, lang) for v in entered],
            hovertemplate=f"{t(lang, 'fct_entered', name=label)}: %{{customdata}}<extra></extra>",
        )
        figure.add_scatter(
            x=x,
            y=[float(v) for v in forecast],
            mode="lines+markers",
            name=t(lang, "fct_one_ahead", name=label),
            line={"width": 1.5, "color": hue, "dash": "dash"},
            customdata=[i18n.euros(v, lang) for v in forecast],
            hovertemplate=f"{t(lang, 'fct_one_ahead', name=label)}: %{{customdata}}<extra></extra>",
        )
    actuals = history_totals(r)
    rows = []
    for name in TOTALS:
        errs = r.forecast.total_errors[name]
        actual = actuals[name]
        forecasts: dict[int, list[Decimal]] = {}
        for (c, k), e in sorted(errs.items()):
            forecasts.setdefault(c, []).append(actual[c + k - 1] - e)
        s = core.score(actual, forecasts)
        rows.append(
            [
                t(lang, f"fct_{name}"),
                ratio(s.mase, lang) if s else "—",
                i18n.percent(s.wape, lang, places=0) if s and s.wape is not None else "—",
                ratio(s.rmsse, lang) if s else "—",
            ]
        )
    header = [t(lang, k) for k in ("col_total", "col_mase", "col_wape", "col_rmsse")]
    table_rows = []
    for name in ("income", "spent"):
        cuts, entered, forecast = one_ahead(r, name)
        for c, a, b in zip(cuts, entered, forecast, strict=True):
            table_rows.append(
                [
                    i18n.month(r.history[c], lang),
                    t(lang, f"fct_{name}"),
                    i18n.euros(a, lang),
                    i18n.euros(b, lang),
                ]
            )
    return [
        html.H3(t(lang, "fct_backtest_title")),
        html.P(t(lang, "fct_backtest_intro")),
        dcc.Graph(
            figure=_layout(figure, view, [r.history[c] for c in core.cuts(len(r.history))]),
            config=GRAPH,
            style={"height": "22rem"},
        ),
        views.data_table(
            [
                t(lang, "col_month"),
                t(lang, "col_total"),
                t(lang, "col_entered"),
                t(lang, "col_one_ahead"),
            ],
            table_rows,
            lang,
        ),
        _table(header, rows),
    ]


def limits(r: service.Result, lang: Language) -> html.Div:
    return html.Div(
        [
            html.P(t(lang, "fct_disclaimer")),
            html.H3(t(lang, "limits_title")),
            html.Ul([html.Li(t(lang, k)) for k in LIMITS]),
            html.P(
                t(
                    lang,
                    "fct_engine",
                    cuts=len(core.cuts(len(r.history))),
                    n=len(r.history),
                    seed=r.seed,
                    version=r.engine_version,
                ),
                style={"fontSize": "0.8rem"},
            ),
        ]
    )


def body(r: service.Result, view: View) -> list[Component]:
    lang = view.lang
    note = band_note(r, lang)
    return [
        *summary(r, lang),
        html.H3(t(lang, "fct_months_title")),
        dcc.Graph(figure=months_chart(r, view), config=GRAPH, style={"height": "26rem"}),
        months_table(r, lang, ("income", "spent", "saved")),
        *([note] if note else []),
        html.H3(t(lang, "fct_rest_title")),
        dcc.Graph(figure=rest_chart(r, view), config=GRAPH, style={"height": "20rem"}),
        months_table(r, lang, ("rest",)),
        *targets(r, lang),
        *year(r, lang),
        *savings(r, lang),
        *income(r, lang),
        *rests_on(r, lang),
        *backtest(r, view),
        limits(r, lang),
    ]


def register(app: Dash, context: Context) -> Callable[[str], html.Div]:
    @app.callback(
        Output("fct-body", "children"),
        Input("fct-trigger", "data"),
        State("url", "search"),
    )
    def update(_: object, search: str | None) -> list[Component]:
        view = view_of(search or "")
        with context.db() as db:
            viewer = context.viewer(db)
            try:
                r = service.compute(db, viewer.household_id, context.now().date())
            except service.NotEnoughHistoryError as short:
                return [html.P(t(view.lang, "fct_not_enough", n=short.months))]
        return body(r, view)

    def render(search: str) -> html.Div:
        view = view_of(search)
        theme = view.theme
        return html.Div(
            [
                dcc.Store(id="fct-trigger", data=True),
                html.P(
                    t(view.lang, "fct_intro"),
                    style={"maxWidth": "42rem", "color": tokens.rgb(theme, "muted")},
                ),
                dcc.Loading(html.Div(id="fct-body"), color=tokens.rgb(theme, "primary-600")),
            ],
            style={
                **dash_colours(theme),
                "background": tokens.rgb(theme, "bg"),
                "color": tokens.rgb(theme, "fg"),
                "minHeight": "100vh",
                "padding": "0.5rem 1rem 2rem",
                "boxSizing": "border-box",
            },
        )

    return render
