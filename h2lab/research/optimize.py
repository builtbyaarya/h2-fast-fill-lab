"""
Multi-objective optimisation of one fill.

Decision variables (x)
    r1, r2     pressure ramp rate of the first and the second stage, MPa/min
    xi_b       normalised pressure at which the ramp rate changes
    dsw1, dsw2 bank switching margins (low to medium, medium to high), MPa
    Ta, Tb     precooler set point at the start of the fill and at P_ref, degC
               (the set point varies linearly with tank pressure in between;
               Ta != Tb is the adaptive precooling)

Objectives (both minimised)
    f1  fill time, s
    f2  specific station electricity, kWh/kg (compressor refill + refrigeration)
    The operating cost is computed for every design but is not an objective:
    with a flat energy price and a demand charge set by the compressor rating
    it is an affine function of f2 (correlation 0.996 in the first study), so
    a third objective adds no trade-off. See the manuscript, Section 6.3.

Constraints (g <= 0)
    g1  maximum local gas temperature (hotter zone) - 85 degC
    g2  maximum tank pressure - 87.5 MPa
    g3  target state of charge not reached (target - final SOC)
    g4  (robust problem only) maximum local gas temperature with weak zone
        mixing - 85 degC. Two weak-mixing cases are used:
        MIX_DATA  the weakest mixing that is still consistent with the JRC
                  thermocouple spread: beta at the lower bound of its range
                  (0.15) and the Ri_c at which the predicted end-of-fill
                  spread of the [A11] Fig. 5 fill is 6 K, twice the measured
                  3 K (run_all.mixing() computes it).
        MIX_BOX   the corner of the a-priori ranges of the sensitivity study
                  (beta = 0.15, Ri_c = 0.1). It predicts a 38 K spread for the
                  same fill, so it is not consistent with the data; it is kept
                  as an upper bound on the cost of robustness.
    The 60 g/s flow limit and the precooler capacity are enforced inside the
    fill model by clipping, and the -40 degC lower bound on the delivery
    temperature is the lower bound of Ta and Tb.

Algorithm
    NSGA-II (Deb et al. 2002) written out below: fast non-dominated sorting,
    crowding distance, binary tournament with constraint domination,
    simulated binary crossover and polynomial mutation. The implementation is
    kept in this file so that the result does not depend on an external
    optimisation package.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from .station import CompressorSpec, Economics, account
from .twozone import Control, Fill

NAMES = ("r1", "r2", "xi_b", "dsw1", "dsw2", "Ta", "Tb")
LOWER = np.array([5.0, 5.0, 0.15, 0.5, 0.5, -40.0, -40.0])
UPPER = np.array([40.0, 40.0, 0.85, 20.0, 20.0, 20.0, 20.0])
T_LIMIT = 273.15 + 85.0
P_LIMIT = 87.5e6
MIX_DATA = dict(beta=0.15, Ri_c=2.08)     # weakest mixing consistent with the JRC thermocouple spread
MIX_BOX = dict(beta=0.15, Ri_c=0.1)       # corner of the sensitivity ranges (not consistent with the data)

# SAE J2601 table-based protocol, H70-T40, 4-7 kg capacity category, with communications, initial pressure 5 MPa.
# Average pressure ramp rate (MPa/min) against ambient temperature (degC):
#   25 degC: 18.5 MPa/min, target pressure 81 MPa (Reddi et al. 2017; Chochlidakis and Rothuizen 2020, base case)
#    0 degC: 28.5 MPa/min, the maximum of the table; 40 degC: 11.5 MPa/min (Schneider et al. 2014, Table 4)
# The 141 L tank holds 5.67 kg at 100 % state of charge, so it falls in the 4-7 kg category.
J2601_APRR = {0.0: 28.5, 25.0: 18.5, 40.0: 11.5}
J2601_TARGET_25C = 81.0e6
T40_WINDOW = (-40.0, -33.0)               # degC, fuel delivery temperature window of a T40 dispenser


def j2601(T_amb_C: float = 25.0) -> np.ndarray:
    """Decision vector of the SAE J2601 baseline: one constant ramp at the table APRR, T40 precooling at -40 degC,
    and the station's 2 MPa bank switching margins (J2601 does not prescribe the station side)."""
    r = J2601_APRR[float(T_amb_C)]
    return np.array([r, r, 0.5, 2.0, 2.0, T40_WINDOW[0], T40_WINDOW[0]])


REFERENCE = j2601(25.0)


def apply(base: Fill, x) -> Fill:
    c = replace(base.control, r1=float(x[0]), r2=float(x[1]), xi_b=float(x[2]), dsw1=float(x[3]) * 1e6,
                dsw2=float(x[4]) * 1e6, Tpc_a=273.15 + float(x[5]), Tpc_b=273.15 + float(x[6]))
    return replace(base, control=c)


def low_mixing(base: Fill, mix: dict) -> Fill:
    return replace(base, closure=replace(base.closure, **mix))


def evaluate(x, base: Fill, spec: CompressorSpec | None = None, eco: Economics | None = None, full=False,
             robust=None):
    """Objectives and constraints of one design. With robust set to a mixing case (MIX_DATA or MIX_BOX) the design
    is also run with that mixing and its maximum local temperature is a fourth constraint. With full=True the fill result and the accounting
    are returned too."""
    out = apply(base, x).run()
    acc = account(out, spec, eco)
    f = np.array([out.t_fill, acc["e_station"]])
    g4 = -1.0
    if robust:
        g4 = apply(low_mixing(base, robust), x).run().T_hot - T_LIMIT
    g = np.array([out.T_hot - T_LIMIT, (out.P_max - P_LIMIT) / 1e6, base.control.soc_target - out.soc - 1e-6, g4])
    if full:
        return f, g, out, acc
    return f, g


