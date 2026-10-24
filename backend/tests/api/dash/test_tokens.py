"""The Dash pages' colours are a copy of the app's design tokens (ARCHITECTURE, spec §7)."""

import re
from pathlib import Path

import pytest
from kwak_api.dash import tokens

CSS = Path(__file__).parents[4] / "frontend" / "src" / "styles" / "tokens.css"
DARK = ':root[data-theme="dark"] {'
DECLARATION = re.compile(r"--color-([a-z0-9-]+):\s*([^;]+);")
VAR = re.compile(r"var\(--color-([a-z0-9-]+)\)")


def _declared(css: str) -> dict[str, str]:
    return {name: value.strip() for name, value in DECLARATION.findall(css)}


def _themes() -> dict[str, dict[str, str]]:
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(), flags=re.DOTALL)
    start = css.index(DARK)
    dark_block = css[start : css.index("\n  }", start)]
    light = _declared(css[:start] + css[start + len(dark_block) :])
    return {"light": light, "dark": light | _declared(dark_block)}


def _resolve(theme: dict[str, str], name: str) -> str:
    value = theme[name]
    match = VAR.fullmatch(value)
    if match:
        return _resolve(theme, match.group(1))
    return "rgb(255 255 255)" if value == "#fff" else value


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_colour_equals_its_css_token(theme: str) -> None:
    css = _themes()[theme]
    copy = tokens.THEMES[theme]
    assert {name: _resolve(css, name) for name in copy} == copy


def test_every_wealth_colour_is_copied() -> None:
    names = {n for n in _themes()["light"] if n.startswith("wealth-")}
    assert names <= set(tokens.THEMES["light"])


def test_plotly_takes_comma_separated_rgb() -> None:
    assert tokens.rgb("dark", "primary-400") == "rgb(115,194,81)"
    assert tokens.rgba("light", "primary-600", 0.5) == "rgba(65,133,35,0.5)"
