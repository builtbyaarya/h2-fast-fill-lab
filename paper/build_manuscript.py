"""
Builds the manuscript (Word) from the results written by run_all.py and the figures drawn by figures.py.
Every number in the text and tables is read from paper/results/. Usage:  python paper/build_manuscript.py
"""
import json, os, pickle, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES, FIG = os.path.join(HERE, "results"), os.path.join(HERE, "figures")
L = lambda n: pickle.load(open(os.path.join(RES, n + ".pkl"), "rb"))
num, val, ref, opt, sen, ene = L("numerics"), L("validation"), L("reference"), L("optimise"), L("sensitivity"), L("energy")
C0 = 273.15


def f(x, d=1):
    s = f"{float(x):.{d}f}"
    return s.replace("-", "\u2212")


def table(head, rows, align=None):
    align = align or ["l"] + ["r"] * (len(head) - 1)
    line = "|" + "|".join({"l": ":--", "r": "--:", "c": ":-:"}[a] for a in align) + "|"
    out = ["| " + " | ".join(head) + " |", line] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


N = {}
# ---- numerics
dts = num["dt"]
N["tab_dt"] = table(["Time step, s", "Fill time, s", "Maximum local temperature, °C", "Hydrogen delivered, kg", "Gas energy balance residual"],
                    [(f(r[0], 5).rstrip("0").rstrip("."), f(r[1], 2), f(r[2], 3), f(r[4], 4), "below $10^{-12}$" if r[6] < 1e-12 else "%.0e" % r[6]) for r in dts])
N["dt_err"] = f(abs(dts[2][2] - dts[-1][2]), 3)
N["node_err"] = f(abs(num["nodes"][2][1] - num["nodes"][-1][1]), 2)
N["tabP"], N["tabT"] = "$5\\times10^{-6}$" if num["table"][0] < 6e-6 else "%.0e" % num["table"][0], f(num["table"][1], 3)
N["ms"] = f(num["ms_per_fill"], 0)
# ---- validation
h = val["hist"]
rp, c19, t8 = val["repeat"], val["cyc19"], val["table8"]
ts, tl = val["tab_two-stage"], val["tab_linear"]
mc = val["mc"]
N.update(boss_area=f(0.012 * 1e4, 0), boss_rmse=f(val["tab_cal"]["m_boss"]["rmse"], 1), beta="0.35",
         rep_T=f(rp["T_end"], 1), rep_err=f(rp["T_end"] - 86.9, 1), rep_noboss=f(rp["T_end_noboss"], 1), rep_noboss_err=f(rp["T_end_noboss"] - 86.9, 1),
         rep_rise=f(rp["T_end"] - 11.2, 1), mc_lo=f(np.percentile(mc["Tend"], 2.5), 1), mc_hi=f(np.percentile(mc["Tend"], 97.5), 1), mc_mean=f(mc["Tend"].mean(), 1),
         mc_n=str(mc["N"]), c19_T=f(c19["T_end"], 1), c19_err=f(c19["T_end"] - 83.1, 1), c19_boss=f(c19["boss"], 1),
         soc_bias=f(t8["m"]["bias"], 1), soc_rmse=f(t8["m"]["rmse"], 1), soc_max=f(t8["m"]["max"], 1),
         amb_rmse=f(h["amb"]["m"]["rmse"], 1), amb_bias=f(h["amb"]["m"]["bias"], 1), amb_max=f(h["amb"]["m"]["max"], 1), amb_end=f(h["amb"]["m"]["pred"][-1] - h["amb"]["m"]["meas"][-1], 1),
         amb_P=f(h["amb"]["m"]["P"]["rmse"], 1), pre_P=f(h["pre"]["m"]["P"]["rmse"], 1),
         pre_rmse=f(h["pre"]["m"]["rmse"], 1), pre_bias=f(h["pre"]["m"]["bias"], 1), pre_end=f(h["pre"]["m"]["pred"][-1] - h["pre"]["m"]["meas"][-1], 1),
         f5_rmse=f(h["fig5"]["m"]["rmse"], 1), f5_bias=f(h["fig5"]["m"]["bias"], 1), f5_end=f(h["fig5"]["m"]["pred"][-1] - h["fig5"]["m"]["meas"][-1], 1),
         f5_dT=f(h["fig5"]["dT_end"], 1), chi1_u=f(h["fig5"]["chi1"]["Tu_end"], 1), chi1_l=f(h["fig5"]["chi1"]["Tl_end"], 1),
         chi0_u=f(h["fig5"]["chi0"]["Tu_end"], 1), chi0_l=f(h["fig5"]["chi0"]["Tl_end"], 1),
         class80=f(val["class"][80.0], 1), class200=f(val["class"][200.0], 1),
         nb_bias=f(val["tab_noboss"]["m_TC5"]["bias"], 1), nb_rmse=f(val["tab_noboss"]["m_TC5"]["rmse"], 1))


