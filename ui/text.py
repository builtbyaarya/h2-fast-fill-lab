"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/text.py

What this file does
    Text helpers: real symbols and subscripts for anything shown on screen.

Where it fits in the model
    At the border between the model and the page. The h2lab package writes its
    messages in plain ASCII so the tests can match them; everything shown
    passes through pretty(), which turns degC into °C, m2 into m², T_wall into
    T<sub>wall</sub> and so on.
"""

from __future__ import annotations

import re

MDOT = '<span class="mdot">m</span>'  # m with a dot above, drawn in CSS

_PLAIN = [
    ("degC", "°C"),
    ("W/m2 K", "W/(m² K)"),
    ("W/m2K", "W/(m² K)"),
    ("kJ/kg K", "kJ/kg K"),
    ("J/kg K", "J/kg K"),
    ("kg/m3", "kg/m³"),
    ("m3/kg", "m³/kg"),
    ("mm2", "mm²"),
    ("/m2", "/m²"),
    ("/m3", "/m³"),
    (" x ", " × "),
    ("+/-", "±"),
]

# symbols whose trailing index should be a real subscript: T2, P1, h_i, m_dot ...
_SUB_UNDERSCORE = re.compile(r"\b([A-Za-z]|COP|SOC)_([A-Za-z0-9]{1,6})\b")
_SUB_DIGIT = re.compile(r"\b([TPhmuvsVU])([12eisL0])\b")


def pretty(s) -> str:
    """ASCII model text to display text with real units and subscripts (HTML)."""
    if s is None:
        return ""
    s = str(s)
    for a, b in _PLAIN:
        s = s.replace(a, b)
    s = s.replace("m_dot", MDOT).replace("ṁ", MDOT)
    s = _SUB_UNDERSCORE.sub(lambda m: f"{m.group(1)}<sub>{m.group(2)}</sub>", s)
    s = _SUB_DIGIT.sub(lambda m: f"{m.group(1)}<sub>{m.group(2)}</sub>", s)
    s = s.replace("k Ti", "k T<sub>i</sub>").replace("cv T", "c<sub>v</sub> T").replace("cp T", "c<sub>p</sub> T")
    return re.sub(r"(?<![\w.])-(?=\d)", "−", s)


def plain(s) -> str:
    """Like pretty() but with no HTML tags: for widget labels, dataframe headers and Plotly ticks."""
    return re.sub(r"</?sub>", "", pretty(s).replace(MDOT, "mass flow"))


def pct(x: float, nd: int = 2) -> str:
    """Percentages shown in a way a reader can use: tiny values become 'below 0.01%'."""
    if x != x:
        return "n/a"
    ax = abs(x)
    floor = 10 ** (-nd)
    if ax == 0.0:
        return "0%"
    if ax < floor:
        return f"below {floor:g}%"
    return f"{x:.{nd}f}%"


def num(x: float, nd: int = 1) -> str:
    return f"{x:,.{nd}f}"


def temp(T_K: float, nd: int = 1) -> str:
    return f"{T_K - 273.15:.{nd}f} °C"


def mpa(P_Pa: float, nd: int = 1) -> str:
    return f"{P_Pa / 1e6:.{nd}f} MPa"


def seconds(t: float) -> str:
    return f"{t:.0f} s"


def minus(s: str) -> str:
    """A real minus sign in front of numbers, instead of a hyphen."""
    return re.sub(r"(?<![\w.])-(?=\d)", "−", s)
