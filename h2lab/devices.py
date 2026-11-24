"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, h2lab/devices.py

What this file does
    The steady-flow devices of the station: the dispenser valve, the
    precooler, the refrigeration cycle behind the precooler, and the station
    compressor.

Where it fits in the model
    Between the tanks. A bank empties through the valve and the precooler into
    the car. These devices hold no mass or energy of their own, so I solve them
    algebraically at every time step in simulation.py. The compressor is not
    part of the fill itself; chain.py uses it afterwards for the electricity
    that put the hydrogen into the banks.

The thermodynamics
    For every steady-state, steady-flow device I start from the first law per
    unit mass with kinetic and potential energy neglected (Borgnakke and
    Sonntag, control-volume chapter):

        q + h_i = h_e + w        or        h_e = h_i + q - w

    DispenserValve      Throttling: q = 0 and w = 0, so h_e = h_i. The flow
                        rate comes from the isentropic nozzle relation through
                        the valve seat, with an opening from 0 to 1. At the
                        pressure ratios of a fill the flow is almost always
                        choked, so it depends only on the upstream state.
    Precooler           Heat exchanger: w = 0, so q = h_e - h_i, negative for
                        the hydrogen. It is controlled by a set point: the
                        outlet is held at T_set and the heat removed follows
                        the flow, Q = m_dot (h_i - h_set), up to a capacity
                        Q_max. Past Q_max the gas simply leaves warmer.
    RefrigerationCycle  Ideal vapor-compression cycle with a real compressor:
                        1 saturated vapour, 1-2 compression with an isentropic
                        efficiency, 2-3 condenser to saturated liquid,
                        3-4 throttle (h4 = h3), 4-1 evaporator.
                        COP = q_L / w_c = (h1 - h4) / (h2 - h1).
    StationCompressor   Two stages with an intercooler. Each stage is
                        isentropic compression corrected by an efficiency:
                        h_e = h_i + (h_es - h_i) / eta_s, w = h_e - h_i.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .properties import Hydrogen, Refrigerant

# SAE J2601 is the fuelling standard for hydrogen cars. Its process limits (Reddi, Elgowainy, Rustagi, Gupta, Int. J. Hydrogen
# Energy 42 (2017), Table 1): maximum flow rate 60 g/s, maximum pressure
# 87.5 MPa (125% of 70 MPa NWP), gas temperature between -40 and 85 degC,
# fuel delivery temperature between -40 and -17.5 degC at the breakaway.
MAX_FLOW_KG_S = 0.060
MAX_PRESSURE_PA = 87.5e6
MAX_GAS_TEMP_K = 273.15 + 85.0
MIN_GAS_TEMP_K = 273.15 - 40.0
PRECOOL_WINDOWS = {
    # SAE J2601 dispenser categories. Within the fill the T40 window is
    # -33 to -40 degC (US patent 10,794,538 describing J2601; the standard
    # itself is paywalled).
    "T40": (273.15 - 40.0, 273.15 - 33.0),
    "T30": (273.15 - 33.0, 273.15 - 26.0),
    "T20": (273.15 - 26.0, 273.15 - 17.5),
}


@dataclass
class DispenserValve:
    """
    Throttling valve. No heat, no work, so the first law leaves h_e = h_i.

    For the flow rate I use the isentropic flow function for a gas with
    specific heat ratio k:

        m_dot = Cd A x sqrt(rho_up P_up) psi(P_r)
        psi   = sqrt( 2k/(k-1) [ P_r^(2/k) - P_r^((k+1)/k) ] )   subsonic
        psi*  = sqrt(k) (2/(k+1))^((k+1)/(2(k-1)))               choked

    where x is the valve opening (0 to 1) and P_r = P_down / P_up. The
    choked branch applies when P_r is below the critical ratio
    (2/(k+1))^(k/(k-1)), which is 0.52 for hydrogen.
    """

    area: float = 2.0e-6  # m2 of fully open seat (about 1.6 mm diameter)
    Cd: float = 0.85
    opening: float = 0.0

    def mass_flow(self, gas: Hydrogen, P_up: float, T_up: float, P_down: float) -> float:
        """Mass flow rate through the seat, kg/s, for the current opening."""
        # A closed valve passes nothing, and gas only flows from high pressure to low.
        if self.opening <= 0.0 or P_up <= P_down:
            return 0.0
        # Step 1. Upstream state: k and density from the property model (real density in real-gas mode).
        k = gas.k(P_up, T_up)
        rho_up = gas.rho_PT(P_up, T_up)
        # Step 2. Compare the pressure ratio with the critical ratio. Below it the flow is choked: it has
        # reached the speed of sound at the seat and lowering the car's pressure further changes nothing.
        Pr = P_down / P_up
        Pr_crit = (2.0 / (k + 1.0)) ** (k / (k - 1.0))
        # Step 3. Flow function psi, choked or subsonic, then m_dot = Cd A x sqrt(rho_up P_up) psi.
        if Pr <= Pr_crit:
            psi = math.sqrt(k) * (2.0 / (k + 1.0)) ** ((k + 1.0) / (2.0 * (k - 1.0)))
        else:
            psi = math.sqrt(max(0.0, 2.0 * k / (k - 1.0) * (Pr ** (2.0 / k) - Pr ** ((k + 1.0) / k))))
        return self.Cd * self.area * self.opening * math.sqrt(rho_up * P_up) * psi

    @staticmethod
    def exit_temperature(gas: Hydrogen, P_in: float, T_in: float, P_out: float) -> float:
        """Throttling, h_e = h_i: I take h at the inlet state and find the temperature that has the same h at the outlet pressure.

        For an ideal gas h depends on T alone, so T does not change. Real hydrogen warms when throttled at
        these temperatures (negative Joule-Thomson coefficient), which is part of why precooling is needed.
        """
        h = gas.h_PT(P_in, T_in)
        return gas.T_from_P_h(P_out, h)


