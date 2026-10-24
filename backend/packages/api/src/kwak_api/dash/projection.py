"""The wealth space's Projection tab (spec §4.11 F-SIM-5): the fan of net worth over the
horizon, in the scope chosen, in today's or current euros; the chance of reaching an amount;
the median by category; up to two what-ifs compared with the base; every chart's table, the
assumptions and the limits. What it shows is built in `projection_views`."""

from collections.abc import Callable, Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal
from urllib.parse import parse_qs
from uuid import UUID

from dash import ALL, Dash, Input, Output, State, dcc, html
from dash.development.base_component import Component
from kwak_analytics import montecarlo as mc
from kwak_core.budget import Month
from kwak_core.goals import add_months
from kwak_core.money import quantize
from kwak_core.projection import (
    Assumption,
    ProjectionError,
    check_allocation,
    check_assumption,
    check_inflation,
)
from kwak_core.visibility import Scope

from kwak_api.dash import i18n, tokens
from kwak_api.dash import projection_views as views
from kwak_api.dash.app import Context
from kwak_api.dash.i18n import Language, t
from kwak_api.dash.projection_views import View
from kwak_api.dash.tokens import Theme
from kwak_api.services import projection

SHORT_HISTORY = 12
"""Complete months below which the capacity misses the year's irregular costs (F-SIM-3)."""
WHAT_IFS = (1, 2)
HUNDRED = Decimal(100)
ROUND_TO = Decimal(10_000)
"""The amount to reach starts at twice today's net worth, to the €10,000 above."""

Euros = Literal["today", "current"]


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


GRAPH = dcc.Graph.Config(displaylogo=False, responsive=True)
"""Charts fill the height their style gives them."""
ROW = {"display": "flex", "flexWrap": "wrap", "gap": "1.5rem", "alignItems": "end"}


def _radio(id_: str, options: Sequence[tuple[str, str]], value: str) -> dcc.RadioItems:
    return dcc.RadioItems(
        id=id_,
        options=[{"label": label, "value": v} for v, label in options],
        value=value,
        inline=True,
        inputStyle={"marginRight": "0.25rem"},
        labelStyle={"marginRight": "0.75rem"},
    )


def _number(
    id_: str | dict[str, Any],
    *,
    value: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
    step: float = 1,
    width: str = "8rem",
) -> dcc.Input:
    return dcc.Input(
        id=id_,
        type="number",
        debounce=True,
        value=value,
        min=minimum,
        max=maximum,
        step=step,
        style={"width": width},
    )


def _what_if_panel(
    n: int, categories: Sequence[projection.CategoryInfo], lang: Language
) -> html.Details:
    def field(name: str) -> dict[str, object]:
        return {"type": "wi", "n": n, "field": name}

    return html.Details(
        [
            html.Summary(t(lang, "whatif", n=n), style={"fontWeight": 600}),
            dcc.Checklist(
                id=field("on"),
                options=[{"label": t(lang, "whatif_on", n=n), "value": "on"}],
                value=[],
                inputStyle={"marginRight": "0.25rem"},
            ),
            html.Div(
                [
                    _label(t(lang, "wi_savings"), _number(field("savings"))),
                    _label(t(lang, "wi_inflation"), _number(field("inflation"), step=0.1)),
                    _label(
                        t(lang, "wi_category"),
                        dcc.Dropdown(
                            id=field("category"),
                            options=[{"label": c.name, "value": str(c.id)} for c in categories],
                            style={"width": "14rem"},
                        ),
                    ),
                    _label(t(lang, "wi_return"), _number(field("ret"), step=0.1)),
                    _label(t(lang, "wi_volatility"), _number(field("volatility"), step=0.1)),
                ],
                style={**ROW, "margin": "0.5rem 0"},
            ),
            html.Span(t(lang, "wi_allocation"), style={"fontSize": "0.8rem", "fontWeight": 600}),
            html.P(t(lang, "wi_allocation_hint"), style={"margin": "0.25rem 0"}),
            html.Div(
                [
                    _label(
                        c.name,
                        _number(
                            {"type": "wi-alloc", "n": n, "cat": str(c.id)}, minimum=0, maximum=100
                        ),
                    )
                    for c in categories
                ],
                style={**ROW, "gap": "0.75rem"},
            ),
        ],
        style={"margin": "0.75rem 0"},
    )


def default_amount(b: projection.Basis | None) -> int:
    """Twice today's net worth, to the €10,000 above; €100,000 without one."""
    if b is None or b.start.net <= 0:
        return 100_000
    doubled = (b.start.net * 2 / ROUND_TO).to_integral_value(rounding="ROUND_CEILING")
    return int(doubled * ROUND_TO)


