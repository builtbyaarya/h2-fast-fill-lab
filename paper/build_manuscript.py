"""
Builds the manuscript from the results written by run_all.py and the figures drawn by figures.py.
Every number in the text and tables is read from paper/results/.

Outputs (in paper/, all gitignored):
  manuscript.md                         the filled text
  H2 Fast-Fill Lab manuscript.docx      Word submission file: double spaced, continuous line numbers
  H2 Fast-Fill Lab paper.pdf            typeset article (XeLaTeX, TeX Gyre Pagella, two columns)

Usage:  python paper/build_manuscript.py [--no-pdf] [--no-docx]
"""
import json, os, pickle, re, shutil, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
RES, FIG = os.path.join(HERE, "results"), os.path.join(HERE, "figures")
L = lambda n: pickle.load(open(os.path.join(RES, n + ".pkl"), "rb"))
num, val, ref, opt, sen, ene, mix = L("numerics"), L("validation"), L("reference"), L("optimise"), L("sensitivity"), L("energy"), L("mixing")
ada = L("adaptive")
C0 = 273.15
TITLE = ("Robust optimisation of precooling, cascade switching and pressure-ramp control for 70 MPa hydrogen refuelling "
         "with a two-zone real-gas tank model")


def f(x, d=1):
    s = f"{float(x):.{d}f}"
    if s.startswith("-") and float(s) == 0.0:
        s = s[1:]
    return s.replace("-", "\u2212")


def sg(x, d=1):
    """Signed number with an explicit plus sign."""
    s = f(x, d)
    return s if s.startswith("\u2212") else "+" + s


def table(head, rows, align=None):
    align = align or ["l"] + ["r"] * (len(head) - 1)
    line = "|" + "|".join({"l": ":--", "r": "--:", "c": ":-:"}[a] for a in align) + "|"
    out = ["| " + " | ".join(head) + " |", line] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


N = {}
# ---- numerics ------------------------------------------------------------------------------------------
dts = num["dt"]
N["tab_dt"] = table(["Time step, s", "Fill time, s", "Maximum local temperature, °C", "Hydrogen delivered, kg", "Gas energy balance residual"],
                    [(f(r[0], 5).rstrip("0").rstrip("."), f(r[1], 2), f(r[2], 3), f(r[4], 4), "below $10^{-12}$" if r[6] < 1e-12 else "%.0e" % r[6]) for r in dts])
N["dt_err"] = f(abs(dts[2][2] - dts[-1][2]), 3)
N["node_err"] = f(abs(num["nodes"][2][1] - num["nodes"][-1][1]), 2)
N["tabP"], N["tabT"] = "$5\\times10^{-6}$" if num["table"][0] < 6e-6 else "%.0e" % num["table"][0], f(num["table"][1], 3)
N["ms"] = f(num["ms_per_fill"], 0)

# ---- validation --------------------------------------------------------------------------------------------
h = val["hist"]
rp, c19, t8 = val["repeat"], val["cyc19"], val["table8"]
ts, tl = val["tab_two-stage"], val["tab_linear"]
mc = val["mc"]
t8T = val["table8_T"]
e8 = np.asarray(t8T["pred"]) - np.asarray(t8T["implied"])
N.update(boss_area=f(0.012 * 1e4, 0), boss_rmse=f(val["tab_cal"]["m_boss"]["rmse"], 1), beta="0.35",
         rep_T=f(rp["T_end"], 1), rep_err=sg(rp["T_end"] - 86.9, 1),
         mc_lo=f(np.percentile(mc["Tend"], 2.5), 1), mc_hi=f(np.percentile(mc["Tend"], 97.5), 1), mc_mean=f(mc["Tend"].mean(), 1),
         mc_n=str(mc["N"]), c19_T=f(c19["T_end"], 1),
         soc_bias=f(t8["m"]["bias"], 1), soc_max=f(t8["m"]["max"], 1),
         amb_rmse=f(h["amb"]["m"]["rmse"], 1), amb_max=f(h["amb"]["m"]["max"], 1), amb_end=sg(h["amb"]["m"]["pred"][-1] - h["amb"]["m"]["meas"][-1], 1),
         pre_rmse=f(h["pre"]["m"]["rmse"], 1), pre_end=sg(h["pre"]["m"]["pred"][-1] - h["pre"]["m"]["meas"][-1], 1),
         f5_rmse=f(h["fig5"]["m"]["rmse"], 1), f5_end=sg(h["fig5"]["m"]["pred"][-1] - h["fig5"]["m"]["meas"][-1], 1),
         f5_dT=f(h["fig5"]["dT_end"], 1), chi1_u=f(h["fig5"]["chi1"]["Tu_end"], 1), chi1_l=f(h["fig5"]["chi1"]["Tl_end"], 1),
         chi0_u=f(h["fig5"]["chi0"]["Tu_end"], 1), chi0_l=f(h["fig5"]["chi0"]["Tl_end"], 1),
         class80=f(val["class"][80.0], 1), class200=f(val["class"][200.0], 1),
         nb_bias=sg(val["tab_noboss"]["m_TC5"]["bias"], 1),
         t8_bias=sg(t8T["m"]["bias"], 1), t8_rmse=f(t8T["m"]["rmse"], 1), t8_max=f(e8.max(), 1), t8_lo=f(e8.min(), 1))


def mrow(label, m, unit="K", n=None):
    return (label, n or m["n"], sg(m["bias"], 1), f(m["mae"], 1), f(m["rmse"], 1), f(m["max"], 1), unit)


g = ts["groups"]
hP = dict(n=9, bias=(h["amb"]["m"]["P"]["bias"] * 5 + h["pre"]["m"]["P"]["bias"] * 4) / 9,
          mae=(h["amb"]["m"]["P"]["mae"] * 5 + h["pre"]["m"]["P"]["mae"] * 4) / 9,
          rmse=np.sqrt((h["amb"]["m"]["P"]["rmse"] ** 2 * 5 + h["pre"]["m"]["P"]["rmse"] ** 2 * 4) / 9),
          max=max(h["amb"]["m"]["P"]["max"], h["pre"]["m"]["P"]["max"]))
