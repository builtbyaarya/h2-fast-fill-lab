"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, h2lab/simulation.py

What this file does
    Runs one fill. It joins the transient banks, the valve, the precooler and
    the car's tank, and steps them forward in time until the fill completes or
    a limit stops it.

Where it fits in the model
    This is the centre. tanks.py gives the rate equations, devices.py gives the
    steady-flow relations, controller.py gives the valve opening, and this file
    puts them in order inside each time step and keeps the record that every
    chart, check and cost downstream is read from.

One time step, in order
    1. Cascade: pick the lowest bank that can still push gas into the car.
    2. Controller: get the valve opening for this step.
    3. Steady-flow chain, solved algebraically (the hose volume is tiny next
       to the tanks, so I treat the flow as quasi-steady within a step):
       mass flow through the valve, throttling h_e = h_i down to the car's
       pressure, then the precooler.
    4. Rate equations of the car and the active bank (mass balance and first
       law for a transient control volume) at that flow.
    5. Advance (m, U, T_wall) of both tanks.
    6. Add up the heat removed by the precooler and the work of its
       refrigeration compressor, W = Q / COP.
    7. Check the limits at the new state.

Numerical method
    The explicit midpoint method (second-order Runge-Kutta):

        k1 = f(y_n)
        k2 = f(y_n + dt/2 k1)
        y_{n+1} = y_n + dt k2

    so steps 3 and 4 are done twice per step, once at the start and once at
    the midpoint, and step 5 uses the midpoint rates. Halving the time step
    changes the answers by a quantity of order dt^2, which a test checks.

Cascade
    Real stations store hydrogen in low, medium and high pressure banks and
    draw from the lowest one that still works, because only the last part of
    the fill needs high-pressure gas and that saves compressor work. I switch
    up a bank when the pressure difference across the valve falls below a
    margin the user sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List

import numpy as np

from .controller import ControllerSettings, Dispenser, check_limits
from .devices import DispenserValve, Precooler, RefrigerationCycle, StationCompressor
from .properties import Hydrogen
from .tanks import TransientTank, WallModel


@dataclass
class BankSpec:
    """One storage bank as the user describes it: a name, a volume and a starting pressure."""

    name: str
    volume_m3: float
    pressure_pa: float


@dataclass
class FillConfig:
    """Everything the user can set for one fill. SI inside, converted at the interface."""

    property_mode: str = "real"
    dt: float = 0.1  # s
    t_max: float = 600.0  # s
    T_amb: float = 273.15 + 25.0
    # vehicle tank: a 141 L Type IV system (5.7 kg at 70 MPa, 15 degC)
    car_volume_m3: float = 0.141
    car_P0_pa: float = 5.0e6
    car_T0: float | None = None  # None means ambient
    car_wall: WallModel = field(default_factory=WallModel)
    car_insulated: bool = False
    # station banks (low to high). Volumes and pressures are typical of a
    # 70 MPa cascade station and are design choices, not standard values.
    banks: List[BankSpec] = field(
        default_factory=lambda: [
            BankSpec("Low bank", 1.0, 35.0e6),
            BankSpec("Medium bank", 1.0, 60.0e6),
            BankSpec("High bank", 0.5, 95.0e6),
        ]
    )
    bank_T0: float | None = None
    banks_insulated: bool = True
    cascade: bool = True
    switch_margin_pa: float = 2.0e6  # switch to the next bank when P_bank - P_car < this
    # devices
    valve: DispenserValve = field(default_factory=DispenserValve)
    precooler: Precooler = field(default_factory=Precooler)
    refrigeration: RefrigerationCycle = field(default_factory=RefrigerationCycle)
    compressor: StationCompressor = field(default_factory=StationCompressor)
    controller: ControllerSettings = field(default_factory=ControllerSettings)
    # the gas leaving the bank runs through pipework at ambient before the valve
    bank_outlet_at_ambient: bool = False
    enforce_limits: bool = True  # validation runs against experiments switch the abort off

    def to_dict(self) -> dict:
        return asdict(self)


