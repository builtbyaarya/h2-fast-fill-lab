"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, h2lab/tanks.py

What this file does
    The two transient parts of the station: the car's tank, which fills, and
    the storage banks, which empty. Both are the same class, TransientTank.

Where it fits in the model
    These are the only places where mass and energy are stored. The valve and
    the precooler in devices.py sit between them and store nothing;
    simulation.py joins the two and steps them forward in time.

The thermodynamics, step by step
    1. I take the gas inside one tank as the control volume. The tank is
       rigid, so there is no boundary work (W = 0), and I neglect kinetic and
       potential energy.
    2. Mass balance (continuity):
           dm/dt = m_dot_i - m_dot_e
    3. First law for a transient control volume (Borgnakke and Sonntag):
           dU/dt = Q_dot + m_dot_i h_i - m_dot_e h_e
    4. I assume the gas is uniform, one temperature and one pressure, so gas
       that leaves has the tank's own enthalpy, h_e = u + Pv. SAE J2601, the
       fuelling standard for hydrogen cars, uses the same lumped assumption.
    5. Heat goes to a lumped wall at one temperature T_w:
           Q_dot (into the gas) = -h_in A (T_gas - T_w)
           m_w c_w dT_w/dt      =  h_in A (T_gas - T_w) - h_out A (T_w - T_amb)
    6. The stored state is (m, U, T_w). Temperature and pressure are found
       from density and specific internal energy through properties.py.

Check I use
    With an insulated tank that starts empty and a constant supply, step 3
    integrates to m2 u2 = m2 h_i, so u2 = h_i, and for an ideal gas T2 = k T_i.
    tests/test_physics.py runs exactly that case.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .properties import Hydrogen, soc_from_density


@dataclass
class WallModel:
    """
    The tank wall as one lump at one temperature (lumped capacity).

    My defaults are a Type IV vehicle tank: a plastic liner wrapped in carbon
    fibre (CFRP). Material data are from the CFD study of a 39.1 L Type IV tank
    by the Saga University IOES group: liner 1286 kg/m3, 1578 J/kg K; CFRP
    1375 kg/m3, 1075 J/kg K. The heat transfer coefficients are from the
    dual-zone lumped model of SAE J2601 tests (Sustainability 2023, 15, 1448):
    about 80 W/m2 K gas to wall averaged over a fill, 20 W/m2 K wall to
    ambient. The outer coefficient barely matters in a three-minute fill.
    """

    h_in: float = 80.0  # W/m2 K, gas to inner wall
    h_out: float = 20.0  # W/m2 K, outer wall to ambient
    thickness_liner: float = 0.003  # m
    thickness_cfrp: float = 0.022  # m
    rho_liner: float = 1286.0
    cp_liner: float = 1578.0
    rho_cfrp: float = 1375.0
    cp_cfrp: float = 1075.0

    def mass_capacity(self, area: float) -> float:
        """m_w c_w of the wall, J/K, for a given inner surface area."""
        liner = self.rho_liner * self.cp_liner * self.thickness_liner * area
        cfrp = self.rho_cfrp * self.cp_cfrp * self.thickness_cfrp * area
        return liner + cfrp


def cylinder_inner_area(volume: float, aspect: float = 3.0) -> float:
    """
    Inner surface area of a cylinder with hemispherical ends whose length to
    diameter ratio is `aspect`. I only use it to turn a tank volume into a
    heat transfer area; the aspect ratio of car tanks is about 3.
    V = pi r^2 L_cyl + 4/3 pi r^3 with L_total = aspect * 2r.
    """
    # L_cyl = 2 r (aspect - 1); V = pi r^2 * 2 r (aspect - 1) + 4/3 pi r^3
    r = (volume / (math.pi * (2.0 * (aspect - 1.0) + 4.0 / 3.0))) ** (1.0 / 3.0)
    L_cyl = 2.0 * r * (aspect - 1.0)
    return 2.0 * math.pi * r * L_cyl + 4.0 * math.pi * r**2