N["tab_val"] = table(
    ["Quantity (source)", "n", "Bias", "MAE", "RMSE", "Max", "Unit"],
    [mrow("Tank-average temperature history, gas at 20 °C ([A13] Fig. 11a)", h["amb"]["m"]),
     mrow("Tank-average temperature history, gas at −30 °C ([A13] Fig. 11a)", h["pre"]["m"]),
     mrow("Gas temperature history, thermocouples TC-1 to TC-6 ([A11] Fig. 5)", h["fig5"]["m"]),
     mrow("Pressure history, both fills of [A13] Fig. 11a (imposed)", hP, "MPa"),
     mrow("TC-5 at end of fill, all tabulated fills ([A11] Tables 1 to 3)", ts["m_TC5"]),
     mrow("TC-5 at end of fill, fills to 72 MPa", g["full fills to 72 MPa"]),
     mrow("TC-5 at end of fill, fills from 15 MPa to 69 MPa", g["from 15 MPa to 69 MPa"]),
     mrow("TC-5 at end of fill, fills to 30 MPa", g["to 30 MPa"]),
     mrow("TC-5 at end of fill, same fills, single linear ramp assumed", tl["m_TC5"]),
     mrow("TC-5 at end of fill, same fills, boss heat sink removed", val["tab_noboss"]["m_TC5"]),
     mrow("Outer wall surface, maximum ([A11] Tables 1 to 3)", ts["m_top"]),
     mrow("Boss, maximum, validation fills ([A11] Tables 1 to 3)", val["tab_val"]["m_boss"]),
     mrow("Boss, maximum, calibration fills (fitted)", val["tab_cal"]["m_boss"]),
     mrow("Final state of charge, precooled fills ([A13] Table 8)", t8["m"], "% points"),
     mrow("Final mean temperature, precooled fills, implied by pressure and state of charge ([A13] Table 8)", t8T["m"]),
     ("Final tank-average temperature, 12 repeated fills ([A13] Table 7)", 1, sg(rp["T_end"] - 86.9, 1), "", "", "", "K"),
     ("Final temperature, 19 L tank, 350 cycles ([A13] Table 6)", 1, sg(c19["T_end"] - 83.1, 1), "", "", "", "K")],
    align=["l", "r", "r", "r", "r", "r", "l"])
N.update(tc5_bias=sg(ts["m_TC5"]["bias"], 1), tc5_mae=f(ts["m_TC5"]["mae"], 1), tc5_rmse=f(ts["m_TC5"]["rmse"], 1),
         full_bias=sg(g["full fills to 72 MPa"]["bias"], 1), full_rmse=f(g["full fills to 72 MPa"]["rmse"], 1),
         p15_bias=sg(g["from 15 MPa to 69 MPa"]["bias"], 1), p15_rmse=f(g["from 15 MPa to 69 MPa"]["rmse"], 1),
         p30_rmse=f(g["to 30 MPa"]["rmse"], 1), top_bias=sg(ts["m_top"]["bias"], 1), top_rmse=f(ts["m_top"]["rmse"], 1),
         bossv_rmse=f(val["tab_val"]["m_boss"]["rmse"], 1))

# 244 L tank
t244 = {r["case"]["name"]: r for r in val["tank244"]}
def run244(name, asp, dT):
    return [r for r in t244[name]["runs"] if r[0] == asp and r[1] == dT][0]
err244 = []
for nm in ("fast", "slow"):
    meas = t244[nm]["case"]["Tf"]
    for dT in (0.0, 10.0):
        err244.append(run244(nm, 3.0, dT)[2] - meas)
asp_spread = max(max(r[2] for r in t244[nm]["runs"] if r[1] == dT) - min(r[2] for r in t244[nm]["runs"] if r[1] == dT)
                 for nm in ("fast", "slow") for dT in (0.0, 10.0))
N.update(t244f_lo=f(run244("fast", 3.0, 0.0)[2], 1), t244f_hi=f(run244("fast", 3.0, 10.0)[2], 1),
         t244s_lo=f(run244("slow", 3.0, 0.0)[2], 1), t244s_hi=f(run244("slow", 3.0, 10.0)[2], 1),
         t244_asp=f(np.ceil(asp_spread * 2) / 2, 1), t244_band=f(run244("fast", 3.0, 10.0)[2] - run244("fast", 3.0, 0.0)[2], 0),
         t244_neg=f(min(err244), 1), t244_pos=sg(max(err244), 1))

# error bounds table
tc5_e = np.array(ts["Tu"]) - np.array([r[5] for r in ts["rows"]])
full_ix = [i for i, r in enumerate(ts["rows"]) if r[2] > 70]
early = lambda key: float(np.max(np.asarray(h[key]["m"]["pred"]) - np.asarray(h[key]["m"]["meas"])))
N["tab_bounds"] = table(
    ["Data set", "n", "Bias, K", "Range, K", "Use in this work"],
    [("29 L, all tabulated fills, TC-5 (upper zone)", len(tc5_e), sg(tc5_e.mean(), 1), f"{sg(tc5_e.min(), 1)} to {sg(tc5_e.max(), 1)}", "model conservative on average"),
     ("29 L, fills to 72 MPa, TC-5", len(full_ix), sg(tc5_e[full_ix].mean(), 1), f"{sg(tc5_e[full_ix].min(), 1)} to {sg(tc5_e[full_ix].max(), 1)}", "closest to a full vehicle fill"),
     ("29 L, precooled, mean temperature implied by $P$ and SOC", len(e8), sg(e8.mean(), 1), f"{sg(e8.min(), 1)} to {sg(e8.max(), 1)}", "error measure for precooled fills"),
     ("29 L, precooled history, end of fill (figure)", 1, N["pre_end"], "", "inlet history uncertain, not used"),
     ("29 L, histories, first 50 s", 2, "", f"up to {sg(max(early('amb'), early('fig5')), 1)} (20 °C gas)", "not active: maximum at end of fill"),
     ("244 L, TC2, inlet at reported minimum", 2, "", f"{sg(err244[0], 1)}, {sg(err244[2], 1)}", "extrapolation check"),
     ("244 L, TC2, inlet 10 K warmer", 2, "", f"{sg(err244[1], 1)}, {sg(err244[3], 1)}", "extrapolation check")],
    align=["l", "r", "r", "l", "l"])

