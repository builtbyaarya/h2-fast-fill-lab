"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, h2lab/missions.py

What this file does
    The four levels: the starting conditions of each one and how a finished
    fill is scored.

Where it fits in the model
    On top of it. A level is only a FillConfig with some inputs fixed and a
    scoring function that reads the FillResult; no physics is added here.

How I score
    From engineering quantities only: fill time against the three-minute
    target of SAE J2601 (the fuelling standard), margin to the 85 degC limit,
    state of charge reached, refrigeration energy per kilogram, and how well
    the pressure followed its ramp. A fill that stops on a hard limit scores
    zero, as it would at a real station.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

from .controller import ControllerSettings
from .simulation import FillConfig, FillResult


@dataclass
class Mission:
    key: str
    title: str
    brief: str
    objective: str
    setup: Callable[[], FillConfig]
    score: Callable[[FillResult], dict]
    locked: list = field(default_factory=list)  # control names the user may not change


def _base(**kw) -> FillConfig:
    cfg = FillConfig(property_mode="real", dt=0.1)
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def score_three_minute(res: FillResult) -> dict:
    """Fill to 70 MPa in under 180 s without passing 85 degC."""
    T_peak_C = res.T_peak - 273.15
    time_score = _clamp(100.0 * min(1.0, 180.0 / max(res.fill_time, 1.0)))
    margin = 85.0 - T_peak_C
    temp_score = 0.0 if res.aborted and "85" in res.end_reason else _clamp(100.0 * min(1.0, margin / 15.0))
    soc_score = _clamp(res.soc_final)
    total = 0.4 * time_score + 0.3 * temp_score + 0.3 * soc_score
    return {
        "Fill time [s]": res.fill_time,
        "Peak temperature [degC]": T_peak_C,
        "Final SOC [%]": res.soc_final,
        "Time score": time_score,
        "Temperature margin score": temp_score,
        "SOC score": soc_score,
        "Total": 0.0 if res.aborted else total,
        "Passed": (not res.aborted) and res.fill_time <= 180.0 and T_peak_C < 85.0,
    }


def score_hot_day(res: FillResult) -> dict:
    """40 degC ambient: finish the fill with at least 10 K of temperature margin."""
    T_peak_C = res.T_peak - 273.15
    margin = 85.0 - T_peak_C
    temp_score = 0.0 if res.aborted else _clamp(100.0 * min(1.0, margin / 10.0))
    time_score = _clamp(100.0 * min(1.0, 240.0 / max(res.fill_time, 1.0)))
    soc_score = _clamp(res.soc_final)
    total = 0.5 * temp_score + 0.2 * time_score + 0.3 * soc_score
    return {
        "Peak temperature [degC]": T_peak_C,
        "Temperature margin [K]": margin,
        "Fill time [s]": res.fill_time,
        "Final SOC [%]": res.soc_final,
        "Total": 0.0 if res.aborted else total,
        "Passed": (not res.aborted) and margin >= 10.0 and res.soc_final >= 85.0,
    }


def score_cheapest(res: FillResult) -> dict:
    """Least refrigeration compressor energy per kg while staying legal and under 5 minutes."""
    kwh_per_kg = (res.E_comp_ref / 3.6e6) / max(res.m_added, 1e-9)
    # 0.05 kWh/kg is excellent, 0.30 kWh/kg is wasteful
    energy_score = _clamp(100.0 * (0.30 - kwh_per_kg) / 0.25)
    time_score = 100.0 if res.fill_time <= 300.0 else _clamp(100.0 * 300.0 / res.fill_time)
    total = 0.7 * energy_score + 0.3 * time_score
    return {
        "Cooling energy per kg [kWh/kg]": kwh_per_kg,
        "Precooler load [kWh]": res.E_cool / 3.6e6,
        "Fill time [s]": res.fill_time,
        "Peak temperature [degC]": res.T_peak - 273.15,
        "Total": 0.0 if res.aborted else total,
        "Passed": (not res.aborted) and res.fill_time <= 300.0 and res.soc_final >= 85.0,
    }


