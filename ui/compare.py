"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/compare.py

What this file does
    Compare two fills. Every finished fill is kept for the visit; this block
    sets the latest one against an earlier one in a table and a chart, with
    the differences called out. With only one fill so far it offers the same
    fill run again as an ideal gas.

Where it fits in the model
    It reads the summaries of two FillResults. The only model run it starts is
    that ideal-gas twin, which is the same FillConfig with the property mode
    switched.
"""

from __future__ import annotations

import copy

import streamlit as st

from h2lab.simulation import FillConfig, FillSimulation

from . import plots
from .styles import gap
from .text import minus, pct, pretty

QUANTITIES = [
    ("Fill time [s]", "Fill time, s", 0, False),
    ("Peak gas temperature [degC]", "Peak gas temperature, °C", 1, False),
    ("Final pressure [MPa]", "Final pressure, MPa", 1, False),
    ("Final SOC [%]", "Final state of charge, %", 0, False),
    ("Hydrogen added [kg]", "Hydrogen added, kg", 2, False),
    ("Cooling energy [kWh]", "Heat removed in the precooler, kWh", 2, False),
    ("Refrigeration compressor energy [kWh]", "Refrigeration compressor energy, kWh", 2, False),
    ("Cooling energy per kg [kWh/kg]", "Compressor energy per kg, kWh/kg", 3, False),
    ("Energy closure error [%]", "Energy closure error", 2, True),
]


def _table(na: str, nb: str, sa: dict, sb: dict) -> str:
    """One table: a row per quantity, a column per fill, and the difference (second minus first)."""
    head = f'<tr><th></th><th>{na}</th><th>{nb}</th><th>Difference</th></tr>'
    body = ""
    for key, label, nd, is_pct in QUANTITIES:
        a, b = sa[key], sb[key]
        if is_pct:
            body += f'<tr><td class="k">{label}</td><td>{pct(a)}</td><td>{pct(b)}</td><td class="d"></td></tr>'
        else:
            d = b - a
            diff = minus(f"{d:+.{nd}f}") if abs(d) > 10 ** (-nd) / 2 else "0"
            body += f'<tr><td class="k">{label}</td><td>{minus(f"{a:.{nd}f}")}</td><td>{minus(f"{b:.{nd}f}")}</td><td class="d">{diff}</td></tr>'
    ends = "".join(f'<td class="{"over" if s_["Aborted"] else ""}">{pretty(s_["End reason"])}</td>' for s_ in (sa, sb))
    body += f'<tr><td class="k">How it ended</td>{ends}<td class="d"></td></tr>'
    return f'<div class="card"><table class="cmp">{head}{body}</table></div>'


def _label(n: int, res) -> str:
    cfg = res.cfg
    kind = "real gas" if cfg.property_mode == "real" else "ideal gas"
    return f"Fill {n}: {cfg.T_amb - 273.15:.0f} °C, {cfg.controller.aprr_mpa_min:g} MPa/min, {kind}"


def render_block(sim, ns: str, run_id: int) -> None:
    """Under a finished fill: this fill set against an earlier one. Fills are remembered for the visit, nothing to save."""
    hist = st.session_state.setdefault(f"{ns}__history", [])
    if st.session_state.get(f"{ns}__hist_run") != run_id:
        res = sim.result()
        n = st.session_state[f"{ns}__fills"] = st.session_state.get(f"{ns}__fills", 0) + 1
        hist.append((_label(n, res), res))
        del hist[:-6]  # the last six fills are plenty
        st.session_state[f"{ns}__hist_run"] = run_id
    gap(24)
    with st.container(key=f"{ns}__cmp"):
        st.markdown('<div class="pf-intro"><h2>Compare two fills</h2><p>Every fill you finish is kept for this visit. Change one thing, run it again, '
                    'and the two are set side by side here.</p></div>', unsafe_allow_html=True)
        if len(hist) < 2:
            if st.button("Compare with the same fill as an ideal gas", key=f"{ns}__cmp_ideal", type="primary"):
                with st.spinner("Running the same fill with the ideal-gas model"):
                    cfg = copy.deepcopy(sim.cfg)
                    cfg.property_mode = "ideal" if cfg.property_mode == "real" else "real"
                    other = FillSimulation(cfg).run()
                hist.insert(0, (_label(0, other).replace("Fill 0", "Same fill"), other))
                st.rerun(scope="fragment")
            st.markdown('<p class="small" style="margin-top:8px">Or press Reset, change one setting and run again.</p>', unsafe_allow_html=True)
            return
        names = [n for n, _ in hist]
        ia = len(hist) - 2
        if len(hist) > 2:
            ia = st.selectbox("Compare this fill with", range(len(hist) - 1), format_func=lambda i: names[i], index=len(hist) - 2, key=f"{ns}__cmp_a")
        (na, ra), (nb, rb) = hist[ia], hist[-1]
        st.markdown(_table(na, nb, ra.summary(), rb.summary()), unsafe_allow_html=True)
        gap(8)
        view = st.segmented_control("Chart", list(plots.COMPARE_VIEWS.keys()), default="Tank pressure", key=f"{ns}__cmp_view", label_visibility="collapsed") or "Tank pressure"
        gap(8)
        plots.show(plots.fig_compare(view, ra.series, rb.series, na, nb), f"{ns}_cmp")