# ---- reference and J2601 baseline -----------------------------------------------------------------------------
r0, oz, cl, s70 = ref["ref"], ref["onezone"], ref["class"], ref["stop70"]
J = ref["j2601"]
assert abs(J[25.0]["t"] - r0["t"]) < 1e-6, "reference fill and J2601 baseline must be the same fill"
N.update(ref_t=f(r0["t"], 0), ref_m=f(r0["m"], 2), ref_Thot=f(r0["T_hot"], 1), ref_dT=f(r0["T_hot"] - r0["T_bulk"], 1),
         ref_P=f(r0["P_end"], 1), ref_e=f(r0["e_station"], 2), ref_ec=f(r0["e_comp"], 2), ref_er=f(r0["e_ref"], 2), ref_q=f(r0["q_cool"], 2),
         ref_cop=f(r0["COP_mean"], 2), ref_cost=f(r0["c_op"], 2), ref_cen=f(r0["c_energy"], 2), ref_cdem=f(r0["c_demand"], 2), ref_rt=f(100 * r0["round_trip"], 1),
         oz_T=f(oz["T_hot"], 1), ref_b0=f(r0["bank_used"][0], 2), ref_b1=f(r0["bank_used"][1], 2), ref_b2=f(r0["bank_used"][2], 2),
         j0_t=f(J[0.0]["t"], 0), j0_T=f(J[0.0]["T_hot"], 1), j40_t=f(J[40.0]["t"], 0), j40_T=f(J[40.0]["T_hot"], 1),
         j0_e=f(J[0.0]["e_station"], 2), j40_e=f(J[40.0]["e_station"], 2),
         jmargin_lo=f(85 - max(J[T]["T_hot"] for T in J), 0), jmargin_hi=f(85 - min(J[T]["T_hot"] for T in J), 0),
         jfull_t=f(ref["j2601_full"]["t"], 0), jfull_soc=f(ref["j2601_full"]["soc"], 1),
         jwarm_t=f(J[25.0]["warm"]["t"], 0), jwarm_T=f(J[25.0]["warm"]["T_hot"], 1))

# ---- mixing and optimisation -------------------------------------------------------------------------------------
b = opt[25.0]
ric_star = mix["contour"][0][1]
N.update(ric_star=f(ric_star, 2), box_spread=f(mix["spread"][0, 0], 0))
chk = lambda rows: max(r[2] for r in rows[:4])               # highest T_hot on the plausible bound
box_T = lambda rows: rows[4][2]
N["j_box"] = f(box_T(b["ref_check"]), 1)
nomP, robP, boxP = b["nominal"]["picks"], b["robust"]["picks"], b["box"]["picks"]
nomC, robC = b["nominal"]["checks"], b["robust"]["checks"]
red_t = lambda p, r: 100 * (1 - p["t"] / r["t"])
red_e = lambda p, r: 100 * (1 - p["e_station"] / r["e_station"])
N.update(n_nom=str(len(b["nominal"]["F"])), n_rob=str(len(b["robust"]["F"])), n_box=str(len(b["box"]["F"])),
         evals=str(b["robust"]["evaluations"]), n_active=str(int((b["nominal"]["G"][:, 0] > -1.0).sum())),
         nfast_t=f(nomP["fast"]["t"], 0), nfast_dt=f(red_t(nomP["fast"], r0), 0), nlean_e=f(nomP["lean"]["e_station"], 2),
         nlean_de=f(red_e(nomP["lean"], r0), 1),
         nlean_weak=f(chk(nomC["lean"]), 1), nknee_weak=f(chk(nomC["knee"]), 1), nfast_weak=f(chk(nomC["fast"]), 1),
         nom_over=f(ada["nominal_weak"].max() - 85.0, 1), nom_n_exceed=str(int((ada["nominal_weak"] > 85.0 + 1e-9).sum())),
         rob_check_max=f(max(chk(v) for v in robC.values()), 1),
         rfast_t=f(robP["fast"]["t"], 0), rfast_dt=f(red_t(robP["fast"], r0), 0), rlean_e=f(robP["lean"]["e_station"], 2),
         rlean_de=f(red_e(robP["lean"], r0), 1),
         price_e=f(100 * (robP["lean"]["e_station"] / nomP["lean"]["e_station"] - 1), 1),
         price_t=f(100 * (robP["fast"]["t"] / nomP["fast"]["t"] - 1), 1),
         price_share=f(100 * (red_e(nomP["lean"], r0) - red_e(robP["lean"], r0)) / red_e(nomP["lean"], r0), 0),
         box_lean_de=f(abs(red_e(boxP["lean"], r0)), 1), box_word="less" if red_e(boxP["lean"], r0) > 0 else "more",
         box_fast_t=f(boxP["fast"]["t"], 0), box_tmax=f(b["box"]["F"][:, 0].max(), 0), box_lean_e=f(boxP["lean"]["e_station"], 2),
         rfast_weak=f(chk(robC["fast"]), 1), rlean_Ta=f(robP["lean"]["x"][5], 0), rlean_Tb=f(robP["lean"]["x"][6], 0),
         nlean_Ta=f(nomP["lean"]["x"][5], 0), nlean_Tb=f(nomP["lean"]["x"][6], 0))
marg = [r[2] - r[3] for k in ("nominal", "robust") for rows in b[k]["checks"].values() for r in rows[:4]]
N["marg_max"] = f(max(marg), 0)


def envelope(F, t):
    F = F[np.argsort(F[:, 0])]
    return np.array([F[F[:, 0] <= x + 1e-9, 1].min() if (F[:, 0] <= x + 1e-9).any() else np.nan for x in t])


