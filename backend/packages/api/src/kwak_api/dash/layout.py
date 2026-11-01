"""The analysis pages' pieces (spec §7): they read top-down, the answer in tiles first, one chart
per question in a card, the method folded. The page's root sets the colours as CSS variables from
the tokens, the stylesheet (in the Dash index) lays them out, one column on a phone."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal

import plotly.graph_objects as go
from dash import dcc, html
from dash.development.base_component import Component

from kwak_api.dash import tokens
from kwak_api.dash.tokens import Theme

type Status = Literal["ok", "watch", "over"]
type Span = Literal["full", "half", "third", "two-thirds"]

ICONS: Mapping[Status, str] = {"ok": "✓", "watch": "△", "over": "▲"}
"""Each status has its icon and word, never its colour alone (spec §7)."""

GRAPH = dcc.Graph.Config(displaylogo=False, responsive=True)
"""Responsive, a chart fills its box and follows the window; Dash then ignores the figure's own
height, so every box states one (`graph`)."""

_LIGHT = {
    "bg": "bg",
    "surface": "surface",
    "fg": "fg",
    "muted": "muted",
    "border": "border",
    "soft": "neutral-100",
    "accent": "primary-600",
    "ok": "primary-600",
    "watch": "secondary-500",
    "over": "secondary-800",
    "ok-bg": "primary-100",
    "watch-bg": "secondary-100",
    "over-bg": "secondary-200",
}
_DARK = _LIGHT | {
    "soft": "neutral-700",
    "accent": "primary-400",
    "ok": "primary-400",
    "watch": "secondary-400",
    "over": "secondary-700",
    "ok-bg": "primary-900",
    "watch-bg": "secondary-900",
    "over-bg": "secondary-800",
}


_HIDDEN: dict[str, Any] = {"aria-hidden": "true"}


def _anchored(anchor: str | None) -> dict[str, Any]:
    return {"id": anchor} if anchor else {}


def status_token(theme: Theme, status: Status) -> str:
    """The token a status is drawn in, for a chart's marks."""
    return (_DARK if theme == "dark" else _LIGHT)[status]


def palette(theme: Theme) -> dict[str, str]:
    """The colours the stylesheet reads, from the month progress and budget status tokens."""
    names = _DARK if theme == "dark" else _LIGHT
    return {f"--kw-{key}": tokens.rgb(theme, name) for key, name in names.items()}


