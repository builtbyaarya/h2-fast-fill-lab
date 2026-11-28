"""
Station energy and cost accounting on one system boundary.

System boundary
    Hydrogen enters the station as gas at the supply pressure P_s and ambient
    temperature (the outlet of an electrolyser, 2 MPa by default) and leaves
    in the vehicle tank. Electricity crosses the boundary at two machines:
    the station compressor that refills the cascade banks, and the
    compressor of the precooling refrigeration cycle. Hydrogen production and
    the fuel cell lie outside the station boundary and are reported
    separately for the pathway efficiency.

Station compressor
    N stages with equal pressure ratio, intercooling to T_amb + dT_ic after
    every stage and an aftercooler to the same temperature. Each stage is an
    isentropic real-gas enthalpy rise divided by the isentropic efficiency:
        w_j = [h(P_j+1, s_j) - h(P_j, T_j)] / eta_s
    The electricity is the gas-side work divided by the mechanical and the
    motor efficiency:
        e = sum_j w_j / (eta_mech eta_motor)

What is compressed, and to what pressure
    The fill draws a mass m_i from bank i and leaves it at a lower pressure.
    The compressor then returns each bank to its initial state. It delivers
    against the bank pressure of the moment, which rises as the bank refills.
    The banks are taken to be at ambient temperature during this slow refill.
    The work per fill is therefore
        W_i = integral from m_i,end to m_i,0 of w(P_s -> P_i(m)) dm ,
        P_i(m) = P(rho = m / V_i, T_amb)
    Every kilogram delivered to the vehicle passes the compressor exactly
    once, and nothing is compressed after the banks (the dispenser only
    throttles), so no compression work is counted twice. The class model
    charged every kilogram with the work to the initial bank pressure; that
    number is kept as `e_comp_class` for the reconciliation table.

Refrigeration
    The fill model integrates the refrigeration compressor work
    Q_pc / COP(T_evap) with T_evap = T_set - pinch. Here it is divided by the
    drive efficiency of that compressor.

Capital cost
    The DOE reference cost (1.9 M$, 2016 dollars) belongs to stations with a
    median capacity of 1,500 kg/day. It is scaled to the capacity of the
    station studied here with C = C_ref (Q / Q_ref)^n, n = 0.7, and the range
    n = 0.6 to 0.8 is reported.

Operating cost per kilogram
    energy charge  p_e (e_comp + e_ref)
    demand charge  c_d P_15 / M_month, where P_15 is the 15-minute average
                   station power during back-to-back fills: the station
                   compressor at rated power plus the refrigeration energy of
                   the fills that fit in 15 minutes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .props import P_rhoT
from .twozone import FillOut, table

KWH = 3.6e6
M_H2 = 2.01588
HHV = 285830.0e3 / M_H2      # J/kg, higher heating value (Borgnakke and Sonntag, Table A.10)
LHV = 241826.0e3 / M_H2      # J/kg, lower heating value


@dataclass
class CompressorSpec:
    stages: int = 5
    eta_s: float = 0.70          # isentropic efficiency of each stage
    eta_mech: float = 0.95       # mechanical (crank, seals, bearings)
    eta_motor: float = 0.95      # electric motor and drive
    dT_ic: float = 10.0          # K above ambient after each cooler
    P_supply: float = 2.0e6      # Pa
    rated_kg_h: float = 20.0     # kg/h


@dataclass
class Economics:
    price_energy: float = 0.15       # $/kWh (assumed, as in the class model)
    demand_charge: float = 15.0      # $/kW per month (assumed)
    t_idle: float = 120.0            # s between two fills on one dispenser at peak (assumed)
    cars_per_day: float = 40.0       # (assumed)
    capex_ref: float = 1.9e6         # $ (2016), median capital cost of 111 California stations (DOE Record 21002)
    capacity_ref: float = 1500.0     # kg/day, median daily capacity of the same stations (DOE Record 21002)
    scale_n: float = 0.7             # capacity exponent of the capital cost (range 0.6 to 0.8, assumed)
    capacity: float | None = None    # kg/day the station is sized for (None: the daily mass dispensed)
    interest: float = 0.08           # (assumed)
    life_years: int = 15             # (assumed)
    fixed_om_frac: float = 0.03      # yearly fixed operation and maintenance as a fraction of capex (assumed)
    eta_ref_drive: float = 0.90      # mechanical x motor efficiency of the refrigeration compressor (assumed)
    electrolyser_kwh_kg: float = 55.0
    fuel_cell_eta: float = 0.64      # of LHV


def stage_table(spec: CompressorSpec, P_out: float, T_amb: float) -> list[dict]:
    """State and work of every stage for compression from the supply pressure to P_out (real gas, CoolProp)."""
    import CoolProp.CoolProp as CP
    n = spec.stages
    ratio = (P_out / spec.P_supply) ** (1.0 / n)
    T_in = T_amb
    rows = []
    for j in range(n):
        P1 = spec.P_supply * ratio ** j
        P2 = P1 * ratio
        h1 = CP.PropsSI("H", "P", P1, "T", T_in, "Hydrogen")
        s1 = CP.PropsSI("S", "P", P1, "T", T_in, "Hydrogen")
        h2s = CP.PropsSI("H", "P", P2, "S", s1, "Hydrogen")
        w = (h2s - h1) / spec.eta_s
        T2 = CP.PropsSI("T", "P", P2, "H", h1 + w, "Hydrogen")
        T_next = T_amb + spec.dT_ic
        q = h1 + w - CP.PropsSI("H", "P", P2, "T", T_next, "Hydrogen")
        rows.append(dict(stage=j + 1, P_in=P1, P_out=P2, T_in=T_in, T_out=T2, w_s=h2s - h1, w=w, q_cool=q))
        T_in = T_next
    return rows


_CURVES: dict = {}


def work_curve(spec: CompressorSpec, T_amb: float):
    """Gas-side specific work (J/kg) against delivery pressure, tabulated once per compressor and ambient."""
    key = (spec.stages, spec.eta_s, spec.dT_ic, spec.P_supply, round(T_amb, 2))
    if key not in _CURVES:
        P = np.linspace(spec.P_supply * 1.05, 100.0e6, 50)
        _CURVES[key] = (P, np.array([sum(r["w"] for r in stage_table(spec, p, T_amb)) for p in P]))
    return _CURVES[key]


def isothermal_ideal(P1, P2, T):
    """Ideal-gas isothermal work, the reference minimum quoted in the class report."""
    return 4124.5 * T * math.log(P2 / P1)


def refill_work(out: FillOut, spec: CompressorSpec, n_quad: int = 24) -> dict:
    """Gas-side work to return every bank to its initial state, with the delivery pressure following the bank."""
    tab = table()
    T_amb = out.fill.T_amb
    Pg, Wg = work_curve(spec, T_amb)
    V = np.array(out.fill.station.bank_V, float)
    rows, W, W_class, m_tot = [], 0.0, 0.0, 0.0
    for i in range(len(V)):
        m0, m1 = out.bank_m0[i], out.bank_m_end[i]
        dm = m0 - m1
        if dm <= 1.0e-9:
            rows.append(dict(bank=i, m=0.0, P_end=out.fill.station.bank_P[i], P0=out.fill.station.bank_P[i], w=0.0, w_class=0.0))
            continue
        m = np.linspace(m1, m0, n_quad)
        P = np.array([P_rhoT(tab, mm / V[i], T_amb) for mm in m])
        w = np.interp(P, Pg, Wg)
        Wi = float(np.sum(0.5 * (w[1:] + w[:-1]) * np.diff(m)))
        w_class = float(np.interp(P[-1], Pg, Wg))
        rows.append(dict(bank=i, m=dm, P_end=P[0], P0=P[-1], w=Wi / dm, w_class=w_class))
        W += Wi
        W_class += w_class * dm
        m_tot += dm
    return dict(rows=rows, W=W, W_class=W_class, m=m_tot)


def capex(eco: "Economics", kg_day: float, n: float | None = None) -> float:
    """Station capital cost scaled from the DOE reference station by the capacity power law C = C_ref (Q/Q_ref)^n."""
    n = eco.scale_n if n is None else n
    return eco.capex_ref * (kg_day / eco.capacity_ref) ** n


def crf(i: float, n: int) -> float:
    g = (1.0 + i) ** n
    return i * g / (g - 1.0)


def account(out: FillOut, spec: CompressorSpec | None = None, eco: Economics | None = None) -> dict:
    """Specific electricity (kWh/kg) of each component, operating cost and pathway efficiency for one fill."""
    spec = spec or CompressorSpec()
    eco = eco or Economics()
    m = max(out.m_added, 1.0e-9)
    rw = refill_work(out, spec)
    drive = spec.eta_mech * spec.eta_motor
    e_comp = rw["W"] / drive / m / KWH
    e_comp_gas = rw["W"] / m / KWH
    e_comp_class = rw["W_class"] / m / KWH                  # class-model accounting, gas side, no drive losses
    e_ref_shaft = out.E_ref / m / KWH
    e_ref = e_ref_shaft / eco.eta_ref_drive
    q_cool = out.E_cool / m / KWH
    e_station = e_comp + e_ref
    # demand: 15-minute average power with back-to-back fills
    n15 = 900.0 / (out.t_fill + eco.t_idle)
    P_comp_rated = spec.rated_kg_h * np.interp(90.0e6, *work_curve(spec, out.fill.T_amb)) / drive / 3600.0 / 1000.0  # kW
    P15 = P_comp_rated + (out.E_ref / eco.eta_ref_drive / KWH) * n15 / 0.25
    M_month = eco.cars_per_day * m * 30.0
    c_energy = eco.price_energy * e_station
    c_demand = eco.demand_charge * P15 / M_month
    c_op = c_energy + c_demand
    # capital and utilisation
    kg_day = eco.cars_per_day * m
    kg_year = kg_day * 365.0
    cap_q = eco.capacity if eco.capacity is not None else kg_day
    ann = crf(eco.interest, eco.life_years) + eco.fixed_om_frac
    C_st = capex(eco, cap_q)
    c_cap = C_st * ann / kg_year
    c_cap_lo = capex(eco, cap_q, 0.8) * ann / kg_year      # n = 0.8 gives the lower cost below the reference capacity
    c_cap_hi = capex(eco, cap_q, 0.6) * ann / kg_year
    # pathway on one basis: electricity in per kg dispensed, electricity out of the fuel cell per kg
    e_prod = eco.electrolyser_kwh_kg
    e_out = eco.fuel_cell_eta * LHV / KWH
    return dict(
        e_comp=e_comp, e_comp_gas=e_comp_gas, e_comp_class=e_comp_class, e_ref=e_ref, e_ref_shaft=e_ref_shaft,
        q_cool=q_cool, e_station=e_station, banks=rw["rows"], P15=P15, P_comp_rated=P_comp_rated,
        c_energy=c_energy, c_demand=c_demand, c_op=c_op, c_cap=c_cap, c_cap_lo=c_cap_lo, c_cap_hi=c_cap_hi, capex=C_st,
        c_total=c_op + c_cap + eco.price_energy * e_prod,
        e_prod=e_prod, e_in=e_prod + e_station, e_out=e_out, round_trip=e_out / (e_prod + e_station),
        eta_station=(LHV / KWH) / (LHV / KWH + e_station), peak_ref_kW=out.Wref_max / eco.eta_ref_drive / 1000.0,
        peak_cool_kW=out.Qpc_max / 1000.0, COP_mean=out.E_cool / out.E_ref if out.E_ref > 0 else float("nan"),
    )