F1, F2 = b["robust"]["F"], b["robust_seed2"]["F"]
t_lo, t_hi = max(F1[:, 0].min(), F2[:, 0].min()), min(F1[:, 0].max(), F2[:, 0].max(), 600.0)
tg = np.linspace(t_lo, t_hi, 200)
tg2 = np.linspace(b["robust"]["F"][:, 0].min(), 420.0, 200)
N["price_e_max"] = f(np.nanmax(envelope(b["robust"]["F"], tg2) / envelope(b["nominal"]["F"], tg2) - 1) * 100, 1)
N.update(seed_de=f(np.nanmax(np.abs(envelope(F1, tg) / envelope(F2, tg) - 1)) * 100, 1), seed_t0=f(t_lo, 0), seed_t1=f(t_hi, 0))
# time at which the local maximum is reached, as a fraction of the fill
fr = []
for k in ("ref", "fast", "lean", "knee"):
    s = b["hist"][k]
    T = np.maximum(s["T_u"], s["T_l"])
    tf = s["t"][int(np.argmax(s["soc"] >= 95.0 - 1e-6))] if (s["soc"] >= 95.0 - 1e-6).any() else s["t"][-1]
    fr.append(s["t"][int(np.argmax(T))] / tf)
N["late_frac"] = f(max(1.0, np.ceil(100 * (1 - min(fr)))), 0)

# designs table
x0 = b["ref_x"]
def drow(name, x, p, weak):
    xs = [f(v, 1) if i != 2 else f(v, 2) for i, v in enumerate(x)]
    return (name, *xs, f(p["t"], 0), f(p["e_station"], 2), f(p["c_op"], 2), f(p["T_hot"], 1), f(weak, 1))
rows = [drow("SAE J2601 table fill", x0, r0, chk(b["ref_check"]))]
for lab, P, C in (("Nominal, shortest", nomP["fast"], nomC["fast"]), ("Nominal, least $e_{st}$", nomP["lean"], nomC["lean"]),
                  ("Robust, shortest", robP["fast"], robC["fast"]), ("Robust, compromise", robP["knee"], robC["knee"]),
                  ("Robust, least $e_{st}$", robP["lean"], robC["lean"])):
    rows.append(drow(lab, P["x"], P, chk(C)))
N["tab_designs"] = table(["Design", "$r_1$", "$r_2$", "$\\xi_b$", "$\\Delta P_{1}$", "$\\Delta P_{2}$", "$T_{pc,a}$", "$T_{pc,b}$",
                          "$t_f$", "$e_{st}$", "$c_{op}$", "$T_{hot}$", "$T_{hot}^{weak}$"], rows)
rows = []
for T in (0.0, 25.0, 40.0):
    bb = opt[T]; rr = bb["ref"]; pp = bb["robust"]["picks"]
    rows.append((f(T, 0), f(bb["ref_x"][0], 1), f(rr["t"], 0), f(rr["e_station"], 2), f(rr["T_hot"], 1),
                 f(pp["fast"]["t"], 0), f(red_t(pp["fast"], rr), 0), f(pp["lean"]["e_station"], 2), f(red_e(pp["lean"], rr), 1),
                 f(100 * (1 - pp["lean"]["c_op"] / rr["c_op"]), 1)))
    N["amb%d_dt" % T] = f(red_t(pp["fast"], rr), 0)
N["tab_amb"] = table(["$T_{amb}$", "APRR", "$t_f$", "$e_{st}$", "$T_{hot}$", "$t_f$", "$\\Delta t_f$, %", "$e_{st}$",
                      "$\\Delta e_{st}$, %", "$\\Delta c_{op}$, %"], rows)
sub = b["subsets"]
N.update(pre_de=f(red_e(sub["precooling"]["picks"]["lean10"], r0), 1), cas_de=f(red_e(sub["cascade"]["picks"]["lean10"], r0), 1),
         ramp_dt=f(red_t(sub["ramp"]["picks"]["fast"], r0), 0), ramp_de=f(red_e(sub["ramp"]["picks"]["lean10"], r0), 1),
         int_de=f(red_e(b["robust"]["picks"]["lean10"], r0), 1),
         ad_max=f(np.ceil(10 * max(abs(100 * (x["e_const"] / x["e_adapt"] - 1)) for x in ada["rows"])) / 10, 1), ad_T=f(ada["rows"][0]["T_const"], 1),
         pre_max=f(early("pre"), 1))

# ---- sensitivity --------------------------------------------------------------------------------------------------
names_in = [i[0] for i in sen["inputs"]]
pretty = {"f_h": "Gas-side heat transfer coefficient, multiplier $f_h$", "k_liner": "Liner conductivity, W/(m K)", "cp_liner": "Liner specific heat, J/(kg K)",
          "k_cfrp": "Composite conductivity, W/(m K)", "T0": "Initial tank temperature minus ambient, K", "P0": "Initial tank pressure, MPa",
          "dT_in": "Precooler set point error, K", "eta_s": "Compressor isentropic efficiency", "dZ": "Relative error of $Z$", "dcv": "Relative error of caloric properties",
          "beta": "Mixing efficiency $\\beta$", "Ri_c": "Critical Richardson number $Ri_c$ (log-uniform)", "phi": "Upper-zone volume fraction $\\phi$"}
jT, jD, jt, je = [sen["outputs"].index(k) for k in ("T_hot", "T_hot_minus_bulk", "t_fill", "e_station")]
rows = [(pretty[n], f(lo, 3).rstrip("0").rstrip("."), f(hi, 3).rstrip("0").rstrip("."), f(max(sen["ST"][i, jT], 0), 2), f(max(sen["ST"][i, jD], 0), 2), f(max(sen["ST"][i, jt], 0), 2), f(max(sen["ST"][i, je], 0), 2))
        for i, (n, lo, hi, _) in enumerate(sen["inputs"])]
N["tab_sobol"] = table(["Input", "Lower", "Upper", "$S_T$: $T_{hot}$", "$S_T$: $T_{hot}-T_{mix}$", "$S_T$: $t_f$", "$S_T$: $e_{st}$"], rows)
ST = sen["ST"]
ix = lambda n: names_in.index(n)
N.update(sob_evals=str(sen["evaluations"]), sT_mean=f(sen["mean"][jT], 1), sT_lo=f(sen["p025"][jT], 1), sT_hi=f(sen["p975"][jT], 1),
         sD_lo=f(sen["p025"][jD], 1), sD_hi=f(sen["p975"][jD], 1), se_lo=f(sen["p025"][je], 2), se_hi=f(sen["p975"][je], 2),
         st_ric=f(ST[ix("Ri_c"), jT], 2), st_beta=f(ST[ix("beta"), jT], 2), st_in=f(ST[ix("dT_in"), jT], 2),
         st_T0=f(ST[ix("T0"), jT], 2), st_P0=f(ST[ix("P0"), jT], 2), st_fh=f(max(ST[ix("f_h"), jT], 0), 3),
         st_wall=f(max(ST[ix("k_liner"), jT], 0) + max(ST[ix("cp_liner"), jT], 0) + max(ST[ix("k_cfrp"), jT], 0), 2),
         st_prop=f(max(ST[ix("dZ"), jT], 0) + max(ST[ix("dcv"), jT], 0), 2),
         st_eta_e=f(ST[ix("eta_s"), je], 2), st_P0_t=f(ST[ix("P0"), jt], 2), st_phi_D=f(ST[ix("phi"), jD], 2))

