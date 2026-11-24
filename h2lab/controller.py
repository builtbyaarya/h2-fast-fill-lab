"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, h2lab/controller.py

What this file does
    The dispenser's control: how far the valve is open at each instant, and
    the limits that stop a fill.

Where it fits in the model
    It closes the loop. simulation.py hands it the tank pressure every step, it
    hands back a valve opening, and devices.py turns that opening into a mass
    flow. It also reads the new state after each step and decides whether the
    fill goes on.

How a real dispenser does it, and what I modelled
    SAE J2601 (the fuelling standard) does not control temperature directly.
    It controls how fast the tank pressure rises, the average pressure ramp
    rate (APRR, MPa/min), picked so the gas never passes 85 degC, and the
    dispenser moves its valve to follow that ramp (Reddi et al. 2017). The
    user chooses between:

      manual   the valve opening x in [0, 1] is set by hand.
      auto     a PID controller follows the ramp P_target(t) = P_start + APRR t,

                 e(t)  = P_target(t) - P_tank(t)
                 x(t)  = Kp e + Ki integral(e) dt + Kd de/dt,  clamped to [0, 1]

               with anti-windup: the integral stops growing while the output
               is pinned at 0 or 1.

    The hard limits end the fill, as they would at a real dispenser:
      gas temperature  >= 85 degC
      tank pressure    >= 87.5 MPa
      state of charge  >= 100%
    The 60 g/s flow limit is applied in simulation.py by clipping the valve.
    The precooling window and the flow limit raise warnings and stop nothing.

    None of this is thermodynamics; it is the control problem that the
    thermodynamics creates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .devices import MAX_FLOW_KG_S, MAX_GAS_TEMP_K, MAX_PRESSURE_PA, PRECOOL_WINDOWS


@dataclass
class ControllerSettings:
    """What the user sets on the dispenser."""

    mode: str = "auto"  # "auto" or "manual"
    manual_opening: float = 0.5
    aprr_mpa_min: float = 18.5  # look-up table example value in Reddi et al. 2017
    Kp: float = 0.6  # opening per MPa of error
    Ki: float = 0.08  # opening per MPa s
    Kd: float = 0.0
    target_pressure_pa: float = 70.0e6  # stop when the tank reaches this
    target_soc: float = 100.0  # or when SOC reaches this, whichever first
    dispenser_class: str = "T40"
    flow_limit_kg_s: float = MAX_FLOW_KG_S


@dataclass
class ControllerState:
    """What the PID loop remembers from one step to the next."""

    integral: float = 0.0
    prev_error: float | None = None
    output: float = 0.0
    P_target: float = 0.0
    error: float = 0.0
    saturated: bool = False


@dataclass
class Dispenser:
    """The dispenser's controller: settings, memory, and the rule that turns a pressure error into a valve opening."""

    settings: ControllerSettings = field(default_factory=ControllerSettings)
    state: ControllerState = field(default_factory=ControllerState)

    def reset(self) -> None:
        self.state = ControllerState()

    def opening(self, t: float, P_tank: float, P_start: float, dt: float) -> float:
        """Valve opening for this step. Pressures in Pa, time in s."""
        s = self.settings
        st = self.state
        if s.mode == "manual":
            st.output = max(0.0, min(1.0, s.manual_opening))
            st.P_target = P_tank
            st.error = 0.0
            return st.output

        # Step 1. Where the tank pressure should be now: a straight ramp from the starting pressure at the
        # chosen rate (MPa/min turned into Pa/s), never above the target.
        P_target = P_start + s.aprr_mpa_min * 1.0e6 / 60.0 * t
        P_target = min(P_target, s.target_pressure_pa)
        # Step 2. The error, in MPa, and how fast it is changing.
        e = (P_target - P_tank) / 1.0e6
        de = 0.0 if st.prev_error is None else (e - st.prev_error) / dt
        # Step 3. Integral of the error, then the PID sum, clamped to a valve that is between shut and fully open.
        # anti-windup: only integrate when the output is not pinned at a limit
        if not st.saturated or (e * st.output < 0):
            st.integral += e * dt
        raw = s.Kp * e + s.Ki * st.integral + s.Kd * de
        out = max(0.0, min(1.0, raw))
        st.saturated = out != raw
        st.prev_error = e
        st.output = out
        st.P_target = P_target
        st.error = e
        return out


@dataclass
class LimitCheck:
    """Result of checking the hard limits and the soft warnings at one instant."""

    abort: bool = False
    abort_reason: str = ""
    warnings: list = field(default_factory=list)
    complete: bool = False
    complete_reason: str = ""


def check_limits(
    T_gas: float,
    P_tank: float,
    soc: float,
    m_dot: float,
    T_delivery: float,
    settings: ControllerSettings,
    t: float,
) -> LimitCheck:
    """Read one instant of the fill against the limits: first the three that stop it, then completion, then the warnings."""
    r = LimitCheck()
    if T_gas >= MAX_GAS_TEMP_K:
        r.abort, r.abort_reason = True, "Tank gas reached 85 degC (SAE J2601 limit)"
    elif P_tank >= MAX_PRESSURE_PA:
        r.abort, r.abort_reason = True, "Tank pressure reached 87.5 MPa (125% of NWP)"
    elif soc >= 100.0:
        r.abort, r.abort_reason = True, "State of charge reached 100%, overfill prevented"
    if not r.abort:
        if P_tank >= settings.target_pressure_pa - 0.2e6:
            r.complete, r.complete_reason = True, "Target pressure reached"
        elif soc >= settings.target_soc:
            r.complete, r.complete_reason = True, "Target state of charge reached"
    if m_dot > settings.flow_limit_kg_s * 0.999:
        r.warnings.append("Flow at the 60 g/s limit, valve clipped")
    if T_gas > MAX_GAS_TEMP_K - 10.0:
        r.warnings.append("Tank gas within 10 K of the 85 degC limit")
    lo, hi = PRECOOL_WINDOWS[settings.dispenser_class]
    # the window applies once the fill is under way (about 30 s in, per J2601)
    if t > 30.0 and m_dot > 0 and not (lo <= T_delivery <= hi):
        r.warnings.append(f"Delivery temperature outside the {settings.dispenser_class} window "
                          f"({lo - 273.15:.0f} to {hi - 273.15:.1f} degC)")
    return r
