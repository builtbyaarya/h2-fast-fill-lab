"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/plots.py

What this file does
    The Plotly charts, all in one look: one chart at a time, the main series
    in the accent blue, other series in greys, light gridlines, 13 px ticks,
    no toolbar, limit lines labelled once at the end of the line, and a second
    axis where two quantities have different units.

Where it fits in the model
    It plots the time series a fill recorded, and the P-h and T-s diagrams of
    the refrigeration cycle from the states devices.py solved.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from .styles import ACCENT, FONT, GREY_LINE, GREY_LINE_2, GRID, INK, LINE, MUTED, RED

PLOT_CONFIG = {"displayModeBar": False, "responsive": True}


def show(fig: go.Figure, key: str, title: str = "") -> None:
    """Draw a figure inside a white card, with an optional title above it."""
    with st.container(key=f"chartcard_{key}"):
        if title:
            st.markdown(f"<h3>{title}</h3>", unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch", key=f"plot_{key}", config=PLOT_CONFIG)
_TICK = dict(size=13, color=MUTED, family=FONT)

VIEWS = ["Pressure", "Temperature", "Mass and flow", "State of charge", "Controller", "Energy"]


def layout(fig: go.Figure, ytitle: str, height: int = 340, xtitle: str = "Time, s", y2title: str | None = None,
           legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8 if y2title is None else 8, t=40 if legend else 16, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font=dict(family=FONT, color=MUTED, size=13),
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0.0, xanchor="left", font=dict(size=13, color=INK),
                    bgcolor="rgba(0,0,0,0)", itemwidth=30),
        showlegend=legend,
        hovermode="x unified",
        hoverlabel=dict(font=dict(family=FONT, size=13), bgcolor="#FFFFFF", bordercolor=LINE),
    )
    fig.update_xaxes(title=dict(text=xtitle, font=dict(size=13, color=MUTED), standoff=10), showgrid=False, zeroline=False,
                     linecolor=LINE, tickfont=_TICK, ticks="outside", tickcolor=LINE, ticklen=4)
    fig.update_yaxes(title=dict(text=ytitle, font=dict(size=13, color=MUTED), standoff=10), gridcolor=GRID, zeroline=False,
                     linecolor="rgba(0,0,0,0)", tickfont=_TICK, rangemode="tozero")
    if y2title is not None:
        fig.update_layout(yaxis2=dict(title=dict(text=y2title, font=dict(size=13, color=MUTED), standoff=10), overlaying="y",
                                      side="right", showgrid=False, zeroline=False, tickfont=_TICK, rangemode="tozero"))
    return fig


def line(fig, x, y, name, color=ACCENT, dash=None, width=2.2, yaxis="y", fmt=".2f"):
    fig.add_trace(go.Scatter(x=x, y=y, name=name, mode="lines", line=dict(color=color, width=width, dash=dash, shape="linear"),
                             yaxis=yaxis, hovertemplate="%{y:" + fmt + "}<extra>" + name + "</extra>"))


def limit(fig, y, text, side="right"):
    """One red dashed limit line, labelled once at one end of the line."""
    fig.add_hline(y=y, line=dict(color=RED, width=1, dash="dash"), annotation_text=text, annotation_position=f"top {side}",
                  annotation_font=dict(size=13, color=RED, family=FONT), annotation_xshift=-2 if side == "right" else 2)