# ---- energy and cost ----------------------------------------------------------------------------------------------------
from h2lab.research.station import Economics, capex
st5 = ene["stages"][5]
N["tab_stages"] = table(["Stage", "Inlet pressure, MPa", "Outlet pressure, MPa", "Inlet temperature, °C", "Outlet temperature, °C", "Isentropic work, kWh/kg", "Gas-side work, kWh/kg", "Heat to cooler, kWh/kg"],
                        [(r["stage"], f(r["P_in"] / 1e6, 2), f(r["P_out"] / 1e6, 2), f(r["T_in"] - C0, 0), f(r["T_out"] - C0, 0), f(r["w_s"] / 3.6e6, 3), f(r["w"] / 3.6e6, 3), f(r["q_cool"] / 3.6e6, 3)) for r in st5]
                        + [("Sum", "", "", "", "", f(sum(r["w_s"] for r in st5) / 3.6e6, 3), f(sum(r["w"] for r in st5) / 3.6e6, 3), f(sum(r["q_cool"] for r in st5) / 3.6e6, 3))])
N["tab_nstage"] = table(["Number of stages", "Stage pressure ratio", "Highest discharge temperature, °C", "Gas-side work to 95 MPa, kWh/kg", "Electricity for the J2601 fill, kWh/kg"],
                        [(n, f((95 / 2) ** (1 / n), 2), f(max(r["T_out"] for r in ene["stages"][n]) - C0, 0), f(sum(r["w"] for r in ene["stages"][n]) / 3.6e6, 2), f(ene["by_stages"][n]["e_comp"], 2)) for n in (2, 3, 4, 5, 6)])
a = ene["ref"]
bk = a["banks"]
N["tab_banks"] = table(["Bank", "Initial pressure, MPa", "Pressure after the fill, MPa", "Hydrogen drawn, kg", "Share, %", "Refill work, kWh/kg (gas side)", "Work to initial pressure, kWh/kg"],
                       [(nm, f(x["P0"] / 1e6, 1), f(x["P_end"] / 1e6, 1), f(x["m"], 2), f(100 * x["m"] / ene["ref_m"], 1), f(x["w"] / 3.6e6, 3), f(x["w_class"] / 3.6e6, 3)) for nm, x in zip(("Low", "Medium", "High"), bk)])
s2 = ref["stop70_2stage"]
N["tab_recon"] = table(["Step", "Compressor, kWh/kg", "Refrigeration, kWh/kg", "Station, kWh/kg"],
                       [("Class report: 2 stages, every kilogram compressed to the initial bank pressure, gas-side work", f(cl["e_comp"], 2), f(cl["e_chill"], 2), f(cl["e_comp"] + cl["e_chill"], 2)),
                        ("Same accounting recomputed with the research model", f(s2["e_comp_class"], 2), f(s2["e_ref_shaft"], 2), f(s2["e_comp_class"] + s2["e_ref_shaft"], 2)),
                        ("Delivery pressure follows the bank during refill", f(s2["e_comp_gas"], 2), f(s2["e_ref_shaft"], 2), f(s2["e_comp_gas"] + s2["e_ref_shaft"], 2)),
                        ("5 stages instead of 2", f(s70["e_comp_gas"], 2), f(s70["e_ref_shaft"], 2), f(s70["e_comp_gas"] + s70["e_ref_shaft"], 2)),
                        ("Mechanical and motor efficiency (0.95 each); refrigeration drive 0.90", f(s70["e_comp"], 2), f(s70["e_ref"], 2), f(s70["e_station"], 2)),
                        ("Fill continued to 95 % state of charge (J2601 baseline of this paper)", f(a["e_comp"], 2), f(a["e_ref"], 2), f(a["e_station"], 2))])
u = ene["util"]
i40 = int(np.argmin(np.abs(u[:, 0] - 40)))
eco = Economics()
kg40 = u[i40, 1]
N.update(iso=f(ene["isothermal"], 2), w5=f(sum(r["w"] for r in st5) / 3.6e6, 2), T2=f(max(r["T_out"] for r in ene["stages"][2]) - C0, 0),
         T5=f(max(r["T_out"] for r in st5) - C0, 0), e_eta60=f(ene["by_eta"][0.6]["e_comp"], 2), e_eta80=f(ene["by_eta"][0.8]["e_comp"], 2),
         e_sup20=f(ene["by_supply"][20.0]["e_comp"], 2), kg40=f(kg40, 0), s2_total=f(s2["e_station"], 2),
         capex40=f(u[i40, 10] / 1e6, 2), capex40_lo=f(capex(eco, kg40, 0.8) / 1e6, 2), capex40_hi=f(capex(eco, kg40, 0.6) / 1e6, 2),
         capex_norm_lo=f(1200 * kg40 / 1e6, 2), capex_norm_hi=f(3000 * kg40 / 1e6, 2),
         cap40=f(u[i40, 2], 2), cap40_lo=f(u[i40, 8], 2), cap40_hi=f(u[i40, 9], 2), cap_ratio=f(u[i40, 2] / r0["c_op"], 1),
         sb40=f(u[i40, 5], 2), cars_h=f(ene["capacity_cars_per_hour"], 1), P15=f(a["P15"], 0), Pc=f(a["P_comp_rated"], 0),
         e_in=f(a["e_in"], 1), e_out=f(a["e_out"], 1), peak_ref=f(a["peak_ref_kW"], 0), fast_cars=f(3600 / (robP["fast"]["t"] + 120), 1))
