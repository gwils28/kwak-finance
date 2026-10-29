"""The Spending space's Forecast tab (spec §4.14 F-FCT-6): the next twelve months by category
with their bands, against the targets, what each forecast rests on and the back-test, their
tables, the disclaimer and the limits. Nothing is set here: the page only reads."""

from calendar import monthrange
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html
from dash.development.base_component import Component
from kwak_analytics import foundation
from kwak_analytics.forecast import TREES
from kwak_core import forecast as core
from kwak_core.budget import Month, month_range, target_for
from kwak_core.categories import CategoryKind
from kwak_core.forecast import BASELINE, Band, Risk

from kwak_api.dash import i18n, layout, tokens
from kwak_api.dash import projection_views as views
from kwak_api.dash.app import Context
from kwak_api.dash.i18n import Language, t
from kwak_api.dash.projection import dash_colours, view_of
from kwak_api.dash.projection_views import View
from kwak_api.services import forecast as service

ZERO = Decimal(0)
SHOWN_HISTORY = 12
"""Months entered the chart shows before the forecast; its table shows `TABLE_HISTORY`."""
TABLE_HISTORY = 24
LIMITS = (
    "fct_limit_fixed",
    "fct_limit_bands",
    "fct_limit_change",
    "fct_limit_yearly",
    "fct_limit_euros",
    "fct_limit_prices",
)
KIND_WORD = {
    CategoryKind.EXPENSE: "expense",
    CategoryKind.INCOME: "income",
    CategoryKind.SAVINGS: "savings",
}
TOTAL_KIND = {
    "income": CategoryKind.INCOME,
    "spent": CategoryKind.EXPENSE,
    "saved": CategoryKind.SAVINGS,
}
ABOUT = Decimal("0.01")
"""Under this bias, the forecast reads as about what was entered."""
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


