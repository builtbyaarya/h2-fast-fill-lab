"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/styles.py

What this file does
    Loads the stylesheet and offers the few HTML building blocks the pages
    share (cards, stat tiles, label and value rows, the page title).

Where it fits in the model
    Looks only. The look itself is in assets/app.css: background #F5F5F7,
    white cards with an 18 px radius, ink #1D1D1F, secondary #6E6E73,
    hairlines #D2D2D7, one accent #0071E3 and red only for exceeded limits.
    Page titles use Instrument Serif, everything else Instrument Sans (both
    bundled in static/).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

BG = "#F5F5F7"
CARD = "#FFFFFF"
INK = "#1D1D1F"
MUTED = "#6E6E73"
FAINT = "#A1A1A6"
LINE = "#D2D2D7"
GRID = "#ECECEF"
ACCENT = "#0071E3"
RED = "#FF3B30"
GREY_LINE = "#8E8E93"    # second data line in a chart
GREY_LINE_2 = "#C7C7CC"  # third data line in a chart
FONT = '"Instrument Sans", -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif'


def asset(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


def inject() -> None:
    """Load the stylesheet. A style-only st.html block takes no space on the page."""
    st.html(f"<style>{asset('app.css')}</style>")


def card(html: str) -> None:
    st.markdown(f'<div class="card">{html}</div>', unsafe_allow_html=True)


def stat(label: str, value: str, sub: str = "", over: bool = False) -> str:
    """A label with its unit, then the number on its own line."""
    return (f'<div class="card stat"><div class="label">{label}</div><div class="value{" over" if over else ""}">{value}</div>'
            f'<div class="sub">{sub}</div></div>')


def stat_row(items) -> None:
    cols = st.columns(len(items), gap="medium")
    for col, item in zip(cols, items):
        col.markdown(stat(*item), unsafe_allow_html=True)


def rows_html(pairs, over: set | None = None, left: bool = False) -> str:
    """Label and value pairs as a quiet table."""
    over = over or set()
    body = "".join(f'<tr><td class="k">{k}</td><td class="v{" over" if k in over else ""}">{v}</td></tr>' for k, v in pairs)
    return f'<table class="rows{" left" if left else ""}">{body}</table>'


def page_head(title: str, sub: str = "") -> None:
    st.markdown(f'<div class="page-head"><h1>{title}</h1>{f"<p>{sub}</p>" if sub else ""}</div>', unsafe_allow_html=True)


def gap(px: int = 16) -> None:
    st.markdown(f'<div style="height:{px}px"></div>', unsafe_allow_html=True)


def _css_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def card_button(key: str, title: str, text: str, eyebrow: str = "", selected: bool = False, height: int = 200) -> bool:
    """A whole card that is one click target: serif title, one or two plain sentences under it.

    Streamlit draws the button; the eyebrow and the body text are added with CSS so the
    card stays a single element with a single action.
    """
    k = f"cardbtn_{key}"
    sel = f".st-key-{k} .stButton > button"
    css = f'{sel} {{ min-height: {height}px; }} {sel}::after {{ content: "{_css_string(text)}"; }}'
    if eyebrow:
        css += f' {sel}::before {{ content: "{_css_string(eyebrow)}"; }}'
    if selected:
        css += (f" {sel} {{ box-shadow: 0 0 0 2px {ACCENT}, 0 8px 28px rgba(0,113,227,0.16); }}"
                f" {sel}::before {{ color: {ACCENT}; font-weight: 600; }}")
    st.html(f"<style>{css}</style>")
    with st.container(key=k):
        return st.button(title, key=f"btn_{key}", width="stretch")


def footer() -> None:
    st.markdown('<div class="h2-footer"><span>Aarya Chiripal</span><span>AME 310, Fall 2026</span></div>', unsafe_allow_html=True)
