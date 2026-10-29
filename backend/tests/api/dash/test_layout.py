"""The analysis pages' pieces (spec §7): tiles, status chips, cards, folds and section links."""

from typing import Any

import plotly.graph_objects as go
import pytest
from dash import html
from kwak_api.dash import layout, tokens


def _text(component: Any) -> str:
    if isinstance(component, str):
        return component
    if isinstance(component, list | tuple):
        return " ".join(_text(c) for c in component)
    children = getattr(component, "children", None)
    return "" if children is None else _text(children)


def test_a_tile_gives_its_figure_and_the_sentence_under_it() -> None:
    tile = layout.tile("Rest, 12 months", "€12,417", note="between €6,356 and €12,417")
    assert tile.className == "kw-tile"
    assert _text(tile) == "Rest, 12 months €12,417 between €6,356 and €12,417"


def test_a_wide_tile_spans_two_columns() -> None:
    assert layout.tile("Rest", "€1", wide=True).className == "kw-tile kw-wide"


@pytest.mark.parametrize(("status", "icon"), [("ok", "✓"), ("watch", "△"), ("over", "▲")])
def test_a_chip_carries_its_icon_and_word(status: layout.Status, icon: str) -> None:
    chip = layout.chip(status, "likely over")
    assert chip.className == f"kw-chip kw-{status}"
    assert _text(chip) == f"{icon} likely over"


def test_a_card_has_its_anchor_title_and_how_to_read_it() -> None:
    card = layout.card(
        "f-year", "The year 2026", "To date plus forecast.", html.P("x"), span="half"
    )
    assert card.id == "f-year"
    assert card.className == "kw-card kw-half"
    assert _text(card) == "The year 2026 To date plus forecast. x"


def test_a_fold_is_closed_until_opened() -> None:
    fold = layout.fold("How reliable it is", "methods, back-test", html.P("x"))
    assert isinstance(fold, html.Details)
    assert not fold.open
    assert _text(fold.children[0]) == "How reliable it is methods, back-test"


def test_the_links_lead_to_the_sections() -> None:
    nav = layout.jump([("f-month", "This month"), ("f-year", "The year")])
    assert [(a.href, a.children) for a in nav.children] == [
        ("#f-month", "This month"),
        ("#f-year", "The year"),
    ]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_page_colours_come_from_the_tokens(theme: tokens.Theme) -> None:
    style = layout.palette(theme)
    copied = {tokens.rgb(theme, name) for name in tokens.THEMES[theme]}
    assert style["--kw-fg"] == tokens.rgb(theme, "fg")
    assert set(style.values()) <= copied


def test_the_stylesheet_stacks_the_cards_on_a_phone() -> None:
    assert "@media (max-width: 640px)" in layout.STYLESHEET
    assert "#" not in layout.STYLESHEET.replace("#kw", ""), "a colour outside the tokens"


def test_a_chart_is_boxed_to_its_figure_height() -> None:
    figure = go.Figure(layout={"height": 320})
    chart = layout.graph("f-rows", figure)
    assert chart.style == {"height": "320px"}, "responsive, it would take its card's height"
    assert chart.config == layout.GRAPH
    assert layout.graph("f-fan", figure, height="26rem").style == {"height": "26rem"}
    later = layout.graph("f-fan", height="26rem")  # a callback brings the figure
    assert "figure" not in later.to_plotly_json()["props"], "null, it breaks the component"


def test_a_chart_without_a_height_is_refused() -> None:
    with pytest.raises(ValueError, match="height"):
        layout.graph("f-rows", go.Figure())
