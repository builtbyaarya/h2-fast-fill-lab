"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/run.py

What this file does
    The run screen, used by Simulate and by every level. The animated station
    is on the left and a control panel on the right with two depths: Guided
    asks one question per card (the weather, how empty the car is, how fast to
    fill, when to stop, and on Simulate which fuel cell is in the car), and
    Engineer shows every parameter in tabs.

Where it fits in the model
    It is the hand on the model. The panel builds a FillConfig, a
    FillSimulation is made from it and kept in st.session_state, and while a
    fill plays a fragment reruns twice a second, advances the model a little
    and hands the new numbers to the scene. That is why settings can change
    while the gas flows, as at a real dispenser. No equation lives here.
"""

from __future__ import annotations

import copy
from html import escape

import streamlit as st

from h2lab import chain
from h2lab.properties import COOLPROP_AVAILABLE
from h2lab.simulation import BankSpec, FillConfig, FillSimulation

from . import fuelcell, scene, tour
from .glossary import TERMS
from .styles import gap, rows_html
from .text import pct, pretty

SPEEDS = {"1×": 1.0, "4×": 4.0, "10×": 10.0, "25×": 25.0}
TICK = 0.5  # seconds between two updates of a playing fill


def _k(ns: str, name: str) -> str:
    return f"{ns}__{name}"


def _split(label: str):
    """'Fill to, MPa' -> ('Fill to', 'MPa'). Labels without a comma have no unit."""
    if ", " in label:
        name, unit = label.rsplit(", ", 1)
        return name, unit
    return label, ""


def qlabel(label: str, definition: str | None) -> None:
    """An input's label with a ? beside it. Clicking the ? shows a plain-words definition (assets/tour.js draws the bubble)."""
    st.markdown(f'<div class="qlabel"><span>{escape(label)}</span>{qmark(label, definition)}</div>', unsafe_allow_html=True)


def qmark(label: str, definition: str | None) -> str:
    if not definition:
        return ""
    return (f'<span class="q-help" role="button" tabindex="0" aria-label="What does {escape(label)} mean?" '
            f'data-term="{escape(label)}" data-def="{escape(definition)}">?</span>')


def num(ns: str, name: str, label: str, lo, hi, value, step, disabled=False, fmt=None, help=None):
    """One input: a slider showing its value and unit, or a number box when Engineer asks for exact numbers.

    The unit is part of the label, for example 'Fill to, MPa'; the slider shows it beside the thumb ('70.0 MPa').
    """
    title, unit = label.rsplit(", ", 1) if ", " in label else (label, "")
    exact = st.session_state.get("path") == "Engineer" and st.session_state.get(_k(ns, "exact"), False)
    if exact:
        qlabel(label, help)
        return st.number_input(label, lo, hi, value, step, key=_k(ns, name + "_n"), disabled=disabled, format=fmt,
                               label_visibility="collapsed")
    is_int = all(isinstance(x, int) for x in (lo, hi, value, step))
    if not is_int:
        lo, hi, value, step = float(lo), float(hi), float(value), float(step)
    value = min(max(value, lo), hi)
    shown = (fmt or ("%d" if is_int else "%.1f")) + ("%%" if unit == "%" else (" " + unit if unit else ""))
    qlabel(title, help)
    return st.slider(title, lo, hi, value, step, key=_k(ns, name), disabled=disabled, format=shown, label_visibility="collapsed")


def toggle(label: str, definition: str, **kw) -> bool:
    """A switch with the same ? as the other inputs."""
    a, b = st.columns([12, 1], gap="small", vertical_alignment="center")
    with a:
        value = st.toggle(label, **kw)
    b.markdown(qmark(label, definition), unsafe_allow_html=True)
    return value


def choose(label: str, definition: str, options, index: int, key: str, **kw):
    """A drop-down with the same ? as the other inputs."""
    qlabel(label, definition)
    return st.selectbox(label, options, index=index, key=key, label_visibility="collapsed", **kw)


def note(text: str) -> None:
    st.markdown(f'<p class="small">{text}</p>', unsafe_allow_html=True)


