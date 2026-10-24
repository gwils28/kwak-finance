"""The wealth space's Projection tab (spec §4.11 F-SIM-5): the fan of net worth over the
horizon, in the scope chosen, in today's or current euros."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html
from dash.development.base_component import Component
from kwak_analytics import montecarlo as mc
from kwak_core.budget import Month
from kwak_core.goals import add_months
from kwak_core.projection import ProjectionError
from kwak_core.visibility import Scope

from kwak_api.dash import i18n, tokens
from kwak_api.dash.app import Context
from kwak_api.dash.i18n import Language, t
from kwak_api.dash.tokens import Theme
from kwak_api.services import projection

SHORT_HISTORY = 12
"""Complete months below which the capacity misses the year's irregular costs (F-SIM-3)."""


@dataclass(frozen=True)
class View:
    lang: Language
    theme: Theme


def view_of(search: str) -> View:
    """The React route passes the app's language and theme in the query string."""
    query = parse_qs(search.removeprefix("?"))
    theme: Theme = "dark" if query.get("theme") == ["dark"] else "light"
    return View(i18n.language(query.get("lang", [""])[0]), theme)


def _label(text: str, control: Component) -> html.Label:
    return html.Label(
        [html.Span(text, style={"fontSize": "0.8rem", "fontWeight": 600}), control],
        style={"display": "flex", "flexDirection": "column", "gap": "0.25rem"},
    )


def layout(view: View) -> html.Div:
    lang, theme = view.lang, view.theme
    return html.Div(
        [
            html.P(
                t(lang, "intro"), style={"maxWidth": "42rem", "color": tokens.rgb(theme, "muted")}
            ),
            html.Div(
                [
                    _label(
                        t(lang, "scope"),
                        dcc.RadioItems(
                            id="scope",
                            options=[
                                {"label": t(lang, f"scope_{s.value}"), "value": s.value}
                                for s in (Scope.HOUSEHOLD, Scope.MINE, Scope.JOINT)
                            ],
                            value=Scope.HOUSEHOLD.value,
                            inline=True,
                            inputStyle={"marginRight": "0.25rem"},
                            labelStyle={"marginRight": "0.75rem"},
                        ),
                    ),
                    _label(
                        t(lang, "euros"),
                        dcc.RadioItems(
                            id="euros",
                            options=[
                                {"label": t(lang, "euros_today"), "value": "today"},
                                {"label": t(lang, "euros_current"), "value": "current"},
                            ],
                            value="today",
                            inline=True,
                            inputStyle={"marginRight": "0.25rem"},
                            labelStyle={"marginRight": "0.75rem"},
                        ),
                    ),
                    html.Div(
                        _label(
                            t(lang, "horizon"),
                            dcc.Slider(
                                id="horizon",
                                min=projection.MIN_YEARS,
                                max=projection.MAX_YEARS,
                                step=1,
                                value=projection.DEFAULT_YEARS,
                                marks={y: str(y) for y in (1, 10, 20, 30, 40)},
                                tooltip={"placement": "bottom"},
                            ),
                        ),
                        style={"flex": "1 1 16rem", "minWidth": "12rem"},
                    ),
                ],
                style={"display": "flex", "flexWrap": "wrap", "gap": "1.5rem", "alignItems": "end"},
            ),
            dcc.Loading(
                html.Div(
                    [
                        dcc.Graph(id="fan", config={"displaylogo": False, "responsive": True}),
                        html.Div(id="notes"),
                    ]
                ),
                color=tokens.rgb(theme, "primary-600"),
            ),
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


def dash_colours(theme: Theme) -> dict[str, str]:
    """Dash's own components (radio buttons, slider) in the app's palette rather than theirs."""
    accent = tokens.rgb(theme, "primary-400" if theme == "dark" else "primary-600")
    return {
        "accentColor": accent,
        "--Dash-Fill-Interactive-Strong": accent,
        "--Dash-Fill-Inverse-Strong": tokens.rgb(theme, "surface"),
        "--Dash-Text-Primary": tokens.rgb(theme, "fg"),
        "--Dash-Text-Strong": tokens.rgb(theme, "fg"),
        "--Dash-Text-Weak": tokens.rgb(theme, "muted"),
        "--Dash-Stroke-Strong": tokens.rgb(theme, "muted"),
        "--Dash-Stroke-Weak": tokens.rgb(theme, "border"),
        # The slider's track and marks beyond the value, the number box's frame.
        "--Dash-Text-Disabled": tokens.rgb(theme, "muted"),
        "--Dash-Fill-Disabled": tokens.rgb(theme, "neutral-600" if theme == "dark" else "border"),
        "--Dash-Fill-Primary-Active": tokens.rgb(theme, "border"),
    }


Euros = Literal["today", "current"]


def fan(outcome: mc.Outcome, start: Month, *, today: bool, view: View) -> go.Figure:
    """The median net worth and its 25-75 % and 10-90 % bands, month by month (F-SIM-5);
    colours per spec §7."""
    lang, theme = view.lang, view.theme
    dark = theme == "dark"
    rows = outcome.percentiles(today=today)
    months = [add_months(start, k) for k in range(len(rows))]
    x = [m.first_day() for m in months]
    labels = [i18n.month(m, lang) for m in months]

    def series(p: int) -> list[float]:
        return [float(r[p]) for r in rows]

    def text(p: int) -> list[str]:
        return [i18n.money(r[p], lang) for r in rows]

    outer = tokens.rgb(theme, "primary-800" if dark else "primary-200")
    inner = tokens.rgb(theme, "primary-700" if dark else "primary-300")
    figure = go.Figure()
    for low, high, colour, name in (
        (10, 90, outer, t(lang, "band_10_90")),
        (25, 75, inner, t(lang, "band_25_75")),
    ):
        figure.add_scatter(
            x=x,
            y=series(low),
            mode="lines",
            line={"width": 0},
            showlegend=False,
            legendgroup=name,
            name=f"{low} %",
            hoverinfo="skip",
        )
        figure.add_scatter(
            x=x,
            y=series(high),
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor=colour,
            legendgroup=name,
            name=name,
            hoverinfo="skip",
        )
    figure.add_scatter(
        x=x,
        y=series(50),
        mode="lines",
        line={"width": 3, "color": tokens.rgb(theme, "primary-400" if dark else "primary-600")},
        name=t(lang, "median"),
        # One label for the month, from the highest outcome to the lowest.
        customdata=list(zip(labels, *(text(p) for p in (90, 75, 50, 25, 10)), strict=True)),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>90 %: %{customdata[1]}<br>75 %: %{customdata[2]}<br>"
            f"{t(lang, 'median')}: %{{customdata[3]}}<br>25 %: %{{customdata[4]}}<br>"
            "10 %: %{customdata[5]}<extra></extra>"
        ),
    )
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
        legend={"orientation": "h", "y": -0.15, "traceorder": "reversed"},
        margin={"l": 8, "r": 8, "t": 16, "b": 8},
        xaxis={"gridcolor": grid, "tickformat": "%Y"},
        yaxis={
            "title": {"text": t(lang, "net_worth")},
            "gridcolor": grid,
            "zerolinecolor": tokens.rgb(theme, "border"),
            "tickformat": ",.0f",
            **({"ticksuffix": " €"} if lang == "fr" else {"tickprefix": "€"}),
        },
    )
    return figure


