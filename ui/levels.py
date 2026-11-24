"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/levels.py

What this file does
    The Levels page. Each level opens with a short scene and one line saying
    what it asks, then the same run screen as Simulate with some inputs fixed.
    The result leads with pass or fail and the one reason, then the score by
    criterion.

Where it fits in the model
    The levels themselves (starting conditions and scoring) are in
    h2lab/missions.py. This file is their wording and their result card.
"""

from __future__ import annotations

import streamlit as st

from h2lab.missions import MISSIONS

from . import run, tour
from .styles import card_button, gap, page_head, rows_html
from .text import minus, pretty

SCENES = {
    "three_minute": {
        "name": "Three-minute fill",
        "scene": "A sedan pulls in with 5 MPa left in its 141 L tank. It is 25 °C outside and the driver expects to be gone in three minutes, "
                 "which is what SAE J2601, the rulebook every hydrogen station follows, promises. Fill it to 70 MPa (full) in under 180 s and keep the gas below 85 °C, the hottest the tank may get.",
        "job": "Under 180 s, below 85 °C, as full as you can.",
    },
    "hot_day": {
        "name": "Hot-day fill",
        "scene": "40 °C in the Mojave. The car arrives at 10 MPa. This station's precooler, the cooler that chills the gas before the hose, is a T20 unit: "
                 "it can only get the gas down to −20 °C, with 45 kW of cooling. Finish with the gas at least 10 K under 85 °C and the tank at least 85% full (charge).",
        "job": "At least 10 K below the limit, at least 85% full. Fill more slowly or cool harder.",
    },
    "cheapest": {
        "name": "Cheapest fill",
        "scene": "A mild 15 °C day and a quiet station. The precooler runs on a fridge, and every kilowatt-hour (kWh) of electricity its compressor draws is money. "
                 "Deliver the fill with the least electricity per kilogram of hydrogen, in under five minutes, to at least 85% full.",
        "job": "Least electricity per kg. A warmer cooler and a slower fill trade against each other.",
    },
    "controller": {
        "name": "Tune the controller",
        "scene": "The dispenser's controller opens and closes the valve so the tank pressure rises along a straight line, the ramp. Its three settings, the gains, were left wrong: "
                 "the pressure lags, then swings around the line. K<sub>p</sub> reacts to the error now, K<sub>i</sub> to error that builds up, K<sub>d</sub> to how fast it changes. "
                 "Set them in Engineer, Dispenser tab, so the pressure stays within 0.5 MPa of the 18.5 MPa/min line on average (RMS error) and never goes more than 0.5 MPa above it (overshoot).",
        "job": "Keep the pressure on its line: average miss and worst overshoot both under 0.5 MPa.",
    },
}


def _reason(mission, res, sc) -> str:
    """The single sentence that explains the verdict."""
    T_peak_C = res.T_peak - 273.15
    if res.aborted:
        return pretty(res.end_reason) + f", at {res.fill_time:.0f} s."
    k = mission.key
    if k == "three_minute":
        if res.fill_time > 180.0:
            return f"Took {res.fill_time:.0f} s, limit 180 s."
        if T_peak_C >= 85.0:
            return f"Gas reached {T_peak_C:.1f} °C, limit 85 °C."
        return f"Filled in {res.fill_time:.0f} s with the gas peaking at {T_peak_C:.1f} °C."
    if k == "hot_day":
        margin = 85.0 - T_peak_C
        if margin < 10.0:
            return f"Only {margin:.1f} K of margin to 85 °C, 10 K needed."
        if res.soc_final < 85.0:
            return f"Reached {res.soc_final:.0f}% charge, 85% needed."
        return f"{margin:.1f} K of margin and {res.soc_final:.0f}% charge."
    if k == "cheapest":
        if res.fill_time > 300.0:
            return f"Took {res.fill_time:.0f} s, limit 300 s."
        if res.soc_final < 85.0:
            return f"Reached {res.soc_final:.0f}% charge, 85% needed."
        return f"{sc['Cooling energy per kg [kWh/kg]']:.3f} kWh per kg in {res.fill_time:.0f} s."
    if k == "controller":
        if sc["RMS tracking error [MPa]"] >= 0.5:
            return f"RMS error {sc['RMS tracking error [MPa]']:.2f} MPa, limit 0.5 MPa."
        if sc["Largest overshoot [MPa]"] >= 0.5:
            return f"Overshoot {sc['Largest overshoot [MPa]']:.2f} MPa, limit 0.5 MPa."
        return f"RMS error {sc['RMS tracking error [MPa]']:.2f} MPa, overshoot {sc['Largest overshoot [MPa]']:.2f} MPa."
    return pretty(res.end_reason)


def _result_block(mission):
    def block(sim):
        res = sim.result()
        sc = mission.score(res)
        passed = sc["Passed"]
        verdict = "Level passed" if passed else "Level not passed"
        rows = []
        for k, v in sc.items():
            if k in ("Total", "Passed"):
                continue
            if isinstance(v, float):
                unit = k[k.find("[") + 1:k.find("]")] if "[" in k else ""
                label = k[:k.find("[")].strip() if "[" in k else k
                if "score" in k.lower():
                    rows.append((label.replace("SOC", "Charge"), f"{v:.0f} of 100"))
                else:
                    nd = 3 if "kWh/kg" in unit else (2 if unit == "MPa" else (1 if unit else 0))
                    label = label.replace("SOC", "charge")
                    rows.append((pretty(label) + (f", {pretty(unit)}" if unit else ""), f"{v:.{nd}f}"))
            else:
                rows.append((pretty(k), pretty(v)))
        total = sc["Total"]
        head = (f'<div class="verdict {"pass" if passed else "fail"}">{verdict}</div>'
                f'<p class="reason">{_reason(mission, res, sc)}</p>')
        score_line = (f'<p class="small" style="margin:0 0 16px 0">Engineering score {total:.0f} of 100'
                      + ("" if passed else ", not counted because the requirement above was missed") + ".</p>")
        rows = [(k, minus(v)) for k, v in rows]
        st.markdown(f'<div class="card">{head}{score_line}{rows_html(rows)}</div>', unsafe_allow_html=True)
    return block


def render_levels() -> None:
    page_head("Levels", "Four fills, each with a job to do. Pick one, read the scene, then run the station.")
    idx_key = "level_idx"
    st.session_state.setdefault(idx_key, 0)
    cols = st.columns(len(MISSIONS), gap="medium")
    for i, (col, m) in enumerate(zip(cols, MISSIONS)):
        sc = SCENES[m.key]
        active = i == st.session_state[idx_key]
        with col:
            if card_button(f"level_{m.key}", sc["name"], sc["job"], eyebrow=f"Level {i + 1}" + (" \u00b7 Selected" if active else ""),
                           selected=active, height=184) and not active:
                st.session_state[idx_key] = i
                st.rerun()
    mission = MISSIONS[st.session_state[idx_key]]
    sc = SCENES[mission.key]
    gap(8)
    with st.container(key="level_scene"):
        st.markdown(f'<div class="card"><p class="scene-text" style="max-width:86ch">{sc["scene"]}</p></div>', unsafe_allow_html=True)
    gap(8)
    tour.request("levels", tour.LEVELS)
    ns = f"m_{mission.key}"
    run.render_run_screen(ns, mission.setup(), mission=mission, locked=set(mission.locked), result_block=_result_block(mission))