@dataclass
class Precooler:
    """
    Heat exchanger that chills the hydrogen before the hose.

    The hydrogen side is a steady-flow device with no work, so the first law
    gives q = h_e - h_i. How it is controlled: by a set point. The user picks
    the outlet temperature T_set; I hold the outlet there and let the heat
    removed follow the flow. Nothing else is tuned. If the heat needed is more
    than the capacity Q_max, the precooler removes Q_max and the gas leaves
    warmer: h_e = h_i - Q_max / m_dot. I neglect pressure drop (isobaric).
    """

    T_set: float = 273.15 - 40.0  # K
    Q_max: float = 60.0e3  # W of cooling available (60 g/s from 25 to -40 degC needs about 55 kW)
    enabled: bool = True

    def outlet(self, gas: Hydrogen, P: float, T_in: float, m_dot: float):
        """Returns (T_out, Q_dot_removed [W, positive], h_in, h_out)."""
        h_in = gas.h_PT(P, T_in)
        # Switched off, no flow, or gas already colder than the set point: it passes through unchanged.
        if not self.enabled or m_dot <= 0.0 or T_in <= self.T_set:
            return T_in, 0.0, h_in, h_in
        # Step 1. Heat that must leave to reach the set point, from the first law with w = 0:
        # Q = m_dot (h_in - h_set), both enthalpies at the line pressure.
        h_set = gas.h_PT(P, self.T_set)
        Q_needed = m_dot * (h_in - h_set)
        # Step 2. Within capacity: the outlet is at the set point.
        if Q_needed <= self.Q_max:
            return self.T_set, Q_needed, h_in, h_set
        # Step 3. Over capacity: remove Q_max, get the outlet enthalpy from the same balance and read T from (P, h).
        h_out = h_in - self.Q_max / m_dot
        return gas.T_from_P_h(P, h_out), self.Q_max, h_in, h_out


