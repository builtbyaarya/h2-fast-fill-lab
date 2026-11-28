"""
Tabulated real-gas hydrogen properties for the research model.

Source of the numbers
    Every value is generated from CoolProp, which implements the Helmholtz
    energy equation of state for normal hydrogen of Leachman et al. (2009)
    and the viscosity and thermal conductivity formulations distributed with
    it. The table is a regular grid in density and temperature, because the
    equation of state is explicit in those two variables and the tank model
    stores mass and internal energy.

Why a table
    One fill needs about 10^5 property evaluations, and the optimisation and
    the sensitivity analysis need about 10^4 fills. Bilinear interpolation on
    the grid below reproduces CoolProp to within 0.02 % in pressure and
    0.01 K in temperature over the range used (tests/test_research.py), and it
    lets the time loop be compiled.

Grid
    density      0 to 80 kg/m3 in steps of 0.25 kg/m3
    temperature  150 to 800 K in steps of 2.5 K

Stored quantities (SI)
    Z    compressibility factor, P = Z rho R T
    u    specific internal energy, J/kg
    cv   isochoric specific heat, J/kg K
    cp   isobaric specific heat, J/kg K
    mu   dynamic viscosity, Pa s
    lam  thermal conductivity, W/m K
    beta isobaric expansion coefficient, 1/K

Property perturbation
    perturbed(tab, dZ, dcv) returns a copy with Z multiplied by (1 + dZ) and
    the temperature-dependent part of u multiplied by (1 + dcv). The
    uncertainty analysis uses it to propagate the stated uncertainty of the
    equation of state.
"""

from __future__ import annotations

import os

import numpy as np

try:  # numba is optional: without it the same code runs, more slowly, in plain Python
    from numba import njit
    NUMBA = True
