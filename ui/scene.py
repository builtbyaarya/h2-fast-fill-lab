"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/scene.py

What this file does
    The Python side of the station scene. The drawing and the animation are in
    assets/scene.js; this file turns a FillSimulation into the plain numbers
    that script needs (time series in display units, thinned to a few hundred
    points) and mounts the component.

Where it fits in the model
    One way only: the model is read here and never changed.
"""

from __future__ import annotations

import numpy as np
import streamlit as st

from h2lab.simulation import FillConfig, FillSimulation

from .styles import asset

_scene = st.components.v2.component("h2lab_scene", html=asset("scene.html"), css=asset("scene.css"), js=asset("scene.js"),
                                    isolate_styles=False)

MAX_POINTS = 320
SHORT = {"Low bank": "Low", "Medium bank": "Medium", "High bank": "High"}


def _thin(n: int) -> np.ndarray:
    """Indices that keep at most MAX_POINTS samples and always the last one."""
    if n <= MAX_POINTS:
        return np.arange(n)
    idx = np.unique(np.round(np.linspace(0, n - 1, MAX_POINTS)).astype(int))
    return idx


def _clean(a, nd: int = 3) -> list:
    return np.round(np.nan_to_num(np.asarray(a, dtype=float), nan=0.0, posinf=0.0, neginf=0.0), nd).tolist()


def bank_histories(sim: FillSimulation, s: dict):
    """Mass and pressure of every bank against time, rebuilt from the recorder.

    The recorder stores the flow rate and which bank was open at each step, so
    the mass left in bank i is its starting mass minus the flow drawn while it
    was the open bank. A bank that is not open keeps its last pressure,
    because the banks are insulated and closed.
    """
    t, m_dot, idx = s["t"], s["m_dot"], s["bank_idx"].astype(int)
    dt = np.diff(t, prepend=t[0])
    masses, pressures = [], []
    for i, bank in enumerate(sim.banks):
        m0 = bank.m + bank.m_out_cum
        masses.append(m0 - np.cumsum(np.where(idx == i, m_dot * dt, 0.0)))
        p = np.where(idx == i, s["P_bank"], np.nan)
        p[0] = p[0] if idx[0] == i else sim.cfg.banks[i].pressure_pa
        last = np.maximum.accumulate(np.where(np.isnan(p), 0, np.arange(len(p))))
        pressures.append(p[last])
    return masses, pressures


def payload(sim: FillSimulation, key: str, playing: bool = False, speed: float = 4.0, run: int = 0, hero: bool = False) -> dict:
    """Everything the scene needs, as JSON-ready numbers in display units."""
    s = sim.rec.arrays()
    masses, pressures = bank_histories(sim, s)
    keep = _thin(len(s["t"]))
    C = 273.15
    series = {
        "t": _clean(s["t"][keep], 2),
        "P": _clean(s["P_car"][keep] / 1e6), "Pt": _clean(s["P_target"][keep] / 1e6), "Pb": _clean(s["P_bank"][keep] / 1e6),
        "T": _clean(s["T_car"][keep] - C, 2), "Tw": _clean(s["T_wall"][keep] - C, 2), "Td": _clean(s["T_delivery"][keep] - C, 2),
        "Tv": _clean(s["T_valve_out"][keep] - C, 2), "Tb": _clean(s["T_bank"][keep] - C, 2),
        "m": _clean(s["m_car"][keep]), "md": _clean(s["m_dot"][keep] * 1000.0, 2), "soc": _clean(s["soc"][keep], 2),
        "open": _clean(s["opening"][keep] * 100.0, 1), "err": _clean(s["error"][keep]),
        "Hf": _clean(s["H_flow"][keep] / 1000.0, 2), "Qp": _clean(s["Q_precool"][keep] / 1000.0, 2),
        "Qw": _clean(-s["Q_wall"][keep] / 1000.0, 2), "Wr": _clean(s["W_ref"][keep] / 1000.0, 2),
        "bi": s["bank_idx"][keep].astype(int).tolist(),
    }
    for i in range(len(sim.banks)):
        series[f"bm{i}"] = _clean(masses[i][keep])
        series[f"bp{i}"] = _clean(pressures[i][keep] / 1e6, 2)
    banks = [{"name": SHORT.get(b.name, b.name), "V": float(b.volume), "P0": round(sim.cfg.banks[i].pressure_pa / 1e6, 1),
              "m0": float(masses[i][0])} for i, b in enumerate(sim.banks)]
    return {"key": key, "run": run, "hero": hero, "playing": bool(playing), "speed": float(speed), "finished": bool(sim.finished),
            "amb": round(sim.cfg.T_amb - C, 1), "cooling": bool(sim.precooler.enabled), "banks": banks, "series": series}


def render(sim: FillSimulation, key: str, playing: bool, speed: float, run: int) -> None:
    """The live scene with its two numbers, clock and chart."""
    _scene(key=f"scene_{key}", data=payload(sim, key, playing, speed, run))


@st.cache_data(show_spinner=False)
def _reference_payload() -> dict:
    sim = FillSimulation(FillConfig(property_mode="real", dt=0.25))
    sim.run()
    return payload(sim, "hero", playing=True, speed=14.0, hero=True)


def render_hero() -> None:
    """The opening animation: the reference fill, computed once by the model and replayed in a loop."""
    _scene(key="scene_hero", data=_reference_payload())