GUIDED_STEPS = [
    ("tamb", "The weather",
     "How warm is it at the station? The hydrogen and the car's tank start at this temperature, so a hot day leaves less room "
     "before the tank's 85 °C limit. A mild day is 25 °C."),
    ("p0", "How empty the car is",
     "The pressure left in the car's tank when it pulls in. Pressure is in MPa: 1 MPa is about ten times the air around you. "
     "A nearly empty tank is about 5 MPa."),
    ("aprr", "How fast to fill",
     "How quickly the station raises the pressure in the car's tank, in MPa per minute. Real stations use about 18.5, which fills "
     "a car in roughly three minutes. Faster is a shorter wait, but squeezing gas in quickly makes it hotter."),
    ("ptar", "When to stop",
     "The pressure at which the fill stops. A full hydrogen car is at 70 MPa, the 700 bar you see on the pumps. The rules never "
     "allow more than 87.5 MPa."),
]
FUEL_CELL_KEY = "fcell"


def fuel_cell_step() -> tuple[str, str, str]:
    """The last Guided card. Its efficiencies are read from chain.FUEL_CELLS, so the words follow the model."""
    cells = chain.FUEL_CELLS
    pefc, aefc = (f"{100 * cells[k]['eta']:.0f}%" for k in ("PEFC", "AEFC"))
    return (FUEL_CELL_KEY, "Which fuel cell is in the car?",
            "The fuel cell turns hydrogen and air back into electricity and water; that electricity turns the wheels. "
            f"PEFC {fuelcell.ABOUT['PEFC']}; at its best it gives back {pefc} of the hydrogen's energy. "
            f"AEFC {fuelcell.ABOUT['AEFC']}, so its {aefc} is my own estimate."
            '</p><p class="step-text">'
            "It does not change how the tank fills. It changes everything after it: the electricity you get back, the round trip, "
            "the distance per kilogram and the cost per kilometre.")


def guided_steps(with_fuel_cell: bool) -> list[tuple[str, str, str]]:
    """The Guided cards in order. Simulate ends with the fuel cell; a level stops at the fill, so it leaves that card out."""
    return GUIDED_STEPS + ([fuel_cell_step()] if with_fuel_cell else [])


READY_TEXT = ("Press Start. Gas flows from the station's tanks, through the valve and the cooler, into the car. Watch the two numbers: "
              "the tank must stay below 85 °C. You can move any slider while the gas flows.")
LIVE_TEXT = "The tank must stay below 85 °C. Move any slider and the station reacts at once, as a real dispenser would."
DONE_TEXT = ("The fill has ended. Below the chart: what happened and why, the station's checks, and where this hydrogen came from. Change one choice and run it again to compare.")
STEP_HELP = {
    "tamb": "How hot or cold it is outside. The hydrogen and the car's tank start at this temperature.",
    "p0": "How much gas is left in the car when it arrives. About 5 MPa means nearly empty.",
    "aprr": TERMS["Fill speed (ramp rate)"],
    "ptar": "The pressure where the fill stops. 70 MPa is a full tank.",
    FUEL_CELL_KEY: TERMS["Fuel cell type (PEFC, AEFC)"],
}


# ---- the control panel --------------------------------------------------------------------------------------
def fuel_cell_card(ns: str) -> None:
    """The control and the side-by-side on the fuel cell card.

    The table is worked out by h2lab/chain.py for the standard fill, because the user's own fill has not run yet.
    After their fill the same table is shown again under the results, for their numbers.
    """
    kinds = list(chain.FUEL_CELLS)
    qlabel("Fuel cell type", STEP_HELP[FUEL_CELL_KEY])
    picked = st.segmented_control("Fuel cell type", kinds, default=fuelcell.chosen(ns), key=_k(ns, "fcpick"), format_func=fuelcell.short_label,
                                  label_visibility="collapsed")
    fuelcell.choose(ns, picked)
    with st.spinner("Running the standard fill once"):
        res = fuelcell.standard_fill()
    st.markdown('<p class="fc-head">What it changes, for one kilogram</p>' + fuelcell.table_html(res, fuelcell.chosen(ns))
                + '<p class="small fc-note">From the model, for the standard fill (25 °C, 5 MPa, 18.5 MPa/min, to 70 MPa). '
                  'Your own fill gets this table under its results.</p>', unsafe_allow_html=True)


