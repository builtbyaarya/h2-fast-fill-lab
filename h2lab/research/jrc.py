"""
Validation against the JRC GasTeF fast-filling experiments.

Sources
    [A11] Acosta, Moretto, Frischauf, Harskamp, Bonato. Hydrogen tank filling
          experiments at the JRC-IE GasTeF facility. 4th International
          Conference on Hydrogen Safety, 2011, paper 101.
    [A13] Acosta, Moretto, de Miguel, Ortiz, Harskamp, Bonato. JRC reference
          data from experiments of on-board hydrogen tanks fast filling. 5th
          International Conference on Hydrogen Safety, 2013, paper 229.

What the papers contain, and how each item is used here
    Tabulated (transcribed exactly)
      [A11] Tables 1 to 3: 30 hydrogen fills of the 29 L Type IV tank with
            initial and final pressure, duration, initial and final
            temperature at thermocouple TC-5 (upper rear of the tank), the
            maximum of the outer-surface thermocouple at the top of the tank,
            and the maximum of the thermocouple on the end boss.
      [A13] Table 7: mean and standard deviation of 12 repeated fills of the
            29 L tank. Table 6: mean of 350 cycles of the 19 L tank.
            Table 8: six precooled fills with final state of charge.
    Read from figures (pressure about +/- 1 MPa, temperature about +/- 2 K)
      [A13] Fig. 11(a): pressure and tank-averaged gas temperature against
            time for one fill with gas at ambient temperature and one with gas
            precooled to -30 degC.
      [A11] Fig. 5: pressure and thermocouple temperatures for one fill.
    Not in the papers
      Mass flow rate (not measured), liner thickness, boss geometry, ambient
      temperature of each fill, and the pressure history of the tabulated
      fills. Both figures show a two-stage history (a fast first stage to
      about 22 MPa, then a slower linear ramp), so the tabulated fills are
      simulated with that shape; `profile="linear"` gives the alternative.

Inputs taken from independent sources (not adjusted)
    Geometry and injector diameter [A13]; wall properties (Molkov et al.
    2019, Table 3); heat transfer correlation (Woodfield et al. 2007);
    entrainment coefficient (Ricou and Spalding 1961); inlet gas temperature
    20 degC for the fills without precooling ([A11] Fig. 5, TC-8 at the inlet
    reads 17 to 22 degC during the fill).

Assumed
    Liner thickness 4 mm; ambient 20 degC; wall and boss start at the initial
    gas temperature; boss mass from the vessel mass minus the wall mass.

Fitted (two parameters, each on a channel that is not the gas temperature rise)
    boss_area  wetted area of the metallic end bosses, fitted to the measured
               boss temperature maxima of the calibration fills.
    beta       mixing efficiency, fitted to the spread between the upper and
               lower thermocouples at the end of the fill of [A11] Fig. 5.
    Ri_c cannot be identified from the published data and is kept at 1; the
    sensitivity study varies it over two decades.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from .twozone import Closure, Control, Fill, Station, Tank, Wall

C0 = 273.15
T_AMB = C0 + 20.0
T_INLET = C0 + 20.0
P_STAGE = 22.0e6        # Pa, end of the fast first stage seen in both figures
BETA_FIT = 0.35         # fitted, calibrate_beta(): 3 K between upper and lower zone at the end of the Fig. 5 fill
BOSS_AREA_FIT = 0.012   # m2, fitted, calibrate_boss(): minimum RMSE of the boss temperature maximum


def tank_29L(boss_area: float = BOSS_AREA_FIT, liner: float = 0.004) -> Tank:
    """29 L Type IV tank of [A13] Table 1: inner diameter 230 mm, outer 279 mm, mass 32.9 kg, steel bosses."""
    wall = Wall(t_liner=liner, t_cfrp=0.0245 - liner)
    tk = Tank(volume=0.0289, D=0.230, d_inj=0.003, wall=wall)
    D, L, A = tk.geometry()
    m_wall = A * (wall.t_liner * wall.rho_liner + wall.t_cfrp * wall.rho_cfrp)
    return replace(tk, boss_area=boss_area, boss_mass=max(32.9 - m_wall, 0.0))


def tank_19L(boss_area: float = BOSS_AREA_FIT, liner: float = 0.004) -> Tank:
    """19 L Type IV tank of [A13] Table 1: inner diameter 180 mm, outer 228 mm, mass 18.3 kg, aluminium bosses."""
    wall = Wall(t_liner=liner, t_cfrp=0.024 - liner)
    tk = Tank(volume=0.019, D=0.180, d_inj=0.003, wall=wall)
    D, L, A = tk.geometry()
    m_wall = A * (wall.t_liner * wall.rho_liner + wall.t_cfrp * wall.rho_cfrp)
    return replace(tk, boss_area=boss_area, boss_mass=max(18.3 - m_wall, 0.5),
                   boss_k=167.0, boss_rho=2700.0, boss_cp=900.0)


def rig_fill(tank: Tank, P0, Pf, T0, r1, r2, P_break, T_in=T_INLET, closure: Closure | None = None,
             t_hold=0.0, dt=0.05, T_amb=T_AMB) -> Fill:
    """A fill on the test rig: the pressure history is imposed and the gas enters at a measured temperature."""
    Pb = min(max(P_break, P0 + 1.0e4), Pf)
    ctl = Control(r1=r1, r2=r2, xi_b=(Pb - P0) / (70.0e6 - P0), precool=False, Kp=-1.0, flow_limit=1.0,
                  P_cap=Pf, soc_target=1.0e9, P_stop=Pf - 2.0e4, t_max=6000.0)
    st = Station(bank_V=(50.0,), bank_P=(100.0e6,), inlet_T=T_in)
    return Fill(tank=tank, closure=closure or Closure(beta=BETA_FIT), control=ctl, station=st, T_amb=T_amb,
                P0=P0, T0=T0, dt=dt, t_hold=t_hold)


def two_stage(P0, Pf, duration_s, r1=26.7, P_break=P_STAGE):
    """Ramp rates (MPa/min) of a two-stage history with a given total duration."""
    if P0 >= P_break - 1.0e5:
        return (Pf - P0) / 1e6 / (duration_s / 60.0), (Pf - P0) / 1e6 / (duration_s / 60.0), P0 + 1.0e4
    t1 = (P_break - P0) / 1e6 / r1 * 60.0
    if t1 > 0.5 * duration_s:      # short fill: keep the first stage to at most half of the duration
        t1 = 0.5 * duration_s
        r1 = (P_break - P0) / 1e6 / (t1 / 60.0)
    r2 = (Pf - P_break) / 1e6 / ((duration_s - t1) / 60.0)
    return r1, r2, P_break


# ---- [A13] Fig. 11(a): histories read from the figure -------------------------------------------------
FIG11_AMBIENT = dict(
    label="[A13] Fig. 11(a), gas at ambient temperature", P0=2.0e6, Pf=76.9e6, T0=C0 + 11.2, T_in=T_INLET,
    r1=26.7, r2=15.6, P_break=22.0e6,
    t=np.array([10, 20, 30, 40, 50, 60, 100, 150, 200, 250, 262.0]),
    T=np.array([42, 54, 63, 68.6, 72, 73, 74.5, 79, 83.5, 88, 89.0]),
    tP=np.array([52, 100, 150, 200, 263.0]), P=np.array([22.1, 34.5, 47.5, 60.5, 76.8]))
FIG11_PRECOOLED = dict(
    label="[A13] Fig. 11(a), gas precooled to -30 degC", P0=2.0e6, Pf=78.1e6, T0=C0 + 11.95, T_in=C0 - 30.0,
    r1=26.0, r2=22.4, P_break=21.0e6,
    t=np.array([20, 30, 40, 50, 75, 100, 125, 150, 175, 200, 207.0]),
    T=np.array([11.5, 15.7, 20, 24, 29.8, 34, 38, 41.6, 45, 48.2, 49.4]),
    tP=np.array([52, 100, 150, 205.0]), P=np.array([21.0, 39.0, 57.5, 78.3]))
# ---- [A11] Fig. 5: thermocouples in position B, fill of Table 2 (3.86 to 72.06 MPa, 4.33 min) -------------
FIG5 = dict(
    label="[A11] Fig. 5, thermocouple array position B", P0=3.86e6, Pf=72.06e6, T0=C0 + 13.9, T_in=T_INLET,
    r1=72.6, r2=12.26, P_break=22.0e6,
    t=60.0 * (np.array([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]) - 0.2),
    T=np.array([71, 70, 71.5, 73.5, 76, 78.5, 81, 83.0]), spread_end=3.0)

# ---- [A11] Tables 1 to 3, hydrogen rows: position, Pi, Pf (MPa), duration (min), Ti, Tf (TC-5), T top max, T boss max
TABLES_2011 = [
    ("A", 3.86, 72.10, 5.11, 19.2, 83.3, 45.2, 34.7), ("A", 2.30, 72.00, 5.15, 18.2, 91.8, 49.0, 38.9),
    ("A", 2.39, 72.25, 4.20, 26.9, 96.8, 51.7, 41.8), ("A", 3.87, 71.91, 3.57, 8.9, 81.3, 40.9, 30.6),
    ("A", 0.03, 72.26, 4.65, 20.6, 101.3, 53.4, 43.7), ("A", 0.04, 72.01, 3.46, 21.2, 101.6, 49.2, 41.6),
    ("B", 0.03, 72.06, 5.51, 20.6, 93.9, 53.3, 46.0), ("B", 0.44, 72.02, 5.17, 22.8, 115.8, 54.8, 45.2),
    ("B", 2.14, 72.21, 5.07, 19.8, 92.8, 51.9, 52.1), ("B", 3.89, 71.94, 4.37, 3.7, 77.2, 40.9, 31.0),
    ("B", 3.86, 72.06, 4.33, 13.9, 82.9, 46.3, 35.1), ("B", 3.84, 72.12, 4.33, 18.9, 85.7, 49.2, 37.7),
    ("B", 0.02, 72.06, 4.70, 20.6, 99.3, 52.6, 43.5), ("B", 2.18, 71.97, 3.70, 24.1, 97.5, 52.5, 40.8),
    ("B", 2.37, 72.31, 4.20, 21.1, 96.7, 51.6, 43.2),
    ("C", 14.94, 16.00, 10.36, 10.0, 16.6, 32.5, 21.5), ("C", 2.30, 29.94, 42.6, 14.1, 37.5, 30.0, 22.9),
    ("C", 2.23, 29.72, 5.17, 15.5, 89.4, 38.6, 23.2), ("C", 15.14, 69.02, 7.20, 20.7, 73.4, 33.2, 26.3),
    ("C", 15.00, 69.20, 6.53, 26.5, 77.1, 42.5, 29.9), ("C", 14.93, 69.13, 6.50, 19.1, 68.3, 33.3, 26.8),
    ("C", 14.93, 69.08, 6.50, 15.8, 65.2, 40.9, 28.6), ("C", 14.99, 69.13, 6.47, 16.0, 68.3, 37.8, 28.3),
    ("C", 14.98, 69.18, 6.44, 11.4, 64.5, 35.6, 27.1), ("C", 2.32, 29.76, 1.39, 20.8, 87.0, 30.9, 25.5),
    ("C", 0.03, 29.89, 1.42, 21.4, 93.0, 34.9, 25.8), ("C", 14.97, 69.01, 1.45, 23.8, 86.0, 40.6, 28.9),
    ("C", 14.92, 69.42, 1.42, 19.5, 82.5, 38.5, 28.5), ("C", 15.01, 69.44, 1.39, 33.9, 95.3, 44.1, 28.9),
    ("C", 2.38, 29.95, 0.41, 21.7, 98.6, 32.2, 24.1),
]
# Fills that start below 1 MPa are excluded from the error statistics: the 0 to 70 MPa transducer has an
# error above 5 % of full scale below 10 MPa [A11], so the initial mass of those fills is not known.
# The fill from 14.94 to 16.0 MPa has a pressure rise of 1 MPa and tests nothing.
def table_rows(position=None, min_Pi=1.0, min_dP=5.0):
    return [r for r in TABLES_2011 if r[1] >= min_Pi and r[2] - r[1] >= min_dP and (position is None or r[0] in position)]


# ---- [A13] Table 7 and Table 6: statistics of repeated fills -------------------------------------------
REPEAT_29L = dict(P0=1.99e6, Pf=76.89e6, t=253.0, T0=C0 + 11.2, Tf=86.9, Tf_sd=2.9, dT=75.6, dT_sd=0.9)
CYCLES_19L = dict(P0=3.28e6, Pf=84.44e6, t=310.4, T0=C0 + 16.9, Tf=83.1, Tf_sd=0.63, boss0=11.3, boss_f=52.6)
# ---- [A13] Table 8: precooled fills, 2 MPa initial pressure: T precool, T tank initial (degC), P end (MPa), APRR (MPa/min), SOC (%)
TABLE8 = [(-28.8, -5.2, 70.2, 15.6, 94.6), (-29.6, -6.3, 70.4, 15.8, 93.8), (-30.0, -13.5, 70.3, 15.5, 95.2),
          (-29.0, -8.4, 70.5, 15.5, 95.3), (-31.0, 0.44, 78.1, 22.2, 99.8), (-30.2, 15.0, 77.9, 22.3, 97.8)]


# ---- error metrics -----------------------------------------------------------------------------------------
def metrics(pred, meas) -> dict:
    """Bias (mean error), mean absolute error, root-mean-square error and maximum absolute error."""
    e = np.asarray(pred, float) - np.asarray(meas, float)
    return dict(n=int(e.size), bias=float(e.mean()), mae=float(np.abs(e).mean()),
                rmse=float(math.sqrt((e ** 2).mean())), max=float(np.abs(e).max()))


# ---- runs --------------------------------------------------------------------------------------------------
def run_history(case: dict, tank: Tank | None = None, closure: Closure | None = None, dt=0.05):
    f = rig_fill(tank or tank_29L(), case["P0"], case["Pf"], case["T0"], case["r1"], case["r2"], case["P_break"],
                 T_in=case["T_in"], closure=closure, dt=dt)
    f.store_every = 0.5
    return f.run()


def history_errors(case: dict, out, channel="T_bulk") -> dict:
    T = np.interp(case["t"], out.s["t"], out.s[channel]) - C0
    m = metrics(T, case["T"])
    m["pred"], m["meas"] = T, case["T"]
    if "tP" in case:
        P = np.interp(case["tP"], out.s["t"], out.s["P"]) / 1e6
        m["P"] = metrics(P, case["P"])
    return m


def run_table_row(row, tank=None, closure=None, profile="two-stage", t_hold=2400.0, dt=0.1, T_in=T_INLET):
    pos, Pi, Pf, dur, Ti, Tf, Ttop, Tboss = row
    if profile == "linear":
        r = (Pf - Pi) / dur
        r1, r2, Pb = r, r, Pi * 1e6 + 1e4
    else:
        r1, r2, Pb = two_stage(Pi * 1e6, Pf * 1e6, dur * 60.0)
    f = rig_fill(tank or tank_29L(), Pi * 1e6, Pf * 1e6, C0 + Ti, r1, r2, Pb, T_in=T_in, closure=closure,
                 t_hold=t_hold, dt=dt)
    f.store_every = 5.0
    return f.run()


def table_validation(rows=None, **kw) -> dict:
    """Predicted against measured TC-5 final temperature, outer-surface maximum and boss maximum for the tabulated fills."""
    rows = table_rows() if rows is None else rows
    out = dict(rows=rows, Tu=[], Tb=[], Ttop=[], Tboss=[], t=[])
    for r in rows:
        o = run_table_row(r, **kw)
        out["Tu"].append(o.Tu_end - C0)
        out["Tb"].append(0.5 * (o.Tu_end + o.Tl_end) - C0)
        out["Ttop"].append(o.T_outer_max - C0)
        out["Tboss"].append(o.T_boss_max - C0)
        out["t"].append(o.t_fill)
    meas = np.array([[r[5], r[6], r[7], r[3] * 60.0] for r in rows])
    out["m_TC5"] = metrics(out["Tu"], meas[:, 0])
    out["m_rise"] = metrics(np.array(out["Tu"]) - np.array([r[4] for r in rows]), meas[:, 0] - np.array([r[4] for r in rows]))
    out["m_top"] = metrics(out["Ttop"], meas[:, 1])
    out["m_boss"] = metrics(out["Tboss"], meas[:, 2])
    out["m_time"] = metrics(out["t"], meas[:, 3])
    return out


def run_repeat(tank=None, closure=None, dt=0.05):
    d = REPEAT_29L
    r1, r2, Pb = two_stage(d["P0"], d["Pf"], d["t"])
    return rig_fill(tank or tank_29L(), d["P0"], d["Pf"], d["T0"], r1, r2, Pb, closure=closure, dt=dt).run()


def run_cycles_19L(tank=None, closure=None, dt=0.05):
    d = CYCLES_19L
    r1, r2, Pb = two_stage(d["P0"], d["Pf"], d["t"])
    return rig_fill(tank or tank_19L(), d["P0"], d["Pf"], d["T0"], r1, r2, Pb, closure=closure, dt=dt, t_hold=1200.0).run()


def run_table8(tank=None, closure=None, dt=0.05):
    """Final state of charge of the six precooled fills."""
    pred = []
    for Tpc, T0, Pe, aprr, soc in TABLE8:
        dur = (Pe - 2.0) / aprr * 60.0
        r1, r2, Pb = two_stage(2.0e6, Pe * 1e6, dur)
        o = rig_fill(tank or tank_29L(), 2.0e6, Pe * 1e6, C0 + T0, r1, r2, Pb, T_in=C0 + Tpc, closure=closure, dt=dt).run()
        pred.append((o.soc, 0.5 * (o.Tu_end + o.Tl_end) - C0))
    return np.array(pred), np.array([r[4] for r in TABLE8])


# ---- calibration of the two fitted parameters -----------------------------------------------------------------
CAL_ROWS = [r for r in TABLES_2011 if r[0] == "A" and r[1] >= 1.0]     # four fills of position A


def calibrate_boss(areas=np.linspace(0.0, 0.04, 9), closure=None):
    """Boss wetted area that minimises the RMSE of the boss temperature maximum over the calibration fills."""
    res = []
    for a in areas:
        v = table_validation(CAL_ROWS, tank=tank_29L(boss_area=float(a)), closure=closure)
        res.append((float(a), v["m_boss"]["rmse"], v["m_boss"]["bias"], v["m_TC5"]["bias"]))
    return res


def calibrate_beta(betas=(0.05, 0.1, 0.2, 0.3, 0.5, 1.0), tank=None):
    """Zone temperature difference at the end of the fill of [A11] Fig. 5 against beta."""
    res = []
    for b in betas:
        o = run_history(FIG5, tank=tank, closure=Closure(beta=b))
        res.append((b, o.Tu_end - o.Tl_end))
    return res