def mrow(label, m, unit="K", n=None):
    return (label, n or m["n"], f(m["bias"], 1), f(m["mae"], 1), f(m["rmse"], 1), f(m["max"], 1), unit)


g = ts["groups"]
N["tab_val"] = table(
    ["Quantity (source)", "n", "Bias", "MAE", "RMSE", "Max", "Unit"],
    [mrow("Tank-average temperature history, gas at 20 °C ([A13] Fig. 11a)", h["amb"]["m"]),
     mrow("Tank-average temperature history, gas at −30 °C ([A13] Fig. 11a)", h["pre"]["m"]),
     mrow("Gas temperature history, thermocouples TC-1 to TC-6 ([A11] Fig. 5)", h["fig5"]["m"]),
     mrow("Pressure history, both fills of [A13] Fig. 11a (imposed)", dict(n=9, bias=(h["amb"]["m"]["P"]["bias"] * 5 + h["pre"]["m"]["P"]["bias"] * 4) / 9,
                                                                          mae=(h["amb"]["m"]["P"]["mae"] * 5 + h["pre"]["m"]["P"]["mae"] * 4) / 9,
                                                                          rmse=np.sqrt((h["amb"]["m"]["P"]["rmse"] ** 2 * 5 + h["pre"]["m"]["P"]["rmse"] ** 2 * 4) / 9),
                                                                          max=max(h["amb"]["m"]["P"]["max"], h["pre"]["m"]["P"]["max"])), "MPa"),
     mrow("TC-5 at end of fill, all tabulated fills ([A11] Tables 1 to 3)", ts["m_TC5"]),
     mrow("   fills to 72 MPa", g["full fills to 72 MPa"]),
     mrow("   fills from 15 MPa to 69 MPa", g["from 15 MPa to 69 MPa"]),
     mrow("   fills to 30 MPa", g["to 30 MPa"]),
     mrow("TC-5 at end of fill, same fills, single linear ramp assumed", tl["m_TC5"]),
     mrow("TC-5 at end of fill, same fills, boss heat sink removed", val["tab_noboss"]["m_TC5"]),
     mrow("Outer wall surface, maximum ([A11] Tables 1 to 3)", ts["m_top"]),
     mrow("Boss, maximum, validation fills ([A11] Tables 1 to 3)", val["tab_val"]["m_boss"]),
     mrow("Boss, maximum, calibration fills (fitted)", val["tab_cal"]["m_boss"]),
     mrow("Final state of charge, precooled fills ([A13] Table 8)", t8["m"], "% points"),
     ("Final tank-average temperature, 12 repeated fills ([A13] Table 7)", 1, f(rp["T_end"] - 86.9, 1), "", "", "", "K"),
     ("Final temperature, 19 L tank, 350 cycles ([A13] Table 6)", 1, f(c19["T_end"] - 83.1, 1), "", "", "", "K")],
    align=["l", "r", "r", "r", "r", "r", "l"])
N.update(tc5_bias=f(ts["m_TC5"]["bias"], 1), tc5_mae=f(ts["m_TC5"]["mae"], 1), tc5_rmse=f(ts["m_TC5"]["rmse"], 1), tc5_max=f(ts["m_TC5"]["max"], 1),
         full_bias=f(g["full fills to 72 MPa"]["bias"], 1), full_rmse=f(g["full fills to 72 MPa"]["rmse"], 1), full_mae=f(g["full fills to 72 MPa"]["mae"], 1),
         p15_bias=f(g["from 15 MPa to 69 MPa"]["bias"], 1), p15_rmse=f(g["from 15 MPa to 69 MPa"]["rmse"], 1),
         p30_rmse=f(g["to 30 MPa"]["rmse"], 1), top_bias=f(ts["m_top"]["bias"], 1), top_rmse=f(ts["m_top"]["rmse"], 1),
         bossv_rmse=f(val["tab_val"]["m_boss"]["rmse"], 1), bossv_bias=f(val["tab_val"]["m_boss"]["bias"], 1), lin_rmse=f(tl["m_TC5"]["rmse"], 1))