class Recorder:
    """Time series storage, one list per quantity, converted to arrays on demand."""

    FIELDS = (
        "t", "P_car", "T_car", "T_wall", "m_car", "soc", "m_dot", "opening", "P_target",
        "error", "P_bank", "T_bank", "bank_idx", "T_valve_out", "T_delivery", "Q_precool",
        "Q_wall", "W_ref", "COP", "H_flow", "E_cool_cum", "E_comp_ref_cum",
    )

    def __init__(self):
        self.data = {k: [] for k in self.FIELDS}
        self.events: list[tuple[float, str]] = []

    def add(self, **kw):
        for k in self.FIELDS:
            self.data[k].append(kw.get(k, np.nan))

    def arrays(self) -> dict:
        return {k: np.asarray(v, dtype=float) for k, v in self.data.items()}

    def __len__(self):
        return len(self.data["t"])


class FillSimulation:
    """One vehicle fill. Call step() repeatedly or run() to the end."""

    def __init__(self, cfg: FillConfig):
        # I build the station from the configuration: one property model shared by everything, the car's tank and
        # the banks as transient control volumes starting at ambient temperature, then the steady-flow devices.
        self.cfg = cfg
        self.gas = Hydrogen(cfg.property_mode)
        T0 = cfg.T_amb if cfg.car_T0 is None else cfg.car_T0
        self.car = TransientTank.from_PT(
            "Vehicle tank", cfg.car_volume_m3, self.gas, cfg.car_P0_pa, T0, cfg.T_amb,
            wall=cfg.car_wall, insulated=cfg.car_insulated,
        )
        Tb = cfg.T_amb if cfg.bank_T0 is None else cfg.bank_T0
        self.banks = [
            TransientTank.from_PT(b.name, b.volume_m3, self.gas, b.pressure_pa, Tb, cfg.T_amb,
                                  insulated=cfg.banks_insulated)
            for b in cfg.banks
        ]
        self.valve = DispenserValve(area=cfg.valve.area, Cd=cfg.valve.Cd)
        self.precooler = cfg.precooler
        self.refrigeration = cfg.refrigeration
        self.dispenser = Dispenser(cfg.controller)
        self.t = 0.0
        self.bank_idx = 0 if cfg.cascade else len(self.banks) - 1
        self.P_start = self.car.P
        self.rec = Recorder()
        self.finished = False
        self.aborted = False
        self.end_reason = ""
        self.warnings_seen: dict[str, float] = {}
        self.E_cool = 0.0  # J removed by the precooler
        self.E_comp_ref = 0.0  # J of refrigeration compressor work
        self.ref_cache = None
        self.initial_energy = self.total_internal_energy()
        self.initial_mass = self.total_mass()
        self.U0_car = self.car.U
        self.U0_banks = sum(b.U for b in self.banks)
        self._record(0.0, 0.0, self.car.T, self.car.T, 0.0, 0.0, {"COP": np.nan, "W_comp": 0.0})

    # ---- helpers -------------------------------------------------------------

    def total_internal_energy(self) -> float:
        return self.car.U + sum(b.U for b in self.banks)

    def total_mass(self) -> float:
        return self.car.m + sum(b.m for b in self.banks)

    @property
    def bank(self) -> TransientTank:
        return self.banks[self.bank_idx]

    def _select_bank(self, P_car: float) -> None:
        """Cascade logic: move up while the active bank cannot keep the margin."""
        if not self.cfg.cascade:
            return
        while (self.bank_idx < len(self.banks) - 1
               and self.banks[self.bank_idx].P - P_car < self.cfg.switch_margin_pa):
            self.bank_idx += 1
            self.rec.events.append((self.t, f"Switched to {self.banks[self.bank_idx].name}"))

    def _flow_chain(self, opening: float, bank_m: float, bank_U: float, car_m: float, car_U: float):
        """
        Solve the steady-flow chain bank -> valve -> precooler -> car for given
        tank states. Returns m_dot, h delivered, T after valve, T delivered,
        Q_precool and the bank exit enthalpy.
        """
        g = self.gas
        bank = self.bank
        # Step 1. The state of each tank from its mass and internal energy (rho and u give T, then P).
        rho_b = bank_m / bank.volume
        T_b = g.T_from_rho_u(rho_b, bank_U / bank_m)
        P_b = g.P_rhoT(rho_b, T_b)
        rho_c = car_m / self.car.volume
        T_c = g.T_from_rho_u(rho_c, car_U / car_m)
        P_c = g.P_rhoT(rho_c, T_c)
        if self.cfg.bank_outlet_at_ambient:
            T_b_out = self.cfg.T_amb
        else:
            T_b_out = T_b
        # Step 2. Mass flow through the valve, from the bank's pressure down to the car's pressure.
        self.valve.opening = opening
        m_dot = self.valve.mass_flow(g, P_b, T_b_out, P_c)
        # the dispenser clips the valve so the flow never exceeds the J2601 limit
        lim = self.cfg.controller.flow_limit_kg_s
        if m_dot > lim:
            scale = lim / m_dot
            m_dot = lim
            self.valve.opening = opening * scale
        # Step 3. Throttling: h_e = h_i. I take the hose to be at the car's pressure, so the gas leaves the
        # valve with the bank's enthalpy at the car's pressure, and (P, h) gives its temperature.
        h_bank_out = g.h_PT(P_b, T_b_out)
        T_valve_out = g.T_from_P_h(P_c, h_bank_out) if m_dot > 0 else T_b_out
        # Step 4. Precooler, at the car's pressure. Its outlet enthalpy is what enters the car's tank.
        T_del, Q_pc, _, h_del = self.precooler.outlet(g, P_c, T_valve_out, m_dot)
        return m_dot, h_del, T_valve_out, T_del, Q_pc, h_bank_out, P_b, P_c, T_c, T_b

    def _record(self, m_dot, opening, T_valve_out, T_del, Q_pc, Q_wall, ref):
        c, b = self.car, self.bank
        self.rec.add(
            t=self.t, P_car=c.P, T_car=c.T, T_wall=c.T_wall, m_car=c.m, soc=c.soc, m_dot=m_dot,
            opening=opening, P_target=self.dispenser.state.P_target or c.P, error=self.dispenser.state.error,
            P_bank=b.P, T_bank=b.T, bank_idx=self.bank_idx, T_valve_out=T_valve_out, T_delivery=T_del,
            Q_precool=Q_pc, Q_wall=Q_wall, W_ref=ref.get("W_comp", 0.0), COP=ref.get("COP", np.nan),
            H_flow=m_dot * self.gas.h_PT(c.P, T_del) if m_dot > 0 else 0.0,
            E_cool_cum=self.E_cool, E_comp_ref_cum=self.E_comp_ref,
        )

    # ---- time stepping ----------------------------------------------------------

    def step(self) -> None:
        if self.finished:
            return
        cfg = self.cfg
        dt = cfg.dt
        car, g = self.car, self.gas
        self._select_bank(car.P)
        bank = self.bank
        opening = self.dispenser.opening(self.t, car.P, self.P_start, dt)

        # Stage 1 of the midpoint method: flow and rates at the state the step starts from.
        # The car only takes gas in and the bank only gives gas out, so each has one flow term.
        m_dot1, h1, Tv1, Td1, Qpc1, hb1, P_b, P_c, T_c, T_b = self._flow_chain(
            opening, bank.m, bank.U, car.m, car.U)
        dm_c1, dU_c1, dTw_c1, Qg_c1, _ = car.rates(m_dot1, h1, 0.0, car.m, car.U, car.T_wall)
        dm_b1, dU_b1, dTw_b1, Qg_b1, he_b1 = bank.rates(0.0, 0.0, m_dot1, bank.m, bank.U, bank.T_wall)

        # Stage 2: half a step forward with the stage 1 rates, then flow and rates again at that midpoint.
        hdt = 0.5 * dt
        m_dot2, h2, Tv2, Td2, Qpc2, hb2, *_ = self._flow_chain(
            opening, bank.m + hdt * dm_b1, bank.U + hdt * dU_b1, car.m + hdt * dm_c1, car.U + hdt * dU_c1)
        dm_c2, dU_c2, dTw_c2, Qg_c2, _ = car.rates(
            m_dot2, h2, 0.0, car.m + hdt * dm_c1, car.U + hdt * dU_c1, car.T_wall + hdt * dTw_c1)
        dm_b2, dU_b2, dTw_b2, Qg_b2, he_b2 = bank.rates(
            0.0, 0.0, m_dot2, bank.m + hdt * dm_b1, bank.U + hdt * dU_b1, bank.T_wall + hdt * dTw_b1)

        # Advance the whole step with the midpoint rates. The same flow leaves the bank and enters the car,
        # which is what keeps mass conserved between them.
        car.apply(dm_c2, dU_c2, dTw_c2, Qg_c2, m_dot2, h2, 0.0, 0.0, dt)
        bank.apply(dm_b2, dU_b2, dTw_b2, Qg_b2, 0.0, 0.0, m_dot2, he_b2, dt)
        self.E_cool += Qpc2 * dt
        # The refrigeration cycle carries whatever the precooler removed in this step.
        ref = self._refrigeration(Qpc2)
        self.E_comp_ref += ref.get("W_comp", 0.0) * dt
        self.t += dt

        # limits and warnings at the new state
        chk = check_limits(car.T, car.P, car.soc, m_dot2, Td2, cfg.controller, self.t)
        for w in chk.warnings:
            if w not in self.warnings_seen:
                self.warnings_seen[w] = self.t
                self.rec.events.append((self.t, "Warning: " + w))
        if chk.abort and cfg.enforce_limits:
            self.finished, self.aborted, self.end_reason = True, True, chk.abort_reason
            self.rec.events.append((self.t, "ABORT: " + chk.abort_reason))
        elif chk.complete:
            self.finished, self.end_reason = True, chk.complete_reason
            self.rec.events.append((self.t, "Complete: " + chk.complete_reason))
        elif self.t >= cfg.t_max:
            self.finished, self.end_reason = True, "Time limit reached"
            self.rec.events.append((self.t, "Stopped: time limit reached"))
        elif m_dot2 <= 1e-7 and self.bank_idx == len(self.banks) - 1 and self.t > 5.0 and \
                self.bank.P - car.P < cfg.switch_margin_pa:
            self.finished, self.end_reason = True, "Station banks cannot push more gas (pressure equalised)"
            self.rec.events.append((self.t, "Stopped: " + self.end_reason))
        self._record(m_dot2, self.valve.opening, Tv2, Td2, Qpc2, Qg_c2, ref)

    def _refrigeration(self, Q_L: float) -> dict:
        """Compressor power of the refrigeration cycle for a cooling load Q_L: W = Q_L / COP.

        The cycle's states depend only on its two temperatures, the refrigerant and the compressor efficiency,
        so the COP is the same for every load. I solve the cycle once per watt and scale it.
        """
        if Q_L <= 0.0:
            return {"W_comp": 0.0, "COP": np.nan}
        if self.ref_cache is None:
            self.ref_cache = self.refrigeration.solve(1.0)  # per watt of load
        base = self.ref_cache
        return {"W_comp": Q_L / base["COP"], "COP": base["COP"], "m_ref": Q_L / base["q_L"]}

    def run(self) -> "FillResult":
        """Step until the fill ends, then return the result."""
        while not self.finished:
            self.step()
        return self.result()

    def advance(self, seconds: float) -> None:
        """Step forward by about this many seconds of fill time. The live animation calls this twice a second."""
        n = max(1, int(round(seconds / self.cfg.dt)))
        for _ in range(n):
            if self.finished:
                break
            self.step()

    # ---- results -----------------------------------------------------------------

    def energy_balance(self) -> dict:
        """
        Whole-station energy balance, my check that the first law was kept over the entire fill. Everything is in J.
          energy leaving the banks (as enthalpy flow)  H_out_banks
          energy removed in the precooler              E_cool
          energy entering the car (as enthalpy flow)   H_in_car
          heat from the car gas to its wall            -Q_wall_car
        Checks: H_out_banks - E_cool = H_in_car (SSSF chain conserves energy)
                dU_car = H_in_car + Q_wall_car (transient car tank)
                dU_banks = -H_out_banks + Q_wall_banks (transient banks)
        The closure error compares the stored energy change computed from the
        final thermodynamic state with the integrated flows.
        """
        H_out_banks = sum(b.H_out_cum for b in self.banks)
        Q_wall_banks = sum(b.Q_wall_cum for b in self.banks)
        dU_car_state = self.car.m * self.gas.u_PT(self.car.P, self.car.T) - self.U0_car
        dU_banks_state = sum(b.m * self.gas.u_PT(b.P, b.T) for b in self.banks) - self.U0_banks
        dU_total_state = dU_car_state + dU_banks_state
        net_in = -self.E_cool + self.car.Q_wall_cum + Q_wall_banks
        closure = abs(dU_total_state - net_in) / max(abs(H_out_banks), 1.0)
        chain = abs(H_out_banks - self.E_cool - self.car.H_in_cum) / max(abs(H_out_banks), 1.0)
        return {
            "H_out_banks": H_out_banks,
            "E_cool": self.E_cool,
            "H_in_car": self.car.H_in_cum,
            "Q_wall_car": self.car.Q_wall_cum,
            "Q_wall_banks": Q_wall_banks,
            "dU_car": dU_car_state,
            "dU_banks": dU_banks_state,
            "closure_error": closure,
            "chain_error": chain,
            "mass_error": abs(self.total_mass() - self.initial_mass) / self.initial_mass,
            "mass_transfer_error": abs(sum(b.m_out_cum for b in self.banks) - self.car.m_in_cum)
            / max(self.car.m_in_cum, 1e-9),
        }

    def result(self) -> "FillResult":
        arr = self.rec.arrays()
        eb = self.energy_balance()
        m_added = self.car.m_in_cum
        return FillResult(
            cfg=self.cfg, series=arr, events=list(self.rec.events), finished=self.finished,
            aborted=self.aborted, end_reason=self.end_reason, fill_time=self.t, m_added=m_added,
            T_peak=float(np.nanmax(arr["T_car"])), P_final=self.car.P, soc_final=self.car.soc,
            E_cool=self.E_cool, E_comp_ref=self.E_comp_ref, energy=eb,
            bank_final=[(b.name, b.P, b.T, b.m) for b in self.banks],
        )