def build_config(ns: str, preset: FillConfig, locked: set | None = None, started: bool = False, with_fuel_cell: bool = False) -> FillConfig:
    """Draw the control panel and return the configuration it describes."""
    locked = locked or set()
    last = st.session_state.get(_k(ns, "cfg"))
    cfg = copy.deepcopy(last if last is not None else preset)
    if _k(ns, "depth") not in st.session_state:
        st.session_state[_k(ns, "depth")] = st.session_state.get("path", "Guided")
    depth = st.segmented_control("Depth", ["Guided", "Engineer"], key=_k(ns, "depth"), label_visibility="collapsed") or "Guided"
    st.session_state["path"] = depth

    c, pc, rf = cfg.controller, cfg.precooler, cfg.refrigeration

    def ambient():
        cfg.T_amb = 273.15 + num(ns, "tamb", "Air temperature, °C", -20.0, 45.0, float(round(cfg.T_amb - 273.15, 1)), 1.0,
                                 disabled="T_amb" in locked, fmt="%.0f", help=STEP_HELP["tamb"])

    def arrives():
        cfg.car_P0_pa = 1e6 * num(ns, "p0", "Car arrives at, MPa", 0.5, 60.0, float(round(cfg.car_P0_pa / 1e6, 1)), 0.5,
                                  disabled="car_P0_pa" in locked, fmt="%.1f", help=STEP_HELP["p0"])

    def fill_speed():
        c.aprr_mpa_min = num(ns, "aprr", "Fill speed, MPa/min", 2.0, 40.0, float(c.aprr_mpa_min), 0.5, disabled="aprr" in locked, fmt="%.1f",
                             help=STEP_HELP["aprr"])

    def fill_to():
        c.target_pressure_pa = 1e6 * num(ns, "ptar", "Fill to, MPa", 20.0, 87.5, float(c.target_pressure_pa / 1e6), 0.5,
                                         disabled="target" in locked, fmt="%.1f", help=STEP_HELP["ptar"])

    fields = {"tamb": (ambient, "T_amb"), "p0": (arrives, "car_P0_pa"), "aprr": (fill_speed, "aprr"), "ptar": (fill_to, "target")}

    if depth == "Guided":
        gap(8)
        steps = guided_steps(with_fuel_cell)
        n_steps = len(steps)  # the card after the last step is the fill itself
        step = n_steps if started else min(st.session_state.get(_k(ns, "gstep"), 0), n_steps)
        with st.container(key=f"{ns}__gcard"):
            if step < n_steps:
                key, title, text = steps[step]
                dots = "".join(f'<span class="{"on" if i <= step else ""}"></span>' for i in range(n_steps + 1))
                st.markdown(f'<div class="step-dots" aria-hidden="true">{dots}</div><p class="step-count">Step {step + 1} of {n_steps}</p>'
                            f'<h3 class="step-title">{title}</h3><p class="step-text">{text}</p>', unsafe_allow_html=True)
                if key == FUEL_CELL_KEY:
                    fuel_cell_card(ns)
                else:
                    fn, lock = fields[key]
                    fn()
                    if lock in locked:
                        note("This one is fixed by the level.")
            else:
                dots = "".join('<span class="on"></span>' for _ in range(n_steps + 1))
                sim_now = st.session_state.get(_k(ns, "sim"))
                done = sim_now is not None and sim_now.finished
                head, title, text = (("Done", "See what happened", DONE_TEXT) if done else
                                     ("Filling", "Watch the tank", LIVE_TEXT) if started else ("Your fill", "Ready to fill", READY_TEXT))
                st.markdown(f'<div class="step-dots" aria-hidden="true">{dots}</div><p class="step-count">{head}</p>'
                            f'<h3 class="step-title">{title}</h3><p class="step-text">{text}</p>', unsafe_allow_html=True)
                for fn, _ in fields.values():
                    fn()
                if with_fuel_cell:
                    note(f"Fuel cell in the car: {fuelcell.label(fuelcell.chosen(ns))}. It does not change the fill; see what it changes under the results.")
        tour.request("inputs", tour.inputs_tour(ns, n_steps, with_fuel_cell))
    else:
        gap(8)
        exact = toggle("Type exact numbers", "Sliders are quick for trying things. Switch this on to type an exact number instead.",
                       value=st.session_state.get(_k(ns, "exact"), False), key=_k(ns, "exact_w"))
        if exact != st.session_state.get(_k(ns, "exact"), False):
            st.session_state[_k(ns, "exact")] = exact
            st.rerun()
        tabs = st.tabs(["Banks", "Dispenser", "Cooling", "Tank", "Solver"])
        with tabs[0]:
            new_banks = []
            names = ["Low bank", "Medium bank", "High bank"]
            for i, b in enumerate(cfg.banks):
                a, bb = st.columns(2, gap="small")
                with a:
                    P = num(ns, f"bp{i}", f"{names[i] if i < 3 else b.name}, MPa", 5.0, 100.0, float(round(b.pressure_pa / 1e6, 1)), 1.0, fmt="%.1f", help=TERMS["Storage banks (cascade)"])
                with bb:
                    V = num(ns, f"bv{i}", "Volume, L", 100, 5000, int(round(b.volume_m3 * 1000)), 50, help=TERMS["Storage banks (cascade)"])
                new_banks.append(BankSpec(b.name, V / 1000.0, P * 1e6))
            cfg.banks = new_banks
            a, bb = st.columns(2, gap="small")
            with a:
                cfg.switch_margin_pa = 1e6 * num(ns, "marg", "Switch margin, MPa", 0.5, 10.0, float(cfg.switch_margin_pa / 1e6), 0.5, fmt="%.1f", help=TERMS["Switch margin"])
            with bb:
                cfg.valve.area = 1e-6 * num(ns, "varea", "Valve seat area, mm²", 0.5, 5.0, float(round(cfg.valve.area * 1e6, 2)), 0.1, fmt="%.2f", help=TERMS["Valve seat area"])
            cfg.cascade = toggle("Cascade, low bank first", TERMS["Storage banks (cascade)"], value=cfg.cascade, key=_k(ns, "casc"))
        with tabs[1]:
            a, bb = st.columns(2, gap="small")
            with a:
                ambient()
                fill_speed()
                mode = choose("Valve control", TERMS["Controller and gains (Kp, Ki, Kd)"], ["Automatic", "Manual"], 0 if c.mode == "auto" else 1, _k(ns, "cmode"))
                c.mode = "auto" if mode.startswith("Auto") else "manual"
            with bb:
                arrives()
                fill_to()
                c.dispenser_class = choose("Station class", TERMS["Station class (T40, T30, T20)"], ["T40", "T30", "T20"],
                                            ["T40", "T30", "T20"].index(c.dispenser_class), _k(ns, "class"))
            a, bb = st.columns(2, gap="small")
            with a:
                if c.mode == "manual":
                    c.manual_opening = num(ns, "open", "Valve opening, %", 0, 100, int(round(c.manual_opening * 100)), 1, help=TERMS["Throttle valve"]) / 100.0
                else:
                    c.Kp = num(ns, "kp", "Kp gain, 1/MPa", 0.0, 2.0, float(c.Kp), 0.01, fmt="%.2f", help=TERMS["Controller and gains (Kp, Ki, Kd)"])
                    c.Kd = num(ns, "kd", "Kd gain, s/MPa", 0.0, 2.0, float(c.Kd), 0.05, fmt="%.2f", help=TERMS["Controller and gains (Kp, Ki, Kd)"])
                c.target_soc = float(num(ns, "soctar", "Stop at charge, %", 50, 100, int(c.target_soc), 1, help=TERMS["State of charge (SOC)"]))
            with bb:
                if c.mode != "manual":
                    c.Ki = num(ns, "ki", "Ki gain, 1/(MPa s)", 0.0, 0.5, float(c.Ki), 0.005, fmt="%.3f", help=TERMS["Controller and gains (Kp, Ki, Kd)"])
                c.flow_limit_kg_s = num(ns, "flow", "Flow limit, g/s", 10, 60, int(round(c.flow_limit_kg_s * 1000)), 1, help=TERMS["Flow limit (60 g/s)"]) / 1000.0
        with tabs[2]:
            a, bb = st.columns(2, gap="small")
            with a:
                pc.T_set = 273.15 + num(ns, "pct", "Delivery set point, °C", -40.0, 20.0, float(round(pc.T_set - 273.15, 1)), 1.0,
                                        disabled="precooler" in locked, fmt="%.0f", help=TERMS["Delivery set point"])
                rf.T_cond = 273.15 + num(ns, "tco", "Condenser, °C", 20.0, 60.0, float(round(rf.T_cond - 273.15, 1)), 1.0, fmt="%.0f", help=TERMS["Refrigeration cycle"])
                rf.refrigerant = choose("Refrigerant", "The liquid inside the precooler's fridge that boils to soak up heat. Each one suits a different temperature range.",
                                        ["R134a", "R410A", "R744"], ["R134a", "R410A", "R744"].index(rf.refrigerant), _k(ns, "ref"))
            with bb:
                pc.Q_max = 1000.0 * num(ns, "pcq", "Cooling capacity, kW", 5, 120, int(round(pc.Q_max / 1000)), 5, disabled="precooler_q" in locked, help=TERMS["Cooling capacity"])
                rf.T_evap = 273.15 + num(ns, "tev", "Evaporator, °C", -60.0, 0.0, float(round(rf.T_evap - 273.15, 1)), 1.0, fmt="%.0f", help=TERMS["Refrigeration cycle"])
                rf.eta_s = num(ns, "eta", "Compressor efficiency", 0.4, 1.0, float(rf.eta_s), 0.05, fmt="%.2f", help=TERMS["Compressor efficiency"])
            pc.enabled = toggle("Precooler on", TERMS["Precooler"], value=pc.enabled, key=_k(ns, "pcon"), disabled="precooler" in locked)
            note("The precooler runs by itself. You pick the temperature it should deliver; it takes out just enough heat to hold that, up to its "
                 "cooling capacity, and its fridge works harder when more hydrogen flows.")
            if rf.T_evap >= pc.T_set:
                note("The evaporator has to be colder than the set point for heat to flow.")
        with tabs[3]:
            a, bb = st.columns(2, gap="small")
            with a:
                cfg.car_volume_m3 = num(ns, "vol", "Tank volume, L", 30, 250, int(round(cfg.car_volume_m3 * 1000)), 1,
                                        disabled="car_volume_m3" in locked,
                                        help="How much the car's tank holds, in litres. A typical car holds about 141 L.") / 1000.0
                cfg.car_wall.h_in = float(num(ns, "hin", "Gas to wall, W/(m² K)", 0, 500, int(cfg.car_wall.h_in), 10, help=TERMS["Gas to wall heat transfer (h_in)"]))
            with bb:
                cfg.car_wall.thickness_cfrp = num(ns, "tcf", "Composite wall, mm", 5, 40, int(round(cfg.car_wall.thickness_cfrp * 1000)), 1, help=TERMS["Tank wall (liner and composite)"]) / 1000.0
                cfg.car_wall.h_out = float(num(ns, "hout", "Wall to air, W/(m² K)", 0, 50, int(cfg.car_wall.h_out), 1, help=TERMS["Wall to air heat transfer (h_out)"]))
            cfg.car_insulated = toggle("Insulated tank, no heat transfer", "Pretend no heat can leave the gas. This is the textbook case where the tank gets hottest.",
                                       value=cfg.car_insulated, key=_k(ns, "ins"))
        with tabs[4]:
            a, bb = st.columns(2, gap="small")
            with a:
                modes = ["real", "ideal"] if COOLPROP_AVAILABLE else ["ideal"]
                labels = {"real": "Real gas", "ideal": "Ideal gas"}
                cfg.property_mode = choose("Property model", TERMS["Real gas and ideal gas"], modes,
                                           modes.index(cfg.property_mode) if cfg.property_mode in modes else 0, _k(ns, "mode"),
                                           format_func=lambda x: labels[x])
            with bb:
                cfg.dt = num(ns, "dt", "Time step, s", 0.02, 0.5, float(cfg.dt), 0.01, fmt="%.2f", help=TERMS["Time step"])
            note("Real gas uses CoolProp. Ideal gas uses the Table A.5 constants.")
        note("Banks, tank and solver apply on Reset. Everything else applies while the gas flows.")
        tour.request("engineer", tour.engineer_tour(ns))

    st.session_state[_k(ns, "cfg")] = cfg
    return cfg