@dataclass
class RefrigerationCycle:
    """
    Vapor-compression refrigeration cycle that carries the precooler's load.

    The cycle load is not an input: it is whatever heat the precooler removed
    at that instant, so the compressor works harder when more hydrogen flows.
    State numbering as in Borgnakke and Sonntag:
      1 saturated vapour leaving the evaporator at T_evap
      2 compressor exit at the condenser pressure
      3 saturated liquid leaving the condenser at T_cond
      4 after the expansion valve, h4 = h3
    """

    refrigerant: str = "R134a"
    T_evap: float = 273.15 - 48.0  # K, must sit below the precooler set point
    T_cond: float = 273.15 + 40.0  # K, must sit above ambient
    eta_s: float = 0.75  # compressor isentropic efficiency

    def solve(self, Q_L: float) -> dict:
        """
        Given the cooling load Q_L [W], return every state and performance
        number: refrigerant flow, compressor power, COP, heat rejected.
        """
        ref = Refrigerant(self.refrigerant)
        # The condenser has to stay below the critical temperature or there is no saturated liquid (matters for CO2).
        T_cond = min(self.T_cond, ref.T_crit() - 2.0)
        # The two pressures of the cycle are the saturation pressures at the evaporator and condenser temperatures.
        P_L = ref.Psat(self.T_evap)
        P_H = ref.Psat(T_cond)
        # State 1: saturated vapour leaving the evaporator.
        h1 = ref.h_sat(self.T_evap, 1.0)
        s1 = ref.s_sat(self.T_evap, 1.0)
        # State 2: I first compress isentropically to P_H (s2s = s1), then correct with the isentropic
        # efficiency, eta_s = (h2s - h1) / (h2 - h1), so the real compressor takes more work.
        h2s = ref.h_Ps(P_H, s1)
        h2 = h1 + (h2s - h1) / self.eta_s
        T2 = ref.T_Ph(P_H, h2)
        s2 = ref.s_Ph(P_H, h2)
        # State 3: saturated liquid leaving the condenser.
        h3 = ref.h_sat(T_cond, 0.0)
        s3 = ref.s_sat(T_cond, 0.0)
        # State 4: after the expansion valve. Throttling, so h4 = h3.
        h4 = h3
        s4 = ref.s_Ph(P_L, h4)
        # First law on the evaporator and on the compressor, per kg of refrigerant, then COP = q_L / w_c.
        q_L = h1 - h4
        w_c = h2 - h1
        cop = q_L / w_c if w_c > 0 else float("nan")
        # Refrigerant flow needed to carry the load: Q_L = m_ref q_L.
        m_ref = Q_L / q_L if q_L > 0 else 0.0
        return {
            "P_L": P_L,
            "P_H": P_H,
            "T1": self.T_evap,
            "T2": T2,
            "T3": T_cond,
            "T4": self.T_evap,
            "h1": h1,
            "h2": h2,
            "h2s": h2s,
            "h3": h3,
            "h4": h4,
            "s1": s1,
            "s2": s2,
            "s3": s3,
            "s4": s4,
            "q_L": q_L,
            "w_c": w_c,
            "COP": cop,
            "m_ref": m_ref,
            "W_comp": m_ref * w_c,
            "Q_H": m_ref * (h2 - h3),
            "Q_L": Q_L,
        }


@dataclass
class StationCompressor:
    """
    Two-stage reciprocating compressor with an intercooler, used to move
    hydrogen from the low-pressure supply (or the low bank) into the medium
    and high banks between vehicles.

    Per stage, with isentropic efficiency eta_s:
        h_es = h at (P_e, s_i)          isentropic exit
        h_e  = h_i + (h_es - h_i)/eta_s  actual exit
        w    = h_e - h_i                 work input per kg
    The intercooler is a steady-flow heat exchanger that returns the gas to
    T_intercool before the second stage: q_ic = h_after - h_before < 0.
    The pressure ratio is split evenly between the two stages, which
    minimises the total work for equal stage efficiencies.
    """

    m_dot_max: float = 0.030  # kg/s, about 100 kg/h, a typical station compressor
    eta_s: float = 0.70
    T_intercool_offset: float = 10.0  # K above ambient after the intercooler
    enabled: bool = False

    def compress(self, gas: Hydrogen, P_in: float, T_in: float, P_out: float, T_amb: float) -> dict:
        """Return per-kg work, intercooler heat and exit temperature for a flow from P_in to P_out."""
        if P_out <= P_in:
            return {"w": 0.0, "q_ic": 0.0, "T_out": T_in, "T_mid": T_in, "P_mid": P_in}
        # Step 1. Equal pressure ratio per stage, so the pressure between the stages is the geometric mean.
        P_mid = math.sqrt(P_in * P_out)
        # Step 2. First stage: isentropic compression to P_mid, corrected with the isentropic efficiency.
        h_i = gas.h_PT(P_in, T_in)
        h_mid = h_i + (gas.h_from_T_P_isentropic(P_in, T_in, P_mid) - h_i) / self.eta_s
        T_mid = gas.T_from_P_h(P_mid, h_mid)
        # Step 3. Intercooler: back down to a little above ambient at constant pressure (it never heats the gas).
        T_ic = max(T_amb + self.T_intercool_offset, 200.0)
        T_ic = min(T_ic, T_mid)
        h_ic = gas.h_PT(P_mid, T_ic)
        # Step 4. Second stage, the same way, from the intercooled state. Total work is the sum of the two stages.
        h_o = h_ic + (gas.h_from_T_P_isentropic(P_mid, T_ic, P_out) - h_ic) / self.eta_s
        T_out = gas.T_from_P_h(P_out, h_o)
        return {
            "w": (h_mid - h_i) + (h_o - h_ic),
            "q_ic": h_ic - h_mid,
            "T_out": T_out,
            "T_mid": T_mid,
            "P_mid": P_mid,
            "w1": h_mid - h_i,
            "w2": h_o - h_ic,
        }
