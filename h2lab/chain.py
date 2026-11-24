"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, h2lab/chain.py

What this file does
    Follows one kilogram of hydrogen around the fill: the electricity to make
    it in an electrolyser, to compress it into the banks and to chill it, then
    the electricity the car's fuel cell gives back, the round trip, the
    distance and the cost.

Where it fits in the model
    After it. The fill in the middle is simulation.py, untouched; this file
    only does bookkeeping on a finished FillResult. The one device it calls is
    the steady-flow compressor from devices.py, for the compression step.

The thermodynamics, step by step
    1. Electrolyser: electricity in per kilogram is an input. Its ceiling is
       the higher heating value, HHV = 285,830 kJ/kmol / 2.016 kg/kmol
       (Borgnakke Table A.10, liquid water), so the share kept is HHV / input.
    2. Compression: for each bank, two-stage compression with an isentropic
       efficiency from the supply pressure to that bank's pressure, weighted
       by how much of the fill came from each bank. The floor I compare it
       with is isothermal ideal-gas work, w = R T ln(P2/P1).
    3. Precooling: the refrigeration compressor work the fill recorded,
       divided by the kilograms delivered.
    4. Fuel cell: electricity out = efficiency x lower heating value, with
       LHV = 241,826 kJ/kmol / 2.016 (water leaves the car as vapour).
    5. Round trip = electricity out / electricity in.
    6. Cost = electricity price x electricity in, plus the station's build
       cost spread over the kilograms it sells with a capital recovery factor.

Sources
    Every number below is either a cited value (the source is named beside it
    and listed in the app under How it works, Sources) or marked DESIGN CHOICE,
    which means I picked it and say so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from .devices import StationCompressor
from .properties import Hydrogen
from .simulation import FillResult

KWH = 3.6e6  # J per kWh
M_H2 = 2.016  # kg/kmol
# Heating values from the enthalpy of formation of water, Borgnakke Table A.10:
# liquid water -285 830 kJ/kmol (higher), water vapour -241 826 kJ/kmol (lower).
HHV = 285830.0e3 / M_H2  # J/kg, 141.8 MJ/kg = 39.38 kWh/kg
LHV = 241826.0e3 / M_H2  # J/kg, 120.0 MJ/kg = 33.32 kWh/kg
R_H2 = 4124.3  # J/kg K, Borgnakke Table A.5

# Electricity a whole electrolyser system uses per kg of hydrogen.
# Ranges: IRENA, Green Hydrogen Cost Reduction (2020), 2020 status.
# PEWE default: 55 kWh/kg, the 2022 status in the U.S. DOE technical targets for
# PEM electrolysis. AEWE default: the middle of its range, a DESIGN CHOICE,
# because no status figure is published for it.
ELECTROLYSERS = {
    "PEWE": dict(name="PEWE, acid membrane", lo=50.0, hi=83.0, default=55.0, sourced=True),
    "AEWE": dict(name="AEWE, alkaline membrane", lo=57.0, hi=69.0, default=63.0, sourced=False),
}
# Pressure at which the electrolyser hands the hydrogen to the station compressor:
# 300 psi, about 2 MPa, the outlet pressure in DOE Hydrogen Program Record 19009.
SUPPLY_PRESSURE = 2.0e6
# Fuel cell system efficiency (electricity out over the lower heating value in).
# PEFC: 64% peak for the Toyota Mirai system, DOE Hydrogen Program Record 20005.
# AEFC: no vehicle system is on sale, so no system figure is published. DESIGN CHOICE.
FUEL_CELLS = {
    "PEFC": dict(name="PEFC, acid membrane", eta=0.64, sourced=True),
    "AEFC": dict(name="AEFC, alkaline membrane", eta=0.55, sourced=False),
}
# Distance: the 2024 Toyota Mirai XLE is EPA-rated at 402 miles on a 5.6 kg tank.
ETA_REF = 0.64
KM_PER_KG_REF = 402.0 * 1.609344 / 5.6  # 115.5 km/kg
# Money. Station cost: DOE Hydrogen Program Record 21002 (median about $1.9 million).
# Precooler share: Elgowainy and Reddi 2015 (about 10% of equipment cost).
STATION_CAPEX = 1.9e6
PRECOOLER_SHARE = 0.10
INTEREST = 0.08  # DESIGN CHOICE
LIFE_YEARS = 15  # DESIGN CHOICE
PUMP_PRICE = 34.55  # $/kg, California monthly average, 1 October 2024