def apply_live_settings(sim: FillSimulation, cfg: FillConfig) -> None:
    """Settings that may change while the gas is flowing, as at a real dispenser."""
    sim.dispenser.settings = cfg.controller
    sim.cfg.controller = cfg.controller
    sim.precooler.enabled = cfg.precooler.enabled
    sim.precooler.T_set = cfg.precooler.T_set
    sim.precooler.Q_max = cfg.precooler.Q_max
    if (sim.refrigeration.refrigerant, sim.refrigeration.T_evap, sim.refrigeration.T_cond, sim.refrigeration.eta_s) != \
            (cfg.refrigeration.refrigerant, cfg.refrigeration.T_evap, cfg.refrigeration.T_cond, cfg.refrigeration.eta_s):
        sim.refrigeration = cfg.refrigeration
        sim.ref_cache = None
    sim.car.wall.h_in = cfg.car_wall.h_in
    sim.car.wall.h_out = cfg.car_wall.h_out
    sim.car.insulated = cfg.car_insulated
    sim.valve.area = cfg.valve.area
    sim.cfg.switch_margin_pa = cfg.switch_margin_pa


# ---- details behind the disclosure --------------------------------------------------------------------------
def _events_html(sim: FillSimulation, n: int = 10) -> str:
    rows = []
    for t, text in sim.rec.events[-n:][::-1]:
        cls = "fail" if ("ABORT" in text or "Warning" in text) else ""
        head, _, rest = text.partition(":")
        head = {"ABORT": "Stopped", "Warning": "Warning", "Complete": "Complete", "Stopped": "Stopped"}.get(head, head)
        rows.append(f'<div class="event {cls}"><span class="t">{t:.1f} s</span><span><b>{pretty(head)}</b>'
                    f'{(": " + pretty(rest.strip())) if rest else ""}</span></div>')
    if not rows:
        rows.append('<div class="event"><span class="t"></span><span>Nothing yet. Press Start.</span></div>')
    return "".join(rows)


