"""A copy of the app's design tokens (`frontend/src/styles/tokens.css`) for the Dash pages,
kept equal to it by a test: the pages never use their own hex values."""

from collections.abc import Mapping
from typing import Literal

type Theme = Literal["light", "dark"]

PALETTE = {
    "neutral-50": "rgb(247 248 246)",
    "neutral-100": "rgb(236 239 235)",
    "neutral-200": "rgb(215 221 213)",
    "neutral-300": "rgb(181 190 177)",
    "neutral-400": "rgb(145 156 139)",
    "neutral-500": "rgb(104 116 99)",
    "neutral-600": "rgb(59 67 56)",
    "neutral-700": "rgb(39 45 37)",
    "neutral-800": "rgb(24 29 22)",
    "neutral-900": "rgb(15 17 13)",
    "primary-50": "rgb(243 249 240)",
    "primary-100": "rgb(228 242 222)",
    "primary-200": "rgb(201 229 189)",
    "primary-300": "rgb(159 209 138)",
    "primary-400": "rgb(115 194 81)",
    "primary-500": "rgb(84 166 48)",
    "primary-600": "rgb(65 133 35)",
    "primary-700": "rgb(46 98 24)",
    "primary-800": "rgb(36 78 18)",
    "primary-900": "rgb(27 57 14)",
    "secondary-50": "rgb(254 248 236)",
    "secondary-100": "rgb(253 240 211)",
    "secondary-200": "rgb(250 222 158)",
    "secondary-300": "rgb(247 206 110)",
    "secondary-400": "rgb(243 183 63)",
    "secondary-500": "rgb(236 156 19)",
    "secondary-600": "rgb(197 125 17)",
    "secondary-700": "rgb(155 94 13)",
    "secondary-800": "rgb(121 70 12)",
    "secondary-900": "rgb(92 51 10)",
}

LIGHT = PALETTE | {
    "bg": "rgb(247 248 246)",
    "surface": "rgb(255 255 255)",
    "fg": "rgb(15 17 13)",
    "muted": "rgb(104 116 99)",
    "border": "rgb(215 221 213)",
    "chart-grid": "rgb(215 221 213)",
    "flow-in": "rgb(47 123 168)",
    "wealth-savings": "rgb(68 131 53)",
    "wealth-current": "rgb(165 189 103)",
    "wealth-stocks": "rgb(23 98 151)",
    "wealth-crypto": "rgb(204 139 197)",
    "wealth-bonds": "rgb(0 128 167)",
    "wealth-private-equity": "rgb(218 129 136)",
    "wealth-gold": "rgb(221 172 55)",
    "wealth-real-estate": "rgb(138 69 23)",
    "wealth-equipment": "rgb(140 137 205)",
    "wealth-exotic": "rgb(74 192 185)",
    "wealth-debts": "rgb(178 57 43)",
}

DARK = PALETTE | {
    "bg": "rgb(15 17 13)",
    "surface": "rgb(24 29 22)",
    "fg": "rgb(247 248 246)",
    "muted": "rgb(145 156 139)",
    "border": "rgb(39 45 37)",
    "chart-grid": "rgb(39 45 37)",
    "flow-in": "rgb(76 155 232)",
    "wealth-savings": "rgb(68 115 43)",
    "wealth-current": "rgb(153 154 71)",
    "wealth-stocks": "rgb(62 116 180)",
    "wealth-crypto": "rgb(190 123 169)",
    "wealth-bonds": "rgb(17 114 154)",
    "wealth-private-equity": "rgb(193 83 86)",
    "wealth-gold": "rgb(191 138 0)",
    "wealth-real-estate": "rgb(153 73 0)",
    "wealth-equipment": "rgb(138 135 207)",
    "wealth-exotic": "rgb(0 144 137)",
    "wealth-debts": "rgb(189 104 85)",
}

THEMES: Mapping[Theme, Mapping[str, str]] = {"light": LIGHT, "dark": DARK}


def _channels(theme: Theme, name: str) -> str:
    return ",".join(THEMES[theme][name].removeprefix("rgb(").removesuffix(")").split())


def rgb(theme: Theme, name: str) -> str:
    """For CSS and Plotly alike, which reads only the comma-separated form."""
    return f"rgb({_channels(theme, name)})"


def rgba(theme: Theme, name: str, alpha: float) -> str:
    return f"rgba({_channels(theme, name)},{alpha})"