@dataclass
class FillResult:
    """A finished (or stopped) fill: the full time record plus the headline numbers."""

    cfg: FillConfig
    series: dict
    events: list
    finished: bool
    aborted: bool
    end_reason: str
    fill_time: float
    m_added: float
    T_peak: float
    P_final: float
    soc_final: float
    E_cool: float
    E_comp_ref: float
    energy: dict
    bank_final: list

    def summary(self) -> dict:
        """Engineering performance indicators used by the scoring."""
        return {
            "Fill time [s]": self.fill_time,
            "Hydrogen added [kg]": self.m_added,
            "Peak gas temperature [degC]": self.T_peak - 273.15,
            "Final pressure [MPa]": self.P_final / 1e6,
            "Final SOC [%]": self.soc_final,
            "Cooling energy [kWh]": self.E_cool / 3.6e6,
            "Refrigeration compressor energy [kWh]": self.E_comp_ref / 3.6e6,
            "Cooling energy per kg [kWh/kg]": (self.E_comp_ref / 3.6e6) / max(self.m_added, 1e-9),
            "Energy closure error [%]": 100.0 * self.energy["closure_error"],
            "Mass transfer error [%]": 100.0 * self.energy["mass_transfer_error"],
            "Aborted": self.aborted,
            "End reason": self.end_reason,
        }
