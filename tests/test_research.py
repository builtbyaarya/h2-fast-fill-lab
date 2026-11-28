"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, tests/test_research.py

Checks on the research model (h2lab/research): the property table against
CoolProp, conservation of mass and energy in the two-zone tank, the limit in
which two zones behave as one, the time-step study, the compressor
accounting and the optimiser.

Run with:  pytest -q tests/test_research.py
"""

from dataclasses import replace

import numpy as np
import pytest

from h2lab.research import jrc, optimize as op, props
from h2lab.research.station import CompressorSpec, account, isothermal_ideal, stage_table, KWH
from h2lab.research.twozone import Closure, Control, Fill, Station, Tank, table

C0 = 273.15


def test_table_reproduces_coolprop():
    import CoolProp.CoolProp as CP
    tab = table()
    rng = np.random.default_rng(1)
    for _ in range(200):
        T, P = rng.uniform(200, 500), rng.uniform(1e6, 95e6)
        rho = CP.PropsSI("D", "P", P, "T", T, "Hydrogen")
        u = CP.PropsSI("U", "P", P, "T", T, "Hydrogen")
        assert abs(props.P_rhoT(tab, rho, T) / P - 1) < 2e-4
        assert abs(props.T_rhou(tab, rho, u, 300.0) - T) < 0.01
        assert abs(props.rho_PT(tab, P, T) / rho - 1) < 2e-4


def test_mass_and_energy_are_conserved():
    o = Fill().run()
    assert o.complete
    assert o.closure_gas < 1e-9 and o.closure_wall < 1e-9
    assert abs(o.bank_used.sum() - o.m_added) / o.m_added < 1e-9


def test_strong_mixing_recovers_one_zone():
    o = Fill(closure=Closure(beta=50.0)).run()
    assert o.T_hot - o.Tbulk_max < 0.3


def test_weak_mixing_makes_upper_zone_hotter():
    a, b = Fill(closure=Closure(beta=0.35)).run(), Fill(closure=Closure(beta=0.05)).run()
    assert b.Tu_max > a.Tu_max > a.Tl_max - 0.5
    assert b.T_hot - b.Tbulk_max > a.T_hot - a.Tbulk_max


def test_adiabatic_ideal_limit_T2_equals_k_Ti():
    """Empty insulated tank filled from a constant supply: at low pressure hydrogen is an ideal gas and T2 -> k Ti."""
    Ti = 300.0
    tank = Tank(volume=0.05, d_inj=0.005)
    tank = replace(tank, wall=replace(tank.wall, k_liner=1e-9, h_out=1e-9))
    f = Fill(tank=tank, closure=Closure(beta=50.0, f_h=1e-9), T_amb=Ti, P0=2.0e4, T0=Ti,
             control=Control(precool=False, Kp=-1.0, r1=6.0, r2=6.0, flow_limit=1.0, P_cap=2.0e6, soc_target=1e9, P_stop=1.98e6, t_max=600.0),
             station=Station(bank_V=(50.0,), bank_P=(20.0e6,), inlet_T=Ti), dt=0.02)
    o = f.run()
    import CoolProp.CoolProp as CP
    k = CP.PropsSI("C", "P", 1.0e6, "T", 360.0, "Hydrogen") / CP.PropsSI("O", "P", 1.0e6, "T", 360.0, "Hydrogen")
    assert abs(o.Tu_end / (k * Ti) - 1) < 0.02


def test_time_step_convergence():
    a, b = Fill(dt=0.05).run(), Fill(dt=0.0125).run()
    assert abs(a.T_hot - b.T_hot) < 0.1 and abs(a.m_added - b.m_added) / b.m_added < 1e-3


def test_compressor_work_bounds():
    spec = CompressorSpec()
    w = sum(r["w"] for r in stage_table(spec, 95e6, 298.15))
    assert w > isothermal_ideal(2e6, 95e6, 298.15)                      # no compressor beats the isothermal minimum
    w2 = sum(r["w"] for r in stage_table(replace(spec, stages=2), 95e6, 298.15))
    assert w2 > w                                                        # more intercooled stages need less work
    a = account(Fill().run(), spec)
    assert a["e_comp_gas"] <= a["e_comp_class"] + 1e-9                   # refill path costs no more than the class accounting
    assert abs(a["e_comp"] - a["e_comp_gas"] / (spec.eta_mech * spec.eta_motor)) < 1e-9
    assert abs(a["e_station"] - a["e_comp"] - a["e_ref"]) < 1e-12


def test_jrc_repeatability_fill_within_stated_error():
    o = jrc.run_repeat()
    T_end = 0.5 * (o.Tu_end + o.Tl_end) - C0
    assert abs(o.t_fill - jrc.REPEAT_29L["t"]) < 2.0
    assert abs(T_end - jrc.REPEAT_29L["Tf"]) < 8.0        # the manuscript reports +5.5 K for this fill (86.9 degC measured)


def test_reference_design_is_feasible_and_optimiser_improves_it():
    base = Fill()
    f, g = op.evaluate(op.REFERENCE, base)
    assert np.all(g <= 0)
    r = op.nsga2(base, pop=24, gens=6, seed=3)
    assert len(r["F"]) >= 3 and np.all(r["G"] <= 1e-9)
    assert r["F"][:, 0].min() < f[0]