@dataclass
class ChainInputs:
    """The choices around the fill: how the hydrogen is made, which fuel cell uses it, and the two cost inputs."""

    electrolyser: str = "PEWE"
    electrolyser_kwh_kg: float = 55.0
    supply_pressure_pa: float = SUPPLY_PRESSURE
    fuel_cell: str = "PEFC"
    fuel_cell_eta: float = 0.64
    electricity_price: float = 0.15  # $/kWh, DESIGN CHOICE
    cars_per_day: float = 40.0  # DESIGN CHOICE


def default_kwh(electrolyser: str) -> float:
    """Electricity per kilogram for an electrolyser type before the user edits it."""
    return ELECTROLYSERS[electrolyser]["default"]


def capital_recovery_factor(i: float = INTEREST, n: int = LIFE_YEARS) -> float:
    """Share of a loan repaid each year: i (1+i)^n / ((1+i)^n - 1)."""
    g = (1.0 + i) ** n
    return i * g / (g - 1.0)


def bank_shares(res: FillResult) -> list[float]:
    """Fraction of the delivered hydrogen that came from each bank, from the fill's own record."""
    s = res.series
    m_dot, idx = np.asarray(s["m_dot"], float), np.asarray(s["bank_idx"], float)
    ok = np.isfinite(m_dot) & np.isfinite(idx)
    total = float(m_dot[ok].sum())
    n = len(res.cfg.banks)
    if total <= 0:
        return [0.0] * n
    return [float(m_dot[ok & (idx == i)].sum()) / total for i in range(n)]


def isothermal_work(P_in: float, P_out: float, T: float) -> float:
    """Least possible work to compress an ideal gas at constant temperature, J/kg: R T ln(P2/P1)."""
    return R_H2 * T * math.log(P_out / P_in) if P_out > P_in else 0.0


def compression(res: FillResult, P_supply: float) -> dict:
    """Work to lift each bank's share from the supply pressure to that bank's pressure, with the model's own compressor.

    A fill draws from three banks at three pressures, so I compress each share to its own bank and weight the work
    by the share. Beside each I keep the isothermal ideal-gas floor, which no real compressor can beat.
    """
    cfg = res.cfg
    gas = Hydrogen(cfg.property_mode)
    comp = StationCompressor(eta_s=cfg.compressor.eta_s)
    shares = bank_shares(res)
    rows, w, w_min = [], 0.0, 0.0
    for b, x in zip(cfg.banks, shares):
        wi = comp.compress(gas, P_supply, cfg.T_amb, b.pressure_pa, cfg.T_amb)["w"]
        wi_min = isothermal_work(P_supply, b.pressure_pa, cfg.T_amb)
        rows.append(dict(name=b.name, P=b.pressure_pa, share=x, w=wi, w_min=wi_min))
        w += x * wi
        w_min += x * wi_min
    return dict(rows=rows, w=w, w_min=w_min, eta_s=comp.eta_s)


