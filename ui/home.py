"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/home.py

What this file does
    The opening screen: the station animation, then two cards side by side.
    Clicking a card starts that mode, Guided or Engineer.

Where it fits in the model
    Before it. The animation replays one default fill, run once and kept;
    nothing the visitor does here reaches the model.
"""

from __future__ import annotations

import streamlit as st

from . import scene
from .styles import card_button, gap


def chosen() -> bool:
    return st.session_state.get("started", False)


def _start(path: str) -> None:
    st.session_state["path"] = path
    st.session_state["started"] = True
    st.session_state["page"] = "simulate"
    for key in [k for k in st.session_state if k.endswith("__depth")]:
        st.session_state[key] = path
    st.rerun()


def render() -> None:
    st.markdown('<div class="page-head" style="margin:16px 0 16px 0"><h1>H<sub>2</sub> Fast-Fill Lab</h1>'
                '<p>Fill a hydrogen car in three minutes without letting its tank pass 85 °C. Learn how by watching the gas move.</p></div>', unsafe_allow_html=True)
    scene.render_hero()
    gap(24)
    _, a, b, _ = st.columns([0.4, 1, 1, 0.4], gap="large")
    with a:
        if card_button("guided", "Guided", "One question at a time: the weather, how empty the car is, how fast to fill, when to stop and which fuel cell is in the car. Every word explained. Start here if you are new.",
                       eyebrow="Start here", height=196):
            _start("Guided")
    with b:
        if card_button("engineer", "Engineer", "Every setting in tabs: storage banks, dispenser, cooling, tank and solver, with sliders or exact numbers. You can switch at any time.",
                       eyebrow="Full control", height=196):
            _start("Engineer")
