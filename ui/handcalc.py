"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/handcalc.py

What this file does
    Check it by hand. For each device I lay out the course working like a page
    of a solutions manual: the step number in a narrow left column, one plain
    sentence, then the equations (general form, numbers substituted, result
    with units). The page ends with the hand result, the model result and the
    difference between them.

Where it fits in the model
    It is the cross-check. The hand route uses the first law in the form the
    course teaches for each device (throttle, heat exchanger, filling tank,
    emptying tank, refrigeration cycle, compressor), with the Table A.5
    constants for hydrogen; the numbers it is compared with come from the
    model's own record of the fill.
"""

from __future__ import annotations

import math

import numpy as np
import streamlit as st

from h2lab.devices import StationCompressor
from h2lab.properties import CP_H2, CV_H2, K_H2, R_H2
from h2lab.simulation import FillSimulation

from . import plots
from .styles import rows_html
from .text import MDOT, minus, pct

DEVICES = ["Dispenser valve", "Precooler", "Vehicle tank", "Storage bank", "Whole station", "Refrigeration cycle", "Station compressor"]
KIND = {"Dispenser valve": "Steady flow, one device", "Precooler": "Steady flow, one device", "Vehicle tank": "Transient, filling",
        "Storage bank": "Transient, emptying", "Whole station": "Combined: steady devices between transient tanks",
        "Refrigeration cycle": "Cycle", "Station compressor": "Steady flow, two stages"}


def _f(x, nd=1):
    return f"{x:,.{nd}f}"


def _C(T):
    return _f(T - 273.15, 1)


def _mass_avg_T_delivery(s):
    m_dot, T, t = np.asarray(s["m_dot"]), np.asarray(s["T_delivery"]), np.asarray(s["t"])
    if len(t) < 2:
        return float(T[-1]) if len(T) else float("nan")
    dt = np.diff(t)
    w = m_dot[1:] * dt
    return float(np.sum(w * T[1:]) / np.sum(w)) if np.sum(w) > 0 else float(T[-1])


def build(device: str, sim: FillSimulation) -> dict:
    """Problem text, steps and the final comparison for one device."""
    g = sim.gas
    car, bank = sim.car, sim.bank
    s = sim.rec.data
    i = len(s["t"]) - 1
    m_dot = s["m_dot"][i]
    cp, cv, R = CP_H2 / 1000, CV_H2 / 1000, R_H2 / 1000  # kJ/kg K
    steps, final = [], None

    if device == "Dispenser valve":
        P_i, T_i = bank.P, (sim.cfg.T_amb if sim.cfg.bank_outlet_at_ambient else bank.T)
        P_e = car.P
        T_model = s["T_valve_out"][i]
        problem = (f"Hydrogen leaves the active bank at {_f(P_i / 1e6)} MPa and {_C(T_i)} °C and passes through the dispenser valve into the hose at "
                   f"{_f(P_e / 1e6)} MPa. The valve passes {_f(m_dot * 1000)} g/s. Find the exit temperature.")
        steps = [
            dict(say="Draw the control volume around the valve. One inlet, one exit, steady state and steady flow, so mass in equals mass out.",
                 eq=r"\dot m_i = \dot m_e = \dot m", sub=None, res=f"ṁ = {_f(m_dot * 1000)} g/s at both ports."),
            dict(say="Write the steady-flow energy equation. The valve is adiabatic, does no work, and the velocity change across it is small.",
                 eq=r"0 = \dot Q - \dot W + \dot m\,(h_i - h_e) \quad\Rightarrow\quad h_e = h_i", sub=None, res="A throttle keeps enthalpy constant."),
            dict(say="For an ideal gas the enthalpy depends on temperature only, so constant enthalpy means constant temperature.",
                 eq=r"h = c_p\,T \quad\Rightarrow\quad T_e = T_i",
                 sub=rf"T_e = {_C(T_i)}\ ^\circ\mathrm{{C}}", res=f"Hand result: {_C(T_i)} °C at the exit."),
            dict(say="The model uses real-gas properties. Hydrogen above about 200 K warms when it is throttled; its Joule-Thomson coefficient is negative, "
                     "the opposite of most gases.",
                 eq=r"T_e = T\,(P_e,\ h = h_i)", sub=rf"T_e = {_C(T_model)}\ ^\circ\mathrm{{C}}", res=f"Model: {_C(T_model)} °C, a change of {T_model - T_i:+.1f} K across the valve."),
        ]
        final = ("Valve exit temperature", T_i, T_model, "K", "absolute")

    elif device == "Precooler":
        T_in, T_out, P = s["T_valve_out"][i], s["T_delivery"][i], car.P
        Q_model = s["Q_precool"][i] / 1000  # kW
        q_hand = cp * (T_out - T_in)
        Q_hand = m_dot * q_hand
        problem = (f"Hydrogen enters the precooler at {_C(T_in)} °C and leaves at {_C(T_out)} °C at {_f(P / 1e6)} MPa, flowing at {_f(m_dot * 1000)} g/s. "
                   f"Find the heat removed.")
        steps = [
            dict(say="Control volume around the hydrogen side of the heat exchanger. Steady flow, no work, pressure drop neglected.",
                 eq=r"q = h_e - h_i, \qquad \dot Q = \dot m\,(h_e - h_i)", sub=None, res="Heat per kilogram is the enthalpy drop."),
            dict(say="With constant specific heat from Table A.5 the enthalpy change is the specific heat times the temperature change.",
                 eq=r"q = c_p\,(T_e - T_i)", sub=rf"q = {_f(cp, 3)}\,({_C(T_out)} - ({_C(T_in)})) = {_f(q_hand)}\ \mathrm{{kJ/kg}}",
                 res=f"q = {_f(q_hand)} kJ/kg. The sign is negative: heat leaves the hydrogen."),
            dict(say="Multiply by the mass flow for the rate.", eq=r"\dot Q = \dot m\,q",
                 sub=rf"\dot Q = {_f(m_dot, 4)} \times {_f(q_hand)} = {_f(Q_hand, 2)}\ \mathrm{{kW}}", res=f"Hand result: {_f(-Q_hand, 2)} kW removed."),
            dict(say="This heat is the evaporator load of the refrigeration cycle. In an exam heat-exchanger question the second stream gains what this one loses.",
                 eq=r"\dot Q_{\text{removed}} = \dot Q_L", sub=rf"\dot Q_L = {_f(Q_model, 2)}\ \mathrm{{kW}}\ \text{{(model, real gas)}}", res=f"Model: {_f(Q_model, 2)} kW."),
        ]
        final = ("Heat removed", -Q_hand, Q_model, "kW", "linear")

    elif device == "Vehicle tank":
        m1 = car.m - car.m_in_cum
        T1 = s["T_car"][0]
        m_i = car.m_in_cum
        T_avg = _mass_avg_T_delivery(s)
        Q = car.Q_wall_cum / 1000  # kJ
        if m_i > 0:
            T2_hand = (m1 * cv * T1 + Q + m_i * cp * T_avg) / (car.m * cv)
        else:
            T2_hand = T1
        P2_hand = car.m * R * T2_hand / car.volume  # kPa
        problem = (f"The {sim.cfg.car_volume_m3 * 1000:.0f} L tank started with {_f(m1, 3)} kg at {_C(T1)} °C. Since then {_f(m_i, 3)} kg entered at an "
                   f"average {_C(T_avg)} °C, and {_f(-Q)} kJ went from the gas into the wall. Find the gas temperature and pressure now.")
        steps = [
            dict(say="Control volume: the tank, a rigid transient system with one inlet and no exit. Mass is conserved.",
                 eq=r"m_2 - m_1 = m_i", sub=rf"m_2 = {_f(m1, 3)} + {_f(m_i, 3)} = {_f(car.m, 3)}\ \mathrm{{kg}}", res=f"m<sub>2</sub> = {_f(car.m, 3)} kg."),
            dict(say="Energy equation for a transient control volume. The tank is rigid so W = 0; kinetic and potential energy are dropped; Q is the heat to the wall.",
                 eq=r"m_2 u_2 - m_1 u_1 = Q - W + m_i\,h_i", sub=None, res="Enthalpy comes in with the gas; internal energy is what is stored."),
            dict(say="Ideal gas with constant specific heats: u = c<sub>v</sub>T and h = c<sub>p</sub>T. Solve for the final temperature.",
                 eq=r"T_2 = \frac{m_1 c_v T_1 + Q + m_i c_p T_i}{m_2 c_v}",
                 sub=rf"T_2 = \frac{{{_f(m1, 3)}\times{_f(cv, 3)}\times{_f(T1)} + ({_f(Q)}) + {_f(m_i, 3)}\times{_f(cp, 3)}\times{_f(T_avg)}}}{{{_f(car.m, 3)}\times{_f(cv, 3)}}} = {_f(T2_hand)}\ \mathrm{{K}}",
                 res=f"Hand result: T<sub>2</sub> = {_C(T2_hand)} °C."),
            dict(say="The pressure follows from the ideal gas law.", eq=r"P_2 = \frac{m_2 R T_2}{V}",
                 sub=rf"P_2 = \frac{{{_f(car.m, 3)}\times{_f(R, 4)}\times{_f(T2_hand)}}}{{{_f(car.volume, 3)}}} = {_f(P2_hand, 0)}\ \mathrm{{kPa}}",
                 res=f"Hand result: P<sub>2</sub> = {_f(P2_hand / 1000, 2)} MPa."),
            dict(say="The model fixes the state from (v, u) with real-gas properties. At 70 MPa the compressibility factor is about 1.5, so the ideal gas law "
                     "underestimates the pressure for the same mass and temperature.",
                 eq=r"T_2 = T(v_2, u_2), \qquad P_2 = P(v_2, u_2)", sub=rf"T_2 = {_C(car.T)}\ ^\circ\mathrm{{C}}, \qquad P_2 = {_f(car.P / 1e6, 2)}\ \mathrm{{MPa}}",
                 res=f"Model: {_C(car.T)} °C and {_f(car.P / 1e6, 2)} MPa."),
            dict(say=f"Limiting case worth remembering: an empty insulated tank filled from a constant source ends at T<sub>2</sub> = k T<sub>i</sub> = {K_H2:.3f} T<sub>i</sub>. "
                     f"From 25 °C that is {K_H2 * 298.15 - 273.15:.0f} °C, which is why precooling exists.",
                 eq=r"m_2 u_2 = m_2 h_i \;\Rightarrow\; c_v T_2 = c_p T_i \;\Rightarrow\; T_2 = k\,T_i", sub=None, res=""),
        ]
        final = ("Gas temperature", T2_hand, car.T, "K", "absolute")

    elif device == "Storage bank":
        P1 = sim.cfg.banks[sim.bank_idx].pressure_pa
        T1 = sim.cfg.T_amb if sim.cfg.bank_T0 is None else sim.cfg.bank_T0
        T2s = T1 * (bank.P / P1) ** ((K_H2 - 1) / K_H2)
        problem = (f"The {bank.name.lower()} started at {_f(P1 / 1e6)} MPa and {_C(T1)} °C and has released {_f(bank.m_out_cum, 3)} kg so far. "
                   f"Its pressure is now {_f(bank.P / 1e6, 2)} MPa. Find the temperature of the gas left in it.")
        steps = [
            dict(say="Control volume: the bank, rigid and insulated, with one exit and no inlet.",
                 eq=r"m_2 - m_1 = -m_e, \qquad m_2 u_2 - m_1 u_1 = -\int h_e\, dm_e", sub=None,
                 res="The leaving gas carries the bank's own enthalpy, which keeps changing, so the integral is done step by step in the model."),
            dict(say="Exam route: the gas that stays behind expands slowly and adiabatically, so it follows an isentropic path.",
                 eq=r"\frac{T_2}{T_1} = \left(\frac{P_2}{P_1}\right)^{\frac{k-1}{k}}",
                 sub=rf"T_2 = {_f(T1)}\left(\frac{{{_f(bank.P / 1e6, 2)}}}{{{_f(P1 / 1e6)}}}\right)^{{{(K_H2 - 1) / K_H2:.3f}}} = {_f(T2s)}\ \mathrm{{K}}",
                 res=f"Hand result: {_C(T2s)} °C."),
            dict(say="The model integrates the energy equation with the real leaving enthalpy at every step.",
                 eq=r"T_2 = T(v_2, u_2)", sub=rf"T_2 = {_C(bank.T)}\ ^\circ\mathrm{{C}}", res=f"Model: {_C(bank.T)} °C."),
        ]
        if bank.m_out_cum <= 0:
            problem += " No gas has left this bank yet, so both results equal the starting temperature; start a fill to see them separate."
        final = ("Bank gas temperature", T2s, bank.T, "K", "absolute")

    elif device == "Whole station":
        eb = sim.energy_balance()
        H_out, E_cool, H_in, dU, Qw = eb["H_out_banks"] / 1e6, eb["E_cool"] / 1e6, eb["H_in_car"] / 1e6, eb["dU_car"] / 1e6, eb["Q_wall_car"] / 1e6
        dU_hand = H_out - E_cool + Qw
        closure_tex = r"\text{" + pct(100 * eb["closure_error"]).replace("%", r"\%") + "}"
        problem = (f"Over the fill so far, {_f(H_out, 3)} MJ of enthalpy left the banks, the precooler removed {_f(E_cool, 3)} MJ and the car gas gave "
                   f"{_f(-Qw, 3)} MJ to its wall. Find the change in the car gas's internal energy.")
        steps = [
            dict(say="Chain the control volumes: the exit of each device is the inlet of the next, so the enthalpy flow into the car is what left the banks "
                     "minus what the precooler took out.",
                 eq=r"\int \dot m\,h_{\text{car,in}}\,dt = \int \dot m\,h_{\text{bank}}\,dt - Q_{\text{precool}}",
                 sub=rf"{_f(H_out, 3)} - {_f(E_cool, 3)} = {_f(H_out - E_cool, 3)}\ \mathrm{{MJ}}", res=f"Hand: {_f(H_out - E_cool, 3)} MJ into the car. Model: {_f(H_in, 3)} MJ."),
            dict(say="Energy equation for the car tank: the stored energy rises by the enthalpy that came in, less the heat lost to the wall.",
                 eq=r"\Delta U_{\text{car}} = \int \dot m\,h_{\text{car,in}}\,dt + Q_{\text{wall}}",
                 sub=rf"\Delta U = {_f(H_out - E_cool, 3)} + ({_f(Qw, 3)}) = {_f(dU_hand, 3)}\ \mathrm{{MJ}}", res=f"Hand result: {_f(dU_hand, 3)} MJ."),
            dict(say="The model evaluates the stored energy from the final states of every tank. The two agree to the closure error of the integration.",
                 eq=r"\Delta U_{\text{car}} = m_2 u_2 - m_1 u_1", sub=rf"\Delta U = {_f(dU, 3)}\ \mathrm{{MJ}}, \quad \text{{closure error }}{closure_tex}",
                 res=f"Mass check: {_f(sum(b.m_out_cum for b in sim.banks), 3)} kg left the banks and {_f(car.m_in_cum, 3)} kg entered the car."),
        ]
        final = ("Change in car gas energy", dU_hand, dU, "MJ", "linear")

    elif device == "Refrigeration cycle":
        Q_L = s["Q_precool"][i] if s["Q_precool"][i] > 0 else 20.0e3
        cyc = sim.refrigeration.solve(Q_L)
        rf = sim.refrigeration
        carnot = rf.T_evap / (rf.T_cond - rf.T_evap)
        problem = (f"An ideal vapor-compression cycle on {rf.refrigerant} evaporates at {_C(rf.T_evap)} °C and condenses at {_C(rf.T_cond)} °C, "
                   f"with a compressor efficiency of {rf.eta_s:.2f}. It carries the precooler load of {_f(Q_L / 1000)} kW"
                   + (". Find the COP and the compressor power." if s["Q_precool"][i] > 0 else " (a representative load; the precooler is idle). Find the COP and the compressor power."))
        steps = [
            dict(say="State 1, saturated vapour leaving the evaporator. Read h and s from the tables at the evaporator temperature.",
                 eq=r"h_1 = h_g(T_L), \qquad s_1 = s_g(T_L)", sub=rf"h_1 = {_f(cyc['h1'] / 1000)}\ \mathrm{{kJ/kg}}, \quad s_1 = {_f(cyc['s1'] / 1000, 4)}\ \mathrm{{kJ/kg\cdot K}}", res=""),
            dict(say="State 2, after the compressor. Isentropic first, then the real exit with the efficiency.",
                 eq=r"s_{2s} = s_1 \Rightarrow h_{2s}, \qquad h_2 = h_1 + \frac{h_{2s} - h_1}{\eta_s}",
                 sub=rf"h_{{2s}} = {_f(cyc['h2s'] / 1000)}, \quad h_2 = {_f(cyc['h1'] / 1000)} + \frac{{{_f(cyc['h2s'] / 1000)} - {_f(cyc['h1'] / 1000)}}}{{{rf.eta_s:.2f}}} = {_f(cyc['h2'] / 1000)}\ \mathrm{{kJ/kg}}", res=""),
            dict(say="State 3, saturated liquid leaving the condenser; state 4 after the throttle, same enthalpy.",
                 eq=r"h_3 = h_f(T_H), \qquad h_4 = h_3", sub=rf"h_3 = h_4 = {_f(cyc['h3'] / 1000)}\ \mathrm{{kJ/kg}}", res=""),
            dict(say="Cooling per kilogram, work per kilogram and their ratio, the coefficient of performance.",
                 eq=r"q_L = h_1 - h_4, \qquad w_c = h_2 - h_1, \qquad \beta = \frac{q_L}{w_c}",
                 sub=rf"q_L = {_f(cyc['q_L'] / 1000)}, \quad w_c = {_f(cyc['w_c'] / 1000)}, \quad \beta = {_f(cyc['COP'], 2)}",
                 res=f"Hand result: COP {_f(cyc['COP'], 2)}. Carnot between the same temperatures would give {_f(carnot, 2)}."),
            dict(say="Scale to the load for the refrigerant flow and the compressor power.",
                 eq=r"\dot m_{\text{ref}} = \frac{\dot Q_L}{q_L}, \qquad \dot W_c = \dot m_{\text{ref}}\,w_c, \qquad \dot Q_H = \dot Q_L + \dot W_c",
                 sub=rf"\dot m_{{\text{{ref}}}} = {_f(cyc['m_ref'], 3)}\ \mathrm{{kg/s}}, \quad \dot W_c = {_f(cyc['W_comp'] / 1000, 2)}\ \mathrm{{kW}}, \quad \dot Q_H = {_f(cyc['Q_H'] / 1000, 2)}\ \mathrm{{kW}}",
                 res=f"Compressor power {_f(cyc['W_comp'] / 1000, 2)} kW for {_f(Q_L / 1000)} kW of cooling."),
        ]
        W_model = s["W_ref"][i] if s["Q_precool"][i] > 0 else cyc["W_comp"]
        final = ("Compressor power", cyc["W_comp"] / 1000, W_model / 1000, "kW", "linear")
        st.session_state["_hc_cycle"] = (cyc, rf.refrigerant)

    else:  # station compressor
        comp = StationCompressor(eta_s=0.70)
        P_in, P_out, T_in = 20.0e6, sim.cfg.banks[-1].pressure_pa, sim.cfg.T_amb
        out = comp.compress(g, P_in, T_in, P_out, sim.cfg.T_amb)
        r = math.sqrt(P_out / P_in)
        T_es = T_in * r ** ((K_H2 - 1) / K_H2)
        w_stage = cp * (T_es - T_in) / 0.70
        w_hand = 2 * w_stage
        problem = (f"The station compressor lifts hydrogen from a {P_in / 1e6:.0f} MPa supply at {_C(T_in)} °C to the {P_out / 1e6:.0f} MPa high bank in two stages "
                   f"with an intercooler back to the inlet temperature. Each stage has an isentropic efficiency of 0.70. Find the work per kilogram.")
        steps = [
            dict(say="Split the pressure ratio equally between the two stages; that minimises the work with ideal intercooling.",
                 eq=r"P_{\text{mid}} = \sqrt{P_i\,P_e}", sub=rf"P_{{\text{{mid}}}} = \sqrt{{{P_in / 1e6:.0f}\times{P_out / 1e6:.0f}}} = {_f(out['P_mid'] / 1e6)}\ \mathrm{{MPa}}", res=f"Stage pressure ratio {r:.2f}."),
            dict(say="Isentropic exit temperature of one stage for an ideal gas.",
                 eq=r"T_{es} = T_i\left(\frac{P_e}{P_i}\right)^{\frac{k-1}{k}}", sub=rf"T_{{es}} = {_f(T_in)}\times{r:.2f}^{{{(K_H2 - 1) / K_H2:.3f}}} = {_f(T_es)}\ \mathrm{{K}}", res=""),
            dict(say="Work per stage with the efficiency, then twice for two identical stages.",
                 eq=r"w_{\text{stage}} = \frac{c_p\,(T_{es} - T_i)}{\eta_s}, \qquad w = 2\,w_{\text{stage}}",
                 sub=rf"w_{{\text{{stage}}}} = \frac{{{_f(cp, 3)}\,({_f(T_es)} - {_f(T_in)})}}{{0.70}} = {_f(w_stage)}, \quad w = {_f(w_hand)}\ \mathrm{{kJ/kg}}", res=f"Hand result: {_f(w_hand)} kJ/kg."),
            dict(say="The model does the same two stages with real-gas enthalpies.",
                 eq=r"w = \frac{h_{es} - h_i}{\eta_s}\ \text{per stage}", sub=rf"w_1 = {_f(out['w1'] / 1000)}, \quad w_2 = {_f(out['w2'] / 1000)}, \quad w = {_f(out['w'] / 1000)}\ \mathrm{{kJ/kg}}",
                 res=f"Model: {_f(out['w'] / 1000)} kJ/kg, exit temperatures {out['T_mid'] - 273.15:.0f} °C and {out['T_out'] - 273.15:.0f} °C."),
        ]
        final = ("Compressor work per kg", w_hand, out["w"] / 1000, "kJ/kg", "linear")

    return dict(problem=problem, steps=steps, final=final)


WHY = {
    "Dispenser valve": "The hand route treats hydrogen as an ideal gas, which keeps its temperature through a throttle. Real hydrogen warms "
                       "when it is throttled, and the model includes that.",
    "Precooler": "The hand route uses one constant specific heat from Table A.5. The model reads real-gas enthalpies at the line pressure.",
    "Vehicle tank": "The hand route is an ideal gas with constant specific heats. The model uses real-gas properties, which matter above about 20 MPa.",
    "Storage bank": "The hand route assumes an ideal gas expanding at constant entropy. The model follows the real gas step by step as it leaves.",
    "Whole station": "Both routes use the same recorded flows, so they differ only by the small error of the step-by-step integration.",
    "Refrigeration cycle": "Both routes use the same refrigerant tables, so they agree. The model scales the cycle to the load at each instant.",
    "Station compressor": "The hand route uses the ideal-gas temperature ratio. The model uses real-gas enthalpies, and compressing dense hydrogen takes more work.",
}


def _signed(x: float, nd: int) -> str:
    """A difference with its sign and a real minus; a value that rounds to zero is shown as plain zero."""
    if abs(x) < 0.5 * 10 ** (-nd):
        return f"{0:.{nd}f}"
    return f"{x:+.{nd}f}".replace("-", "−")


def _aligned(eq: str, sub: str | None) -> str:
    """General form on the first line, numbers on the second, both starting at the same left edge."""
    lines = [eq] + ([sub] if sub else [])
    return r"\begin{aligned}" + r" \\[6pt] ".join("&" + ln for ln in lines) + r"\end{aligned}"


def render_handcalc(sim: FillSimulation, reference: bool) -> None:
    device = st.segmented_control("Device", DEVICES, default="Dispenser valve", key="hc_device", label_visibility="collapsed") or "Dispenser valve"
    data = build(device, sim)
    ideal = sim.gas.mode != "real"
    source = "a reference fill" if reference else "your fill"
    with st.container(key="explain_card_hand"):
        st.markdown(f'<p class="small">{KIND[device]}. Numbers from {source} at {sim.t:.1f} s.</p>'
                    f'<p class="scene-text" style="margin:8px 0 16px 0;max-width:68ch">{minus(data["problem"])}</p>', unsafe_allow_html=True)
        for j, stp in enumerate(data["steps"]):
            with st.container(key=f"hc_step_{j}"):
                n_col, body = st.columns([0.06, 1], gap="small")
                n_col.markdown(f'<div class="hc-n">{j + 1}</div>', unsafe_allow_html=True)
                with body:
                    st.markdown(f'<p class="hc-say">{stp["say"]}</p>', unsafe_allow_html=True)
                    st.latex(_aligned(stp["eq"], stp.get("sub")))
                    if stp.get("res"):
                        st.markdown(f'<p class="hc-res">{minus(stp["res"]).replace("ṁ", MDOT)}</p>', unsafe_allow_html=True)
        if data["final"]:
            label, hand, model, unit, kind = data["final"]
            if kind == "absolute":  # temperatures: show in °C, difference in kelvin
                rows = [("Hand result, °C", f"{hand - 273.15:.1f}"), ("Model result, °C", f"{model - 273.15:.1f}"),
                        ("Difference, K", _signed(hand - model, 1))]
            else:
                nd = 3 if unit == "MJ" else 2
                rows = [(f"Hand result, {unit}", f"{hand:.{nd}f}".replace("-", "−")), (f"Model result, {unit}", f"{model:.{nd}f}".replace("-", "−")),
                        (f"Difference, {unit}", _signed(hand - model, nd))]
            why = "The model is set to ideal gas for this fill, so the two routes agree apart from rounding." if ideal and device not in (
                "Whole station", "Refrigeration cycle") else WHY[device]
            with st.container(key="hc_step_final"):
                _, body = st.columns([0.06, 1], gap="small")
                body.markdown(f'<h3>{label}</h3><div style="max-width:360px">{rows_html(rows)}</div>'
                              f'<p class="hc-res" style="margin-top:8px;max-width:68ch">{why}</p>', unsafe_allow_html=True)
    if device == "Refrigeration cycle" and "_hc_cycle" in st.session_state:
        cyc, ref = st.session_state["_hc_cycle"]
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            plots.show(plots.fig_ph_diagram(cyc, ref), "hc_ph")
        with c2:
            plots.show(plots.fig_ts_diagram(cyc, ref), "hc_ts")
