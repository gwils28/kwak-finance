"""The wealth space's Retirement tab (spec §4.13 F-RET-4): the standard of living the pensions
and the wealth give against the retirement spending, the chance that the wealth lasts, the fan
of net worth to the horizon and the monthly income once retired, their tables, the inputs and
the limits. The inputs are set under the charts, in React (Dash pages only read)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html
from dash.development.base_component import Component
from kwak_analytics import montecarlo as mc
from kwak_core import retirement as core
from kwak_core.budget import Month
from kwak_core.goals import add_months, months_between
from kwak_core.money import quantize

from kwak_api.dash import i18n, layout, tokens
from kwak_api.dash import projection_views as views
from kwak_api.dash.app import Context
from kwak_api.dash.i18n import Language, t
from kwak_api.dash.projection_views import View, view_of
from kwak_api.services import projection
from kwak_api.services import retirement as service

ONE = Decimal(1)
TENTH = Decimal("0.1")
HALF = Decimal("0.5")
LIMITS = (
    "limit_independent",
    "limit_crashes",
    "limit_inflation",
    "limit_shortfall",
    "ret_limit_pensions",
    "ret_limit_tax",
    "ret_limit_care",
    "ret_limit_household",
    "ret_limit_home",
)
MESSAGES = {
    "no_wealth": "no_wealth",
    "no_member": "ret_no_member",
    "horizon": "ret_horizon",
    "no_allocation": "no_allocation",
}


def _real(amount: Decimal, rate: Decimal, inflation: Decimal, t: int) -> Decimal:
    """An amount of today's euros growing by `rate` a year, in today's euros at month t."""
    return amount * ((ONE + rate) / (ONE + inflation)) ** (Decimal(t) / 12)


def _youngest(p: service.Plan) -> Month:
    return max(m.birth for _, m in p.members if m.birth is not None)


def pensions_at(p: service.Plan, t: int) -> Decimal:
    """The pensions received in month t, in today's euros."""
    month = add_months(p.this_month, t)
    rate = p.basis.inflation + p.settings.indexation
    return sum(
        (
            _real(m.pension, rate, p.basis.inflation, t)
            for _, m in p.members
            if m.pension_month <= month
        ),
        Decimal(0),
    )


def spending_at(p: service.Plan, t: int, costs: Sequence[Decimal]) -> Decimal:
    """The retirement spending in month t, the loans still running included, today's euros."""
    return p.spending.retirement + costs[t - 1] / (ONE + p.basis.inflation) ** (Decimal(t) / 12)


@dataclass(frozen=True)
class Living:
    """The standard of living at the household's retirement (F-RET-4) and its sentences."""

    pensions: Decimal
    withdrawal: Decimal | None
    spending: Decimal
    sentences: list[str]

    @property
    def total(self) -> Decimal | None:
        return None if self.withdrawal is None else self.pensions + self.withdrawal

    @property
    def covered(self) -> Decimal | None:
        total = self.total
        return None if total is None or not self.spending else total / self.spending


def living(p: service.Plan, result: service.Result, lang: Language) -> Living:
    at = p.retired_at
    last = max(m.pension_month for _, m in p.members)
    full = max(at, months_between(p.this_month, last))
    pensions = quantize(pensions_at(p, full))
    spending = p.spending.retirement
    month = i18n.month(p.retired, lang)
    w = result.withdrawal
    sentences: list[str] = []
    if w.nine_tenths is None:
        sentences.append(
            t(
                lang,
                "ret_living_none",
                month=month,
                pensions=i18n.money(pensions, lang),
                spending=i18n.money(spending, lang),
            )
        )
    else:
        total = pensions + w.nine_tenths
        half = pensions + (w.half or w.nine_tenths)
        covered = total / spending if spending else Decimal(0)
        sentences.append(
            t(
                lang,
                "ret_living",
                month=month,
                pensions=i18n.money(pensions, lang),
                withdrawal=i18n.money(w.nine_tenths, lang),
                total=i18n.money(total, lang),
                total_half=i18n.money(half, lang),
                spending=i18n.money(spending, lang),
                covered=i18n.percent(covered, lang, places=0),
            )
        )
    if last > p.retired:
        sentences.append(t(lang, "ret_later_pension"))
    return Living(pensions, w.nine_tenths, spending, sentences)


