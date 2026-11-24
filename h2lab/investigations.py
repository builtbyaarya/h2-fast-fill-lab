"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, h2lab/investigations.py

What this file does
    The parameter studies for my report. Each study changes one input, runs
    the fill to the end and records what the physics says should move: peak
    temperature, fill time, final state of charge and cooling energy.

Where it fits in the model
    On top of it. Every point on every graph is a full run of simulation.py
    with one number changed; nothing here has an equation of its own.

The studies
      1. precooling temperature     (-40 to -10 degC and off)
      2. fill rate                  (APRR 5 to 35 MPa/min)
      3. ambient temperature        (-10 to 45 degC)
      4. starting pressure          (2 to 35 MPa)
      5. controller gains           (Kp sweep, tracking error)
    and a sixth that my proposal promised: ideal gas against real gas.

Graphs are saved as PNG files with matplotlib so they go straight into the
report. The interface shows the same data with interactive plots.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass

import numpy as np

from .controller import ControllerSettings
from .simulation import FillConfig, FillSimulation

INK = "#1D1D1F"
MUTED = "#6E6E73"
ACCENT = "#0B7285"
LIMIT = "#C2410C"
BG = "#F5F5F7"


def _ramp(n: int):
    """Single-hue sequential ramp of the accent, light to dark, for an ordered parameter."""
    import matplotlib.colors as mc

    base = np.array(mc.to_rgb(ACCENT))
    white = np.ones(3)
    return [tuple(white + (base - white) * (0.35 + 0.65 * i / max(n - 1, 1))) for i in range(n)]


@dataclass
class Study:
    key: str
    title: str
    parameter: str
    unit: str
    values: list
    apply: callable  # (cfg, value) -> None
    note: str


def _base_cfg(mode="real") -> FillConfig:
    cfg = FillConfig(property_mode=mode, dt=0.2)
    cfg.controller = ControllerSettings(mode="auto", aprr_mpa_min=18.5, target_pressure_pa=70.0e6)
    return cfg


def _set_precool(cfg, v):
    if v is None:
        cfg.precooler.enabled = False
    else:
        cfg.precooler.T_set = 273.15 + v


def _set_aprr(cfg, v):
    cfg.controller.aprr_mpa_min = v


def _set_tamb(cfg, v):
    cfg.T_amb = 273.15 + v


def _set_p0(cfg, v):
    cfg.car_P0_pa = v * 1e6


def _set_kp(cfg, v):
    cfg.controller.Kp = v
    cfg.controller.Ki = 0.0


STUDIES = [
    Study("precool", "Precooling temperature", "Precooler set point", "degC",
          [-40, -30, -20, -10, 0, None], _set_precool,
          "Colder delivery gas lowers the inlet enthalpy, so the same mass arrives with less energy and the "
          "tank runs cooler; the price is refrigeration work. With no precooling the fill aborts at 85 degC."),
    Study("aprr", "Fill rate", "Average pressure ramp rate", "MPa/min",
          [5, 10, 15, 18.5, 25, 35], _set_aprr,
          "A faster ramp leaves the wall less time to absorb heat, so the peak temperature rises and the fill "
          "may abort. Slower fills cost the driver time but need less precooling."),
    Study("tamb", "Ambient temperature", "Ambient temperature", "degC",
          [-10, 0, 10, 25, 35, 45], _set_tamb,
          "Ambient temperature sets the starting gas and wall temperature and the bank gas temperature. "
          "A hot day starts the tank closer to the limit and warms the gas arriving at the valve."),
    Study("p0", "Starting pressure", "Vehicle tank starting pressure", "MPa",
          [2, 5, 10, 20, 35], _set_p0,
          "A nearly empty tank heats most: with little gas already inside, the incoming flow work has less "
          "mass to share with, which is the T2 = k Ti limit for an empty insulated tank."),
    Study("kp", "Controller gain", "Proportional gain Kp (Ki = 0)", "per MPa",
          [0.02, 0.05, 0.1, 0.3, 0.6, 1.0], _set_kp,
          "With a low gain the valve opens too little and the pressure lags the ramp; with a high gain it "
          "tracks tightly but reacts hard to every error. The tracking error shows the trade-off."),
]


def run_study(study: Study, mode: str = "real", progress=None) -> dict:
    rows = []
    series = []
    for i, v in enumerate(study.values):
        cfg = _base_cfg(mode)
        study.apply(cfg, v)
        res = FillSimulation(cfg).run()
        err = res.series["error"]
        rows.append({
            "value": v,
            "label": "off" if v is None else f"{v:g}",
            "T_peak_C": res.T_peak - 273.15,
            "fill_time_s": res.fill_time,
            "soc_final": res.soc_final,
            "E_cool_kWh": res.E_cool / 3.6e6,
            "E_ref_kWh_per_kg": (res.E_comp_ref / 3.6e6) / max(res.m_added, 1e-9),
            "rms_error_MPa": float(np.sqrt(np.nanmean(err**2))),
            "aborted": res.aborted,
            "end_reason": res.end_reason,
        })
        series.append({"label": rows[-1]["label"], "t": res.series["t"], "T": res.series["T_car"] - 273.15,
                       "P": res.series["P_car"] / 1e6, "P_target": res.series["P_target"] / 1e6,
                       "soc": res.series["soc"]})
        if progress:
            progress(i + 1, len(study.values))
    return {"study": study, "rows": rows, "series": series}