def score_controller(res: FillResult) -> dict:
    """Tune the PID so the tank pressure tracks the J2601 ramp closely."""
    import numpy as np

    err = res.series["error"]
    rms = float(np.sqrt(np.nanmean(err**2))) if len(err) else 0.0
    overshoot = float(np.nanmax(-err)) if len(err) else 0.0
    track_score = _clamp(100.0 * (1.0 - rms / 2.0))  # 2 MPa rms error scores zero
    overshoot_score = _clamp(100.0 * (1.0 - max(0.0, overshoot) / 1.0))
    total = 0.6 * track_score + 0.4 * overshoot_score
    return {
        "RMS tracking error [MPa]": rms,
        "Largest overshoot [MPa]": max(0.0, overshoot),
        "Fill time [s]": res.fill_time,
        "Total": 0.0 if res.aborted else total,
        "Passed": (not res.aborted) and rms < 0.5 and overshoot < 0.5,
    }


def _three_minute() -> FillConfig:
    cfg = _base(T_amb=273.15 + 25.0, car_P0_pa=5.0e6)
    cfg.controller = ControllerSettings(mode="auto", aprr_mpa_min=18.5, target_pressure_pa=70.0e6)
    return cfg


def _hot_day() -> FillConfig:
    cfg = _base(T_amb=273.15 + 40.0, car_P0_pa=10.0e6)
    cfg.precooler.T_set = 273.15 - 20.0
    cfg.precooler.Q_max = 45.0e3
    cfg.controller = ControllerSettings(mode="auto", aprr_mpa_min=18.5, target_pressure_pa=70.0e6)
    return cfg


def _cheapest() -> FillConfig:
    cfg = _base(T_amb=273.15 + 15.0, car_P0_pa=10.0e6)
    cfg.precooler.T_set = 273.15 - 40.0
    cfg.controller = ControllerSettings(mode="auto", aprr_mpa_min=18.5, target_pressure_pa=70.0e6)
    return cfg


def _controller() -> FillConfig:
    cfg = _base(T_amb=273.15 + 25.0, car_P0_pa=5.0e6)
    # deliberately poor starting gains: sluggish and oscillatory
    cfg.controller = ControllerSettings(mode="auto", aprr_mpa_min=18.5, target_pressure_pa=70.0e6,
                                        Kp=0.05, Ki=0.0, Kd=0.0)
    return cfg


MISSIONS = [
    Mission(
        key="three_minute",
        title="Three-minute fill",
        brief="A standard 141 L car arrives at 50 bar on a 25 degC day. SAE J2601 expects a full fill "
              "in about three minutes.",
        objective="Reach 70 MPa in under 180 s with the gas below 85 degC. Score weights: time 40%, "
                  "temperature margin 30%, state of charge 30%.",
        setup=_three_minute,
        score=score_three_minute,
    ),
    Mission(
        key="hot_day",
        title="Hot-day fill",
        brief="40 degC in the Mojave. The precooler is a T20 unit with 45 kW of cooling and the car "
              "arrives half warm at 100 bar.",
        objective="Finish the fill with at least 10 K of margin to 85 degC and at least 85% SOC. "
                  "Slowing the ramp or lowering the set point are your levers.",
        setup=_hot_day,
        score=score_hot_day,
    ),
    Mission(
        key="cheapest",
        title="Cheapest fill",
        brief="A mild 15 degC day. Every kilowatt-hour of refrigeration costs the station money.",
        objective="Deliver the fill with the least refrigeration compressor energy per kg while finishing "
                  "in under five minutes and reaching 85% SOC. Warmer precooling and a slower ramp "
                  "trade against each other.",
        setup=_cheapest,
        score=score_cheapest,
    ),
    Mission(
        key="controller",
        title="Tune the dispenser controller",
        brief="The dispenser's PID loop has been left with poor gains. The pressure ramp lags and hunts.",
        objective="Choose Kp, Ki and Kd so the tank pressure tracks the 18.5 MPa/min ramp with an RMS "
                  "error below 0.5 MPa and no overshoot above 0.5 MPa.",
        setup=_controller,
        score=score_controller,
    ),
]

MISSION_BY_KEY = {m.key: m for m in MISSIONS}