def _split(life: Living, view: View) -> list[Component]:
    """The pensions and the withdrawal as one bar, a mark at the spending under it."""
    lang, theme = view.lang, view.theme
    dark = theme == "dark"
    parts = [
        (life.pensions, "ret_split_pensions", "primary-400" if dark else "primary-600", "surface"),
        (
            life.withdrawal or Decimal(0),
            "ret_split_withdrawal",
            "primary-700" if dark else "primary-300",
            "fg",
        ),
    ]
    total = sum((v for v, *_ in parts), Decimal(0))
    if not total:
        return []
    bar = html.Div(
        [
            html.Div(
                t(lang, key, amount=i18n.money(v, lang)),
                style={
                    "flex": f"{v} 1 0",
                    "background": tokens.rgb(theme, fill),
                    "color": tokens.rgb(theme, ink),
                },
            )
            for v, key, fill, ink in parts
            if v
        ],
        className="kw-split",
    )
    at = min(life.spending / total, Decimal(1)) * 100
    mark = html.Div(
        html.Span(
            t(lang, "ret_against", amount=i18n.money(life.spending, lang)),
            style={"left": f"{at:.1f}%"},
        ),
        className="kw-against",
    )
    return [bar, mark]


def tiles(p: service.Plan, result: service.Result, view: View) -> html.Div:
    lang = view.lang
    life = living(p, result, lang)
    total, covered = life.total, life.covered
    outcome = result.outcome
    chance = Decimal(1) - outcome.shortfall_share()
    lasting = lasts(p, outcome, lang)
    return layout.tiles(
        layout.tile(
            t(lang, "ret_tile_living", month=i18n.month(p.retired, lang)),
            t(
                lang,
                "ret_per_month",
                amount=i18n.money(total if total is not None else life.pensions, lang),
            ),
            body=_split(life, view),
            note=" ".join(life.sentences),
            wide=True,
        ),
        layout.tile(
            t(lang, "ret_tile_covered"),
            "—" if covered is None else i18n.percent(covered, lang, places=0),
            chips=[]
            if covered is None
            else [
                layout.chip("ok", t(lang, "ret_covered"))
                if covered >= 1
                else layout.chip("over", t(lang, "ret_short"))
            ],
        ),
        layout.tile(
            t(lang, "ret_tile_lasts"),
            i18n.chance(chance, lang),
            note=" ".join(lasting),
        ),
    )


def lasts(p: service.Plan, outcome: mc.Outcome, lang: Language) -> list[str]:
    youngest = _youngest(p)
    chance = Decimal(1) - outcome.shortfall_share()

    def age_by(share: Decimal) -> int | None:
        k = outcome.ran_out_by(share)
        return None if k is None else core.age(youngest, add_months(p.this_month, k))

    ten, half = age_by(TENTH), age_by(HALF)
    if ten is None:
        runs_out = t(lang, "ret_never", age=p.settings.horizon_age)
    elif half is None:
        runs_out = t(lang, "ret_runs_out_ten", ten=ten, age=p.settings.horizon_age)
    else:
        runs_out = t(lang, "ret_runs_out", ten=ten, half=half)
    out = [
        t(
            lang,
            "ret_lasts",
            chance=i18n.chance(chance, lang),
            month=i18n.month(p.horizon, lang),
            age=core.age(youngest, p.horizon),
        ),
        runs_out,
    ]
    if outcome.shortfall_share():
        out.append(t(lang, "ret_shortfall_after"))
    return out


def _marker(figure: go.Figure, month: Month, label: str, theme: tokens.Theme, row: int = 0) -> None:
    """A dotted vertical line with its label (Plotly's add_vline cannot label a date axis)."""
    x = month.first_day()
    colour = tokens.rgb(theme, "neutral-500")
    figure.add_shape(
        type="line",
        x0=x,
        x1=x,
        y0=0,
        y1=1,
        yref="paper",
        line={"dash": "dot", "width": 1.5, "color": colour},
    )
    figure.add_annotation(
        x=x,
        y=1 - 0.07 * row,  # one row per label, so close months do not overlap
        yref="paper",
        text=label,
        showarrow=False,
        xanchor="left",
        yanchor="top",
        font={"color": tokens.rgb(theme, "muted")},
    )