json.dump({k: v for k, v in N.items() if not k.startswith("tab_")}, open(os.path.join(RES, "numbers.json"), "w"), indent=1, ensure_ascii=False)

# ---- fill the template ----------------------------------------------------------------------------------------------------
body = open(os.path.join(HERE, "manuscript_template.md"), encoding="utf-8").read()
missing = set(re.findall(r"<<(\w+)>>", body)) - set(N)
assert not missing, missing
for k, v in N.items():
    body = body.replace("<<" + k + ">>", v)
refs = json.load(open(os.path.join(HERE, "references.json"), encoding="utf-8"))
order = []


def cite(m):
    out = []
    for key in m.group(1).split(";"):
        key = key.strip().lstrip("@")
        assert key in refs, key
        if key not in order:
            order.append(key)
        out.append(order.index(key) + 1)
    out.sort()
    s, i = [], 0
    while i < len(out):
        j = i
        while j + 1 < len(out) and out[j + 1] == out[j] + 1:
            j += 1
        s.append(str(out[i]) if j == i else (f"{out[i]},{out[j]}" if j == i + 1 else f"{out[i]}\u2013{out[j]}"))
        i = j + 1
    return "[" + ",".join(s) + "]"


body = body.replace("[A11;A13]", "[@a11;@a13]").replace("[A11]", "[@a11]").replace("[A13]", "[@a13]")
body = re.sub(r"\[((?:@[\w-]+;?\s*)+)\]", cite, body)
REFS = [(i + 1, refs[k]) for i, k in enumerate(order)]
assert "\u2014" not in body, "em dash found"
md_core = body
open(os.path.join(HERE, "manuscript.md"), "w", encoding="utf-8").write(md_core)
print("references:", len(order), "unused:", sorted(set(refs) - set(order)))

# ==========================================================================================================
# Word submission file
# ==========================================================================================================
def build_docx():
    from docx import Document
    from docx.shared import Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    md = md_core.replace("FIGDIR/", FIG + "/")
    md = re.sub(r"\]\((" + re.escape(FIG) + r"/[\w]+)\)", r"](\1.png)", md)
    md = md.replace("{width=3.3in}", "{width=3.4in}")
    md += "\n\n# References\n\n" + "\n\n".join(f"[{i}] {t}" for i, t in REFS) + "\n"
    md += ("\n\n# Graphical abstract (optional)\n\n![The two-zone tank model with the 85 °C limit applied to the hotter zone, "
           "and the Pareto fronts of fill time and station electricity at 25 °C for the nominal and the robust problem, with the SAE J2601 table fill.]"
           f"({FIG}/graphical_abstract.png){{width=6.5in}}\n")
    src = os.path.join(HERE, "manuscript_docx.md")
    open(src, "w", encoding="utf-8").write(md)
    out = os.path.join(HERE, "H2 Fast-Fill Lab manuscript.docx")
    subprocess.run(["pandoc", src, "-o", out, "--from", "markdown+pipe_tables+tex_math_dollars+implicit_figures",
                    "--reference-doc", os.path.join(HERE, "reference.docx")], check=True)
    os.remove(src)
    d = Document(out)

    def border(el, edges):
        bdr = OxmlElement("w:tcBorders")
        for e, sz in edges:
            x = OxmlElement("w:" + e); x.set(qn("w:val"), "single"); x.set(qn("w:sz"), str(sz)); x.set(qn("w:color"), "000000"); bdr.append(x)
        el.get_or_add_tcPr().append(bdr)
    # page: A4, 2.5 cm margins, continuous line numbers
    for s in d.sections:
        s.page_height, s.page_width = Cm(29.7), Cm(21.0)
        s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Cm(2.5)
        ln = OxmlElement("w:lnNumType"); ln.set(qn("w:countBy"), "1"); ln.set(qn("w:restart"), "continuous"); ln.set(qn("w:distance"), "340")
        s._sectPr.append(ln)
    # fonts: Times New Roman 12 pt for the body
    for st in d.styles:
        try:
            if st.type == 1 and st.font is not None:
                st.font.name = "Times New Roman"
                rpr = st.element.get_or_add_rPr()
                rf = rpr.find(qn("w:rFonts"))
                if rf is None:
                    rf = OxmlElement("w:rFonts"); rpr.append(rf)
                for k in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
                    rf.set(qn(k), "Times New Roman")
        except Exception:
            pass
    for name, size in (("Normal", 12), ("Body Text", 12), ("First Paragraph", 12), ("Compact", 12), ("Title", 16),
                       ("Heading 1", 13), ("Heading 2", 12), ("Image Caption", 11), ("Table Caption", 11)):
        try:
            d.styles[name].font.size = Pt(size)
        except KeyError:
            pass
    for t in d.tables:
        tblPr = t._tbl.tblPr
        for old in tblPr.findall(qn("w:tblW")):
            tblPr.remove(old)
        w = OxmlElement("w:tblW"); w.set(qn("w:type"), "pct"); w.set(qn("w:w"), "5000"); tblPr.append(w)
        n = len(t.rows); ncol = len(t.columns)
        fs = 10 if ncol <= 5 else (9 if ncol <= 9 else 8)
        def wt(j):
            body_ = [row.cells[j].text for row in list(t.rows)[1:]] or [""]
            longest_word = max([len(w_) for c in [t.rows[0].cells[j].text] + body_ for w_ in c.split()] or [4])
            data = max(len(c) for c in body_)
            hdr = len(t.rows[0].cells[j].text)
            return max(min(max(data, min(hdr, 14)), 40 if ncol <= 7 else (24 if j == 0 else 12)), 1.6 * longest_word + 3, 6)
        wts = [wt(j) for j in range(ncol)]
        widths = [int(9070 * w_ / float(sum(wts))) for w_ in wts]
        lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblPr.append(lay)
        for j, gc in enumerate(t._tbl.tblGrid.findall(qn("w:gridCol"))):
            gc.set(qn("w:w"), str(widths[j]))
        for i, row in enumerate(t.rows):
            for j, c in enumerate(row.cells):
                tcPr = c._tc.get_or_add_tcPr()
                for old in tcPr.findall(qn("w:tcW")):
                    tcPr.remove(old)
                tw = OxmlElement("w:tcW"); tw.set(qn("w:type"), "dxa"); tw.set(qn("w:w"), str(widths[j])); tcPr.insert(0, tw)
                for p in c.paragraphs:
                    p.paragraph_format.space_after = Pt(1); p.paragraph_format.space_before = Pt(1); p.paragraph_format.line_spacing = 1.0
                    for r_ in p.runs:
                        r_.font.size = Pt(fs)
                        if i == 0:
                            r_.font.bold = True
                edges = []
                if i == 0:
                    edges += [("top", 8), ("bottom", 4)]
                if i == n - 1:
                    edges += [("bottom", 8)]
                if edges:
                    border(c._tc, edges)
            if i == 0:
                trPr = row._tr.get_or_add_trPr(); trPr.append(OxmlElement("w:tblHeader"))
    # double spacing for all text outside tables; captions and references 1.5 is not allowed: keep double
    for p in d.paragraphs:
        pf = p.paragraph_format
        pf.line_spacing_rule = WD_LINE_SPACING.DOUBLE
        if p.style.name in ("Image Caption", "Captioned Figure"):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if p.style.name == "Captioned Figure" else WD_ALIGN_PARAGRAPH.LEFT
        if p.text.startswith("Table ") and p.runs and p.runs[0].bold:
            pf.keep_with_next = True
    d.core_properties.author = "Aarya Chiripal"; d.core_properties.last_modified_by = "Aarya Chiripal"
    d.core_properties.title = TITLE
    d.core_properties.comments = ""; d.core_properties.keywords = ""
    d.save(out)
    print("wrote", out)


