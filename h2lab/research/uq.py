"""
Uncertainty propagation and global sensitivity analysis.

Method
    Variance-based sensitivity indices (Sobol) with the sampling scheme of
    Saltelli et al. (2010): two independent sample matrices A and B of N rows,
    and one matrix AB_i per input in which column i of A is replaced by column
    i of B. First-order index S_i and total index ST_i use the estimators
    recommended in Saltelli et al. (2010), applied to centred outputs:
        S_i  = mean(f(B) (f(AB_i) - f(A))) / Var
        ST_i = mean((f(A) - f(AB_i))^2) / (2 Var)
    The cost is N (k + 2) fills for k inputs. Inputs are sampled uniformly
    between the bounds given in the manuscript (Table 6).
    The same A matrix gives the Monte Carlo distribution of each output.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from .props import perturbed
from .station import CompressorSpec, Economics, account
from .twozone import Closure, Fill, table

# name, lower, upper, description
INPUTS = [
    ("f_h", 0.5, 2.0, "multiplier on the gas-side heat transfer coefficient"),
    ("k_liner", 0.385, 0.50, "liner thermal conductivity, W/m K"),
    ("cp_liner", 1580.0, 2300.0, "liner specific heat, J/kg K"),
    ("k_cfrp", 0.5, 1.0, "composite thermal conductivity, W/m K"),
    ("T0", -5.0, 5.0, "initial tank temperature minus ambient, K"),
    ("P0", 2.0, 10.0, "initial tank pressure, MPa"),
    ("dT_in", -3.0, 3.0, "precooler set point error, K"),
    ("eta_s", 0.60, 0.80, "isentropic efficiency of the station compressor"),
    ("dZ", -0.001, 0.001, "relative error of the compressibility factor"),
    ("dcv", -0.01, 0.01, "relative error of the caloric properties"),
    ("beta", 0.15, 1.0, "zone mixing efficiency"),
    ("Ri_c", 0.1, 10.0, "critical Richardson number (sampled in log)"),
    ("phi", 0.3, 0.7, "upper-zone volume fraction"),
]
OUTPUTS = ("T_hot", "T_hot_minus_bulk", "t_fill", "soc", "e_station")
LOG = {"Ri_c"}


def _scale(U):
    X = np.empty_like(U)
    for j, (n, lo, hi, _) in enumerate(INPUTS):
        if n in LOG:
            X[:, j] = np.exp(np.log(lo) + U[:, j] * (np.log(hi) - np.log(lo)))
        else:
            X[:, j] = lo + U[:, j] * (hi - lo)
    return X


def model(x, base: Fill, spec: CompressorSpec | None = None, eco: Economics | None = None):
    """One fill with the uncertain inputs set to x. Returns the outputs in the order of OUTPUTS."""
    p = dict(zip([i[0] for i in INPUTS], x))
    wall = replace(base.tank.wall, k_liner=p["k_liner"], cp_liner=p["cp_liner"], k_cfrp=p["k_cfrp"])
    tank = replace(base.tank, wall=wall)
    clo = replace(base.closure, f_h=p["f_h"], beta=p["beta"], Ri_c=p["Ri_c"], phi=p["phi"])
    ctl = replace(base.control, Tpc_a=base.control.Tpc_a + p["dT_in"], Tpc_b=base.control.Tpc_b + p["dT_in"])
    f = replace(base, tank=tank, closure=clo, control=ctl, T0=base.T_amb + p["T0"], P0=p["P0"] * 1e6)
    tab = table() if (p["dZ"] == 0 and p["dcv"] == 0) else perturbed(table(), p["dZ"], p["dcv"])
    out = f.run(tab)
    sp = replace(spec or CompressorSpec(), eta_s=p["eta_s"])
    acc = account(out, sp, eco)
    return np.array([out.T_hot - 273.15, out.T_hot - out.Tbulk_max, out.t_fill, out.soc, acc["e_station"]])


def sobol(base: Fill, N=256, seed=7, spec=None, eco=None):
    rng = np.random.default_rng(seed)
    k = len(INPUTS)
    A, B = _scale(rng.random((N, k))), _scale(rng.random((N, k)))
    fA = np.array([model(x, base, spec, eco) for x in A])
    fB = np.array([model(x, base, spec, eco) for x in B])
    S, ST = np.zeros((k, fA.shape[1])), np.zeros((k, fA.shape[1]))
    both = np.vstack([fA, fB])
    var = np.var(both, axis=0)
    var = np.where(var > 0, var, np.inf)
    f0 = both.mean(axis=0)      # the first-order estimator is applied to centred outputs, which lowers its variance
    for i in range(k):
        AB = A.copy()
        AB[:, i] = B[:, i]
        fAB = np.array([model(x, base, spec, eco) for x in AB])
        S[i] = np.mean((fB - f0) * (fAB - fA), axis=0) / var
        ST[i] = 0.5 * np.mean((fA - fAB) ** 2, axis=0) / var
    return dict(S=S, ST=ST, fA=fA, A=A, var=var, mean=fA.mean(axis=0), std=fA.std(axis=0),
                p025=np.percentile(fA, 2.5, axis=0), p975=np.percentile(fA, 97.5, axis=0), evaluations=N * (k + 2))


def one_at_a_time(base: Fill, spec=None, eco=None):
    """Change of each output when one input moves from its lower to its upper bound, the others at mid-range."""
    mid = _scale(np.full((1, len(INPUTS)), 0.5))[0]
    rows = []
    for i, (n, lo, hi, _) in enumerate(INPUTS):
        a, b = mid.copy(), mid.copy()
        a[i], b[i] = lo, hi
        rows.append((n, model(a, base, spec, eco), model(b, base, spec, eco)))
    return mid, model(mid, base, spec, eco), rows