def fan(p: service.Plan, run: projection.Run, view: View) -> go.Figure:
    """The projection's fan to the horizon, the liquid holdings' median, the retirement and
    each pension's start marked."""
    lang, theme = view.lang, view.theme
    scenario = views.Scenario(t(lang, "base"), run, projection.BASE)
    figure = views.fan([scenario], p.this_month, today=True, view=view)
    liquid = run.outcome.liquid_medians()
    figure.add_scatter(
        x=[add_months(p.this_month, k).first_day() for k in range(len(liquid))],
        y=[float(v) for v in liquid],
        mode="lines",
        line={"width": 2, "color": tokens.rgb(theme, "secondary-500")},
        name=t(lang, "ret_liquid"),
        customdata=[i18n.money(v, lang) for v in liquid],
        hovertemplate=f"{t(lang, 'ret_liquid')}: %{{customdata}}<extra></extra>",
    )
    _marker(figure, p.retired, t(lang, "ret_retires"), theme)
    later = [(name, m) for name, m in p.members if m.pension_month != p.retired]
    for row, (name, m) in enumerate(later, start=1):
        _marker(figure, m.pension_month, t(lang, "ret_pension_of", name=name), theme, row)
    return figure


def _income(
    p: service.Plan, withdrawal: Decimal | None
) -> tuple[list[int], list[Decimal], list[Decimal], list[Decimal]]:
    months = len(p.scenario.savings)
    costs = core.debt_costs(
        [core.Debt(owed, p.basis.debts[k]) for k, owed in p.basis.start.debts.items()], months
    )
    ts = list(range(p.retired_at, months + 1))
    pensions = [pensions_at(p, k) for k in ts]
    paid = [withdrawal or Decimal(0)] * len(ts)
    spending = [spending_at(p, k, costs) for k in ts]
    return ts, pensions, paid, spending


def income(p: service.Plan, result: service.Result, view: View) -> go.Figure:
    """From the retirement: the pensions stacked with the sustainable withdrawal, the
    retirement spending as a line (spec §7's colours)."""
    lang, theme = view.lang, view.theme
    dark = theme == "dark"
    ts, pensions, paid, spending = _income(p, result.withdrawal.nine_tenths)
    x = [add_months(p.this_month, k).first_day() for k in ts]
    figure = go.Figure()
    edge = {"width": 1, "color": tokens.rgb(theme, "surface")}
    for values, key, colour in (
        (pensions, "ret_pensions", "primary-400" if dark else "primary-600"),
        (paid, "ret_withdrawal", "primary-700" if dark else "primary-300"),
    ):
        figure.add_scatter(
            x=x,
            y=[float(v) for v in values],
            mode="lines",
            stackgroup="income",
            line=edge,
            fillcolor=tokens.rgb(theme, colour),
            name=t(lang, key),
            customdata=[i18n.money(v, lang) for v in values],
            hovertemplate=f"{t(lang, key)}: %{{customdata}}<extra></extra>",
        )
    figure.add_scatter(
        x=x,
        y=[float(v) for v in spending],
        mode="lines",
        line={"width": 2, "color": tokens.rgb(theme, "fg")},
        name=t(lang, "ret_spending"),
        customdata=[i18n.money(v, lang) for v in spending],
        hovertemplate=f"{t(lang, 'ret_spending')}: %{{customdata}}<extra></extra>",
    )
    views.chart_layout(figure, view, y_title=t(lang, "ret_income_axis"))
    figure.update_layout(hovermode="x unified", legend={"traceorder": "normal"})
    return figure


def income_table(p: service.Plan, result: service.Result, lang: Language) -> html.Details:
    ts, pensions, paid, spending = _income(p, result.withdrawal.nine_tenths)
    rows = [k for k in range(0, len(ts), 12)]
    if rows[-1] != len(ts) - 1:
        rows.append(len(ts) - 1)
    return views.data_table(
        [
            t(lang, "col_month"),
            t(lang, "ret_pensions"),
            t(lang, "ret_withdrawal"),
            t(lang, "ret_spending"),
        ],
        [
            [
                i18n.month(add_months(p.this_month, ts[k]), lang),
                i18n.money(pensions[k], lang),
                i18n.money(paid[k], lang),
                i18n.money(spending[k], lang),
            ]
            for k in rows
        ],
        lang,
    )


