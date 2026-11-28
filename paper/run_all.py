"""
Runs every calculation reported in the manuscript and writes the results to paper/results/.
Usage:  python paper/run_all.py [part ...]     parts: numerics validation reference maps optimise sensitivity energy
"""
import json, os, pickle, sys, time
from dataclasses import replace
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from h2lab.research import jrc, optimize as op, uq
from h2lab.research.props import perturbed
from h2lab.research.station import CompressorSpec, Economics, account, stage_table, isothermal_ideal, KWH, crf, LHV
from h2lab.research.twozone import Closure, Control, Fill, Station, Tank, Wall, table

C0 = 273.15
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)


def save(name, obj):
    with open(os.path.join(OUT, name + ".pkl"), "wb") as f:
        pickle.dump(obj, f)
    print("saved", name, flush=True)


def summ(o, a=None):
    d = dict(t=o.t_fill, m=o.m_added, T_hot=o.T_hot - C0, Tu=o.Tu_max - C0, Tl=o.Tl_max - C0, T_bulk=o.Tbulk_max - C0,
             P_end=o.P_end / 1e6, P_max=o.P_max / 1e6, soc=o.soc, E_cool=o.E_cool / KWH, E_ref=o.E_ref / KWH,
             Qpc_max=o.Qpc_max / 1e3, mdot_max=o.mdot_max * 1e3, reason=o.reason, T_del=o.T_del_mean - C0,
             bank_used=o.bank_used.tolist(), clos_gas=o.closure_gas, clos_wall=o.closure_wall,
             dT_end=o.Tu_end - o.Tl_end, Ts_max=o.Ts_max - C0)
    if a:
        d.update({k: (float(v) if not isinstance(v, list) else v) for k, v in a.items()})
    return d


def base_fill(T_amb_C=25.0, **kw):
    return Fill(T_amb=C0 + T_amb_C, **kw)


# ---------------------------------------------------------------------------------------------------------
def numerics():
    res = dict(dt=[], nodes=[], table=None)
    for dt in (0.2, 0.1, 0.05, 0.025, 0.0125, 0.00625):
        o = base_fill(dt=dt).run()
        res["dt"].append((dt, o.t_fill, o.T_hot - C0, o.Tbulk_max - C0, o.m_added, o.E_cool / KWH, o.closure_gas, o.closure_wall))
    for nl, nc in ((2, 3), (4, 5), (6, 8), (8, 10), (12, 16)):
        o = base_fill(dt=0.0125, tank=Tank(wall=Wall(n_liner=nl, n_cfrp=nc))).run()
        res["nodes"].append((len(Wall(n_liner=nl, n_cfrp=nc).grid(0.0125)[0]), o.T_hot - C0, o.Ts_max - C0))
    import CoolProp.CoolProp as CP
    from h2lab.research import props as pr
    rng = np.random.default_rng(0)
    tab = table()
    eP, eT = [], []
    for _ in range(2000):
        T, P = rng.uniform(200, 500), rng.uniform(1e6, 95e6)
        rho = CP.PropsSI("D", "P", P, "T", T, "Hydrogen")
        u = CP.PropsSI("U", "P", P, "T", T, "Hydrogen")
        eP.append(pr.P_rhoT(tab, rho, T) / P - 1)
        eT.append(pr.T_rhou(tab, rho, u, 300.0) - T)
    res["table"] = (float(np.abs(eP).max()), float(np.abs(eT).max()))
    t0 = time.time()
    for _ in range(50):
        base_fill().run()
    res["ms_per_fill"] = (time.time() - t0) / 50 * 1e3
    save("numerics", res)