STYLESHEET = """
.kw-page { background: var(--kw-bg); color: var(--kw-fg); min-height: 100vh;
  padding: 0.5rem 1rem 2rem; box-sizing: border-box; }
.kw-page *, .kw-page *::before { box-sizing: border-box; }
.kw-intro { max-width: 42rem; color: var(--kw-muted); margin: 0.25rem 0 0.5rem; }
.kw-jump { display: flex; gap: 0.4rem; overflow-x: auto; padding: 0.25rem 0 0.75rem; }
.kw-jump a { white-space: nowrap; color: var(--kw-muted); text-decoration: none;
  border: 1px solid var(--kw-border); border-radius: 999px; padding: 0.15rem 0.7rem;
  font-size: 0.82rem; background: var(--kw-surface); }
.kw-jump a:hover { color: var(--kw-fg); border-color: var(--kw-muted); }
.kw-callout { display: flex; gap: 0.6rem; border-radius: 10px; padding: 0.6rem 0.8rem;
  background: var(--kw-watch-bg); margin-bottom: 0.75rem; }
.kw-callout.kw-info { background: var(--kw-soft); }
.kw-callout p { margin: 0; }
.kw-tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem;
  margin-bottom: 0.75rem; }
.kw-tile { background: var(--kw-surface); border: 1px solid var(--kw-border);
  border-radius: 12px; padding: 0.85rem 1rem; min-width: 0; }
.kw-tile.kw-wide { grid-column: span 2; }
.kw-label { color: var(--kw-muted); font-size: 0.82rem; margin: 0; }
.kw-value { font-size: 1.6rem; font-weight: 700; margin: 0.1rem 0;
  font-variant-numeric: tabular-nums; }
.kw-note { color: var(--kw-muted); font-size: 0.82rem; margin: 0.15rem 0 0; }
.kw-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.3rem; }
.kw-chip { display: inline-block; font-size: 0.78rem; font-weight: 600;
  padding: 0.1rem 0.55rem; border-radius: 999px; color: var(--kw-fg); }
.kw-chip.kw-ok { background: var(--kw-ok-bg); }
.kw-chip.kw-watch { background: var(--kw-watch-bg); }
.kw-chip.kw-over { background: var(--kw-over-bg); }
.kw-meter { position: relative; height: 10px; border-radius: 5px; background: var(--kw-soft);
  margin: 0.5rem 0 0.3rem; }
.kw-meter > .kw-fill { position: absolute; inset: 0 auto 0 0; border-radius: 5px; }
.kw-meter > .kw-mark { position: absolute; top: -4px; bottom: -4px; width: 2px;
  background: var(--kw-fg); }
.kw-split { display: flex; height: 34px; border-radius: 8px; overflow: hidden; gap: 2px;
  margin: 0.6rem 0 0.2rem; }
.kw-split > div { display: flex; align-items: center; padding: 0 0.6rem; color: var(--kw-surface);
  font-size: 0.82rem; font-weight: 600; white-space: nowrap; overflow: hidden; }
.kw-against { position: relative; height: 1.2rem; font-size: 0.78rem; color: var(--kw-muted); }
.kw-against > span { position: absolute; top: 0; bottom: 0; border-left: 2px solid var(--kw-fg);
  padding-left: 6px; white-space: nowrap; }
.kw-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 0.75rem; }
.kw-card { grid-column: span 12; background: var(--kw-surface); border: 1px solid var(--kw-border);
  border-radius: 12px; padding: 1rem; min-width: 0; scroll-margin-top: 0.5rem; }
.kw-card.kw-half { grid-column: span 6; }
.kw-card.kw-third { grid-column: span 4; }
.kw-card.kw-two-thirds { grid-column: span 8; }
.kw-card h3 { font-size: 1.05rem; margin: 0 0 0.15rem; }
.kw-lede { color: var(--kw-muted); font-size: 0.85rem; margin: 0 0 0.5rem; }
.kw-card details { margin-top: 0.5rem; }
.kw-card summary, .kw-fold summary { cursor: pointer; }
.kw-fold { grid-column: span 12; background: var(--kw-surface); border: 1px solid var(--kw-border);
  border-radius: 12px; padding: 0.75rem 1rem; scroll-margin-top: 0.5rem; }
.kw-fold > summary { font-weight: 600; }
.kw-fold > summary span { color: var(--kw-muted); font-weight: 400; margin-left: 0.4rem; }
.kw-fold[open] > summary { margin-bottom: 0.75rem; }
.kw-fold .kw-card { border: 0; padding: 0; }
.kw-people { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.kw-person { border: 1px solid var(--kw-border); border-radius: 10px; padding: 0.7rem 0.8rem;
  font-size: 0.88rem; }
.kw-person p { margin: 0.15rem 0 0; }
.kw-life { position: relative; margin: 1.8rem 0 1.6rem; }
.kw-life-row { display: grid; grid-template-columns: 5rem 1fr; align-items: center; gap: 0.5rem;
  margin-bottom: 0.45rem; font-size: 0.85rem; }
.kw-track { position: relative; height: 26px; }
.kw-segment { position: absolute; top: 0; bottom: 0; border-radius: 6px; display: flex;
  align-items: center; padding: 0 0.5rem; font-size: 0.78rem; white-space: nowrap;
  overflow: hidden; color: var(--kw-fg); border: 1px solid var(--kw-hue); }
.kw-marks { position: absolute; left: 5.5rem; right: 0; top: -1.6rem; bottom: -1.5rem;
  pointer-events: none; }
.kw-at { position: absolute; top: 0; bottom: 1.3rem; border-left: 1px dashed var(--kw-muted); }
.kw-at span { position: absolute; top: 0; left: 4px; font-size: 0.72rem; color: var(--kw-muted);
  white-space: nowrap; }
.kw-at.kw-end span { left: auto; right: 4px; }
.kw-at.kw-low span { top: auto; bottom: -1.2rem; }
.kw-at.kw-now { border-left: 2px solid var(--kw-accent); }
.kw-at.kw-now span { color: var(--kw-accent); font-weight: 600; }
.kw-years { position: absolute; bottom: 0; left: 0; right: 0; height: 1rem; font-size: 0.72rem;
  color: var(--kw-muted); }
.kw-years span { position: absolute; transform: translateX(-50%); }
@media (max-width: 640px) {
  .kw-page { padding: 0.5rem 0.75rem 1.5rem; }
  .kw-tiles { grid-template-columns: 1fr 1fr; }
  .kw-value { font-size: 1.3rem; }
  .kw-card.kw-half, .kw-card.kw-third, .kw-card.kw-two-thirds { grid-column: span 12; }
  .kw-people { grid-template-columns: 1fr; }
  .kw-at.kw-mid span { display: none; }
}
"""