except Exception:  # pragma: no cover
    NUMBA = False

    def njit(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

R_H2 = 8.314462618 / 2.01588e-3  # J/kg K, specific gas constant of H2 (4124.5)
RHO_MAX, DRHO = 80.0, 0.25
T_MIN, T_MAX, DT_TAB = 150.0, 800.0, 2.5
NR = int(round(RHO_MAX / DRHO)) + 1
NT = int(round((T_MAX - T_MIN) / DT_TAB)) + 1
T_REF = 298.15
_FILE = os.path.join(os.path.dirname(__file__), "h2_table.npz")
NAMES = ("Z", "u", "cv", "cp", "mu", "lam", "beta")


def build_table() -> np.ndarray:
    """Evaluate CoolProp on the grid. Returns an array of shape (7, NR, NT)."""
    import CoolProp.CoolProp as CP

    st = CP.AbstractState("HEOS", "Hydrogen")
    tab = np.zeros((len(NAMES), NR, NT))
    for i in range(NR):
        rho = max(i * DRHO, 1.0e-6)  # the first row is the ideal-gas limit
        for j in range(NT):
            T = T_MIN + j * DT_TAB
            st.update(CP.DmassT_INPUTS, rho, T)
            tab[0, i, j] = st.p() / (rho * R_H2 * T)
            tab[1, i, j] = st.umass()
            tab[2, i, j] = st.cvmass()
            tab[3, i, j] = st.cpmass()
            tab[4, i, j] = st.viscosity()
            tab[5, i, j] = st.conductivity()
            tab[6, i, j] = st.isobaric_expansion_coefficient()
    return tab


def load_table() -> np.ndarray:
    """Load the table shipped with the package, or build and save it on first use."""
    if os.path.exists(_FILE):
        tab = np.load(_FILE)["tab"]
        if tab.shape == (len(NAMES), NR, NT):
            return np.ascontiguousarray(tab, dtype=np.float64)
    tab = build_table()
    try:
        np.savez_compressed(_FILE, tab=tab)
    except OSError:  # read-only file system: keep the table in memory only
        pass
    return tab


def perturbed(tab: np.ndarray, dZ: float = 0.0, dcv: float = 0.0) -> np.ndarray:
    """Copy of the table with a relative shift dZ on Z and dcv on the caloric part of u, cv and cp."""
    out = tab.copy()
    out[0] *= 1.0 + dZ
    j_ref = int(round((T_REF - T_MIN) / DT_TAB))
    u_ref = out[1][:, j_ref:j_ref + 1]
    out[1] = u_ref + (1.0 + dcv) * (out[1] - u_ref)
    out[2] *= 1.0 + dcv
    out[3] *= 1.0 + dcv
    return out


# ---- compiled interpolation -------------------------------------------------------------------

@njit(cache=True)
def _idx(rho, T):
    x = rho / DRHO
    if x < 0.0:
        x = 0.0
    if x > NR - 1.000001:
        x = NR - 1.000001
    y = (T - T_MIN) / DT_TAB
    if y < 0.0:
        y = 0.0
    if y > NT - 1.000001:
        y = NT - 1.000001
    i = int(x)
    j = int(y)
    return i, j, x - i, y - j


@njit(cache=True)
def interp(tab, k, rho, T):
    """Bilinear interpolation of quantity k at (rho, T)."""
    i, j, a, b = _idx(rho, T)
    t = tab[k]
    return ((1 - a) * (1 - b) * t[i, j] + a * (1 - b) * t[i + 1, j]
            + (1 - a) * b * t[i, j + 1] + a * b * t[i + 1, j + 1])


@njit(cache=True)
def P_rhoT(tab, rho, T):
    return interp(tab, 0, rho, T) * rho * R_H2 * T


@njit(cache=True)
def T_rhou(tab, rho, u, T_guess):
    """Temperature from density and specific internal energy.

    u is piecewise linear in T on the grid at fixed rho, so the inverse is found by walking to the
    cell that brackets u and solving the linear relation in that cell. The result is exact for the
    interpolated table, which keeps the energy balance closed to round-off.
    """
    x = rho / DRHO
    if x < 0.0:
        x = 0.0
    if x > NR - 1.000001:
        x = NR - 1.000001
    i = int(x)
    a = x - i
    t = tab[1]
    j = int((T_guess - T_MIN) / DT_TAB)
    if j < 0:
        j = 0
    if j > NT - 2:
        j = NT - 2
    for _ in range(NT):
        u0 = (1 - a) * t[i, j] + a * t[i + 1, j]
        u1 = (1 - a) * t[i, j + 1] + a * t[i + 1, j + 1]
        if u < u0 and j > 0:
            j -= 1
        elif u > u1 and j < NT - 2:
            j += 1
        else:
            return T_MIN + (j + (u - u0) / (u1 - u0)) * DT_TAB
    return T_MIN + j * DT_TAB


@njit(cache=True)
def rho_PT(tab, P, T):
    """Density from pressure and temperature by fixed-point iteration on rho = P / (Z R T)."""
    rho = P / (R_H2 * T)
    for _ in range(60):
        new = P / (interp(tab, 0, rho, T) * R_H2 * T)
        if abs(new - rho) < 1.0e-10 * (1.0 + rho):
            return new
        rho = 0.5 * (rho + new)
    return rho


@njit(cache=True)
def h_PT(tab, P, T):
    rho = rho_PT(tab, P, T)
    return interp(tab, 1, rho, T) + P / rho


@njit(cache=True)
def T_Ph(tab, P, h, T_guess):
    """Temperature from pressure and specific enthalpy (secant iteration on h(P, T))."""
    T0 = T_guess
    f0 = h_PT(tab, P, T0) - h
    T1 = T0 - f0 / 14500.0
    for _ in range(40):
        f1 = h_PT(tab, P, T1) - h
        if abs(f1) < 1.0e-3 or f1 == f0:
            return T1
        T2 = T1 - f1 * (T1 - T0) / (f1 - f0)
        T0, f0, T1 = T1, f1, T2
    return T1