# ---------------------------------------------------------------------------------------------------------
def validation():
    res = {}
    res["cal_boss"] = jrc.calibrate_boss(areas=[0.0, 0.004, 0.008, 0.010, 0.011, 0.012, 0.013, 0.014, 0.016, 0.02, 0.03])
    res["cal_beta"] = jrc.calibrate_beta(betas=(0.05, 0.1, 0.15, 0.2, 0.3, 0.35, 0.5, 1.0))
    hist = {}
    for key, case in (("amb", jrc.FIG11_AMBIENT), ("pre", jrc.FIG11_PRECOOLED), ("fig5", jrc.FIG5)):
        o = jrc.run_history(case)
        m = jrc.history_errors(case, o)
        o0 = jrc.run_history(case, tank=jrc.tank_29L(boss_area=0.0))
        m0 = jrc.history_errors(case, o0)
        mu = jrc.history_errors(case, o, "T_u")
        hist[key] = dict(case={k: v for k, v in case.items()}, s={k: o.s[k] for k in ("t", "P", "T_u", "T_l", "T_bulk", "mdot")},
                         m=m, m_noboss=m0, m_upper=mu, s0=dict(t=o0.s["t"], T_bulk=o0.s["T_bulk"]), t_fill=o.t_fill,
                         dT_end=o.Tu_end - o.Tl_end, mdot_max=o.mdot_max)
    # the configuration of the brief: inlet flow delivered to the upper zone (chi = 1)
    oc = jrc.run_history(jrc.FIG5, closure=Closure(beta=jrc.BETA_FIT, chi=1.0))
    hist["fig5"]["chi1"] = dict(Tu_end=oc.Tu_end - C0, Tl_end=oc.Tl_end - C0)
    o5 = jrc.run_history(jrc.FIG5)
    hist["fig5"]["chi0"] = dict(Tu_end=o5.Tu_end - C0, Tl_end=o5.Tl_end - C0)
    res["hist"] = hist
    o = jrc.run_repeat()
    o0 = jrc.run_repeat(tank=jrc.tank_29L(boss_area=0.0))
    res["repeat"] = dict(T_end=0.5 * (o.Tu_end + o.Tl_end) - C0, Tu_end=o.Tu_end - C0, t=o.t_fill, T_end_noboss=0.5 * (o0.Tu_end + o0.Tl_end) - C0,
                         meas=jrc.REPEAT_29L)
    o = jrc.run_cycles_19L()
    res["cyc19"] = dict(T_end=0.5 * (o.Tu_end + o.Tl_end) - C0, boss=o.T_boss_max - C0, t=o.t_fill, meas=jrc.CYCLES_19L)
    p, m = jrc.run_table8()
    res["table8"] = dict(pred=p, meas=m, m=jrc.metrics(p[:, 0], m), rows=jrc.TABLE8)
    for prof in ("two-stage", "linear"):
        v = jrc.table_validation(profile=prof)
        res["tab_" + prof] = v
        groups = {"full fills to 72 MPa": [i for i, r in enumerate(v["rows"]) if r[2] > 70],
                  "from 15 MPa to 69 MPa": [i for i, r in enumerate(v["rows"]) if 14 < r[1] < 16],
                  "to 30 MPa": [i for i, r in enumerate(v["rows"]) if r[2] < 31]}
        v["groups"] = {g: jrc.metrics(np.array(v["Tu"])[ix], np.array([v["rows"][i][5] for i in ix])) for g, ix in groups.items()}
    vcal = jrc.table_validation(jrc.CAL_ROWS)
    vval = jrc.table_validation([r for r in jrc.table_rows() if r not in jrc.CAL_ROWS])
    res["tab_cal"], res["tab_val"] = vcal, vval
    res["tab_noboss"] = jrc.table_validation(tank=jrc.tank_29L(boss_area=0.0))
    # Monte Carlo band for the repeatability fill and the ambient history
    rng = np.random.default_rng(3)
    N = 300
    tg = np.linspace(0, 256, 129)
    band, Tend = [], []
    case = jrc.FIG11_AMBIENT
    for _ in range(N):
        liner = rng.uniform(0.003, 0.006)
        tk = jrc.tank_29L(boss_area=jrc.BOSS_AREA_FIT * rng.uniform(0.5, 1.5), liner=liner)
        tk = replace(tk, wall=replace(tk.wall, k_liner=rng.uniform(0.385, 0.50), cp_liner=rng.uniform(1580, 2300), k_cfrp=rng.uniform(0.5, 1.0)))
        clo = Closure(beta=rng.uniform(0.15, 1.0), Ri_c=float(np.exp(rng.uniform(np.log(0.1), np.log(10)))), f_h=rng.uniform(0.5, 2.0))
        f = jrc.rig_fill(tk, case["P0"] + rng.normal(0, 0.36e6) * 0.5, case["Pf"], case["T0"] + rng.normal(0, 2.0), case["r1"], case["r2"],
                         case["P_break"], T_in=jrc.T_INLET + rng.uniform(-5, 5), closure=clo, T_amb=jrc.T_AMB + rng.uniform(-5, 5))
        f.P0 = max(f.P0, 1.0e6)
        o = f.run(perturbed(table(), rng.uniform(-0.001, 0.001), rng.uniform(-0.01, 0.01)))
        band.append(np.interp(tg, o.s["t"], o.s["T_bulk"]) - C0)
        Tend.append(0.5 * (o.Tu_end + o.Tl_end) - C0)
    band = np.array(band)
    res["mc"] = dict(t=tg, p025=np.percentile(band, 2.5, axis=0), p50=np.percentile(band, 50, axis=0), p975=np.percentile(band, 97.5, axis=0),
                     Tend=np.array(Tend), N=N)
    # class model on the same repeatability fill (lumped gas, lumped wall)
    from h2lab.validation import jrc_comparison
    jc = jrc_comparison((80.0, 200.0))
    res["class"] = {h: float(r.series["T_car"][-1] - C0) for h, r in jc["runs"].items()}
    save("validation", res)