# ---- reference
r0, oz, cl, s70 = ref["ref"], ref["onezone"], ref["class"], ref["stop70"]
N.update(ref_mdot=f(r0["mdot_max"], 0), ref_t=f(r0["t"], 0), ref_m=f(r0["m"], 2), ref_Thot=f(r0["T_hot"], 1), ref_Tb=f(r0["T_bulk"], 1), ref_dT=f(r0["T_hot"] - r0["T_bulk"], 1),
         ref_P=f(r0["P_end"], 1), ref_e=f(r0["e_station"], 2), ref_ec=f(r0["e_comp"], 2), ref_er=f(r0["e_ref"], 2), ref_q=f(r0["q_cool"], 2),
         ref_cop=f(r0["COP_mean"], 2), ref_cost=f(r0["c_op"], 2), ref_cen=f(r0["c_energy"], 2), ref_cdem=f(r0["c_demand"], 2), ref_rt=f(100 * r0["round_trip"], 1),
         ref_Ts=f(r0["Ts_max"], 1), oz_T=f(oz["T_hot"], 1), ref_b0=f(r0["bank_used"][0], 2), ref_b1=f(r0["bank_used"][1], 2), ref_b2=f(r0["bank_used"][2], 2),
         cl_t=f(cl["t"], 1), cl_T=f(cl["T_peak"], 1), cl_m=f(cl["m"], 2), cl_soc=f(cl["soc"], 0), s70_T=f(s70["T_hot"], 1), s70_t=f(s70["t"], 1), s70_m=f(s70["m"], 2),
         ref0_Thot=f(ref["ref_0"]["T_hot"], 1), ref40_Thot=f(ref["ref_40"]["T_hot"], 1), ref0_e=f(ref["ref_0"]["e_station"], 2), ref40_e=f(ref["ref_40"]["e_station"], 2),
         ref0_cop=f(ref["ref_0"]["COP_mean"], 2), ref40_cop=f(ref["ref_40"]["COP_mean"], 2))
# ---- optimisation
b = opt[25.0]
F = b["front"]["F"]
pk = b["picks"]
N.update(n_front=str(len(F)), evals=str(b["front"]["evaluations"]), opt_wall=f(b["wall_s"] / 60, 1),
         corr_ec=f(np.corrcoef(F[:, 1], F[:, 2])[0, 1], 3), n_active=str(int((b["front"]["G"][:, 0] > -1.0).sum())),
         e_min=f(F[:, 1].min(), 2), e_max=f(F[:, 1].max(), 2), t_min=f(F[:, 0].min(), 0), t_max=f(F[:, 0].max(), 0),
         fast_t=f(pk["fast"]["t"], 0), fast_dt=f(100 * (1 - pk["fast"]["t"] / r0["t"]), 0), fast_e=f(pk["fast"]["e_station"], 2),
         fast_de=f(100 * (pk["fast"]["e_station"] / r0["e_station"] - 1), 1), fast_T=f(pk["fast"]["T_hot"], 1),
         lean_t=f(pk["lean"]["t"], 0), lean_e=f(pk["lean"]["e_station"], 2), lean_de=f(100 * (1 - pk["lean"]["e_station"] / r0["e_station"]), 1),
         lean_dc=f(100 * (1 - pk["lean"]["c_op"] / r0["c_op"]), 1), lean_T=f(pk["lean"]["T_hot"], 1), lean_er=f(pk["lean"]["e_ref"], 2),
         lean_der=f(100 * (1 - pk["lean"]["e_ref"] / r0["e_ref"]), 0), lean_P=f(pk["lean"]["P_end"], 1),
         knee_t=f(pk["knee"]["t"], 0), knee_dt=f(100 * (1 - pk["knee"]["t"] / r0["t"]), 0), knee_e=f(pk["knee"]["e_station"], 2),
         knee_de=f(100 * (1 - pk["knee"]["e_station"] / r0["e_station"]), 1), knee_T=f(pk["knee"]["T_hot"], 1), knee_Tb=f(pk["knee"]["T_bulk"], 1))
sub = b["subsets"]
N.update(pre_de=f(100 * (1 - sub["precooling"]["front"]["F"][:, 1].min() / r0["e_station"]), 1),
         cas_de=f(100 * (1 - sub["cascade"]["front"]["F"][:, 1].min() / r0["e_station"]), 1),
         ramp_dt=f(100 * (1 - sub["ramp"]["front"]["F"][:, 0].min() / r0["t"]), 0), ramp_de=f(100 * (1 - sub["ramp"]["front"]["F"][:, 1].min() / r0["e_station"]), 1),
         int_de=f(100 * (1 - F[:, 1].min() / r0["e_station"]), 1))