def notes(b: projection.Basis, outcome: mc.Outcome, scope: Scope, lang: Language) -> list[html.P]:
    amount = i18n.money(b.savings, lang)
    savings = (
        t(lang, "savings_set", amount=amount)
        if b.savings_set
        else t(lang, "savings_measured", amount=amount, n=b.savings_months)
    )
    if not b.savings_set and b.savings_months < SHORT_HISTORY:
        savings += " " + t(lang, "savings_short")
    if scope is not Scope.HOUSEHOLD:
        savings += " " + t(lang, "savings_household")
    engine = t(
        lang,
        "engine",
        paths=i18n.number(int(outcome.net.shape[1]), lang),
        seed=outcome.seed,
        version=mc.ENGINE_VERSION,
    )
    return [html.P(t(lang, "caption")), html.P(savings), html.P(engine)]


def _message(text: str) -> tuple[dict[str, object], list[html.P]]:
    return {"data": [], "layout": {"height": 0}}, [html.P(text)]


def register(app: Dash, context: Context) -> Callable[[str], html.Div]:
    @app.callback(
        Output("fan", "figure"),
        Output("notes", "children"),
        Input("scope", "value"),
        Input("horizon", "value"),
        Input("euros", "value"),
        State("url", "search"),
    )
    def update(
        scope: str, years: int, euros: Euros, search: str | None
    ) -> tuple[object, list[html.P]]:
        view = view_of(search or "")
        chosen = Scope(scope)
        with context.db() as db:
            viewer = context.viewer(db)
            b = projection.basis(db, viewer, chosen, context.now().date())
        if b is None:
            return _message(t(view.lang, "no_wealth"))
        try:
            outcome = projection.run(b, years=int(years))
        except ProjectionError:
            return _message(t(view.lang, "no_allocation"))
        today = euros != "current"
        return fan(outcome, b.start.month, today=today, view=view), notes(
            b, outcome, chosen, view.lang
        )

    def render(search: str) -> html.Div:
        return layout(view_of(search))

    return render
