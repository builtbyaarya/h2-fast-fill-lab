"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, tests/test_physics.py

What this file does
    The physics checks for the fill model. Run with:  pytest -q

Where it fits in the model
    Each test is one of the validation items I promised in my proposal:
      1. empty insulated tank, ideal gas: T2 = k T_i
      2. mass leaving the banks equals mass entering the car
      3. energy balance closes within 0.1%
      4. results do not change when the time step is halved
      5. a 141 L tank at 700 bar and 15 degC holds about 5.7 kg (real gas)
    plus device checks: the throttle keeps enthalpy, the valve chokes, the
    precooler respects its capacity, the cycle's COP is physical and two
    compressor stages take less work than one.
"""

import math

import pytest

from h2lab.controller import ControllerSettings
from h2lab.devices import DispenserValve, Precooler, RefrigerationCycle, StationCompressor
from h2lab.properties import CP_H2, CV_H2, K_H2, R_H2, Hydrogen
from h2lab.simulation import BankSpec, FillConfig, FillSimulation
from h2lab.tanks import TransientTank


def _single_bank_cfg(**kw) -> FillConfig:
    cfg = FillConfig(
        banks=[BankSpec("Bank", 2.0, 90.0e6)],
        cascade=False,
        **kw,
    )
    return cfg


def test_table_a5_constants():
    # Borgnakke and Sonntag Table A.5, hydrogen: R = 4.1243, cp = 14.209, cv = 10.085, k = 1.409
    assert math.isclose(R_H2, 4124.3)
    assert math.isclose(CP_H2 - CV_H2, R_H2, rel_tol=1e-3)
    assert math.isclose(K_H2, 1.409, rel_tol=1e-3)


def test_empty_insulated_tank_gives_T2_equals_k_Ti():
    """
    Filling an evacuated, insulated rigid tank from a line at T_i:
    m2 u2 = m2 h_i, so cv T2 = cp T_i and T2 = k T_i (ideal gas).
    The tank cannot start truly empty numerically, so start at 0.1 bar and
    fill to 30 bar from a bank at 300 bar; the residual gas adds a small,
    predictable deviation that shrinks as the starting pressure drops.
    """
    T_i = 240.0  # k T_i = 338 K, below the 85 degC abort so the fill runs to its target
    cfg = _single_bank_cfg(property_mode="ideal", dt=0.05, t_max=2000.0)
    cfg.banks = [BankSpec("Bank", 50.0, 30.0e6)]  # huge bank so T_i stays constant
    cfg.T_amb = T_i
    cfg.car_P0_pa = 1.0e4
    cfg.car_insulated = True
    cfg.precooler.enabled = False
    cfg.controller = ControllerSettings(mode="manual", manual_opening=1.0, target_pressure_pa=3.0e6, target_soc=1e9)
    sim = FillSimulation(cfg)
    res = sim.run()
    T2 = sim.car.T
    assert res.end_reason == "Target pressure reached"
    assert math.isclose(T2, K_H2 * T_i, rel_tol=0.005), (T2, K_H2 * T_i)


def test_T2_k_Ti_closed_form_from_tank_class():
    """The same result straight from the energy equation with one Euler step of mass."""
    gas = Hydrogen("ideal")
    T_i = 300.0
    h_i = gas.h_PT(5.0e6, T_i)
    u2 = h_i  # m2 u2 = m_i h_i with m1 = 0
    assert math.isclose(u2 / CV_H2, K_H2 * T_i, rel_tol=1e-9)


@pytest.mark.parametrize("mode", ["ideal", "real"])
def test_mass_conservation(mode):
    cfg = FillConfig(property_mode=mode, dt=0.2)
    sim = FillSimulation(cfg)
    sim.run()
    eb = sim.energy_balance()
    assert eb["mass_error"] < 1e-9
    assert eb["mass_transfer_error"] < 1e-9


@pytest.mark.parametrize("mode", ["ideal", "real"])
def test_energy_balance_closes(mode):
    cfg = FillConfig(property_mode=mode, dt=0.2)
    sim = FillSimulation(cfg)
    sim.run()
    eb = sim.energy_balance()
    assert eb["closure_error"] < 1e-3, eb
    assert eb["chain_error"] < 1e-3, eb
    # the car gas lost heat to its wall, so the enthalpy delivered exceeds dU
    assert eb["H_in_car"] > eb["dU_car"]


@pytest.mark.parametrize("mode", ["ideal", "real"])
def test_time_step_independence(mode):
    """Halving dt must leave the peak temperature and final mass essentially unchanged."""
    r1 = FillSimulation(FillConfig(property_mode=mode, dt=0.2)).run()
    r2 = FillSimulation(FillConfig(property_mode=mode, dt=0.1)).run()
    assert math.isclose(r1.T_peak, r2.T_peak, abs_tol=0.2), (r1.T_peak, r2.T_peak)
    assert math.isclose(r1.m_added, r2.m_added, rel_tol=2e-3)
    assert math.isclose(r1.fill_time, r2.fill_time, rel_tol=1e-2)


def test_141L_tank_holds_5p7kg_real_gas():
    gas = Hydrogen("real")
    m = gas.rho_PT(70.0e6, 288.15) * 0.141
    assert math.isclose(m, 5.7, rel_tol=0.01), m
    # the ideal gas law overpredicts by about 50% (Z = 1.5)
    m_ideal = Hydrogen("ideal").rho_PT(70.0e6, 288.15) * 0.141
    assert m_ideal / m > 1.4


def test_throttle_is_isenthalpic_and_hydrogen_warms_in_real_mode():
    gas_r, gas_i = Hydrogen("real"), Hydrogen("ideal")
    T_in = 293.15
    T_out_real = DispenserValve.exit_temperature(gas_r, 90.0e6, T_in, 8.0e6)
    T_out_ideal = DispenserValve.exit_temperature(gas_i, 90.0e6, T_in, 8.0e6)
    assert math.isclose(T_out_ideal, T_in)
    assert 20.0 < T_out_real - T_in < 60.0  # negative Joule-Thomson coefficient
    assert math.isclose(gas_r.h_PT(8.0e6, T_out_real), gas_r.h_PT(90.0e6, T_in), rel_tol=1e-7)


def test_valve_flow_is_choked_and_scales_with_opening():
    gas = Hydrogen("real")
    v = DispenserValve(opening=1.0)
    full = v.mass_flow(gas, 80.0e6, 300.0, 10.0e6)
    v.opening = 0.5
    half = v.mass_flow(gas, 80.0e6, 300.0, 10.0e6)
    assert math.isclose(half, 0.5 * full)
    # choked: lowering the downstream pressure further changes nothing
    v.opening = 1.0
    assert math.isclose(v.mass_flow(gas, 80.0e6, 300.0, 5.0e6), full)
    assert 0.03 < full < 0.12  # the right order of magnitude for a dispenser


def test_precooler_energy_and_capacity_limit():
    gas = Hydrogen("ideal")
    pc = Precooler(T_set=233.15, Q_max=1.0e9)
    T_out, Q, h_in, h_out = pc.outlet(gas, 50.0e6, 300.0, 0.05)
    assert math.isclose(T_out, 233.15)
    assert math.isclose(Q, 0.05 * CP_H2 * (300.0 - 233.15), rel_tol=1e-9)
    pc_small = Precooler(T_set=233.15, Q_max=10.0e3)
    T_out2, Q2, *_ = pc_small.outlet(gas, 50.0e6, 300.0, 0.05)
    assert math.isclose(Q2, 10.0e3) and T_out2 > 233.15


def test_refrigeration_cycle_cop_is_physical():
    cyc = RefrigerationCycle(refrigerant="R134a", T_evap=225.15, T_cond=313.15, eta_s=0.75)
    out = cyc.solve(50.0e3)
    carnot = 225.15 / (313.15 - 225.15)
    assert 0.5 < out["COP"] < carnot
    assert math.isclose(out["Q_L"] + out["W_comp"], out["Q_H"], rel_tol=1e-9)  # cycle energy balance
    assert out["h4"] == out["h3"]


def test_compressor_two_stage_less_work_than_one():
    gas = Hydrogen("real")
    comp = StationCompressor(eta_s=1.0)
    two = comp.compress(gas, 5.0e6, 300.0, 90.0e6, 298.15)
    one_stage = gas.h_from_T_P_isentropic(5.0e6, 300.0, 90.0e6) - gas.h_PT(5.0e6, 300.0)
    assert two["w"] < one_stage
    assert two["w"] > 0


def test_cascade_switches_upward_and_drains_low_bank_first():
    cfg = FillConfig(property_mode="ideal", dt=0.2)
    sim = FillSimulation(cfg)
    sim.run()
    names = [e[1] for e in sim.rec.events if e[1].startswith("Switched")]
    assert names[:2] == ["Switched to Medium bank", "Switched to High bank"] or names[:1] == ["Switched to Medium bank"]
    assert sim.banks[0].m_out_cum > 0


def test_abort_at_85C_without_precooling_on_hot_day():
    cfg = FillConfig(property_mode="real", dt=0.2, T_amb=273.15 + 40.0)
    cfg.precooler.enabled = False
    cfg.controller = ControllerSettings(mode="manual", manual_opening=1.0)
    res = FillSimulation(cfg).run()
    assert res.aborted and "85 degC" in res.end_reason
    assert res.T_peak >= 273.15 + 85.0 - 0.5