def fig_view(view: str, s: dict, target_pa: float | None = None) -> go.Figure:
    t = s["t"]
    fig = go.Figure()
    if view == "Pressure":
        line(fig, t, s["P_car"] / 1e6, "Vehicle tank", fmt=".1f")
        line(fig, t, s["P_target"] / 1e6, "Ramp set point", color=GREY_LINE, dash="dot", width=1.6, fmt=".1f")
        line(fig, t, s["P_bank"] / 1e6, "Active bank", color=GREY_LINE_2, width=1.6, fmt=".1f")
        limit(fig, 87.5, "87.5 MPa limit")
        return layout(fig, "MPa")
    if view == "Temperature":
        line(fig, t, s["T_car"] - 273.15, "Tank gas", fmt=".1f")
        line(fig, t, s["T_wall"] - 273.15, "Tank wall", color=GREY_LINE, width=1.6, fmt=".1f")
        line(fig, t, s["T_delivery"] - 273.15, "Delivered gas", color=GREY_LINE_2, width=1.6, fmt=".1f")
        limit(fig, 85.0, "85 °C limit")
        fig = layout(fig, "°C")
        fig.update_yaxes(rangemode="normal")
        return fig
    if view == "Mass and flow":
        line(fig, t, s["m_car"], "Mass in tank", fmt=".2f")
        line(fig, t, s["m_dot"] * 1000.0, "Flow", color=GREY_LINE, width=1.6, yaxis="y2", fmt=".1f")
        return layout(fig, "kg", y2title="g/s")
    if view == "State of charge":
        line(fig, t, s["soc"], "State of charge", fmt=".0f")
        limit(fig, 100.0, "100% limit")
        return layout(fig, "%")
    if view == "Controller":
        line(fig, t, s["opening"] * 100.0, "Valve opening", fmt=".0f")
        line(fig, t, s["error"], "Ramp error", color=GREY_LINE, width=1.6, yaxis="y2", fmt=".2f")
        fig = layout(fig, "% open", y2title="MPa")
        fig.update_layout(yaxis2=dict(rangemode="normal"))
        return fig
    if view == "Energy":
        line(fig, t, s["H_flow"] / 1000.0, "Enthalpy into tank", fmt=".1f")
        line(fig, t, s["Q_precool"] / 1000.0, "Heat removed in precooler", color=GREY_LINE, width=1.6, fmt=".1f")
        line(fig, t, -s["Q_wall"] / 1000.0, "Gas to wall", color=GREY_LINE_2, width=1.6, fmt=".1f")
        line(fig, t, s["W_ref"] / 1000.0, "Refrigeration compressor", color=INK, width=1.2, dash="dot", fmt=".1f")
        return layout(fig, "kW")
    raise ValueError(view)


COMPARE_VIEWS = {
    "Tank pressure": ("P_car", 1e-6, 0.0, "MPa", 87.5, "87.5 MPa limit"),
    "Gas temperature": ("T_car", 1.0, -273.15, "°C", 85.0, "85 °C limit"),
    "Mass in tank": ("m_car", 1.0, 0.0, "kg", None, None),
    "Flow": ("m_dot", 1000.0, 0.0, "g/s", 60.0, "60 g/s limit"),
    "Valve opening": ("opening", 100.0, 0.0, "% open", None, None),
    "Refrigeration energy": ("E_comp_ref_cum", 1 / 3.6e6, 0.0, "kWh", None, None),
}


def fig_compare(view: str, sa: dict, sb: dict, na: str, nb: str) -> go.Figure:
    key, k, c, unit, lim, lim_text = COMPARE_VIEWS[view]
    fig = go.Figure()
    line(fig, sa["t"], sa[key] * k + c, na)
    line(fig, sb["t"], sb[key] * k + c, nb, color=INK, width=1.6)
    if lim is not None:
        limit(fig, lim, lim_text)
    fig = layout(fig, unit, height=360)
    if key == "T_car":
        fig.update_yaxes(rangemode="normal")
    return fig


def fig_family(curves: list[tuple[str, np.ndarray, np.ndarray]], ytitle: str, limit_y=None, limit_text=None, height=360,
               xtitle="Time, s", limit_side="right") -> go.Figure:
    """A family of curves from one study: the accent for the last case, greys fading for the others."""
    fig = go.Figure()
    n = len(curves)
    for i, (name, x, y) in enumerate(curves):
        if i == n - 1:
            color, width = ACCENT, 2.2
        else:
            shade = 0.25 + 0.55 * i / max(n - 1, 1)
            color, width = f"rgba(29,29,31,{shade:.2f})", 1.6
        line(fig, x, y, name, color=color, width=width, fmt=".1f")
    if limit_y is not None:
        limit(fig, limit_y, limit_text, limit_side)
    fig = layout(fig, ytitle, height=height, xtitle=xtitle)
    fig.update_yaxes(rangemode="normal")
    return fig