def layout(view: View, b: projection.Basis | None, this_month: Month) -> html.Div:
    lang, theme = view.lang, view.theme
    categories = b.categories if b is not None else []
    horizon_end = add_months(this_month, projection.DEFAULT_YEARS * 12)
    return html.Div(
        [
            dcc.Store(
                id="basis",
                data={
                    "start": str(this_month),
                    "inflation": str(b.inflation if b is not None else 0),
                },
            ),
            html.P(
                t(lang, "intro"), style={"maxWidth": "42rem", "color": tokens.rgb(theme, "muted")}
            ),
            html.Div(
                [
                    _label(
                        t(lang, "scope"),
                        _radio(
                            "scope",
                            [
                                (s.value, t(lang, f"scope_{s.value}"))
                                for s in (Scope.HOUSEHOLD, Scope.MINE, Scope.JOINT)
                            ],
                            Scope.HOUSEHOLD.value,
                        ),
                    ),
                    _label(
                        t(lang, "euros"),
                        _radio(
                            "euros",
                            [
                                ("today", t(lang, "euros_today")),
                                ("current", t(lang, "euros_current")),
                            ],
                            "today",
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
                style=ROW,
            ),
            html.H3(t(lang, "reach_title")),
            html.Div(
                [
                    _label(
                        t(lang, "amount"),
                        _number(
                            "amount", value=default_amount(b), minimum=0, step=1000, width="11rem"
                        ),
                    ),
                    _label(
                        t(lang, "reach_month"),
                        dcc.Dropdown(
                            id="reach-month",
                            options=[
                                {"label": i18n.MONTHS[lang][m - 1], "value": m}
                                for m in range(1, 13)
                            ],
                            value=horizon_end.month,
                            clearable=False,
                            style={"width": "8rem"},
                        ),
                    ),
                    _label(
                        t(lang, "reach_year"),
                        dcc.Dropdown(
                            id="reach-year",
                            options=[this_month.year + k for k in range(projection.MAX_YEARS + 1)],
                            value=horizon_end.year,
                            clearable=False,
                            style={"width": "7rem"},
                        ),
                    ),
                ],
                style=ROW,
            ),
            html.H3(t(lang, "whatifs_title")),
            html.P(t(lang, "whatifs_intro"), style={"color": tokens.rgb(theme, "muted")}),
            *(_what_if_panel(n, categories, lang) for n in WHAT_IFS),
            dcc.Loading(
                html.Div(
                    [
                        html.Div(id="invalid", style={"color": tokens.rgb(theme, "fg")}),
                        dcc.Graph(id="fan", config=GRAPH, style={"height": "30rem"}),
                        html.Div(id="fan-after"),
                        html.H3(id="categories-title"),
                        dcc.Graph(id="categories", config=GRAPH, style={"height": "26rem"}),
                        html.Div(id="categories-after"),
                        html.Div(id="compare"),
                        html.Div(id="about"),
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


class WhatIfError(ValueError):
    """A what-if the page cannot run: its reason's key."""


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def what_if(fields: Mapping[str, Any], allocation: Mapping[UUID, Any]) -> projection.WhatIf:
    """A what-if from its controls (percentages as typed, 6.5 for 6.5 %); raises `WhatIfError`."""
    savings = _decimal(fields.get("savings"))
    inflation = _decimal(fields.get("inflation"))
    ret, volatility = _decimal(fields.get("ret")), _decimal(fields.get("volatility"))
    category = fields.get("category")
    assumptions: dict[UUID, Assumption] = {}
    if category and (ret is not None or volatility is not None):
        assumptions[UUID(category)] = Assumption(
            ret / HUNDRED if ret is not None else Decimal(0),
            volatility / HUNDRED if volatility is not None else Decimal(0),
        )
    try:
        for a in assumptions.values():
            check_assumption(a)
    except ProjectionError:
        raise WhatIfError("reason_assumption") from None
    if inflation is not None:
        try:
            check_inflation(inflation / HUNDRED)
        except ProjectionError:
            raise WhatIfError("reason_inflation") from None
    shares: dict[UUID, int] | None = None
    typed = {k: _decimal(v) for k, v in allocation.items()}
    if any(v is not None for v in typed.values()):
        if any(v is not None and v != v.to_integral_value() for v in typed.values()):
            raise WhatIfError("reason_allocation")
        shares = {k: int(v) for k, v in typed.items() if v is not None}
        try:
            check_allocation(shares)
        except ProjectionError:
            raise WhatIfError("reason_allocation") from None
    return projection.WhatIf(
        savings=None if savings is None else quantize(savings),
        allocation=shares,
        assumptions=assumptions,
        inflation=None if inflation is None else inflation / HUNDRED,
    )


def _month_index(start: Month, year: int, month: int) -> int:
    return max(0, (year - start.year) * 12 + month - start.month)


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


EMPTY: dict[str, object] = {"data": [], "layout": {"height": 0}}


def _grouped(
    ids: Sequence[Mapping[str, Any]], values: Sequence[Any], key: str
) -> dict[int, dict[Any, Any]]:
    out: dict[int, dict[Any, Any]] = {}
    for i, v in zip(ids, values, strict=True):
        out.setdefault(i["n"], {})[i[key]] = v
    return out


def register(app: Dash, context: Context) -> Callable[[str], html.Div]:
    @app.callback(
        Output("amount", "value"),
        Input("euros", "value"),
        State("amount", "value"),
        State("reach-year", "value"),
        State("reach-month", "value"),
        State("basis", "data"),
        prevent_initial_call=True,
    )
    def convert(
        euros: Euros, amount: object, year: int, month: int, basis: dict[str, str]
    ) -> object:
        """The amount follows the toggle, so its chance does not change (F-SIM-5)."""
        value = _decimal(amount)
        if value is None:
            return amount
        start = Month.parse(basis["start"])
        if start is None:
            return amount
        k = _month_index(start, year, month)
        factor = (1 + Decimal(basis["inflation"])) ** (Decimal(k) / 12)
        converted = value * factor if euros == "current" else value / factor
        # To the nearest €100, as the page's amounts.
        return int((converted / HUNDRED).quantize(Decimal(1), rounding=ROUND_HALF_UP) * HUNDRED)

    @app.callback(
        Output("invalid", "children"),
        Output("fan", "figure"),
        Output("fan-after", "children"),
        Output("categories-title", "children"),
        Output("categories", "figure"),
        Output("categories-after", "children"),
        Output("compare", "children"),
        Output("about", "children"),
        Input("scope", "value"),
        Input("horizon", "value"),
        Input("euros", "value"),
        Input("amount", "value"),
        Input("reach-year", "value"),
        Input("reach-month", "value"),
        Input({"type": "wi", "n": ALL, "field": ALL}, "value"),
        Input({"type": "wi-alloc", "n": ALL, "cat": ALL}, "value"),
        State({"type": "wi", "n": ALL, "field": ALL}, "id"),
        State({"type": "wi-alloc", "n": ALL, "cat": ALL}, "id"),
        State("url", "search"),
    )
    def update(
        scope: str,
        years: int,
        euros: Euros,
        amount: object,
        year: int,
        month: int,
        wi_values: list[Any],
        alloc_values: list[Any],
        wi_ids: list[dict[str, Any]],
        alloc_ids: list[dict[str, Any]],
        search: str | None,
    ) -> tuple[object, ...]:
        view = view_of(search or "")
        lang = view.lang
        chosen = Scope(scope)
        with context.db() as db:
            b = projection.basis(db, context.viewer(db), chosen, context.now().date())
        if b is None:
            return None, EMPTY, [html.P(t(lang, "no_wealth"))], None, EMPTY, None, None, None
        fields = _grouped(wi_ids, wi_values, "field")
        allocations = _grouped(alloc_ids, alloc_values, "cat")
        what_ifs: list[tuple[str, projection.WhatIf]] = []
        invalid: list[html.P] = []
        for n in WHAT_IFS:
            f = fields.get(n, {})
            if "on" not in (f.get("on") or []):
                continue
            try:
                parsed = what_if(f, {UUID(k): v for k, v in allocations.get(n, {}).items()})
            except WhatIfError as reason:
                invalid.append(html.P(t(lang, "wi_invalid", n=n, reason=t(lang, str(reason)))))
                continue
            what_ifs.append((t(lang, "whatif", n=n), parsed))
        try:
            scenarios = [
                views.Scenario(
                    t(lang, "base"), projection.run(b, years=int(years)), projection.BASE
                ),
                *(
                    views.Scenario(name, projection.run(b, years=int(years), what_if=w), w)
                    for name, w in what_ifs
                ),
            ]
        except ProjectionError:
            return None, EMPTY, [html.P(t(lang, "no_allocation"))], None, EMPTY, None, None, None
        today = euros != "current"
        start = b.start.month
        value = _decimal(amount)
        target = (
            views.Target(value, _month_index(start, year, month)) if value is not None else None
        )
        base = scenarios[0].run
        categories = [views.CategoryInfo(c.id, c.name, c.colour) for c in b.categories]
        fan_after: list[Component] = [views.fan_table(scenarios, start, today=today, lang=lang)]
        fan_after += notes(b, base.outcome, chosen, lang)
        fan_after += (
            views.reach(base, target, start, today=today, lang=lang)
            if target is not None
            else [html.P(t(lang, "amount_missing"))]
        )
        shortfall = views.shortfall_note(base, lang)
        if shortfall is not None:
            fan_after.append(shortfall)
        categories_after: list[Component] = [
            html.P(t(lang, "by_category_note")),
            views.category_table(base, categories, start, today=today, lang=lang),
        ]
        if shortfall is not None:
            categories_after.append(shortfall)
        return (
            invalid,
            views.fan(scenarios, start, today=today, view=view, target=target),
            fan_after,
            t(lang, "by_category_title"),
            views.by_category(base, categories, start, today=today, view=view),
            categories_after,
            views.comparison(scenarios, start, today=today, lang=lang, target=target),
            [views.assumptions(b, scenarios, lang), views.limits(lang)],
        )

    def render(search: str) -> html.Div:
        with context.db() as db:
            now = context.now().date()
            b = projection.basis(db, context.viewer(db), Scope.HOUSEHOLD, now)
        return layout(view_of(search), b, Month.of(now))

    return render