def summary(r: service.Result, view: View, today: date) -> html.Div:
    """The answer first (spec §7): the rest over the months, the current month so far, the
    targets at risk this month and this year, and the totals over the months."""
    lang, theme = view.lang, view.theme
    f = r.forecast
    over = {name: f.total_over(name, core.HORIZON) for name in TOTALS}
    rest = over["rest"]
    has_band = core.sum_errors(f.total_errors["rest"], core.HORIZON) is not None
    first, last = i18n.month(r.ahead[0], lang), i18n.month(r.ahead[-1], lang)
    values = {
        "first": first,
        "last": last,
        "income": i18n.euros(over["income"].point, lang),
        "spent": i18n.euros(over["spent"].point, lang),
        "saved": i18n.euros(over["saved"].point, lang),
        "rest": i18n.euros(rest.point, lang),
    }
    sentence = (
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
    month = r.ahead[0]
    if now.high > now.point and entered > now.high:
        current = t(
            lang,
            "fct_now_above",
            entered=i18n.euros(entered, lang),
            month=first,
            high=i18n.euros(now.high, lang),
        )
    else:
        current = t(
            lang,
            "fct_now",
            entered=i18n.euros(entered, lang),
            month=first,
            expected=i18n.euros(now.point, lang),
        )
    gone = (
        Decimal(today.day) / monthrange(today.year, today.month)[1]
        if (today.year, today.month) == (month.year, month.month)
        else None
    )
    share = entered / now.point if now.point > 0 else ZERO
    pace = layout.meter(
        float(share),
        float(gone) if gone is not None else None,
        tokens.rgb(theme, _token(theme, "spent")),
    )
    in_month = month_targets(r, CategoryKind.EXPENSE)
    in_year = year_targets(r)
    return layout.tiles(
        layout.tile(
            t(lang, "fct_tile_rest", first=first, last=last),
            values["rest"],
            note=sentence,
            wide=True,
        ),
        layout.tile(
            t(lang, "fct_tile_month", month=first),
            i18n.euros(entered, lang),
            note=current,
            body=[pace],
            anchor="fct-month",
        ),
        _risk_tile(t(lang, "fct_tile_targets"), in_month, lang, OVER),
        _risk_tile(t(lang, "fct_tile_year", year=month.year), in_year, lang, OVER, names=True),
        layout.tile(
            t(lang, "fct_tile_income"),
            values["income"],
            note=_per_month(over["income"].point, lang),
        ),
        layout.tile(
            t(lang, "fct_tile_spent"), values["spent"], note=_per_month(over["spent"].point, lang)
        ),
        layout.tile(
            t(lang, "fct_tile_saved"), values["saved"], note=_per_month(over["saved"].point, lang)
        ),
    )


def _per_month(total: Decimal, lang: Language) -> str:
    return t(lang, "fct_per_month", amount=i18n.euros(total / core.HORIZON, lang))


def _risk_tile(
    label: str,
    items: Sequence["Against"],
    lang: Language,
    words: Mapping[Risk, str],
    *,
    names: bool = False,
) -> html.Div:
    """How many targets are at risk, a chip per level; with no target, says so."""
    if not items:
        return layout.tile(label, "—", note=t(lang, "fct_no_target"))
    counts = {risk: [a for a in items if a.risk is risk] for risk in Risk}
    at_risk = len(counts[Risk.LIKELY]) + len(counts[Risk.POSSIBLE])
    chips = [
        layout.chip(STATUS[risk], t(lang, f"fct_count_{STATUS[risk]}", n=len(counts[risk])))
        for risk in (Risk.LIKELY, Risk.POSSIBLE)
        if counts[risk]
    ]
    if not at_risk:
        chips = [layout.chip("ok", t(lang, "fct_all_within"))]
    note = ", ".join(a.name for a in counts[Risk.LIKELY]) if names and counts[Risk.LIKELY] else None
    return layout.tile(
        label, t(lang, "fct_at_risk", n=at_risk, of=len(items)), note=note, chips=chips
    )


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
    views.chart_layout(figure, view, y_title=t(view.lang, "fct_axis"))
    figure.update_layout(hovermode="x unified", xaxis=_month_ticks(months, view.lang))
    return figure


def ratio(value: Decimal, lang: Language) -> str:
    """A MASE or RMSSE, two decimals, the decimal sign of the language."""
    text = f"{value:.2f}"
    return text.replace(".", ",") if lang == "fr" else text


def _shown(r: service.Result) -> list[Month]:
    return [*r.history[max(0, len(r.history) - SHOWN_HISTORY) :], *r.ahead]


def _month_ticks(months: Sequence[Month], lang: Language) -> dict[str, object]:
    """Month ticks in the page's language, every third month (Plotly's own are English)."""
    ticks = [m for m in months if m.month % 3 == 1]
    return {
        "tickmode": "array",
        "tickvals": _x(ticks),
        "ticktext": [i18n.month(m, lang) for m in ticks],
    }


def months_chart(r: service.Result, view: View) -> go.Figure:
    """Income and spent as lines with their bands, the fixed part as bars, and under them, on
    the same months, the rest as bars, the forecast ones lighter with their band (F-FCT-6)."""
    lang, theme = view.lang, view.theme
    figure = go.Figure()
    h = history_totals(r)
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
    start = max(0, len(r.history) - SHOWN_HISTORY)
    past = r.history[start:]
    fixed = [*h["fixed"][start:], *known_spent(r)]
    name = t(lang, "fct_spent_fixed")
    figure.add_bar(
        x=_x([*past, *r.ahead]),
        y=[float(v) for v in fixed],
        name=name,
        marker={"color": tokens.rgba(theme, _token(theme, "fixed"), 0.6)},
        customdata=[i18n.euros(v, lang) for v in fixed],
        hovertemplate=f"{name}: %{{customdata}}<extra></extra>",
    )
    rest = h["rest"][start:]
    ink = _token(theme, "rest")
    label = t(lang, "fct_rest")
    figure.add_bar(
        x=_x(past),
        y=[float(v) for v in rest],
        name=label,
        xaxis="x2",
        yaxis="y2",
        marker={"color": tokens.rgba(theme, ink, 0.75)},
        customdata=[i18n.euros(v, lang) for v in rest],
        hovertemplate=f"{label}: %{{customdata}}<extra></extra>",
    )
    bands = forecast_bands(r, "rest")
    ahead = t(lang, "fct_forecast_of", name=label)
    figure.add_bar(
        x=_x(r.ahead),
        y=[float(b.point) for b in bands],
        name=ahead,
        xaxis="x2",
        yaxis="y2",
        marker={
            "color": tokens.rgba(theme, ink, 0.25),
            "line": {"color": tokens.rgba(theme, ink, 0.75), "width": 1},
        },
        error_y={
            "type": "data",
            "symmetric": False,
            "array": [float(b.high - b.point) for b in bands],
            "arrayminus": [float(b.point - b.low) for b in bands],
            "color": tokens.rgba(theme, ink, 0.5),
            "thickness": 1,
            "width": 0,
        },
        customdata=[[i18n.euros(b.point, lang), _band_text(b, lang)] for b in bands],
        hovertemplate=f"{ahead}: %{{customdata[0]}} (%{{customdata[1]}})<extra></extra>",
    )
    _origin(figure, r.origin, view)
    views.chart_layout(figure, view, y_title="")
    axis = {
        "gridcolor": tokens.rgb(theme, "chart-grid"),
        "tickformat": ",.0f",
        **({"ticksuffix": " €"} if lang == "fr" else {"tickprefix": "€"}),
    }
    figure.update_layout(
        hovermode="x unified",
        barmode="overlay",
        bargap=0.35,
        legend={"orientation": "h", "y": 1.12, "x": 0},
        margin={"l": 8, "r": 8, "t": 40, "b": 8},
        xaxis={"anchor": "y", "showticklabels": False, "matches": "x2"},
        xaxis2={
            "anchor": "y2",
            "gridcolor": tokens.rgb(theme, "chart-grid"),
            **_month_ticks(_shown(r), lang),
        },
        yaxis={**axis, "domain": [0.42, 1], "rangemode": "tozero", "title": None},
        yaxis2={
            **axis,
            "domain": [0, 0.3],
            "zeroline": True,
            "zerolinecolor": tokens.rgb(theme, "muted"),
        },
    )
    figure.add_annotation(
        xref="paper",
        yref="paper",
        x=0,
        y=0.34,
        text=f"<b>{t(lang, 'fct_rest_of_month')}</b>",
        showarrow=False,
        xanchor="left",
    )
    return figure


def months_table(r: service.Result, lang: Language, names: Sequence[str]) -> html.Details:
    h = history_totals(r)
    start = max(0, len(r.history) - TABLE_HISTORY)
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


def _table(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    text: int = 1,
    worded: Collection[int] = (),
) -> html.Div:
    """The first `text` columns hold words, left-aligned and wrapping; the others figures,
    right-aligned and on one line, except the `worded` ones (a chance, a status, a bias), which wrap
    like the headers so the table fits its frame (issue #164)."""
    cell = {"padding": "0.25rem 0.75rem", "textAlign": "right", "whiteSpace": "nowrap"}
    wrapping = {**cell, "whiteSpace": "normal"}
    words = {**wrapping, "textAlign": "left", "minWidth": "8rem"}

    def style(i: int, head: bool) -> dict[str, str]:
        if i < text:
            return words
        return wrapping if head or i in worded else cell

    return html.Div(
        html.Table(
            [
                html.Thead(
                    html.Tr([html.Th(h, style=style(i, True)) for i, h in enumerate(header)])
                ),
                html.Tbody(
                    [
                        html.Tr([html.Td(v, style=style(i, False)) for i, v in enumerate(row)])
                        for row in rows
                    ]
                ),
            ],
            style={"borderCollapse": "collapse", "fontSize": "0.9rem"},
        ),
        style={"overflowX": "auto"},
    )


STATUS: dict[Risk, layout.Status] = {
    Risk.LIKELY: "over",
    Risk.POSSIBLE: "watch",
    Risk.UNLIKELY: "ok",
}
CAP = Decimal(160)
"""The targets chart stops at 160 % of the target: a point beyond sits on its edge."""


@dataclass(frozen=True)
class Against:
    """A category against its target or objective, this month or this year."""

    name: str
    kind: CategoryKind
    point: Decimal
    band: Band
    target: Decimal
    risk: Risk
    chance: Decimal | None
    to_date: Decimal = ZERO
    """The year only: entered to the origin; `point` less it is the forecast to December."""

    @property
    def word(self) -> str:
        return (SHORT if self.kind is CategoryKind.SAVINGS else OVER)[self.risk]

    def share(self, value: Decimal) -> Decimal:
        return 100 * value / self.target if self.target else ZERO


def _ranked(items: list[Against]) -> list[Against]:
    order = {Risk.LIKELY: 0, Risk.POSSIBLE: 1, Risk.UNLIKELY: 2}
    return sorted(items, key=lambda a: (order[a.risk], -(a.chance or ZERO)))


def month_targets(r: service.Result, kind: CategoryKind) -> list[Against]:
    """This month's expense targets (the chance of going over) or savings objectives (of
    falling short), the likeliest first."""
    month = r.ahead[0]
    out = []
    for c in r.categories:
        target = r.target(c.id, month) if c.kind is kind else None
        if target is None:
            continue
        cf = r.forecast.categories[c.id]
        b = cf.bands[0]
        check = core.against_objective if kind is CategoryKind.SAVINGS else core.against_target
        risk, chance = check(b.point, cf.steps.at(1), target)
        out.append(Against(c.name, kind, b.point, b, target, risk, chance))
    return _ranked(out)


def year_targets(r: service.Result) -> list[Against]:
    """Each target's and objective's year: to date plus the forecast to December (F-BUD-10)."""
    first = r.ahead[0]
    left = 12 - first.month + 1
    year_months = month_range(Month(first.year, 1), Month(first.year, 12))
    out = []
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
        check = core.against_objective if c.kind is CategoryKind.SAVINGS else core.against_target
        risk, chance = check(point, errs, full)
        out.append(Against(c.name, c.kind, point, whole, full, risk, chance, to_date))
    return _ranked(out)


def _row_label(a: Against, lang: Language, *, amounts: bool) -> str:
    label = f"{layout.ICONS[STATUS[a.risk]]} {a.name}"
    if amounts:
        point, target = i18n.euros(a.point, lang), i18n.euros(a.target, lang)
        label += f'  <span style="font-size:0.85em">{point} / {target}</span>'
    return label


def _percent_axis(theme: tokens.Theme, top: Decimal, step: int) -> dict[str, object]:
    return {
        "range": [0, float(top)],
        "ticksuffix": " %",
        "dtick": step,
        "fixedrange": True,
        "gridcolor": tokens.rgb(theme, "chart-grid"),
        "tickformat": "",
        "tickprefix": "",
    }


def _hundred(theme: tokens.Theme) -> dict[str, object]:
    return {
        "type": "line",
        "x0": 100,
        "x1": 100,
        "yref": "paper",
        "y0": 0,
        "y1": 1,
        "line": {"color": tokens.rgb(theme, "fg"), "width": 2},
    }


def _rows_layout(figure: go.Figure, view: View, rows: int, **extra: object) -> go.Figure:
    views.chart_layout(figure, view, y_title="")
    figure.update_layout(
        height=34 * rows + 48,
        hovermode="closest",
        showlegend=False,
        yaxis={**views.ROWS_AXIS, "fixedrange": True},
        **({"margin": {"l": 8, "r": 12, "t": 8, "b": 8}} | extra),
    )
    return figure


def targets_chart(items: Sequence[Against], view: View) -> go.Figure:
    """A row per category in percent of its target: the forecast a point, the band a bar, the
    target a line at 100 % (F-FCT-6); the likeliest overrun on top."""
    lang, theme = view.lang, view.theme
    rows = list(reversed(items))
    labels = [_row_label(a, lang, amounts=True) for a in rows]
    hues = [layout.status_token(theme, STATUS[a.risk]) for a in rows]

    def clip(v: Decimal) -> float:
        return float(min(v, CAP))

    banded = [a.band.low != a.band.high for a in rows]
    figure = go.Figure()
    figure.add_bar(
        orientation="h",
        y=labels,
        base=[clip(a.share(a.band.low)) if b else None for a, b in zip(rows, banded, strict=True)],
        x=[
            clip(a.share(a.band.high)) - clip(a.share(a.band.low)) if b else 0
            for a, b in zip(rows, banded, strict=True)
        ],
        marker={"color": [tokens.rgba(theme, h, 0.3) for h in hues]},
        width=0.45,
        hoverinfo="skip",
    )
    figure.add_scatter(
        mode="markers",
        y=labels,
        x=[clip(a.share(a.point)) for a in rows],
        marker={
            "color": [tokens.rgb(theme, h) for h in hues],
            "size": 11,
            "line": {"color": tokens.rgb(theme, "surface"), "width": 2},
        },
        customdata=[
            [
                a.name,
                i18n.euros(a.point, lang),
                i18n.euros(a.target, lang),
                _band_text(a.band, lang),
                _chance(a.chance, lang),
                t(lang, a.word),
            ]
            for a in rows
        ],
        hovertemplate=(
            f"<b>%{{customdata[0]}}</b><br>{t(lang, 'col_forecast')}: %{{customdata[1]}}"
            f"<br>{t(lang, 'col_target')}: %{{customdata[2]}}"
            f"<br>{t(lang, 'col_band')}: %{{customdata[3]}}"
            f"<br>{t(lang, 'col_odds')}: %{{customdata[4]}}<br>%{{customdata[5]}}<extra></extra>"
        ),
    )
    return _rows_layout(
        figure,
        view,
        len(rows),
        xaxis=_percent_axis(theme, CAP, 50),
        shapes=[_hundred(theme)],
    )


def _against_table(items: Sequence[Against], lang: Language, objective: bool) -> html.Details:
    header = [
        t(lang, k)
        for k in (
            "col_category",
            "col_forecast",
            "col_band",
            "col_objective" if objective else "col_target",
            "col_odds",
            "col_status",
        )
    ]
    rows = [
        [
            a.name,
            i18n.euros(a.point, lang),
            _band_text(a.band, lang),
            i18n.euros(a.target, lang),
            _chance(a.chance, lang),
            t(lang, a.word),
        ]
        for a in items
    ]
    return _folded(lang, _table(header, rows, worded=(4, 5)))


def _folded(lang: Language, table: Component) -> html.Details:
    return html.Details([html.Summary(t(lang, "show_data")), table])


def targets(r: service.Result, view: View) -> html.Section:
    lang = view.lang
    month = i18n.month(r.ahead[0], lang)
    items = month_targets(r, CategoryKind.EXPENSE)
    title = t(lang, "fct_targets_title")
    if not items:
        return layout.card(
            "fct-targets", title, None, html.P(t(lang, "fct_no_target")), span="two-thirds"
        )
    return layout.card(
        "fct-targets",
        title,
        t(lang, "fct_targets_intro", month=month) + " " + t(lang, "fct_targets_lede"),
        _legend(view, [STATUS[r_] for r_ in (Risk.LIKELY, Risk.POSSIBLE, Risk.UNLIKELY)], OVER),
        layout.graph("fct-targets-chart", targets_chart(items, view)),
        _against_table(items, lang, objective=False),
        span="two-thirds",
    )


def _legend(view: View, statuses: Sequence[layout.Status], words: Mapping[Risk, str]) -> html.Div:
    by_status = {STATUS[k]: v for k, v in words.items()}
    return html.Div(
        [layout.chip(s, t(view.lang, by_status[s]).split(" ", 1)[1]) for s in statuses],
        className="kw-chips",
    )


def year_chart(items: Sequence[Against], origin: Month, view: View) -> go.Figure:
    """A bar per category in percent of its full-year target: to date solid, the forecast to
    December lighter, the band of the year's total at its end, the target a line at 100 %."""
    lang, theme = view.lang, view.theme
    rows = list(reversed(items))
    labels = [_row_label(a, lang, amounts=False) for a in rows]
    hues = [_token(theme, "saved" if a.kind is CategoryKind.SAVINGS else "spent") for a in rows]
    top = max([Decimal(125), *(a.share(a.band.high) + 15 for a in rows)])
    figure = go.Figure()
    figure.add_bar(
        orientation="h",
        y=labels,
        x=[float(a.share(a.to_date)) for a in rows],
        name=t(lang, "fct_to_origin", month=i18n.month(origin, lang)),
        marker={"color": [tokens.rgb(theme, h) for h in hues]},
        width=0.55,
        customdata=[
            [
                a.name,
                i18n.euros(a.to_date, lang),
                i18n.euros(a.point - a.to_date, lang),
                i18n.euros(a.point, lang),
                i18n.euros(a.target, lang),
                _chance(a.chance, lang),
                t(lang, a.word),
            ]
            for a in rows
        ],
        hovertemplate=(
            f"<b>%{{customdata[0]}}</b><br>{t(lang, 'col_to_date')}: %{{customdata[1]}}"
            f"<br>{t(lang, 'col_to_december')}: %{{customdata[2]}}"
            f"<br>{t(lang, 'col_year')}: %{{customdata[3]}}"
            f"<br>{t(lang, 'col_year_target')}: %{{customdata[4]}}"
            f"<br>{t(lang, 'col_odds')}: %{{customdata[5]}}<br>%{{customdata[6]}}<extra></extra>"
        ),
    )
    banded = [a.band.low != a.band.high for a in rows]
    figure.add_bar(
        orientation="h",
        y=labels,
        x=[float(a.share(a.point - a.to_date)) for a in rows],
        name=t(lang, "col_to_december"),
        marker={
            "color": [tokens.rgba(theme, h, 0.35) for h in hues],
            "line": {"color": [tokens.rgb(theme, h) for h in hues], "width": 1},
        },
        width=0.55,
        hoverinfo="skip",
        error_x={
            "type": "data",
            "symmetric": False,
            "array": [
                float(a.share(a.band.high - a.point)) if b else 0
                for a, b in zip(rows, banded, strict=True)
            ],
            "arrayminus": [
                float(a.share(a.point - a.band.low)) if b else 0
                for a, b in zip(rows, banded, strict=True)
            ],
            "color": tokens.rgb(theme, "fg"),
            "thickness": 1.2,
            "width": 4,
        },
    )
    figure.add_scatter(
        mode="text",
        y=labels,
        # Past the band's end, so the figure never sits on its whisker.
        x=[float(min(a.share(a.band.high), top - 10)) + 3 for a in rows],
        text=[f"<b>{i18n.percent(a.point / a.target, lang, places=0)}</b>" for a in rows],
        textposition="middle right",
        hoverinfo="skip",
        cliponaxis=False,
    )
    return _rows_layout(
        figure,
        view,
        len(rows),
        barmode="stack",
        xaxis=_percent_axis(theme, top, 25),
        shapes=[_hundred(theme)],
    )


def year(r: service.Result, view: View) -> html.Section | None:
    lang = view.lang
    items = year_targets(r)
    if not items:
        return None
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
    rows = [
        [
            a.name,
            i18n.euros(a.to_date, lang),
            i18n.euros(a.point - a.to_date, lang),
            i18n.euros(a.point, lang),
            _band_text(a.band, lang),
            i18n.euros(a.target, lang),
            _chance(a.chance, lang),
            t(lang, a.word),
        ]
        for a in items
    ]
    first = r.ahead[0]
    return layout.card(
        "fct-year",
        t(lang, "fct_year_title", year=first.year),
        t(lang, "fct_year_intro", origin=i18n.month(r.origin, lang))
        + " "
        + t(lang, "fct_year_lede"),
        layout.graph("fct-year-chart", year_chart(items, r.origin, view)),
        _folded(lang, _table(header, rows, worded=(6, 7))),
    )


def income_chart(r: service.Result, view: View) -> go.Figure:
    lang, theme = view.lang, view.theme
    rows = [
        (c.name, r.forecast.categories[c.id].bands[0])
        for c in r.categories
        if c.kind is CategoryKind.INCOME
    ][::-1]
    hue = _token(theme, "income")
    figure = go.Figure()
    figure.add_bar(
        orientation="h",
        y=[name for name, _ in rows],
        x=[float(b.point) for _, b in rows],
        marker={"color": tokens.rgb(theme, hue)},
        width=0.5,
        error_x={
            "type": "data",
            "symmetric": False,
            "array": [float(b.high - b.point) for _, b in rows],
            "arrayminus": [float(b.point - b.low) for _, b in rows],
            "color": tokens.rgb(theme, "fg"),
            "thickness": 1.2,
            "width": 4,
        },
        text=[i18n.euros(b.point, lang) for _, b in rows],
        textposition="outside",
        cliponaxis=False,
        customdata=[_band_text(b, lang) for _, b in rows],
        hovertemplate="%{y}: %{text} (%{customdata})<extra></extra>",
    )
    return _rows_layout(
        figure,
        view,
        len(rows),
        xaxis={"visible": False, "fixedrange": True},
        margin={"l": 8, "r": 64, "t": 4, "b": 4},
    )


def income(r: service.Result, view: View) -> html.Section | None:
    """This month's income by category, then the savings objectives as chips."""
    lang = view.lang
    month = i18n.month(r.ahead[0], lang)
    rows = [
        [c.name, i18n.euros(b.point, lang), _band_text(b, lang)]
        for c in r.categories
        if c.kind is CategoryKind.INCOME
        for b in [r.forecast.categories[c.id].bands[0]]
    ]
    objectives = month_targets(r, CategoryKind.SAVINGS)
    if not rows and not objectives:
        return None
    body: list[Component] = []
    if rows:
        header = [t(lang, k) for k in ("col_category", "col_forecast", "col_band")]
        body += [
            layout.graph("fct-income-chart", income_chart(r, view)),
            _folded(lang, _table(header, rows)),
        ]
    if objectives:
        body += [
            html.H3(t(lang, "fct_savings_title"), style={"marginTop": "0.75rem"}),
            html.P(t(lang, "fct_savings_intro", month=month), className="kw-lede"),
            html.Div(
                [
                    layout.chip(
                        STATUS[a.risk],
                        t(
                            lang,
                            "fct_objective_chip",
                            name=a.name,
                            point=i18n.euros(a.point, lang),
                            target=i18n.euros(a.target, lang),
                            word=t(lang, a.word).split(" ", 1)[1],
                        ),
                    )
                    for a in objectives
                ],
                className="kw-chips",
            ),
            _against_table(objectives, lang, objective=True),
        ]
    return layout.card(
        "fct-income",
        t(lang, "fct_income_title"),
        t(lang, "fct_income_lede", month=month),
        *body,
        span="third",
    )


# What it rests on, and the back-test


def bias_text(bias: Decimal, kind: CategoryKind, lang: Language) -> str:
    """A bias (entered - forecast, over the amounts entered) in words, for its kind."""
    if abs(bias) < ABOUT:
        return t(lang, "fct_bias_none")
    side = "less" if bias > 0 else "more"
    share = i18n.percent(abs(bias), lang, places=0)
    return t(lang, f"fct_bias_{KIND_WORD[kind]}_{side}", share=share)


def set_aside_text(choice: core.Choice, kind: CategoryKind, lang: Language) -> str | None:
    """The candidate set aside for its optimism that erred least, when less than the one kept."""
    kept = choice.gains.get(choice.model, core.ONE)
    better = [m for m in choice.set_aside if choice.gains[m] < kept]
    if not better:
        return None
    model = min(better, key=lambda m: choice.gains[m])
    bias = choice.scores[model].bias
    assert bias is not None  # set aside on its bias  # noqa: S101
    return t(
        lang,
        "fct_set_aside",
        model=t(lang, f"fct_name_{model}")
        if model in foundation.NAMES
        else t(lang, f"fct_m_{model}"),
        share=i18n.percent(1 - choice.gains[model] / kept, lang, places=0),
        bias=bias_text(bias, kind, lang),
    )


def method(r: service.Result, category: UUID, lang: Language) -> str:
    choice = r.forecast.categories[category].choice
    if choice is None:
        return t(lang, "fct_m_none")
    words = t(lang, f"fct_m_{choice.model}")
    if not choice.contest:
        return t(lang, "fct_no_contest", method=words)
    if choice.model == TREES and (shares := r.contributions.get(category)):
        features = ", ".join(t(lang, f"fct_f_{name}") for name, _ in shares[:3])
        words = t(lang, "fct_mostly", method=words, features=features)
    aside = set_aside_text(choice, r.forecast.categories[category].series.kind, lang)
    return f"{words}. {aside}" if aside else words


def rests_on(r: service.Result, view: View) -> html.Section:
    lang = view.lang
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
                bias_text(score.bias, c.kind, lang) if score and score.bias is not None else "—",
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
            "col_bias",
            "col_coverage",
        )
    ]
    return layout.card(
        "fct-rests",
        t(lang, "fct_rests_title"),
        t(lang, "fct_rests_intro"),
        layout.graph("fct-reliability-chart", reliability_chart(r, view)),
        _folded(lang, _table(header, rows, text=2, worded=(6,))),
    )