def page(
    theme: Theme, children: Sequence[Component | str], *, extra: Mapping[str, str]
) -> html.Div:
    """A page's root: the colours for its stylesheet, and Dash's own (`extra`)."""
    return html.Div(list(children), className="kw-page", style={**palette(theme), **extra})


def intro(text: str) -> html.P:
    return html.P(text, className="kw-intro")


def jump(sections: Sequence[tuple[str, str]]) -> html.Nav:
    """Links to the page's sections, by their anchors."""
    return html.Nav(
        [html.A(label, href=f"#{anchor}") for anchor, label in sections], className="kw-jump"
    )


def chip(status: Status, word: str) -> html.Span:
    return html.Span(f"{ICONS[status]} {word}", className=f"kw-chip kw-{status}")


def tile(
    label: str,
    value: Component | str,
    *,
    note: str | None = None,
    chips: Sequence[html.Span] = (),
    body: Sequence[Component] = (),
    wide: bool = False,
    anchor: str | None = None,
) -> html.Div:
    """A figure, what it is above it, its sentence under it and its status, when it judges."""
    children: list[Component] = [
        html.P(label, className="kw-label"),
        html.P(value, className="kw-value"),
    ]
    children += body
    if note:
        children.append(html.P(note, className="kw-note"))
    if chips:
        children.append(html.Div(list(chips), className="kw-chips"))
    return html.Div(
        children,
        className="kw-tile kw-wide" if wide else "kw-tile",
        **_anchored(anchor),
    )


def tiles(*items: html.Div) -> html.Div:
    return html.Div(list(items), className="kw-tiles")


def callout(text: str, *, info: bool = False) -> html.Div:
    """A warning that changes how to read the figures, above them."""
    return html.Div(
        [html.Span("ℹ️" if info else "⚠️", **_HIDDEN), html.P(text)],  # noqa: RUF001
        className="kw-callout kw-info" if info else "kw-callout",
    )


def meter(share: float, mark: float | None, colour: str) -> html.Div:
    """A bar filled to `share` of its width, a mark at `mark` (both 0 to 1)."""
    parts: list[Component] = [
        html.Div(
            className="kw-fill",
            style={"width": f"{min(share, 1) * 100:.1f}%", "background": colour},
        )
    ]
    if mark is not None:
        parts.append(html.Div(className="kw-mark", style={"left": f"{min(mark, 1) * 100:.1f}%"}))
    return html.Div(parts, className="kw-meter")


def card(
    anchor: str, title: Component | str, lede: str | None, *body: Component, span: Span = "full"
) -> html.Section:
    """One question: its title, how to read its chart, the chart and its table."""
    head: list[Component] = [html.H3(title)]
    if lede:
        head.append(html.P(lede, className="kw-lede"))
    return html.Section(
        [*head, *body], id=anchor, className="kw-card" if span == "full" else f"kw-card kw-{span}"
    )


def graph_style(height: float) -> dict[str, str]:
    """A chart's box, for a callback that sends the figure."""
    return {"height": f"{height:g}px"}


def graph(id_: str, figure: go.Figure | None = None, *, height: str | None = None) -> dcc.Graph:
    """A chart in a box of its figure's height (a row per category), or of the `height` given
    for the charts that stretch to it."""
    if height is None:
        if figure is None or figure.layout.height is None:
            raise ValueError(f"{id_}: a chart needs its figure's height or one of its own")
        style = graph_style(figure.layout.height)
    else:
        style = {"height": height}
    if figure is None:  # a null figure breaks the component; a callback brings one
        return dcc.Graph(id=id_, config=GRAPH, style=style)
    return dcc.Graph(id=id_, figure=figure, config=GRAPH, style=style)


def grid(*items: Component) -> html.Div:
    return html.Div(list(items), className="kw-grid")


def fold(title: str, hint: str, *body: Component, anchor: str | None = None) -> html.Details:
    """The method and the limits: there to check, not read every day."""
    return html.Details(
        [html.Summary([title, html.Span(hint)]), *body],
        open=False,
        className="kw-fold",
        **_anchored(anchor),
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
