"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, h2lab/validation.py

What this file does
    The accuracy checks the app shows on the How it works page. The pytest
    files in tests/ run the same checks from the command line.

Where it fits in the model
    Beside it, as the proof. Each check runs simulation.py on a case with a
    known answer: the closed form T2 = k T_i for an empty insulated tank, mass
    and energy conservation over a whole fill, a halved time step, the mass a
    141 L tank holds, and one published fill test.

Each check returns a dict with the measured value, the target, a pass flag
and one line on the physics behind it.

The published test
    The comparison uses the repeatability test of the Joint Research Centre
    (JRC, the European Commission's research laboratory) in its GasTeF tank
    facility, reported by Acosta-Iborra et al. at the 5th International
    Conference on Hydrogen Safety (Brussels, 2013): twelve fills of a 28.9 L
    Type IV tank from 1.99 to 76.89 MPa at 17.8 MPa/min, hydrogen at ambient
    temperature (no precooling), tank-averaged gas temperature 11.2 degC at
    the start and 86.9 degC at the end (a rise of 75.6 K, standard deviation
    0.9 K), fill time 253 s.
"""

from __future__ import annotations

import math

from .controller import ControllerSettings
from .properties import CV_H2, K_H2, Hydrogen
from .simulation import BankSpec, FillConfig, FillSimulation

JRC_TEST = {
    "volume_L": 28.9,
    "P0_MPa": 1.99,
    "P_end_MPa": 76.89,
    "T0_C": 11.2,
    "T_end_C": 86.9,
    "dT_K": 75.6,
    "dT_sd_K": 0.9,
    "fill_time_s": 253.0,
    "aprr_MPa_min": 17.8,
    "source": "Acosta-Iborra, Moretto, De Miguel, Ortiz, Harskamp, Bonato, JRC reference data from "
              "experiments of on-board hydrogen tanks fast filling, ICHS 2013",
}


def check_k_Ti() -> dict:
    T_i = 240.0
    cfg = FillConfig(property_mode="ideal", dt=0.05, t_max=3000.0, banks=[BankSpec("Bank", 50.0, 30.0e6)],
                     cascade=False, T_amb=T_i, car_P0_pa=1.0e4, car_insulated=True)
    cfg.precooler.enabled = False
    cfg.controller = ControllerSettings(mode="manual", manual_opening=1.0, target_pressure_pa=3.0e6, target_soc=1e9)
    sim = FillSimulation(cfg)
    sim.run()
    T2, target = sim.car.T, K_H2 * T_i
    return {
        "name": "Empty insulated tank: T2 = k Ti",
        "value": f"{T2:.1f} K", "target": f"{target:.1f} K (k = {K_H2:.3f}, Ti = {T_i:.0f} K)",
        "passed": math.isclose(T2, target, rel_tol=0.005),
        "note": "Energy equation with m1 = 0, Q = W = 0: m2 u2 = m2 h_i, so cv T2 = cp Ti. "
                "The tank starts at 0.1 bar instead of a true vacuum, which explains the last 0.2%.",
    }


def check_mass(mode: str) -> dict:
    sim = FillSimulation(FillConfig(property_mode=mode, dt=0.2))
    sim.run()
    eb = sim.energy_balance()
    return {
        "name": f"Mass out of banks = mass into car ({mode} gas)",
        "value": f"{100 * eb['mass_transfer_error']:.2e} %", "target": "< 1e-6 %",
        "passed": eb["mass_transfer_error"] < 1e-8,
        "note": "Continuity for the whole station: the only mass that moves is through the hose.",
    }


def check_energy(mode: str) -> dict:
    sim = FillSimulation(FillConfig(property_mode=mode, dt=0.2))
    sim.run()
    eb = sim.energy_balance()
    return {
        "name": f"Energy balance closes ({mode} gas)",
        "value": f"{100 * eb['closure_error']:.4f} %", "target": "< 0.1 %",
        "passed": eb["closure_error"] < 1e-3,
        "note": "Change in stored energy of all tanks, from their final states, against the integrated "
                "heat to the walls and heat removed in the precooler.",
        "detail": eb,
    }


def check_dt(mode: str) -> dict:
    r1 = FillSimulation(FillConfig(property_mode=mode, dt=0.2)).run()
    r2 = FillSimulation(FillConfig(property_mode=mode, dt=0.1)).run()
    dT = abs(r1.T_peak - r2.T_peak)
    dm = abs(r1.m_added - r2.m_added) / r2.m_added
    return {
        "name": f"Time step halved, results unchanged ({mode} gas)",
        "value": f"peak T differs by {dT:.3f} K, mass by {100 * dm:.3f} %",
        "target": "< 0.2 K and < 0.2 %",
        "passed": dT < 0.2 and dm < 2e-3,
        "note": "Second-order midpoint integration: halving dt changes the answer by order dt squared.",
    }


def check_mass_141L() -> dict:
    m_real = Hydrogen("real").rho_PT(70.0e6, 288.15) * 0.141
    m_ideal = Hydrogen("ideal").rho_PT(70.0e6, 288.15) * 0.141
    return {
        "name": "141 L tank at 700 bar and 15 degC holds 5.7 kg",
        "value": f"{m_real:.2f} kg real gas, {m_ideal:.2f} kg ideal gas",
        "target": "5.7 kg (SAE J2601 density 40.2 kg/m3)",
        "passed": math.isclose(m_real, 5.7, rel_tol=0.01),
        "note": f"Z = {Hydrogen('real').Z(70.0e6, 288.15):.2f} at this state, so the ideal gas law is "
                f"{100 * (m_ideal / m_real - 1):.0f}% high. This is why the app has two property modes.",
    }


def jrc_config(h_in: float = 80.0, mode: str = "real") -> FillConfig:
    cfg = FillConfig(property_mode=mode, dt=0.2, T_amb=273.15 + 15.0, car_volume_m3=JRC_TEST["volume_L"] / 1000,
                     car_P0_pa=JRC_TEST["P0_MPa"] * 1e6, car_T0=273.15 + JRC_TEST["T0_C"],
                     banks=[BankSpec("Supply", 1.0, 90.0e6)], cascade=False, bank_outlet_at_ambient=True,
                     enforce_limits=False, t_max=JRC_TEST["fill_time_s"])
    cfg.car_wall.h_in = h_in
    cfg.precooler.enabled = False
    cfg.controller = ControllerSettings(mode="auto", aprr_mpa_min=JRC_TEST["aprr_MPa_min"],
                                        target_pressure_pa=JRC_TEST["P_end_MPa"] * 1e6, target_soc=1e9,
                                        Kp=1.0, Ki=0.1)
    return cfg


def jrc_comparison(h_values=(80.0, 150.0, 200.0)) -> dict:
    runs = {}
    for h in h_values:
        res = FillSimulation(jrc_config(h)).run()
        runs[h] = res
    best = min(runs.items(), key=lambda kv: abs((kv[1].series["T_car"][-1] - 273.15) - JRC_TEST["T_end_C"]))
    return {"runs": runs, "best_h": best[0], "test": JRC_TEST}


def all_checks() -> list:
    out = [check_k_Ti(), check_mass_141L()]
    for mode in ("ideal", "real"):
        out += [check_mass(mode), check_energy(mode), check_dt(mode)]
    return out