# ---- NSGA-II --------------------------------------------------------------------------------------------

def _violation(G):
    return np.maximum(G, 0.0).sum(axis=1)


def _dominates(fa, va, fb, vb):
    if va > 0 or vb > 0:
        return va < vb
    return bool(np.all(fa <= fb) and np.any(fa < fb))


def _sort(F, V):
    n = len(F)
    S = [[] for _ in range(n)]
    cnt = np.zeros(n, int)
    fronts = [[]]
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if _dominates(F[p], V[p], F[q], V[q]):
                S[p].append(q)
            elif _dominates(F[q], V[q], F[p], V[p]):
                cnt[p] += 1
        if cnt[p] == 0:
            fronts[0].append(p)
    i = 0
    while fronts[i]:
        nxt = []
        for p in fronts[i]:
            for q in S[p]:
                cnt[q] -= 1
                if cnt[q] == 0:
                    nxt.append(q)
        fronts.append(nxt)
        i += 1
    return fronts[:-1]


def _crowding(F, front):
    d = np.zeros(len(front))
    Ff = F[front]
    for m in range(F.shape[1]):
        o = np.argsort(Ff[:, m])
        span = Ff[o[-1], m] - Ff[o[0], m]
        d[o[0]] = d[o[-1]] = np.inf
        if span > 0:
            d[o[1:-1]] += (Ff[o[2:], m] - Ff[o[:-2], m]) / span
    return d


def nsga2(base: Fill, pop=96, gens=60, seed=1, spec=None, eco=None, lower=LOWER, upper=UPPER, fixed=None,
          seeds=(REFERENCE,), log=None, robust=None):
    """Run NSGA-II. `fixed` maps a variable index to a value that is held constant (strategy subsets)."""
    rng = np.random.default_rng(seed)
    nv = len(lower)
    fixed = fixed or {}

    def fix(X):
        for i, v in fixed.items():
            X[:, i] = v
        return np.clip(X, lower, upper)

    def ev(X):
        res = [evaluate(x, base, spec, eco, robust=robust) for x in X]
        return np.array([r[0] for r in res]), np.array([r[1] for r in res])

    X = lower + rng.random((pop, nv)) * (upper - lower)
    for i, s in enumerate(seeds):
        X[i] = s
    X = fix(X)
    F, G = ev(X)
    hist = []
    for gen in range(gens):
        V = _violation(G)
        fronts = _sort(F, V)
        rank = np.zeros(pop, int)
        crowd = np.zeros(pop)
        for r, fr in enumerate(fronts):
            rank[fr] = r
            crowd[fr] = _crowding(F, fr)
        # binary tournament
        a, b = rng.integers(0, pop, pop), rng.integers(0, pop, pop)
        win = np.where((rank[a] < rank[b]) | ((rank[a] == rank[b]) & (crowd[a] > crowd[b])), a, b)
        P = X[win]
        # simulated binary crossover (eta_c = 15) and polynomial mutation (eta_m = 20)
        C = P.copy()
        for i in range(0, pop - 1, 2):
            if rng.random() < 0.9:
                u = rng.random(nv)
                beta = np.where(u <= 0.5, (2 * u) ** (1 / 16.0), (1 / (2 * (1 - u))) ** (1 / 16.0))
                C[i] = 0.5 * ((1 + beta) * P[i] + (1 - beta) * P[i + 1])
                C[i + 1] = 0.5 * ((1 - beta) * P[i] + (1 + beta) * P[i + 1])
        mut = rng.random((pop, nv)) < 1.0 / nv
        u = rng.random((pop, nv))
        delta = np.where(u < 0.5, (2 * u) ** (1 / 21.0) - 1, 1 - (2 * (1 - u)) ** (1 / 21.0))
        C = fix(np.where(mut, C + delta * (upper - lower), C))
        Fc, Gc = ev(C)
        # environmental selection from parents and children
        XX, FF, GG = np.vstack([X, C]), np.vstack([F, Fc]), np.vstack([G, Gc])
        VV = _violation(GG)
        keep = []
        for fr in _sort(FF, VV):
            if len(keep) + len(fr) <= pop:
                keep += fr
            else:
                d = _crowding(FF, fr)
                keep += [fr[j] for j in np.argsort(-d)[:pop - len(keep)]]
                break
        X, F, G = XX[keep], FF[keep], GG[keep]
        feas = _violation(G) == 0
        hist.append((gen, int(feas.sum()), F[feas].min(axis=0).tolist() if feas.any() else None))
        if log and gen % 10 == 0:
            log(hist[-1])
    V = _violation(G)
    nd = _sort(F, V)[0]
    nd = [i for i in nd if V[i] == 0]
    o = np.argsort(F[nd, 0])
    return dict(X=X[nd][o], F=F[nd][o], G=G[nd][o], history=hist, evaluations=pop * (gens + 1))


def knee(F):
    """Index of the compromise point: smallest distance to the ideal point after normalising each objective to [0, 1]."""
    lo, hi = F.min(axis=0), F.max(axis=0)
    N = (F - lo) / np.where(hi > lo, hi - lo, 1.0)
    return int(np.argmin(np.linalg.norm(N[:, :2], axis=1)))
