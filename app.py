"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, app.py

What this file does
    This is the file Streamlit runs. It sets the page up, loads the stylesheet,
    shows the opening screen until a mode is picked, then draws the bar at the
    top and sends the visitor to one of three pages: Simulate, Levels or
    How it works.

Where it fits in the model
    Nowhere in the thermodynamics; I kept every equation in the h2lab package
    so this file only joins screens together. The one model object it creates
    is the starting FillConfig for Simulate (real-gas properties, 0.1 s step).

Run it with

    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from h2lab.simulation import FillConfig
from ui import explained, home, levels, run, styles, tour

st.set_page_config(page_title="H₂ Fast-Fill Lab", page_icon=None, layout="wide", initial_sidebar_state="collapsed",
                   menu_items={"Get help": None, "Report a bug": None, "About": None})
styles.inject()

PAGES = [("simulate", "Simulate"), ("levels", "Levels"), ("explained", "How it works")]

st.session_state.setdefault("page", "simulate")
if st.session_state["page"] not in dict(PAGES):
    st.session_state["page"] = "simulate"

if not home.chosen():
    home.render()
    tour.mount()
    styles.footer()
    st.stop()


def topnav() -> None:
    """The name on the left (it returns to the opening screen) and three destinations on the right."""
    with st.container(key="topnav", horizontal=True, vertical_alignment="center", gap="small"):
        if st.button("Fast-Fill Lab", key="nav_home", type="tertiary", width="content"):
            st.session_state["started"] = False
            st.rerun()
        st.markdown("", width="stretch")
        for key, label in PAGES:
            active = st.session_state["page"] == key
            if st.button(label, key=f"nav_{key}", type="primary" if active else "tertiary", width="content") and not active:
                st.session_state["page"] = key
                st.rerun()


topnav()
page = st.session_state["page"]

if page == "simulate":
    styles.page_head("Simulate", "Set the station up, press Start and change anything while the gas flows. When the fill ends, scroll down to see what happened.")
    run.render_run_screen("free", FillConfig(property_mode="real", dt=0.1))
elif page == "levels":
    levels.render_levels()
else:
    explained.render(st.session_state.get("free__sim"))

tour.mount()
styles.footer()
