"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/research.py

What this file does
    The Research model page. It runs the two-zone tank model of the
    h2lab.research package for the settings chosen here and shows the result:
    the temperature of the two gas zones, the station electricity on one
    system boundary, and where the fill sits against the Pareto front that
    the optimisation found.

Where it fits in the model
    Beside the class model. Simulate, Levels and How it works still use the
    one-temperature tank of h2lab/tanks.py. This page uses
    h2lab/research/twozone.py, where the gas in the car's tank is split into
    an upper and a lower zone, each with its own mass, internal energy and
    temperature, and the wall is solved through its thickness. The 85 degC
    limit is checked against the hotter zone instead of the average.
"""

from __future__ import annotations

import json
import os

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from .styles import page_head

C0 = 273.15
_FRONT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "paper", "results", "pareto_25C.json")


@st.cache_resource(show_spinner="Building the hydrogen property table (once)...")
def _table():
    from h2lab.research.twozone import table
    return table()


@st.cache_data(show_spinner="Running the two-zone fill...")
def _run(T_amb, P0, r1, r2, xi_b, dsw1, dsw2, Ta, Tb, beta, Ri_c, soc):
    from h2lab.research.station import account
    from h2lab.research.twozone import Closure, Control, Fill
    f = Fill(T_amb=C0 + T_amb, P0=P0 * 1e6, closure=Closure(beta=beta, Ri_c=Ri_c),
             control=Control(r1=r1, r2=r2, xi_b=xi_b, dsw1=dsw1 * 1e6, dsw2=dsw2 * 1e6, Tpc_a=C0 + Ta, Tpc_b=C0 + Tb,
                             soc_target=soc), dt=0.1)
    o = f.run(_table())
    a = account(o)
    keep = ("t", "P", "T_u", "T_l", "T_bulk", "mdot", "Q_pc", "Ts_u")
    return dict(s={k: o.s[k] for k in keep}, t=o.t_fill, m=o.m_added, T_hot=o.T_hot - C0, T_bulk=o.Tbulk_max - C0,
                P=o.P_end / 1e6, soc=o.soc, reason=o.reason, acc={k: float(v) for k, v in a.items() if not isinstance(v, list)},
                banks=[dict(bank=("Low", "Medium", "High")[b["bank"]], kg=float(b["m"]), P_end=float(b["P_end"]) / 1e6,
                            kWh_kg=float(b["w"]) / 3.6e6) for b in a["banks"]])


def _line(fig, x, y, name, dash=None, color=None):
    fig.add_trace(go.Scatter(x=x, y=y, name=name, mode="lines", line=dict(dash=dash, color=color, width=2)))


def render() -> None:
    page_head("Research model", "The two-zone tank model behind the journal manuscript. The gas in the car's tank is split into an "
              "upper and a lower zone, and the 85 °C limit is checked against the hotter one.")
    left, right = st.columns([1, 2.2], gap="large")
    with left:
        st.subheader("Settings")
        T_amb = st.slider("Ambient temperature, °C", -10.0, 45.0, 25.0, 1.0)
        P0 = st.slider("Tank pressure at the start, MPa", 2.0, 30.0, 5.0, 0.5)
        st.markdown("**Fill-rate control**")
        r1 = st.slider("Ramp rate, first stage, MPa/min", 5.0, 40.0, 18.5, 0.5)
        r2 = st.slider("Ramp rate, second stage, MPa/min", 5.0, 40.0, 18.5, 0.5)
        xi_b = st.slider("Stage change, fraction of the way to 70 MPa", 0.15, 0.85, 0.5, 0.05)
        st.markdown("**Precooling**")
        Ta = st.slider("Set point at the start of the fill, °C", -40.0, 20.0, -40.0, 1.0)
        Tb = st.slider("Set point at 70 MPa, °C", -40.0, 20.0, -40.0, 1.0)
        st.markdown("**Bank switching**")
        dsw1 = st.slider("Margin, low to medium bank, MPa", 0.5, 20.0, 2.0, 0.5)
        dsw2 = st.slider("Margin, medium to high bank, MPa", 0.5, 20.0, 2.0, 0.5)
        with st.expander("Two-zone closure and stop rule"):
            beta = st.slider("Mixing efficiency β (fitted value 0.35)", 0.05, 1.0, 0.35, 0.05)
            Ri_c = st.select_slider("Critical Richardson number", [0.1, 0.3, 1.0, 3.0, 10.0], 1.0)
            soc = st.slider("Stop at state of charge, %", 85.0, 100.0, 95.0, 1.0)
    try:
        r = _run(T_amb, P0, r1, r2, xi_b, dsw1, dsw2, Ta, Tb, beta, Ri_c, soc)
    except Exception as exc:  # the page must not take the rest of the app down
        with right:
            st.error(f"The research model could not run here: {exc}")
        return
    a, s = r["acc"], r["s"]
    with right:
        c = st.columns(4)
        c[0].metric("Fill time", f"{r['t']:.0f} s")
        c[1].metric("Hotter zone, peak", f"{r['T_hot']:.1f} °C", f"{r['T_hot'] - r['T_bulk']:+.1f} K above the average", delta_color="off")
        c[2].metric("State of charge", f"{r['soc']:.1f} %")
        c[3].metric("Station electricity", f"{a['e_station']:.2f} kWh/kg")
        if r["T_hot"] >= 85.0:
            st.error("The hotter zone passes 85 °C. A one-temperature model would report "
                     f"{r['T_bulk']:.1f} °C for the same fill.")
        if r["soc"] < soc - 0.05:
            st.warning(f"The fill stopped before the target: {r['reason']}.")
        fig = go.Figure()
        _line(fig, s["t"], s["T_u"] - C0, "Upper zone", color="#f47230")
        _line(fig, s["t"], s["T_l"] - C0, "Lower zone", dash="dash", color="#257de0")
        _line(fig, s["t"], s["T_bulk"] - C0, "Mixed average", dash="dot", color="#191919")
        _line(fig, s["t"], s["Ts_u"] - C0, "Liner surface, upper", dash="dashdot", color="#8a8a8a")
        fig.add_hline(y=85, line_dash="dash", line_color="#dc3c3d", annotation_text="85 °C limit")
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Time, s", yaxis_title="Temperature, °C",
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, width="stretch")
        g1, g2 = st.columns(2)
        with g1:
            fig = go.Figure()
            _line(fig, s["t"], s["P"] / 1e6, "Tank pressure", color="#257de0")
            fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Time, s", yaxis_title="Pressure, MPa", showlegend=False)
            st.plotly_chart(fig, width="stretch")
        with g2:
            fig = go.Figure()
            _line(fig, s["t"], s["mdot"] * 1e3, "Mass flow", color="#257de0")
            fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Time, s", yaxis_title="Mass flow, g/s", showlegend=False)
            st.plotly_chart(fig, width="stretch")

        st.subheader("Station electricity on one system boundary")
        st.caption("Hydrogen enters at 2 MPa and ambient temperature and leaves in the car's tank. Each bank is refilled to the state it "
                   "started from, so every kilogram passes the compressor once.")
        st.dataframe([
            {"Item": "Compressor, gas-side work (5 stages, isentropic efficiency 0.70)", "kWh/kg": round(a["e_comp_gas"], 3)},
            {"Item": "Compressor, electricity (mechanical 0.95, motor 0.95)", "kWh/kg": round(a["e_comp"], 3)},
            {"Item": "Precooler, heat removed", "kWh/kg": round(a["q_cool"], 3)},
            {"Item": "Refrigeration compressor, electricity (drive 0.90)", "kWh/kg": round(a["e_ref"], 3)},
            {"Item": "Station total", "kWh/kg": round(a["e_station"], 3)},
        ], hide_index=True, width="stretch")
        st.dataframe([{"Bank": b["bank"], "Hydrogen drawn, kg": round(b["kg"], 3), "Pressure after the fill, MPa": round(b["P_end"], 1),
                       "Refill work, kWh/kg (gas side)": round(b["kWh_kg"], 3)} for b in r["banks"]], hide_index=True, width="stretch")
        st.caption(f"Operating cost {a['c_op']:.2f} $/kg (energy {a['c_energy']:.2f}, demand {a['c_demand']:.2f}). "
                   f"Pathway: {a['e_prod']:.0f} kWh/kg to make the hydrogen, {a['e_station']:.2f} at the station, "
                   f"{a['e_out']:.1f} back from the fuel cell, round trip {100 * a['round_trip']:.1f} %.")

        if os.path.exists(_FRONT):
            with open(_FRONT) as f:
                fr = json.load(f)
            st.subheader("Against the optimised fills (25 °C ambient, 5 MPa start)")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=fr["t"], y=fr["e"], mode="markers", name="Pareto front", marker=dict(color="#6a4ce2", size=6)))
            fig.add_trace(go.Scatter(x=[fr["ref"]["t"]], y=[fr["ref"]["e"]], mode="markers", name="SAE J2601 table fill",
                                     marker=dict(color="#191919", size=12, symbol="star-open")))
            fig.add_trace(go.Scatter(x=[r["t"]], y=[a["e_station"]], mode="markers", name="This fill",
                                     marker=dict(color="#f47230", size=12, symbol="diamond")))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Fill time, s",
                              yaxis_title="Station electricity, kWh/kg", legend=dict(orientation="h", y=1.12))
            st.plotly_chart(fig, width="stretch")
            st.caption("Each point of the front is a fill that reaches 95 % state of charge with the hotter zone below 85 °C, also when "
                       "zone mixing is as weak as the JRC thermocouple data allow, and the pressure below 87.5 MPa, and that no other "
                       "such fill beats on both time and electricity.")