@dataclass
class TransientTank:
    """
    A rigid control volume whose mass and internal energy change with time.

    I store the total mass m (kg) and the total internal energy U (J), because
    those are what the mass balance and the first law give rates for. Density
    and specific internal energy follow (rho = m/V, u = U/m), and temperature
    and pressure are then found through the property model.
    """

    name: str
    volume: float  # m3
    gas: Hydrogen
    m: float  # kg
    U: float  # J
    T_wall: float  # K
    T_amb: float  # K
    wall: WallModel = field(default_factory=WallModel)
    insulated: bool = False
    aspect: float = 3.0
    label: str = "transient"

    # cumulative bookkeeping for the energy balance display
    Q_wall_cum: float = 0.0  # J, heat into the gas from the wall (negative when the gas is hotter)
    m_in_cum: float = 0.0
    m_out_cum: float = 0.0
    H_in_cum: float = 0.0  # J, sum of m_dot_i h_i dt
    H_out_cum: float = 0.0

    @classmethod
    def from_PT(
        cls,
        name: str,
        volume: float,
        gas: Hydrogen,
        P: float,
        T: float,
        T_amb: float,
        wall: WallModel | None = None,
        insulated: bool = False,
        T_wall: float | None = None,
    ) -> "TransientTank":
        """Start a tank from a pressure and a temperature: m = rho(P, T) V and U = m u(P, T)."""
        rho = gas.rho_PT(P, T)
        m = rho * volume
        U = m * gas.u_PT(P, T)
        return cls(
            name=name,
            volume=volume,
            gas=gas,
            m=m,
            U=U,
            T_wall=T if T_wall is None else T_wall,
            T_amb=T_amb,
            wall=wall or WallModel(),
            insulated=insulated,
        )

    # ---- derived state -----------------------------------------------------

    @property
    def rho(self) -> float:
        return self.m / self.volume

    @property
    def u(self) -> float:
        return self.U / self.m

    @property
    def area(self) -> float:
        return cylinder_inner_area(self.volume, self.aspect)

    def state(self):
        return self.gas.state_rho_u(self.rho, self.u)

    @property
    def T(self) -> float:
        return self.gas.T_from_rho_u(self.rho, self.u)

    @property
    def P(self) -> float:
        T = self.T
        return self.gas.P_rhoT(self.rho, T)

    @property
    def soc(self) -> float:
        return soc_from_density(self.rho)

    def wall_capacity(self) -> float:
        return self.wall.mass_capacity(self.area)

    # ---- rates -------------------------------------------------------------

    def rates(self, m_dot_in: float, h_in: float, m_dot_out: float, m: float, U: float, T_wall: float):
        """
        The rates of change of the three stored quantities for a given state (m, U, T_wall).
        Returns (dm/dt, dU/dt, dT_wall/dt, Q_dot_wall_to_gas, h_e).
        """
        # Step 1. Fix the state. Two independent properties are known, rho = m/V and u = U/m,
        # so the property model gives T, and then P.
        rho = m / self.volume
        T = self.gas.T_from_rho_u(rho, U / m)
        P = self.gas.P_rhoT(rho, T)
        # Step 2. Gas that leaves has the uniform tank state, so its enthalpy is h_e = u + Pv.
        h_e = U / m + P / rho
        # Step 3. Heat transfer by Newton's law of cooling, gas to wall and wall to air. The wall is one
        # lump, so its own energy balance is m_w c_w dT_w/dt = (heat in from the gas) - (heat out to the air).
        if self.insulated:
            Q_gas = 0.0
            dTw = 0.0
        else:
            A = self.area
            Q_gas = -self.wall.h_in * A * (T - T_wall)  # into the gas
            Q_out = self.wall.h_out * A * (T_wall - self.T_amb)
            dTw = (-Q_gas - Q_out) / self.wall_capacity()
        # Step 4. Mass balance: dm/dt = m_dot_i - m_dot_e.
        dm = m_dot_in - m_dot_out
        # Step 5. First law for a transient control volume with W = 0 (rigid tank):
        # dU/dt = Q_dot + m_dot_i h_i - m_dot_e h_e.
        dU = Q_gas + m_dot_in * h_in - m_dot_out * h_e
        return dm, dU, dTw, Q_gas, h_e

    def apply(self, dm: float, dU: float, dTw: float, Q_gas: float, m_dot_in: float, h_in: float,
              m_dot_out: float, h_e: float, dt: float) -> None:
        """Advance the stored state by one time step with the rates given (the midpoint rates, from simulation.py).

        I also add up the heat and the enthalpy that crossed the boundary, so the energy balance can be checked
        at the end against the change in stored energy.
        """
        self.m += dm * dt
        self.U += dU * dt
        self.T_wall += dTw * dt
        self.Q_wall_cum += Q_gas * dt
        self.m_in_cum += m_dot_in * dt
        self.m_out_cum += m_dot_out * dt
        self.H_in_cum += m_dot_in * h_in * dt
        self.H_out_cum += m_dot_out * h_e * dt