def run_property_mode_study(progress=None) -> dict:
    """Same fill in textbook (ideal gas) and real-gas mode."""
    out = {}
    for i, mode in enumerate(("ideal", "real")):
        cfg = _base_cfg(mode)
        res = FillSimulation(cfg).run()
        out[mode] = res
        if progress:
            progress(i + 1, 2)
    return out


def save_study_figure(result: dict, folder: str) -> str:
    """Two-panel figure: temperature histories and the summary metric against the parameter."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    study = result["study"]
    rows, series = result["rows"], result["series"]
    os.makedirs(folder, exist_ok=True)
    colors = _ramp(len(series))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), dpi=160)
    fig.patch.set_facecolor("white")
    ax = axes[0]
    for s, c in zip(series, colors):
        ax.plot(s["t"], s["T"], color=c, lw=1.8, label=f"{s['label']} {study.unit}" if s["label"] != "off" else "off")
    ax.axhline(85.0, color=LIMIT, lw=1.0, ls="--")
    ax.text(ax.get_xlim()[1], 85.5, "85 degC limit", color=LIMIT, ha="right", va="bottom", fontsize=8)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Tank gas temperature [degC]")
    ax.set_title(f"{study.title}: temperature history", loc="left", fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=8, title=study.parameter, title_fontsize=8)
    ax = axes[1]
    x = np.arange(len(rows))
    if study.key == "kp":
        y = [r["rms_error_MPa"] for r in rows]
        ylabel = "RMS ramp tracking error [MPa]"
    else:
        y = [r["T_peak_C"] for r in rows]
        ylabel = "Peak gas temperature [degC]"
        ax.axhline(85.0, color=LIMIT, lw=1.0, ls="--")
    bars = ax.bar(x, y, color=colors, width=0.62)
    for b, r in zip(bars, rows):
        if r["aborted"]:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), "abort", ha="center", va="bottom",
                    fontsize=7, color=LIMIT)
    ax.set_xticks(x)
    ax.set_xticklabels([r["label"] for r in rows])
    ax.set_xlabel(f"{study.parameter} [{study.unit}]")
    ax.set_ylabel(ylabel)
    ax.set_title("Summary", loc="left", fontsize=11, color=INK)
    for a in axes:
        a.spines[["top", "right"]].set_visible(False)
        a.spines[["left", "bottom"]].set_color("#C9CBD1")
        a.tick_params(colors=MUTED, labelsize=8)
        a.grid(axis="y", color="#E8E9EE", lw=0.6)
        a.set_axisbelow(True)
    fig.tight_layout()
    path = os.path.join(folder, f"study_{study.key}.png")
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def save_property_mode_figure(results: dict, folder: str) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(folder, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), dpi=160)
    styles = {"ideal": (MUTED, "Ideal gas (Table A.5)"), "real": (ACCENT, "Real gas (CoolProp)")}
    for mode, res in results.items():
        c, lab = styles[mode]
        s = res.series
        axes[0].plot(s["t"], s["T_car"] - 273.15, color=c, lw=1.8, label=lab)
        axes[1].plot(s["t"], s["m_car"], color=c, lw=1.8, label=lab)
        axes[2].plot(s["t"], s["T_valve_out"] - 273.15, color=c, lw=1.8, label=lab)
    axes[0].axhline(85.0, color=LIMIT, lw=1.0, ls="--")
    axes[0].set_ylabel("Tank gas temperature [degC]")
    axes[1].set_ylabel("Hydrogen in tank [kg]")
    axes[2].set_ylabel("Temperature after the valve [degC]")
    titles = ["Tank temperature", "Mass stored", "Throttling effect"]
    for a, t in zip(axes, titles):
        a.set_xlabel("Time [s]")
        a.set_title(t, loc="left", fontsize=11, color=INK)
        a.spines[["top", "right"]].set_visible(False)
        a.spines[["left", "bottom"]].set_color("#C9CBD1")
        a.tick_params(colors=MUTED, labelsize=8)
        a.grid(axis="y", color="#E8E9EE", lw=0.6)
        a.set_axisbelow(True)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    path = os.path.join(folder, "study_property_mode.png")
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def run_all(folder: str, mode: str = "real", progress=None) -> dict:
    out = {}
    for i, st in enumerate(STUDIES):
        res = run_study(st, mode)
        res["png"] = save_study_figure(res, folder)
        out[st.key] = res
        if progress:
            progress(i + 1, len(STUDIES) + 1)
    pm = run_property_mode_study()
    out["property_mode"] = {"results": pm, "png": save_property_mode_figure(pm, folder)}
    if progress:
        progress(len(STUDIES) + 1, len(STUDIES) + 1)
    return out