rob = b["robust"]
N.update(rob_knee_max=f(max(r[2] for r in rob["knee"]), 0), rob_lean_max=f(max(r[2] for r in rob["lean"]), 0), rob_fast_max=f(max(r[2] for r in rob["fast"]), 0),
         rob_knee_b=f([r[2] for r in rob["knee"] if r[0] == 0.15 and r[1] == 1.0][0], 1))
rows = []
names = {"fast": "Shortest fill time", "knee": "Compromise", "lean": "Least electricity within the reference time"}
x0 = [18.5, 18.5, 0.5, 2.0, 2.0, -40.0, -40.0]
rows.append(("Reference", *[f(v, 1) if i != 2 else f(v, 2) for i, v in enumerate(x0)], f(r0["t"], 0), f(r0["e_station"], 2), f(r0["c_op"], 2), f(r0["T_hot"], 1), f(r0["T_bulk"], 1), f(r0["P_end"], 1)))
for k in ("fast", "knee", "lean"):
    p = pk[k]
    rows.append((names[k], *[f(v, 1) if i != 2 else f(v, 2) for i, v in enumerate(p["x"])], f(p["t"], 0), f(p["e_station"], 2), f(p["c_op"], 2), f(p["T_hot"], 1), f(p["T_bulk"], 1), f(p["P_end"], 1)))
N["tab_designs"] = table(["Design", "$r_1$", "$r_2$", "$\\xi_b$", "$\\Delta P_{1}$", "$\\Delta P_{2}$", "$T_{pc,a}$", "$T_{pc,b}$", "$t_f$, s", "$e_{st}$, kWh/kg", "$c_{op}$, \\$/kg", "$T_{hot}$, °C", "$T_{mix}$, °C", "$P_f$, MPa"], rows)
rows = []
for T in (0.0, 25.0, 40.0):
    if T not in opt:
        continue
    bb = opt[T]; rr = bb["ref"]; pp = bb["picks"]
    rows.append((f(T, 0), f(rr["t"], 0), f(rr["e_station"], 2), f(rr["T_hot"], 1), f(pp["fast"]["t"], 0), f(100 * (1 - pp["fast"]["t"] / rr["t"]), 0),
                 f(pp["lean"]["e_station"], 2), f(100 * (1 - pp["lean"]["e_station"] / rr["e_station"]), 1), f(100 * (1 - pp["lean"]["c_op"] / rr["c_op"]), 1)))
    N["amb%d_dt" % T] = f(100 * (1 - pp["fast"]["t"] / rr["t"]), 0)
    N["amb%d_de" % T] = f(100 * (1 - pp["lean"]["e_station"] / rr["e_station"]), 1)
N["tab_amb"] = table(["Ambient, °C", "Reference $t_f$, s", "Reference $e_{st}$, kWh/kg", "Reference $T_{hot}$, °C", "Shortest $t_f$, s", "Reduction, %",
                      "Least $e_{st}$ within reference time, kWh/kg", "Reduction, %", "Cost reduction, %"], rows)
# ---- sensitivity
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
order = np.argsort(-ST[:, jT])
N.update(sob_evals=str(sen["evaluations"]), sT_mean=f(sen["mean"][jT], 1), sT_lo=f(sen["p025"][jT], 1), sT_hi=f(sen["p975"][jT], 1), sT_sd=f(sen["std"][jT], 1),
         sD_lo=f(sen["p025"][jD], 1), sD_hi=f(sen["p975"][jD], 1), se_lo=f(sen["p025"][je], 2), se_hi=f(sen["p975"][je], 2),
         st_ric=f(ST[names_in.index("Ri_c"), jT], 2), st_beta=f(ST[names_in.index("beta"), jT], 2), st_in=f(ST[names_in.index("dT_in"), jT], 2),
         st_T0=f(ST[names_in.index("T0"), jT], 2), st_P0=f(ST[names_in.index("P0"), jT], 2), st_fh=f(max(ST[names_in.index("f_h"), jT], 0), 3),
         st_wall=f(max(ST[names_in.index("k_liner"), jT], 0) + max(ST[names_in.index("cp_liner"), jT], 0) + max(ST[names_in.index("k_cfrp"), jT], 0), 2),
         st_prop=f(max(ST[names_in.index("dZ"), jT], 0) + max(ST[names_in.index("dcv"), jT], 0), 2),
         st_eta_e=f(ST[names_in.index("eta_s"), je], 2), st_P0_t=f(min(ST[names_in.index("P0"), jt], 1.0), 2),
         st_mix_sum=f(ST[names_in.index("Ri_c"), jT] + ST[names_in.index("beta"), jT] + ST[names_in.index("phi"), jT], 2))
