"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, h2lab/properties.py

What this file does
    Gives every other file the properties of hydrogen (and of the refrigerant
    in the precooler's cycle). I wrote two modes for hydrogen and the user
    picks one:

    "ideal"  The course route. Ideal gas with constant specific heats from
             Borgnakke and Sonntag, Table A.5 (hydrogen at 300 K):
                 R = 4.1243 kJ/kg K, cp = 14.209 kJ/kg K,
                 cv = 10.085 kJ/kg K, k = 1.409
             so   Pv = RT,  u = cv T,  h = cp T   (u and h measured from 0 K).

    "real"   Real gas. Properties come from CoolProp, an open property
             library that uses the Helmholtz equation of state for normal
             hydrogen (Leachman et al. 2009). I need it because hydrogen at
             70 to 90 MPa has a compressibility factor Z of about 1.5, so
             Pv = RT overpredicts the mass in a 700 bar tank by about 50%.

Where it fits in the model
    At the bottom. The tanks, the valve, the precooler and the compressor never
    use a property formula of their own; they ask this file. That is how one
    switch changes the whole station from ideal gas to real gas.

Units
    Every function takes SI: Pa, K, kg/m3, J/kg. The interface converts to
    MPa, degC and kJ for display. The refrigerant is always evaluated with
    CoolProp (the course equivalent is Table B.5 for R-134a).
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import CoolProp.CoolProp as CP

    COOLPROP_AVAILABLE = True
except ImportError:  # pragma: no cover
    CP = None
    COOLPROP_AVAILABLE = False


# Table A.5 values for hydrogen (Borgnakke and Sonntag). kJ/kg K -> J/kg K.
R_H2 = 4.1243e3
CP_H2 = 14.209e3
CV_H2 = 10.085e3
K_H2 = CP_H2 / CV_H2  # 1.409 to three decimals, as printed in the table

T_REF_SOC = 288.15  # 15 degC, the SOC reference temperature in SAE J2601
P_NWP = 70.0e6  # nominal working pressure of an H70 vehicle, Pa
RHO_FULL = 40.2  # kg/m3, hydrogen density at 70 MPa and 15 degC (SAE J2601 100% SOC)


@dataclass
class State:
    """A single-phase gas state. All SI."""

    P: float  # Pa
    T: float  # K
    rho: float  # kg/m3
    u: float  # J/kg
    h: float  # J/kg
    s: float  # J/kg K


class Hydrogen:
    """Hydrogen property model with a switch between ideal and real gas.

    Every method has the same two branches: the Table A.5 formula in ideal mode, a CoolProp call in real mode.
    """

    def __init__(self, mode: str = "ideal"):
        if mode not in ("ideal", "real"):
            raise ValueError("mode must be 'ideal' or 'real'")
        if mode == "real" and not COOLPROP_AVAILABLE:
            raise RuntimeError("CoolProp is not installed; real-gas mode unavailable")
        self.mode = mode
        self.fluid = "Hydrogen"

    # ---- fundamental relations -------------------------------------------

    def rho_PT(self, P: float, T: float) -> float:
        """Density from pressure and temperature. Ideal: rho = P / (R T)."""
        if self.mode == "ideal":
            return P / (R_H2 * T)
        return CP.PropsSI("D", "P", P, "T", T, self.fluid)

    def P_rhoT(self, rho: float, T: float) -> float:
        if self.mode == "ideal":
            return rho * R_H2 * T
        return CP.PropsSI("P", "D", rho, "T", T, self.fluid)

    def u_PT(self, P: float, T: float) -> float:
        """Specific internal energy. Ideal: u = cv T."""
        if self.mode == "ideal":
            return CV_H2 * T
        return CP.PropsSI("U", "P", P, "T", T, self.fluid)

    def h_PT(self, P: float, T: float) -> float:
        """Specific enthalpy. Ideal: h = cp T (so h = u + Pv = u + RT)."""
        if self.mode == "ideal":
            return CP_H2 * T
        return CP.PropsSI("H", "P", P, "T", T, self.fluid)

    def s_PT(self, P: float, T: float) -> float:
        """Specific entropy. Ideal: s = cp ln(T/T0) - R ln(P/P0), T0 = 298.15 K, P0 = 1 bar."""
        import math

        if self.mode == "ideal":
            return CP_H2 * math.log(T / 298.15) - R_H2 * math.log(P / 1.0e5)
        return CP.PropsSI("S", "P", P, "T", T, self.fluid)

    def T_from_rho_u(self, rho: float, u: float) -> float:
        """
        Temperature from density and specific internal energy. The tank solver
        stores mass and internal energy, so this is how I get the state back
        from them. Ideal: T = u / cv.
        """
        if self.mode == "ideal":
            return u / CV_H2
        return CP.PropsSI("T", "D", rho, "U", u, self.fluid)

    def T_from_P_h(self, P: float, h: float) -> float:
        """
        Exit temperature of a throttle (h_e = h_i) or a heat exchanger with a
        known exit enthalpy. Ideal: T = h / cp, so a throttle leaves T unchanged.
        Real hydrogen has a negative Joule-Thomson coefficient at room
        temperature, so throttling warms it by tens of kelvin.
        """
        if self.mode == "ideal":
            return h / CP_H2
        return CP.PropsSI("T", "P", P, "H", h, self.fluid)

    def h_from_T_P_isentropic(self, P1: float, T1: float, P2: float) -> float:
        """Enthalpy after an isentropic change from (P1, T1) to P2. Used by the compressor."""
        if self.mode == "ideal":
            T2s = T1 * (P2 / P1) ** ((K_H2 - 1.0) / K_H2)
            return CP_H2 * T2s
        s1 = CP.PropsSI("S", "P", P1, "T", T1, self.fluid)
        return CP.PropsSI("H", "P", P2, "S", s1, self.fluid)

    def k(self, P: float, T: float) -> float:
        """Ratio of specific heats, used in the choked-flow relation of the valve."""
        if self.mode == "ideal":
            return K_H2
        cp = CP.PropsSI("C", "P", P, "T", T, self.fluid)
        cv = CP.PropsSI("O", "P", P, "T", T, self.fluid)
        return cp / cv

    def Z(self, P: float, T: float) -> float:
        """Compressibility factor Z = Pv / RT. Exactly 1 in ideal mode."""
        if self.mode == "ideal":
            return 1.0
        return P / (self.rho_PT(P, T) * R_H2 * T)

    def state_PT(self, P: float, T: float) -> State:
        return State(
            P=P,
            T=T,
            rho=self.rho_PT(P, T),
            u=self.u_PT(P, T),
            h=self.h_PT(P, T),
            s=self.s_PT(P, T),
        )

    def state_rho_u(self, rho: float, u: float) -> State:
        T = self.T_from_rho_u(rho, u)
        P = self.P_rhoT(rho, T)
        return State(P=P, T=T, rho=rho, u=u, h=u + P / rho, s=self.s_PT(P, T))


def soc_from_density(rho: float) -> float:
    """
    State of charge as SAE J2601 defines it: the stored density relative to
    the density at the nominal working pressure (70 MPa) and 15 degC,
    40.2 kg/m3. 100% SOC is a hard limit (never overfill).
    """
    return 100.0 * rho / RHO_FULL


class Refrigerant:
    """
    Refrigerant properties for the precooler's vapor-compression cycle.
    Always CoolProp; R-134a is the textbook fluid (Borgnakke and Sonntag
    Table B.5). The user may also choose R-410A or CO2 (R-744).
    """

    def __init__(self, name: str = "R134a"):
        if not COOLPROP_AVAILABLE:
            raise RuntimeError("CoolProp is not installed")
        self.name = name

    def Psat(self, T: float) -> float:
        return CP.PropsSI("P", "T", T, "Q", 0, self.name)

    def h_sat(self, T: float, quality: float) -> float:
        return CP.PropsSI("H", "T", T, "Q", quality, self.name)

    def s_sat(self, T: float, quality: float) -> float:
        return CP.PropsSI("S", "T", T, "Q", quality, self.name)

    def h_Ps(self, P: float, s: float) -> float:
        return CP.PropsSI("H", "P", P, "S", s, self.name)

    def T_Ph(self, P: float, h: float) -> float:
        return CP.PropsSI("T", "P", P, "H", h, self.name)

    def s_Ph(self, P: float, h: float) -> float:
        return CP.PropsSI("S", "P", P, "H", h, self.name)

    def T_crit(self) -> float:
        return CP.PropsSI("Tcrit", self.name)