def reliability_chart(r: service.Result, view: View) -> go.Figure:
    """Each category in a contest: how much less its method errs than the 6-month average,
    and how optimistic it was in the past months tested (to the right)."""
    lang, theme = view.lang, view.theme
    rows = []
    for c in r.categories:
        choice = r.forecast.categories[c.id].choice
        if choice is None or not choice.contest:
            continue
        score = choice.scores.get(choice.model)
        gain = 1 - choice.gains.get(choice.model, core.ONE)
        lean = core.optimism(score.bias, c.kind) if score and score.bias is not None else ZERO
        rows.append((c.name, gain, lean))
    rows.reverse()
    muted, accent = "muted", "primary-400" if theme == "dark" else "primary-600"
    warn = layout.status_token(theme, "watch")
    figure = go.Figure()
    figure.add_bar(
        orientation="h",
        y=[n for n, _, _ in rows],
        x=[float(100 * g) for _, g, _ in rows],
        marker={"color": [tokens.rgb(theme, accent if g else muted) for _, g, _ in rows]},
        width=0.55,
        text=[
            f"−{i18n.percent(g, lang, places=0)}" if g else t(lang, "fct_same")  # noqa: RUF001
            for _, g, _ in rows
        ],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}: %{text}<extra></extra>",
    )
    figure.add_bar(
        orientation="h",
        y=[n for n, _, _ in rows],
        x=[float(100 * b) for _, _, b in rows],
        xaxis="x2",
        marker={"color": [tokens.rgb(theme, warn if b > core.BIAS else muted) for _, _, b in rows]},
        width=0.55,
        customdata=[i18n.percent(b, lang, places=0) for _, _, b in rows],
        hovertemplate=f"%{{y}}: {t(lang, 'col_bias')} %{{customdata}}<extra></extra>",
    )
    side = max([Decimal(25), *(abs(b) * 100 + 5 for _, _, b in rows)])
    return _rows_layout(
        figure,
        view,
        len(rows),
        margin={"l": 8, "r": 8, "t": 28, "b": 8},
        xaxis={"domain": [0, 0.56], "range": [0, 125], "visible": False, "fixedrange": True},
        xaxis2={
            "domain": [0.66, 1],
            "range": [-float(side), float(side)],
            "ticksuffix": " %",
            "tickprefix": "",
            "tickformat": "",
            "zeroline": True,
            "zerolinecolor": tokens.rgb(theme, "fg"),
            "gridcolor": tokens.rgb(theme, "chart-grid"),
            "fixedrange": True,
        },
        annotations=[
            {
                "xref": "x",
                "yref": "paper",
                "x": 0,
                "y": 1,
                "yanchor": "bottom",
                "xanchor": "left",
                "text": t(lang, "fct_gain_axis"),
                "showarrow": False,
                "font": {"color": tokens.rgb(theme, "muted")},
            },
            {
                "xref": "x2",
                "yref": "paper",
                "x": 0,
                "y": 1,
                "yanchor": "bottom",
                "text": t(lang, "fct_bias_axis"),
                "showarrow": False,
                "font": {"color": tokens.rgb(theme, "muted")},
            },
        ],
    )