def _energy_html(sim: FillSimulation) -> str:
    eb = sim.energy_balance()
    return rows_html([
        ("Enthalpy out of the banks, MJ", f'{eb["H_out_banks"] / 1e6:.2f}'),
        ("Removed in the precooler, MJ", f'{eb["E_cool"] / 1e6:.2f}'),
        ("Enthalpy into the car, MJ", f'{eb["H_in_car"] / 1e6:.2f}'),
        ("Car gas to its wall, MJ", f'{-eb["Q_wall_car"] / 1e6:.2f}'),
        ("Change in car gas energy, MJ", f'{eb["dU_car"] / 1e6:.2f}'),
        ("Energy closure error", pct(100 * eb["closure_error"])),
        ("Mass transfer error", pct(100 * eb["mass_transfer_error"])),
    ])


def _what_happened(sim: FillSimulation) -> str:
    """Plain-words reading of a finished fill: what the numbers mean and why it came out this way."""
    res = sim.result()
    peak = res.T_peak - 273.15
    margin = 85.0 - peak
    start = sim.cfg.T_amb - 273.15
    cool = sim.cfg.precooler.enabled
    lines = []
    if res.aborted:
        lines.append(f"The station stopped the fill to protect the tank: {pretty(res.end_reason)}.")
    lines.append(f"The gas in the tank went from {start:.0f} °C to a peak of {peak:.0f} °C. "
                 + (f"That is {margin:.0f} K under the 85 °C limit." if margin >= 0 else f"That is {-margin:.0f} K over the 85 °C limit."))
    lines.append("It warms because gas pushed into a closed tank carries the work of pushing it in, and that energy stays in the tank as heat, "
                 "like a bike pump getting warm."
                 + (" The cooler chilled the incoming gas to offset part of that." if cool else " The cooler was off, so nothing offset it."))
    lines.append(f"The tank ended at {res.P_final / 1e6:.0f} MPa and {res.soc_final:.0f}% charge in {res.fill_time:.0f} s "
                 + ("(a real station aims for about 180 s)." if res.fill_time > 180 else "(inside the 180 s a real station aims for)."))
    if margin < 5 and not res.aborted:
        lines.append("Try a slower fill speed: the gas has more time to lose heat to the tank wall, so it peaks lower.")
    elif res.fill_time > 180 and not res.aborted:
        lines.append("Try a faster fill speed and watch the peak temperature climb. That trade is the whole problem a station solves.")
    else:
        lines.append("Try a hotter day or a faster fill and see how close you can get to the limit.")
    body = "".join(f"<p>{x}</p>" for x in lines)
    return f'<div class="card what"><h3>What happened, and why</h3>{body}</div>'