def fig_ph_diagram(cycle: dict, refrigerant: str):
    """P-h diagram of the refrigeration cycle with the saturation dome from CoolProp."""
    import CoolProp.CoolProp as CP

    Tc = CP.PropsSI("Tcrit", refrigerant)
    Tt = max(CP.PropsSI("Ttriple", refrigerant), 170.0)
    Ts = np.linspace(Tt + 1.0, Tc - 0.5, 80)
    hl = [CP.PropsSI("H", "T", T, "Q", 0, refrigerant) / 1000 for T in Ts]
    hv = [CP.PropsSI("H", "T", T, "Q", 1, refrigerant) / 1000 for T in Ts]
    Ps = [CP.PropsSI("P", "T", T, "Q", 0, refrigerant) / 1000 for T in Ts]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hl + hv[::-1], y=Ps + Ps[::-1], mode="lines", name="Saturation dome",
                             line=dict(color=LINE, width=1.5), hoverinfo="skip"))
    h = [cycle["h1"], cycle["h2"], cycle["h3"], cycle["h4"], cycle["h1"]]
    P = [cycle["P_L"], cycle["P_H"], cycle["P_H"], cycle["P_L"], cycle["P_L"]]
    fig.add_trace(go.Scatter(x=np.array(h) / 1000, y=np.array(P) / 1000, mode="lines+markers+text", name="Cycle",
                             text=["1", "2", "3", "4", ""], textposition="top right", textfont=dict(size=13, color=INK),
                             line=dict(color=ACCENT, width=2.2), marker=dict(size=8, color=ACCENT), hoverinfo="skip"))
    fig = layout(fig, "P, kPa", height=320, xtitle="h, kJ/kg")
    fig.update_yaxes(type="log", rangemode="normal", dtick=1)
    fig.update_layout(hovermode="closest")
    return fig


def fig_ts_diagram(cycle: dict, refrigerant: str):
    import CoolProp.CoolProp as CP

    Tc = CP.PropsSI("Tcrit", refrigerant)
    Tt = max(CP.PropsSI("Ttriple", refrigerant), 170.0)
    Ts = np.linspace(Tt + 1.0, Tc - 0.5, 80)
    sl = [CP.PropsSI("S", "T", T, "Q", 0, refrigerant) / 1000 for T in Ts]
    sv = [CP.PropsSI("S", "T", T, "Q", 1, refrigerant) / 1000 for T in Ts]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sl + sv[::-1], y=list(Ts - 273.15) + list(Ts[::-1] - 273.15), mode="lines",
                             name="Saturation dome", line=dict(color=LINE, width=1.5), hoverinfo="skip"))
    s_pts = [cycle["s1"], cycle["s2"], cycle["s3"], cycle["s4"], cycle["s1"]]
    T_pts = [cycle["T1"], cycle["T2"], cycle["T3"], cycle["T4"], cycle["T1"]]
    fig.add_trace(go.Scatter(x=np.array(s_pts) / 1000, y=np.array(T_pts) - 273.15, mode="lines+markers+text",
                             name="Cycle", text=["1", "2", "3", "4", ""], textposition="top right", textfont=dict(size=13, color=INK),
                             line=dict(color=ACCENT, width=2.2), marker=dict(size=8, color=ACCENT), hoverinfo="skip"))
    fig = layout(fig, "T, °C", height=320, xtitle="s, kJ/kg K")
    fig.update_yaxes(rangemode="normal")
    fig.update_layout(hovermode="closest")
    return fig