# ---- energy
st5 = ene["stages"][5]
N["tab_stages"] = table(["Stage", "Inlet pressure, MPa", "Outlet pressure, MPa", "Inlet temperature, °C", "Outlet temperature, °C", "Isentropic work, kWh/kg", "Gas-side work, kWh/kg", "Heat to cooler, kWh/kg"],
                        [(r["stage"], f(r["P_in"] / 1e6, 2), f(r["P_out"] / 1e6, 2), f(r["T_in"] - C0, 0), f(r["T_out"] - C0, 0), f(r["w_s"] / 3.6e6, 3), f(r["w"] / 3.6e6, 3), f(r["q_cool"] / 3.6e6, 3)) for r in st5]
                        + [("Sum", "", "", "", "", f(sum(r["w_s"] for r in st5) / 3.6e6, 3), f(sum(r["w"] for r in st5) / 3.6e6, 3), f(sum(r["q_cool"] for r in st5) / 3.6e6, 3))])
N["tab_nstage"] = table(["Number of stages", "Stage pressure ratio", "Highest discharge temperature, °C", "Gas-side work to 95 MPa, kWh/kg", "Electricity for the reference fill, kWh/kg"],
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
                        ("Fill continued to 95 % state of charge (reference fill of this paper)", f(a["e_comp"], 2), f(a["e_ref"], 2), f(a["e_station"], 2))])
N.update(iso=f(ene["isothermal"], 2), w2=f(sum(r["w"] for r in ene["stages"][2]) / 3.6e6, 2), w5=f(sum(r["w"] for r in st5) / 3.6e6, 2), T2=f(max(r["T_out"] for r in ene["stages"][2]) - C0, 0),
         T5=f(max(r["T_out"] for r in st5) - C0, 0), e_gas=f(a["e_comp_gas"], 2), e_cl=f(a["e_comp_class"], 2), e_eta60=f(ene["by_eta"][0.6]["e_comp"], 2), e_eta80=f(ene["by_eta"][0.8]["e_comp"], 2),
         e_sup20=f(ene["by_supply"][20.0]["e_comp"], 2), cap40=f(ene["util"][3, 2], 2), cap200=f(ene["util"][-1, 2], 2), cap5=f(ene["util"][0, 2], 1), kg40=f(ene["util"][3, 1], 0),
         sb40=f(ene["util"][3, 5], 2), esb40=f(ene["util"][3, 6], 2), sb5=f(ene["util"][0, 5], 2), cars_h=f(ene["capacity_cars_per_hour"], 1), P15=f(a["P15"], 0), Pc=f(a["P_comp_rated"], 0),
         e_in=f(a["e_in"], 1), e_out=f(a["e_out"], 1), cl_rt=f(100 * cl["round_trip"], 0), s70_ec=f(s70["e_comp"], 2), s70_er=f(s70["e_ref"], 2), s70_e=f(s70["e_station"], 2),
         cl_ec=f(cl["e_comp"], 2), cl_er=f(cl["e_chill"], 2), cl_e=f(cl["e_comp"] + cl["e_chill"], 2), s2_cl=f(s2["e_comp_class"], 2), s2_gas=f(s2["e_comp_gas"], 2),
         peak_ref=f(a["peak_ref_kW"], 0), fast_cars=f(3600 / (pk["fast"]["t"] + 120), 1))
json.dump({k: v for k, v in N.items() if not k.startswith("tab_")}, open(os.path.join(RES, "numbers.json"), "w"), indent=1, ensure_ascii=False)

body = open(os.path.join(HERE, "manuscript_template.md"), encoding="utf-8").read()
missing = set(re.findall(r"<<(\w+)>>", body)) - set(N)
assert not missing, missing
for k, v in N.items():
    body = body.replace("<<" + k + ">>", v)