def inputs(p: service.Plan, view: View) -> html.Section:
    lang = view.lang
    people = []
    for name, m in p.members:
        assert m.birth is not None  # noqa: S101 - counted members have one
        people.append(
            html.Div(
                [
                    html.B(name),
                    html.P(
                        t(
                            lang,
                            "ret_input_member",
                            name=name,
                            birth=i18n.month(m.birth, lang),
                            retirement=i18n.month(m.retirement, lang),
                            age=core.age(m.birth, m.retirement),
                            earnings=i18n.money(m.earnings, lang),
                            pension=i18n.money(m.pension, lang),
                            pension_month=i18n.month(m.pension_month, lang),
                            pension_age=core.age(m.birth, m.pension_month),
                        )
                    ),
                ],
                className="kw-person",
                style={"borderLeft": f"4px solid {_hue(p, name, view.theme)}"},
            )
        )
    s = p.spending
    how = (
        t(lang, "ret_how_amount")
        if p.settings.share is None
        else t(
            lang,
            "ret_how_share",
            share=i18n.percent(p.settings.share, lang, places=0),
            base=i18n.money(s.base, lang),
            months=s.months,
        )
    )
    items = [
        html.Li(t(lang, "ret_input_spending", amount=i18n.money(s.retirement, lang), how=how)),
        html.Li(
            t(
                lang,
                "ret_input_indexation",
                rate=i18n.percent(p.settings.indexation, lang),
            )
        ),
        html.Li(
            t(
                lang,
                "ret_input_horizon",
                month=i18n.month(p.horizon, lang),
                age=p.settings.horizon_age,
            )
        ),
    ]
    if p.left_out:
        items.append(html.Li(t(lang, "ret_left_out", names=", ".join(p.left_out))))
    items.append(html.Li(t(lang, "ret_scope")))
    return layout.card(
        "ret-inputs",
        t(lang, "ret_inputs_title"),
        None,
        html.Div(people, className="kw-people"),
        html.Ul(items, className="kw-lede"),
    )


def limits(lang: Language) -> html.Details:
    return layout.fold(
        t(lang, "limits_title"),
        t(lang, "ret_limits_hint"),
        html.Ul([html.Li(t(lang, k)) for k in LIMITS]),
    )


PEOPLE = ("wealth-stocks", "wealth-crypto")
"""The members' hues on the timeline, from the categorical set (spec §7)."""


def _hue(p: service.Plan, name: str, theme: tokens.Theme = "light") -> str:
    k = [n for n, _ in p.members].index(name)
    return tokens.rgb(theme, PEOPLE[k % len(PEOPLE)])


def _year(m: Month) -> float:
    return m.year + (m.month - 1) / 12