# ---- the screen ---------------------------------------------------------------------------------------------
def render_run_screen(ns: str, preset: FillConfig, mission=None, locked: set | None = None, result_block=None) -> None:
    """The scene with the panel beside it."""
    sim_key, play_key, saved_key, run_key = _k(ns, "sim"), _k(ns, "playing"), _k(ns, "saved"), _k(ns, "run")
    # Simulate follows the hydrogen on to the fuel cell after the fill, so its Guided cards end with the fuel cell
    # choice. A level supplies its own result block and stops at the fill, so it keeps the four fill cards.
    with_fuel_cell = result_block is None
    n_steps = len(guided_steps(with_fuel_cell))
    if with_fuel_cell:
        fuelcell.warm()
    left, right = st.columns([2.2, 1], gap="medium")

    def fresh(cfg):
        st.session_state[_k(ns, "cfg0")] = copy.deepcopy(cfg)
        st.session_state[sim_key] = FillSimulation(cfg)
        st.session_state[play_key] = False
        st.session_state[saved_key] = False
        st.session_state[run_key] = st.session_state.get(run_key, 0) + 1

    with right:
        with st.container(key=f"panel_{ns}"):
            existing = st.session_state.get(sim_key)
            started = existing is not None and existing.t > 0
            cfg = build_config(ns, preset, locked, started=started, with_fuel_cell=with_fuel_cell)
            if sim_key not in st.session_state:
                fresh(cfg)
            elif not started and st.session_state.get(_k(ns, "cfg0")) != cfg:
                # Nothing has flowed yet, so every choice (the weather, how empty the car is, the banks, the tank)
                # must reach the model. Once the fill starts only the live settings below can change.
                fresh(cfg)
            sim: FillSimulation = st.session_state[sim_key]
            apply_live_settings(sim, cfg)
            playing = st.session_state[play_key] and not sim.finished
            guided = st.session_state.get("path") == "Guided"
            step_key = _k(ns, "gstep")
            step = n_steps if sim.t > 0 else min(st.session_state.get(step_key, 0), n_steps)
            gap(8)
            if guided and step < n_steps:
                b1, b2 = st.columns(2, gap="small")
                if b1.button("Back", key=_k(ns, "gback"), disabled=step == 0, width="stretch"):
                    st.session_state[step_key] = step - 1
                    st.rerun()
                if b2.button("Next", type="primary", key=_k(ns, "gnext"), width="stretch"):
                    st.session_state[step_key] = step + 1
                    st.rerun()
            else:
                b1, b2, b3 = st.columns([1.3, 1, 1], gap="small")
                if b1.button("Start" if not playing else "Running", type="primary", key=_k(ns, "start"), disabled=playing or sim.finished, width="stretch"):
                    st.session_state[play_key] = True
                    st.rerun()
                if b2.button("Pause", key=_k(ns, "pause"), disabled=not playing, width="stretch"):
                    st.session_state[play_key] = False
                    st.rerun()
                if b3.button("Reset", key=_k(ns, "reset"), width="stretch"):
                    fresh(cfg)
                    st.rerun()
                if st.button("Skip to the end", key=_k(ns, "finish"), disabled=sim.finished, width="stretch"):
                    sim.run()
                    st.session_state[play_key] = False
                    st.rerun()
                s1, s2 = st.columns([1, 2.4], gap="small", vertical_alignment="center")
                s1.markdown('<p class="small">Speed</p>', unsafe_allow_html=True)
                with s2:
                    st.segmented_control("Playback speed", list(SPEEDS.keys()), default="4×", key=_k(ns, "speed"), label_visibility="collapsed")
                if guided and not playing:
                    if st.button("Change my choices", key=_k(ns, "gagain"), type="tertiary", width="stretch"):
                        fresh(cfg)
                        st.session_state[step_key] = 0
                        st.rerun()

    with left:
        sim = st.session_state[sim_key]
        playing = st.session_state[play_key] and not sim.finished

        @st.fragment(run_every=TICK if playing else None)
        def live():
            sim = st.session_state[sim_key]
            speed = SPEEDS.get(st.session_state.get(_k(ns, "speed")) or "4×", 4.0)
            if st.session_state[play_key] and not sim.finished:
                sim.advance(speed * TICK)
            just_finished = sim.finished and st.session_state[play_key]
            if just_finished:
                st.session_state[play_key] = False
            scene.render(sim, ns, st.session_state[play_key] and not sim.finished, speed, st.session_state[run_key])
            if sim.finished:
                ok = not sim.aborted
                jump = '<a class="jump" href="#results" target="_self">See what happened &darr;</a>' if result_block is None else ""
                st.markdown(f'<div class="card done-line"><span><span class="{"pass" if ok else "fail"}">{"Fill complete" if ok else "Fill stopped"}</span>'
                            f'<span class="muted"> at {sim.t:.1f} s. {pretty(sim.end_reason)}.</span></span>{jump}</div>', unsafe_allow_html=True)
                if result_block is not None:
                    result_block(sim)
            with st.expander("Event log and energy balance"):
                e1, e2 = st.columns(2, gap="large")
                e1.markdown("<h3>Event log</h3>" + _events_html(sim), unsafe_allow_html=True)
                e2.markdown("<h3>Energy balance</h3>" + (_energy_html(sim) if sim.t > 0 else '<p class="small">Available once the fill starts.</p>'),
                            unsafe_allow_html=True)
            if just_finished:
                st.rerun()

        live()

    # Under the scene, full width: the station's checks, where this hydrogen came from and goes, and the comparison.
    if st.session_state[sim_key].finished and result_block is None:
        if st.session_state.get("tours_offered", {}).get("results", 0) < 2:
            tour.request("results", tour.results_tour(ns))
        _after_fill(ns, sim_key, run_key)


@st.fragment
def _after_fill(ns: str, sim_key: str, run_key: str) -> None:
    """Its own fragment, so changing a choice here redraws only this part and not the scene."""
    from . import compare, journey  # here, because both import helpers from this module

    sim = st.session_state[sim_key]
    gap(24)
    with st.container(key=f"{ns}__what"):
        st.markdown('<div id="results" class="anchor"></div>' + _what_happened(sim), unsafe_allow_html=True)
    gap(24)
    journey.render_after_fill(sim, ns)
    compare.render_block(sim, ns, st.session_state[run_key])