# ---------------------------------------------------------------------------------------------------------
def reference():
    res = {}
    f = base_fill(store_every=0.5)
    o = f.run()
    res["ref"] = dict(summ(o, account(o)), s=o.s)
    o1 = replace(f, closure=Closure(beta=50.0)).run()
    res["onezone"] = dict(summ(o1, account(o1)), s=o1.s)
    for T in (0.0, 40.0):
        ox = base_fill(T).run()
        res["ref_%d" % T] = summ(ox, account(ox))
    # class model (lumped gas and wall, stop at 70 MPa) and the research model with the same stop rule
    from h2lab.simulation import FillConfig, FillSimulation
    from h2lab import chain
    r = FillSimulation(FillConfig()).run()
    pk = chain.per_kilogram(r, chain.ChainInputs())
    res["class"] = dict(t=r.fill_time, m=r.m_added, T_peak=r.T_peak - C0, P=r.P_final / 1e6, soc=r.soc_final, E_cool=r.E_cool / KWH,
                        E_ref=r.E_comp_ref / KWH, e_comp=pk["e_comp"], e_chill=pk["e_chill"], round_trip=pk["round_trip"],
                        shares=pk["shares"], t_series=r.series["t"], T_series=r.series["T_car"], cost=pk["cost"])
    o70 = replace(f, control=Control(soc_target=1e9, P_stop=69.8e6)).run()
    res["stop70"] = dict(summ(o70, account(o70)), s=o70.s)
    res["stop70_2stage"] = account(o70, CompressorSpec(stages=2))
    save("reference", res)


# ---------------------------------------------------------------------------------------------------------
def maps():
    res = {}
    rr = np.linspace(5, 40, 15)
    tp = np.linspace(-40, 0, 11)
    for T in (0.0, 25.0, 40.0):
        base = base_fill(T)
        Z = np.zeros((len(tp), len(rr), 6))
        Z0 = np.zeros((len(rr), 2))
        for j, r in enumerate(rr):
            o0 = replace(base, control=replace(base.control, r1=r, r2=r, precool=False)).run()
            Z0[j] = (o0.T_hot - C0, o0.soc)
            for i, t in enumerate(tp):
                o = replace(base, control=replace(base.control, r1=r, r2=r, Tpc_a=C0 + t, Tpc_b=C0 + t)).run()
                a = account(o)
                Z[i, j] = (o.T_hot - C0, o.t_fill, a["e_station"], o.soc, o.T_hot - o.Tbulk_max, a["e_ref"])
        res[T] = dict(r=rr, tp=tp, Z=Z, Z0=Z0)
    save("maps", res)


# ---------------------------------------------------------------------------------------------------------
def pick(front, base, t_ref, e_ref):
    """Representative designs of a front: fastest, least energy within the reference time, and compromise."""
    F, X = front["F"], front["X"]
    out = {}
    i = int(np.argmin(F[:, 0]))
    ok = F[:, 0] <= t_ref + 1e-9
    j = int(np.argmin(np.where(ok, F[:, 1], np.inf))) if ok.any() else int(np.argmin(F[:, 1]))
    k = op.knee(F)
    ok10 = F[:, 0] <= 1.10 * t_ref          # least electricity at a fill time up to 10 % above the reference
    j10 = int(np.argmin(np.where(ok10, F[:, 1], np.inf))) if ok10.any() else j
    for name, ix in (("fast", i), ("lean", j), ("knee", k), ("lean10", j10)):
        f, g, o, a = op.evaluate(X[ix], base, full=True)
        out[name] = dict(x=X[ix].tolist(), **summ(o, a))
    return out