# ---- numbered references in order of first citation
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
    # compress runs
    s, i = [], 0
    while i < len(out):
        j = i
        while j + 1 < len(out) and out[j + 1] == out[j] + 1:
            j += 1
        s.append(str(out[i]) if j == i else (f"{out[i]},{out[j]}" if j == i + 1 else f"{out[i]}-{out[j]}"))
        i = j + 1
    return "[" + ",".join(s) + "]"
body = body.replace("[A11;A13]", "[@a11;@a13]").replace("[A11]", "[@a11]").replace("[A13]", "[@a13]")
body = re.sub(r"\[((?:@[\w-]+;?\s*)+)\]", cite, body)
body += "\n\n# References\n\n" + "\n\n".join(f"[{i + 1}] {refs[k]}" for i, k in enumerate(order)) + "\n"
body = body.replace("FIGDIR", FIG)
assert "\u2014" not in body and "\u2013" not in body, "dash found"
md = os.path.join(HERE, "manuscript.md")
open(md, "w", encoding="utf-8").write(body)
out = os.path.join(HERE, "H2 Fast-Fill Lab manuscript.docx")
subprocess.run(["pandoc", md, "-o", out, "--from", "markdown+pipe_tables+tex_math_dollars+implicit_figures", "--reference-doc", os.path.join(HERE, "reference.docx")], check=True)
# ---- table and caption formatting
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
d = Document(out)
def border(el, edges):
    b = OxmlElement("w:tcBorders")
    for e, sz in edges:
        x = OxmlElement("w:" + e); x.set(qn("w:val"), "single"); x.set(qn("w:sz"), str(sz)); x.set(qn("w:color"), "000000"); b.append(x)
    el.get_or_add_tcPr().append(b)
for t in d.tables:
    tblPr = t._tbl.tblPr
    for old in tblPr.findall(qn("w:tblW")):
        tblPr.remove(old)
    w = OxmlElement("w:tblW"); w.set(qn("w:type"), "pct"); w.set(qn("w:w"), "5000"); tblPr.append(w)
    n = len(t.rows)
    ncol = len(t.columns)
    fs = 9 if ncol <= 9 else 7.5
    wts = []
    for j in range(ncol):
        longest = max(len(row.cells[j].text) for row in t.rows)
        wts.append(min(max(longest, 8), 40 if ncol <= 10 else (22 if j == 0 else 10)))
    tot = float(sum(wts))
    widths = [int(9360 * w / tot) for w in wts]
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblPr.append(lay)
    grid = t._tbl.tblGrid
    for j, gc in enumerate(grid.findall(qn("w:gridCol"))):
        gc.set(qn("w:w"), str(widths[j]))
    for row in t.rows:
        for j, c in enumerate(row.cells):
            tcPr = c._tc.get_or_add_tcPr()
            for old in tcPr.findall(qn("w:tcW")):
                tcPr.remove(old)
            tw = OxmlElement("w:tcW"); tw.set(qn("w:type"), "dxa"); tw.set(qn("w:w"), str(widths[j])); tcPr.insert(0, tw)
    for i, row in enumerate(t.rows):
        for c in row.cells:
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(1); p.paragraph_format.space_before = Pt(1); p.paragraph_format.line_spacing = 1.0
                for r in p.runs:
                    r.font.size = Pt(fs)
                    if i == 0:
                        r.font.bold = True
            edges = []
            if i == 0:
                edges += [("top", 8), ("bottom", 4)]
            if i == n - 1:
                edges += [("bottom", 8)]
            if edges:
                border(c._tc, edges)
        if i == 0:
            trPr = row._tr.get_or_add_trPr(); h = OxmlElement("w:tblHeader"); trPr.append(h)
for p in d.paragraphs:
    if p.style.name in ("Image Caption", "Captioned Figure"):
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if p.style.name == "Captioned Figure" else WD_ALIGN_PARAGRAPH.LEFT
    if p.text.startswith("Table ") and p.runs and p.runs[0].bold:
        p.paragraph_format.keep_with_next = True; p.paragraph_format.line_spacing = 1.15
        for r in p.runs:
            r.font.size = Pt(10)
d.core_properties.author = "Aarya Chiripal"; d.core_properties.last_modified_by = "Aarya Chiripal"
d.core_properties.title = "Integrated optimisation of precooling, cascade switching and pressure-ramp control for 70 MPa hydrogen refuelling with a two-zone real-gas tank model"
d.core_properties.comments = ""; d.core_properties.keywords = ""
d.save(out)
print("wrote", out, "references:", len(order), "unused:", sorted(set(refs) - set(order)))