def per_kilogram(res: FillResult, inp: ChainInputs) -> dict:
    """Energy and money for one kilogram, station by station. Energies in kWh per kg dispensed."""
    m = max(res.m_added, 1e-9)
    # Electricity in, three steps: make it (an input), compress it (steady-flow compressor work, J/kg to kWh/kg)
    # and chill it (the refrigeration compressor work the fill recorded, shared over the kilograms delivered).
    comp = compression(res, inp.supply_pressure_pa)
    e_make = inp.electrolyser_kwh_kg
    e_comp = comp["w"] / KWH
    e_chill = res.E_comp_ref / KWH / m
    q_chill = res.E_cool / KWH / m
    e_in = e_make + e_comp + e_chill
    # Electricity out: the fuel cell turns a share (its efficiency) of the lower heating value into electricity.
    # This is the only place the fuel cell type enters, and everything after the fill follows from it.
    e_out = inp.fuel_cell_eta * LHV / KWH
    # Distance: the rated car's km per kg, scaled with the efficiency. The scaling is my simplification.
    km = KM_PER_KG_REF * inp.fuel_cell_eta / ETA_REF
    # Money: the station's price turned into a yearly payment, spread over the kilograms sold in a year,
    # plus the electricity for all three steps.
    kg_year = inp.cars_per_day * m * 365.0
    crf = capital_recovery_factor()
    capital = STATION_CAPEX * crf / kg_year
    power = inp.electricity_price * e_in
    cost = power + capital
    return dict(
        e_make=e_make, e_comp=e_comp, e_chill=e_chill, q_chill=q_chill, e_in=e_in, e_out=e_out,
        eta_electrolyser=(HHV / KWH) / e_make, round_trip=e_out / e_in, km_per_kg=km, kwh_in_per_km=e_in / km,
        station_kwh=e_comp + e_chill, comp=comp, shares=[r["share"] for r in comp["rows"]],
        kg_per_fill=m, kg_year=kg_year, crf=crf,
        cost_power=power, cost_power_make=inp.electricity_price * e_make, cost_power_comp=inp.electricity_price * e_comp,
        cost_power_chill=inp.electricity_price * e_chill,
        cost_capital=capital, cost_capital_precooler=capital * PRECOOLER_SHARE, cost_capital_rest=capital * (1.0 - PRECOOLER_SHARE),
        cost=cost, cost_per_km=cost / km,
    )


def compare_fuel_cells(res: FillResult, inp: ChainInputs | None = None) -> dict:
    """The same kilogram through each fuel cell type, so the two can be set side by side.

    I keep every other choice in `inp` as it is (electrolyser, electricity price, cars per day) and only swap the
    fuel cell. The type picked in `inp` keeps its own efficiency, in case it was edited in Engineer; the other type
    uses its value from FUEL_CELLS. Returns {type: the per_kilogram() result for that type}.
    """
    inp = inp or ChainInputs()
    out = {}
    for key, cell in FUEL_CELLS.items():
        eta = inp.fuel_cell_eta if key == inp.fuel_cell else cell["eta"]
        out[key] = per_kilogram(res, replace(inp, fuel_cell=key, fuel_cell_eta=eta))
    return out


def punch_list(res: FillResult) -> list[dict]:
    """The checks a station must pass before hand-over (a punch list), read off the finished fill.

    The limits are the ones the fill model already enforces (85 degC, 87.5 MPa, 60 g/s, from SAE J2601), the 180 s
    the app uses as a real station's aim, and a 0.1% book-keeping tolerance, which is a DESIGN CHOICE.
    """
    s = res.series
    P_peak = float(np.nanmax(s["P_car"])) / 1e6
    flow = float(np.nanmax(s["m_dot"])) * 1000.0
    T_peak = res.T_peak - 273.15
    e_err = abs(100.0 * res.energy["closure_error"])
    m_err = abs(100.0 * res.energy["mass_transfer_error"])
    items = [
        ("Gas in the car's tank stays below 85 °C", "below 85 °C", f"{T_peak:.1f} °C", T_peak < 85.0),
        ("Tank pressure stays below 87.5 MPa", "below 87.5 MPa", f"{P_peak:.1f} MPa", P_peak < 87.5),
        ("Flow never passes 60 g/s", "60 g/s or less", f"{flow:.1f} g/s", flow <= 60.0 + 1e-6),
        ("Fill runs to its target without a safety stop", "no stop", "stopped" if res.aborted else "no stop", not res.aborted),
        ("Fill is done within three minutes", "180 s or less", f"{res.fill_time:.0f} s", res.fill_time <= 180.0),
        ("Energy books balance", "within 0.1%", f"{e_err:.4f}%", e_err < 0.1),
        ("Mass books balance", "within 0.1%", f"{m_err:.4f}%", m_err < 0.1),
    ]
    return [dict(n=i + 1, check=c, limit=l, measured=v, closed=bool(ok)) for i, (c, l, v, ok) in enumerate(items)]