# ==========================================================================================================
# Typeset article (XeLaTeX)
# ==========================================================================================================
def upright(tex):
    """Multi-letter subscripts and superscripts are labels, set upright (ISO 80000-2)."""
    def fix(m):
        body_ = m.group(2)
        parts = body_.split(",")
        if all(re.fullmatch(r"[A-Za-z]+\d*", p_) for p_ in parts) and any(len(p_) > 1 for p_ in parts):
            return m.group(1) + "{\\mathrm{" + body_ + "}}"
        return m.group(0)
    return re.sub(r"([_^])\{([A-Za-z0-9,]+)\}", fix, tex)


def tex_inline(s):
    """Convert the small amount of markdown that appears in table cells and captions to LaTeX."""
    s = s.replace("\\$", "\x00")
    parts = re.split(r"(\$[^$]+\$)", s)
    out = []
    for p in parts:
        if p.startswith("$") and p.endswith("$") and len(p) > 1:
            out.append(upright(p))
            continue
        p = p.replace("&", "\\&").replace("%", "\\%").replace("#", "\\#").replace("_", "\\_")
        p = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", p)
        p = re.sub(r"(https?://\S+)", lambda m: "\\url{" + m.group(1) + "}", p)
        p = p.replace("\x00", "\\$")
        out.append(p)
    return "".join(out)


def tex_table(head, rows, caption):
    ncol = len(head)
    longest = [max(len(re.sub(r"\$[^$]*\$", "xx", str(r[j]))) for r in [head] + rows) for j in range(ncol)]
    textish = [j for j in range(ncol) if any(re.search(r"[A-Za-z]{3,}", re.sub(r"\$[^$]*\$", "", str(r[j]))) for r in rows)]
    wide = ncol > 4 or sum(longest) > 70
    env = "table*" if wide else "table"
    size = "\\footnotesize" if ncol <= 8 else "\\scriptsize"
    spec = []
    wrap_cols = set()
    for j in range(ncol):
        if j in textish and longest[j] > 22:
            spec.append(">{\\raggedright\\arraybackslash}X")
        elif j in textish:
            spec.append("l")
        else:
            hl = len(re.sub(r"\$[^$]*\$", "xx", str(head[j])))
            dl = max(len(re.sub(r"\$[^$]*\$", "xx", str(r[j]))) for r in rows)
            spec.append("r")
            if hl > max(8, 1.6 * dl):
                wrap_cols.add(j)
    use_fill = "X" not in "".join(spec)
    def hcell(j, hh):
        t_ = tex_inline(hh)
        if j in wrap_cols:
            w_ = max(2.2, min(len(re.sub(r"\$[^$]*\$", "xx", hh)), 20) * (0.5 if ncol <= 6 else 0.34))
            return "\\parbox[b]{%.1fem}{\\raggedleft %s}" % (w_, t_)
        return t_
    head_tex = " & ".join(hcell(j, hh) for j, hh in enumerate(head))
    lines = [f"\\begin{{{env}}}[!tbp]", "\\centering", size, f"\\caption{{{caption}}}",
             (f"\\begin{{tabular*}}{{\\{'textwidth' if wide else 'columnwidth'}}}{{@{{\\extracolsep{{\\fill}}}}{''.join(spec)}@{{}}}}" if use_fill else
              f"\\begin{{tabularx}}{{\\{'textwidth' if wide else 'columnwidth'}}}{{@{{}}{''.join(spec)}@{{}}}}"), "\\toprule",
             head_tex + " \\\\", "\\midrule"]
    for r in rows:
        cells = [tex_inline(str(c)) for c in r]
        cells = ["{}" + c if c.startswith("[") else c for c in cells]
        if cells[0].startswith("   "):
            cells[0] = "\\hspace{1em}" + cells[0].strip()
        lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular*}" if use_fill else "\\end{tabularx}", f"\\end{{{env}}}"]
    return "\n".join(lines)