def optimise():
    res = {}
    for T, pop, gens in ((25.0, 120, 100), (0.0, 96, 60), (40.0, 96, 60)):
        base = base_fill(T)
        fr, gr, o, a = op.evaluate(op.REFERENCE, base, full=True)
        t0 = time.time()
        full = op.nsga2(base, pop=pop, gens=gens, seed=11, log=lambda h: print(T, h, flush=True))
        block = dict(ref=summ(o, a), ref_g=gr.tolist(), front=full, wall_s=time.time() - t0)
        block["picks"] = pick(full, base, fr[0], fr[1])
        if T == 25.0:
            subsets = {"precooling": {0: 18.5, 1: 18.5, 2: 0.5, 3: 2.0, 4: 2.0},
                       "cascade": {0: 18.5, 1: 18.5, 2: 0.5, 5: -40.0, 6: -40.0},
                       "ramp": {3: 2.0, 4: 2.0, 5: -40.0, 6: -40.0}}
            block["subsets"] = {}
            for name, fixed in subsets.items():
                s = op.nsga2(base, pop=64, gens=50, seed=5, fixed=fixed)
                block["subsets"][name] = dict(front=s, picks=pick(s, base, fr[0], fr[1]))
                print("subset", name, len(s["F"]), flush=True)
            # second seed, to check that the front is reproduced
            full2 = op.nsga2(base, pop=pop, gens=gens, seed=23)
            block["front_seed2"] = full2
            # sensitivity of the selected designs to the closure parameters
            rob = {}
            for name in ("fast", "lean", "knee"):
                x = block["picks"][name]["x"]
                rows = []
                for b in (0.15, 0.35, 1.0):
                    for ric in (0.1, 1.0, 10.0):
                        oo = op.apply(replace(base, closure=Closure(beta=b, Ri_c=ric)), x).run()
                        rows.append((b, ric, oo.T_hot - C0, oo.Tbulk_max - C0, oo.t_fill, oo.soc))
                rob[name] = rows
            block["robust"] = rob
            # histories of reference and selected designs
            block["hist"] = {}
            for name in ("fast", "lean", "knee"):
                oo = op.apply(replace(base, store_every=0.5), block["picks"][name]["x"]).run()
                block["hist"][name] = oo.s
        res[T] = block
        save("optimise", res)


# ---------------------------------------------------------------------------------------------------------
def sensitivity():
    base = base_fill()
    t0 = time.time()
    s = uq.sobol(base, N=512, seed=7)
    s["wall_s"] = time.time() - t0
    mid, fm, rows = uq.one_at_a_time(base)
    s["oat"] = dict(mid=mid, f_mid=fm, rows=rows)
    s["inputs"] = uq.INPUTS
    s["outputs"] = uq.OUTPUTS
    # convergence of the indices with sample size
    s2 = uq.sobol(base, N=256, seed=19)
    s["ST_N256"] = s2["ST"]
    save("sensitivity", s)


# ---------------------------------------------------------------------------------------------------------
def energy():
    res = {}
    spec = CompressorSpec()
    res["stages"] = {n: stage_table(replace(spec, stages=n), 95.0e6, C0 + 25.0) for n in (2, 3, 4, 5, 6)}
    res["isothermal"] = isothermal_ideal(2e6, 95e6, C0 + 25) / KWH
    f = base_fill()
    o = f.run()
    res["ref"] = account(o, spec)
    res["ref_m"] = o.m_added
    res["ref_t"] = o.t_fill
    res["by_stages"] = {n: account(o, replace(spec, stages=n)) for n in (2, 3, 4, 5, 6)}
    res["by_eta"] = {e: account(o, replace(spec, eta_s=e)) for e in (0.6, 0.65, 0.7, 0.75, 0.8)}
    res["by_supply"] = {p: account(o, replace(spec, P_supply=p * 1e6)) for p in (2.0, 3.0, 20.0)}
    # utilisation: cost per kg against cars per day
    eco = Economics()
    cars = np.array([5, 10, 20, 40, 60, 80, 120, 160, 200.0])
    standby_kW = 1.5      # assumed continuous electric power to keep the precooler cold between fills
    rows = []
    for c in cars:
        a = account(o, spec, replace(eco, cars_per_day=float(c)))
        kg_day = c * o.m_added
        e_standby = standby_kW * 24.0 / kg_day
        rows.append((c, kg_day, a["c_cap"], a["c_energy"], a["c_demand"], eco.price_energy * e_standby, e_standby, a["e_station"]))
    res["util"] = np.array(rows)
    res["capacity_cars_per_hour"] = 3600.0 / (o.t_fill + eco.t_idle)
    res["eco"] = eco.__dict__
    res["spec"] = spec.__dict__
    save("energy", res)


if __name__ == "__main__":
    parts = sys.argv[1:] or ["numerics", "validation", "reference", "maps", "optimise", "sensitivity", "energy"]
    for p in parts:
        t0 = time.time()
        globals()[p]()
        print(p, "done in %.0f s" % (time.time() - t0), flush=True)