def timeline(p: service.Plan, view: View) -> html.Section:
    """Each member's working months then pension to the horizon, today, each retirement and
    the horizon marked (F-RET-4)."""
    lang, theme = view.lang, view.theme
    start, end = p.this_month.year - 6, p.horizon.year + 1

    def at(m: Month) -> str:
        return f"{100 * (_year(m) - start) / (end - start):.2f}%"

    rows = []
    for k, (name, m) in enumerate(p.members):
        hue = PEOPLE[k % len(PEOPLE)]
        style = {"--kw-hue": tokens.rgb(theme, hue)}
        segments = []
        if m.retirement > p.this_month:
            segments.append(
                html.Div(
                    t(lang, "ret_working", amount=i18n.money(m.earnings, lang)),
                    className="kw-segment",
                    style={
                        **style,
                        "left": 0,
                        "right": f"calc(100% - {at(m.retirement)})",
                        "background": tokens.rgba(theme, hue, 0.15),
                    },
                )
            )
        segments.append(
            html.Div(
                t(lang, "ret_pension_segment", amount=i18n.money(m.pension, lang)),
                className="kw-segment",
                style={
                    **style,
                    "left": at(max(m.pension_month, p.this_month)),
                    "right": f"calc(100% - {at(p.horizon)})",
                    "background": tokens.rgba(theme, hue, 0.5),
                },
            )
        )
        rows.append(
            html.Div(
                [html.B(name), html.Div(segments, className="kw-track")], className="kw-life-row"
            )
        )
    youngest = max(p.members, key=lambda nm: nm[1].birth or p.this_month)
    marks = [
        html.Div(
            html.Span(t(lang, "ret_today")),
            className="kw-at kw-now",
            style={"left": at(p.this_month)},
        )
    ]
    for k, (name, m) in enumerate(p.members):
        assert m.birth is not None  # noqa: S101 - counted members have one
        if m.retirement > p.this_month:
            marks.append(
                html.Div(
                    html.Span(
                        t(lang, "ret_retires_at", name=name, age=core.age(m.birth, m.retirement))
                    ),
                    className="kw-at kw-mid kw-low" if k % 2 == 0 else "kw-at kw-mid",
                    style={"left": at(m.retirement)},
                )
            )
    assert youngest[1].birth is not None  # noqa: S101
    marks.append(
        html.Div(
            html.Span(
                t(
                    lang,
                    "ret_horizon_at",
                    name=youngest[0],
                    age=core.age(youngest[1].birth, p.horizon),
                )
            ),
            className="kw-at kw-end",
            style={"left": at(p.horizon)},
        )
    )
    years = [y for y in range(start, end + 1) if y % 10 == 0]
    marks.append(
        html.Div(
            [
                html.Span(str(y), style={"left": f"{100 * (y - start) / (end - start):.2f}%"})
                for y in years
            ],
            className="kw-years",
        )
    )
    return layout.card(
        "ret-life",
        t(lang, "ret_life_title"),
        t(lang, "ret_life_lede"),
        html.Div([*rows, html.Div(marks, className="kw-marks")], className="kw-life"),
    )


def body(p: service.Plan, result: service.Result, view: View) -> list[Component]:
    lang = view.lang
    run = projection.Run(p.scenario, result.outcome)
    return [
        layout.jump(
            [
                ("ret-life", t(lang, "ret_jump_life")),
                ("ret-income", t(lang, "ret_jump_income")),
                ("ret-fan", t(lang, "ret_jump_fan")),
                ("ret-inputs", t(lang, "ret_jump_inputs")),
            ]
        ),
        tiles(p, result, view),
        *(
            [layout.callout(t(lang, "ret_model"), info=True)]
            if result.withdrawal.nine_tenths
            else []
        ),
        layout.grid(
            timeline(p, view),
            layout.card(
                "ret-income",
                t(lang, "ret_income_title"),
                t(lang, "ret_income_lede"),
                layout.graph("ret-income-chart", income(p, result, view), height="22rem"),
                income_table(p, result, lang),
                span="half",
            ),
            layout.card(
                "ret-fan",
                t(lang, "ret_fan_title"),
                t(lang, "ret_fan_lede"),
                layout.graph("ret-fan-chart", fan(p, run, view), height="22rem"),
                views.fan_table(
                    [views.Scenario(t(lang, "base"), run, projection.BASE)],
                    p.this_month,
                    today=True,
                    lang=lang,
                ),
                span="half",
            ),
            inputs(p, view),
            limits(lang),
        ),
        html.P(t(lang, "ret_disclaimer"), className="kw-intro"),
    ]


def register(app: Dash, context: Context) -> Callable[[str], html.Div]:
    @app.callback(
        Output("ret-body", "children"),
        Input("ret-trigger", "data"),
        State("url", "search"),
    )
    def update(_: object, search: str | None) -> list[Component]:
        view = view_of(search or "")
        with context.db() as db:
            try:
                p = service.plan(db, context.viewer(db), context.now().date())
            except service.PlanError as reason:
                return [html.P(t(view.lang, MESSAGES[str(reason)]))]
        return body(p, service.run(p), view)

    def render(search: str) -> html.Div:
        view = view_of(search)
        theme = view.theme
        return layout.page(
            theme,
            [
                dcc.Store(id="ret-trigger", data=True),
                layout.intro(t(view.lang, "ret_intro")),
                dcc.Loading(html.Div(id="ret-body"), color=tokens.rgb(theme, "primary-600")),
            ],
            extra=layout.dash_colours(theme),
        )

    return render