def build_pdf():
    text = md_core
    # front matter
    fm = re.search(r"^---\n(.*?)\n---\n", text, re.S)
    text = text[fm.end():]
    pre, rest = text.split("# Highlights", 1)
    affil, corr = [l.strip() for l in pre.strip().split("\n\n")][:2]
    hl, rest = rest.split("# Abstract", 1)
    abstract, rest = rest.split("**Keywords:**", 1)
    keywords, rest = rest.split("\n", 1)
    highlights = [l[2:].strip() for l in hl.strip().splitlines() if l.startswith("- ")]
    # nomenclature table goes into its own float
    nomen_block = re.search(r"# Nomenclature\n\n(\|.*?)\n\n", rest, re.S)
    nomen_rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in nomen_block.group(1).splitlines()[2:]]
    rest = rest[:nomen_block.start()] + rest[nomen_block.end():]
    blocks = {}

    def stash(tex):
        key = f"RAWBLOCK{len(blocks):03d}"
        blocks[key] = tex
        return f"\n\n{key}\n\n"
    # tables: caption paragraph followed by a pipe table
    def repl_table(m):
        mm = re.match(r"\*\*(Table \d+\.)\*\*\s*(.*)", m.group(1).strip())
        caption = "\\textbf{" + mm.group(1) + "} " + tex_inline(mm.group(2))
        lines = [l for l in m.group(2).strip().splitlines()]
        head = [c.strip() for c in lines[0].strip().strip("|").split("|")]
        rows_ = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines[2:]]
        return stash(tex_table(head, rows_, caption))
    rest = re.sub(r"\n(\*\*Table \d+\.\*\*[^\n]*)\n\n((?:\|[^\n]*\n?)+)", repl_table, rest)
    # figures
    def repl_fig(m):
        cap, path, width = m.group(1), m.group(2), m.group(3)
        lab = re.match(r"(Fig\. \d+\.)\s*(.*)", cap, re.S)
        capt = "\\textbf{" + lab.group(1) + "} " + tex_inline(lab.group(2))
        one = "3.3in" in width
        env = "figure" if one else "figure*"
        return stash(f"\\begin{{{env}}}[!tbp]\n\\centering\n\\includegraphics{{{path.replace('FIGDIR', FIG)}.pdf}}\n\\caption{{{capt}}}\n\\end{{{env}}}")
    rest = re.sub(r"!\[(.*?)\]\((FIGDIR/\w+)\)\{width=([\d.]+in)\}", repl_fig, rest, flags=re.S)
    # display equations with their number
    def repl_eq(m):
        body_, n = m.group(1).strip(), m.group(2)
        return stash(f"\\begin{{equation}}\n{body_}\n\\tag{{{n}}}\n\\end{{equation}}")
    rest = re.sub(r"\$\$(.*?)\\qquad \((\d+)\)\s*\$\$", repl_eq, rest, flags=re.S)
    assert "$$" not in rest, "unnumbered display equation left"
    tmp = os.path.join(HERE, "_body.md")
    open(tmp, "w", encoding="utf-8").write(rest)
    tex_body = subprocess.run(["pandoc", tmp, "-f", "markdown+tex_math_dollars-implicit_figures", "-t", "latex", "--wrap=none"],
                              capture_output=True, text=True, check=True).stdout
    os.remove(tmp)
    for k, v in blocks.items():
        tex_body = tex_body.replace(k, v)
    tex_body = re.sub(r"\\hypertarget\{[^}]*\}\{%\n(\\(?:sub)*section\{.*?\})\}", r"\1", tex_body)
    tex_body = re.sub(r"\\label\{[^}]*\}", "", tex_body)
    tex_body = tex_body.replace("\\tightlist\n", "")
    # nomenclature float
    nom = ["\\begin{table}[!tbp]", "\\scriptsize", "\\caption{\\textbf{Nomenclature}}",
           "\\begin{tabularx}{\\columnwidth}{@{}l>{\\raggedright\\arraybackslash}X l@{}}", "\\toprule"]
    for r in nomen_rows:
        if r[0] == "Subscripts":
            nom.append("\\midrule")
            nom.append("\\multicolumn{3}{@{}>{\\raggedright\\arraybackslash}p{\\columnwidth}@{}}{\\textit{Subscripts:} " + tex_inline(r[1]) + "} \\\\")
        else:
            nom.append(" & ".join(tex_inline(c) for c in r) + " \\\\")
    nom += ["\\bottomrule", "\\end{tabularx}", "\\end{table}"]
    tex_body = tex_body.replace("\\section{1. Introduction", "\n".join(nom) + "\n\n\\section{1. Introduction", 1)
    refs_tex = "\n".join(f"\\bibitem{{r{i}}} {tex_inline(t)}" for i, t in REFS)
    hl_tex = "\n".join(f"\\item {tex_inline(x)}" for x in highlights)
    abs_tex = subprocess.run(["pandoc", "-f", "markdown", "-t", "latex", "--wrap=none"], input=abstract.strip(), capture_output=True, text=True, check=True).stdout
    kw = [k.strip().rstrip(".") for k in keywords.strip().split(";")]
    title = TITLE
    tex_body = upright(tex_body)
    doc = open(os.path.join(HERE, "article_template.tex"), encoding="utf-8").read()
    doc = (doc.replace("%%TITLE%%", title).replace("%%AFFIL%%", tex_inline(affil)).replace("%%CORR%%", tex_inline(corr.replace("Corresponding author: ", "")))
              .replace("%%HIGHLIGHTS%%", hl_tex).replace("%%ABSTRACT%%", abs_tex).replace("%%KEYWORDS%%", "\\\\\n".join(kw))
              .replace("%%BODY%%", tex_body).replace("%%REFS%%", refs_tex).replace("%%GA%%", FIG + "/graphical_abstract.pdf"))
    bdir = os.path.join(HERE, "_build")
    os.makedirs(bdir, exist_ok=True)
    texf = os.path.join(bdir, "article.tex")
    open(texf, "w", encoding="utf-8").write(doc)
    for _ in range(2):
        p = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "article.tex"], cwd=bdir, capture_output=True, text=True)
    log = open(os.path.join(bdir, "article.log"), encoding="utf-8", errors="replace").read()
    errs = [l for l in log.splitlines() if l.startswith("!")]
    over = [l for l in log.splitlines() if "Overfull" in l]
    print("latex errors:", len(errs), "overfull:", len(over))
    for l in errs[:10] + over[:20]:
        print("  ", l)
    if os.path.exists(os.path.join(bdir, "article.pdf")):
        shutil.copy(os.path.join(bdir, "article.pdf"), os.path.join(HERE, "H2 Fast-Fill Lab paper.pdf"))
        print("wrote", os.path.join(HERE, "H2 Fast-Fill Lab paper.pdf"))


if __name__ == "__main__":
    if "--no-docx" not in sys.argv:
        build_docx()
    if "--no-pdf" not in sys.argv:
        build_pdf()