def one_ahead(r: service.Result, name: str) -> tuple[list[int], list[Decimal], list[Decimal]]:
    """The cuts, what was entered the month after each, and the total forecast for it."""
    actual = history_totals(r)[name]
    errs = r.forecast.total_errors[name]
    cuts = [c for c in core.cuts(len(r.history)) if (c, 1) in errs]
    return cuts, [actual[c] for c in cuts], [actual[c] - errs[(c, 1)] for c in cuts]


def total_bias_text(r: service.Result, name: str, lang: Language) -> str:
    """A total's bias in the back-test: a share for income, spent and saved, euros for the rest."""
    bias = r.forecast.bias(name)
    if bias is None:
        return "—"
    if name != "rest":
        return bias_text(bias.share, TOTAL_KIND[name], lang) if bias.share is not None else "—"
    if abs(bias.per_month) < 1:
        return t(lang, "fct_bias_none")
    side = "above" if bias.per_month < 0 else "below"
    return t(lang, f"fct_bias_rest_{side}", amount=i18n.euros(abs(bias.per_month), lang))


def backtest(r: service.Result, view: View) -> html.Section:
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
                total_bias_text(r, name, lang),
            ]
        )
    header = [t(lang, k) for k in ("col_total", "col_mase", "col_wape", "col_rmsse", "col_bias")]
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
    return layout.card(
        "fct-backtest",
        t(lang, "fct_backtest_title"),
        t(lang, "fct_backtest_intro"),
        layout.graph(
            "fct-backtest-chart",
            _layout(figure, view, [r.history[c] for c in core.cuts(len(r.history))]),
            height="22rem",
        ),
        _table(header, rows, worded=(4,)),
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
    )


def models_text(r: service.Result, lang: Language) -> str:
    if not r.foundation:
        return t(lang, "fct_no_models")
    models = ", ".join(
        f"{t(lang, f'fct_name_{name}')} ({revision})" for name, revision in r.foundation.items()
    )
    return t(lang, "fct_models", models=models)


def limits(r: service.Result, lang: Language) -> html.Div:
    return html.Div(
        [
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
                )
                + " "
                + models_text(r, lang),
                style={"fontSize": "0.8rem"},
            ),
        ]
    )


def body(r: service.Result, view: View, today: date) -> list[Component]:
    lang = view.lang
    note = band_note(r, lang)
    out: list[Component] = [
        layout.jump(
            [
                ("fct-month", t(lang, "fct_jump_month")),
                ("fct-months", t(lang, "fct_jump_months")),
                ("fct-targets", t(lang, "fct_jump_targets")),
                ("fct-year", t(lang, "fct_jump_year")),
                ("fct-reliable", t(lang, "fct_jump_reliable")),
            ]
        )
    ]
    if (above := r.forecast.rest_above()) is not None:
        out.append(layout.callout(t(lang, "fct_rest_warning", amount=i18n.euros(above, lang))))
    out.append(summary(r, view, today))
    cards: list[Component] = [
        layout.card(
            "fct-months",
            t(lang, "fct_months_title"),
            t(lang, "fct_months_lede"),
            layout.graph("fct-months-chart", months_chart(r, view), height="30rem"),
            *([note] if note else []),
            months_table(r, lang, ("income", "spent", "saved", "rest")),
        ),
        targets(r, view),
    ]
    if (money_in := income(r, view)) is not None:
        cards.append(money_in)
    if (the_year := year(r, view)) is not None:
        cards.append(the_year)
    cards.append(
        layout.fold(
            t(lang, "fct_reliable_title"),
            t(lang, "fct_reliable_hint"),
            layout.grid(rests_on(r, view), backtest(r, view)),
            limits(r, lang),
            anchor="fct-reliable",
        )
    )
    out += [layout.grid(*cards), html.P(t(lang, "fct_disclaimer"), className="kw-intro")]
    return out


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
        return body(r, view, context.now().date())

    def render(search: str) -> html.Div:
        view = view_of(search)
        theme = view.theme
        return layout.page(
            theme,
            [
                dcc.Store(id="fct-trigger", data=True),
                layout.intro(t(view.lang, "fct_intro")),
                dcc.Loading(html.Div(id="fct-body"), color=tokens.rgb(theme, "primary-600")),
            ],
            extra=dash_colours(theme),
        )

    return render
