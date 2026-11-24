"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/explained.py

What this file does
    The How it works page. The top half is for anyone: the idea in plain words
    and why hydrogen cars are still rare. The bottom half is the working,
    folded away until someone wants it: every term, a fill checked by hand,
    the one-variable experiments, the accuracy checks, the assumptions and the
    sources.

Where it fits in the model
    It is where the model is explained and defended. The experiments come from
    h2lab/investigations.py, the accuracy checks from h2lab/validation.py and
    the hand calculation from ui/handcalc.py.
"""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from h2lab import investigations as inv
from h2lab import validation as val

from h2lab.simulation import FillConfig, FillSimulation

from . import handcalc, plots
from .styles import gap, rows_html, stat_row
from .glossary import TERMS
from .text import MDOT, minus, pct, plain, pretty

# the old study names, asked as plain questions
QUESTIONS = {
    "precool": "What if the precooler is weaker?",
    "aprr": "What if the fill is faster?",
    "tamb": "What if the day is hotter?",
    "p0": "What if the car arrives emptier?",
    "kp": "What if the controller reacts harder?",
}
PROPERTY_QUESTION = "What if hydrogen were an ideal gas?"


def _section(title: str, why: str, first: bool = False) -> None:
    if not first:
        gap(40)
    st.markdown(f'<div class="chapter"><h1>{title}</h1><p class="why">{why}</p></div>', unsafe_allow_html=True)
    gap(8)


def render(sim) -> None:
    """The whole page. sim is the Simulate fill if one has been run."""
    _, body, _ = st.columns([0.55, 4, 0.55], gap="medium")
    with body:
        gap(8)
        _section("How it works", "What happens when a hydrogen car fills up, in plain words. About two minutes to read.", first=True)
        render_idea()
        _section("Why hydrogen cars are still rare", "The physics works. These are the things that hold it back, with the source for each number.")
        render_limits_world()
        gap(16)
        with st.expander("Words: every term the app uses, in plain English"):
            render_words()

        _section("The working", "Everything behind the numbers, for anyone who wants to check them. Open what you need.")
        with st.expander("Check a fill by hand, with the formulas from the course"):
            reference = sim is None or sim.t == 0.0
            if reference:
                if "hand_demo_sim" not in st.session_state:
                    demo = FillSimulation(FillConfig(property_mode="real", dt=0.1))
                    demo.advance(90.0)
                    st.session_state["hand_demo_sim"] = demo
                sim = st.session_state["hand_demo_sim"]
            handcalc.render_handcalc(sim, reference)
            if reference:
                st.markdown('<p class="small" style="margin-top:8px">Run a fill in Simulate and this follows your own numbers.</p>', unsafe_allow_html=True)
        gap(8)
        with st.expander("Experiments: change one thing and see what it does"):
            render_experiments()
        gap(8)
        with st.expander("Accuracy: does the model keep count, and does it match a real test?"):
            render_accuracy()
        gap(8)
        with st.expander("Assumptions, and what the model cannot tell you"):
            render_limits_model()
            gap(16)
            render_assumptions()
        gap(8)
        with st.expander("Sources: where each number comes from"):
            render_references()


IDEA = [
    ("A hydrogen car", "A hydrogen car is an electric car that makes its own electricity. Hydrogen gas from a tank meets air in a fuel cell, and "
     "the reaction gives electricity and water. To carry enough hydrogen for 500 km or so, the tank is filled to 70 MPa, the 700 bar written on the "
     "pumps: about 700 times the pressure of the air around you."),
    ("The problem", "Push gas into a closed tank and it gets hot. A bike pump warms for the same reason. The gas already inside is squeezed, and the "
     "gas coming in brings the work done pushing it in, which ends up as heat. Fill an empty, insulated tank from 25 °C and the gas would reach about "
     "147 °C. The car's tank, plastic wrapped in carbon fibre, is only allowed to reach 85 °C."),
    ("What a station does about it", "A station keeps hydrogen in three big storage tanks, called banks, at different pressures. It fills from the "
     "lowest one first and moves up, which saves energy. The gas passes a valve that controls how fast it flows, then a precooler that chills it to "
     "as low as −40 °C, so it arrives cold enough to offset the heating. The precooler runs by itself: it is set to a delivery temperature and takes "
     "out just enough heat to hold it, up to its cooling capacity. The rules every station follows (SAE J2601) set how fast the pressure may "
     "rise so a car fills in about three minutes without passing 85 °C."),
    ("What you can do here", "Pick Guided or Engineer, choose the weather, how empty the car is, how fast to fill, when to stop and which fuel cell is in the car, then watch the gas flow "
     "and the tank heat up. When the fill ends the app tells you what happened and why, checks the fill the way a real station is checked, and follows the "
     "same hydrogen back to the machine that made it and forward to the fuel cell that uses it. Levels give you a job to do."),
    ("Why I built this", "In summer 2026 I was a research intern at RWTH Aachen University, a technical university in Germany, on the EU DECODE project. "
     "I built a lifecycle cost framework there for four hydrogen technologies: two electrolysers, which make hydrogen from water (PEWE and AEWE), and two fuel "
     "cells, which turn it back into electricity (PEFC and AEFC). Those are the choices you get around every fill: the fuel cell before it, in Guided, and both again after it. The year before, at RCT Solutions, a German "
     "solar consulting company, I built the build-cost and running-cost models for a factory, which is how the cost of a kilogram is split here. I have also "
     "helped commission a solar cell factory, where nothing is handed over until its list of checks is closed; the station checks after each fill are drawn "
     "the same way. All of it taught me that the cost of the equipment decides whether a technology spreads, and this app is the thermodynamics underneath "
     "that question for hydrogen."),
]


def render_idea() -> None:
    with st.container(key="explain_card_idea"):
        html = "".join(f'<h3{" style=\"margin-top:24px\"" if i else ""}>{t}</h3><p>{x}</p>' for i, (t, x) in enumerate(IDEA))
        st.markdown(html, unsafe_allow_html=True)


def render_words() -> None:
    with st.container(key="explain_card_words"):
        st.markdown(rows_html([(k, pretty(v)) for k, v in TERMS.items()], left=True), unsafe_allow_html=True)


MODEL_LIMITS = [
    ("One temperature for the whole tank",
     "The model treats the gas in the car's tank as one uniform lump. A real tank is hotter at the far end than near the inlet, and the sensor on "
     "the tank reads below the true average [9]. The model also heats too fast in the first 30 seconds."),
    ("One fitted number sets the end temperature",
     "How fast heat soaks from the gas into the tank wall (h<sub>in</sub>) is not measured here. With the published average of 80 W/(m² K) [7], "
     "the 29 L lab test [5] ends about 21 K too hot; the model matches it within 1 K only with that value raised to 200. So the end temperature is "
     "only as good as that one choice."),
    ("Some station sizes are design choices",
     "The bank sizes and pressures, the valve opening and the station compressor's flow are design choices, not values from a real station. "
     "They are sensible, but another station would differ."),
    ("A simplified fridge and valve",
     "The refrigeration cycle is the ideal textbook cycle with one compressor efficiency, and the valve uses a fixed flow coefficient. Real "
     "equipment has losses these leave out."),
    ("Not a safety tool",
     "This is a teaching model of one car at a time. Real stations use the J2601 tables, tested on real tanks, to decide how fast to fill."),
]

INDUSTRY = [
    ("Stations are expensive",
     "A typical recent station costs about $1.9 million to build, roughly $1,200 to $3,000 for each kilogram per day it can dispense [13]. A petrol "
     "pump costs a small fraction of that."),
    ("Few cars, few stations",
     "California, the biggest market in the US, had 61 hydrogen stations in August 2025 and about 14,000 hydrogen cars on the road [14]. "
     "Few cars means stations sell little hydrogen, so each kilogram carries a big share of the station's cost; few stations means few people buy the cars."),
    ("Squeezing and chilling cost energy",
     "Compressing hydrogen to 70 MPa takes about 1.4 kWh per kg in theory and around 3 kWh per kg in practice [15]. The precooler and its heat "
     "exchanger are about a tenth of a station's equipment cost [16]. For scale, a kilogram of hydrogen holds about 33 kWh [15]."),
    ("The fuel is expensive and supply is fragile",
     "California pump prices passed $34 per kilogram in late 2024 [17], and a car takes about 5 kg. Stations have been shut for days by "
     "maintenance, equipment failures and hydrogen supply disruptions [18]."),
    ("What this app shows about it",
     "The precooler and the slow, careful ramp you fight with in Levels are part of that cost: every station needs a fridge running at −40 °C "
     "and a controller that cannot fill faster than the tank allows. Battery cars avoid both. After every fill the app puts numbers on it: it follows "
     "one kilogram from the electrolyser to the fuel cell and shows what each step takes in electricity and what the station adds in cost."),
]


def render_limits_model() -> None:
    with st.container(key="explain_card_limits_model"):
        html = "<h2>What the model cannot tell you</h2>"
        html += "".join(f'<h3 style="margin-top:24px">{t}</h3><p>{x}</p>' for t, x in MODEL_LIMITS)
        st.markdown(html, unsafe_allow_html=True)


def render_limits_world() -> None:
    with st.container(key="explain_card_limits_world"):
        html = "".join(f'<h3{" style=\"margin-top:24px\"" if i else ""}>{t}</h3><p>{x}</p>' for i, (t, x) in enumerate(INDUSTRY))
        st.markdown(html, unsafe_allow_html=True)


_SCI = re.compile(r"(-?\d+(?:\.\d+)?)e([-+]?\d+)\s*%")


def _tidy_value(s: str) -> str:
    """Percentages a reader can use: tiny values become 'below 0.01%'; everything else is prettified."""
    s = s.replace("< 1e-6 %", "below 0.000001%")

    def rep(m):
        v = float(m.group(1))
        return pct(v) if abs(v) < 0.01 else m.group(0).replace(" %", "%")
    s = _SCI.sub(lambda m: pct(float(f"{m.group(1)}e{m.group(2)}")), s)
    s = re.sub(r"(-?\d+(?:\.\d+)?) ?%", rep, s)
    return minus(pretty(s).replace("< ", "below ").replace("below below", "below"))


# ---------------------------------------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _cached_study(key: str, mode: str):
    study = next(s for s in inv.STUDIES if s.key == key)
    res = inv.run_study(study, mode)
    return {"rows": res["rows"], "series": res["series"]}


def render_experiments() -> None:
    titles = [QUESTIONS[s.key] for s in inv.STUDIES] + [PROPERTY_QUESTION]
    pick = st.selectbox("Experiment", titles, key="inv_pick", label_visibility="collapsed")
    if pick != PROPERTY_QUESTION:
        study = inv.STUDIES[titles.index(pick)]
        values = ", ".join("off" if v is None else f"{v:g}".replace("-", "−") for v in study.values)
        with st.container(key=f"explain_card_exp_{study.key}"):
            st.markdown(f'<h3>{pick}</h3><p class="scene-text" style="max-width:68ch">{pretty(study.note)}</p>'
                        f'<p class="small" style="margin:8px 0 16px 0">{plain(study.parameter)} set to {values} {plain(study.unit)}. '
                        f'Six fills, about ten seconds.</p>', unsafe_allow_html=True)
            if st.button("Run the experiment", key=f"run_{study.key}", type="primary"):
                st.session_state[f"ran_{study.key}"] = True
            if st.session_state.get(f"ran_{study.key}"):
                with st.spinner("Running each fill"):
                    data = _cached_study(study.key, "real")
                curves = [(f"{s_['label']} {plain(study.unit)}".replace("-", "−") if s_["label"] != "off" else "off", s_["t"], s_["T"]) for s_ in data["series"]]
                st.markdown('<p class="small" style="margin-top:16px">Tank gas temperature for each fill</p>', unsafe_allow_html=True)
                st.plotly_chart(plots.fig_family(curves, "°C", 85.0, "85 °C limit"), width="stretch", key=f"plot_inv_{study.key}", config=plots.PLOT_CONFIG)
                df = pd.DataFrame(data["rows"])[["label", "T_peak_C", "fill_time_s", "soc_final", "E_ref_kWh_per_kg", "rms_error_MPa", "end_reason"]]
                df["end_reason"] = df["end_reason"].map(plain)
                df.columns = [f"{plain(study.parameter)}, {plain(study.unit)}", "Peak temperature, °C", "Fill time, s", "Final charge, %",
                              "Refrigeration energy, kWh/kg", "Ramp error (RMS), MPa", "How it ended"]
                st.dataframe(df.round(2), hide_index=True, width="stretch")
    else:
        with st.container(key="explain_card_exp_pm"):
            st.markdown(f'<h3>{pick}</h3><p class="scene-text" style="max-width:68ch">The same fill with the ideal-gas model of the course (Table A.5) and '
                        'with real-gas properties. At 70 MPa real hydrogen takes up about 1.5 times the volume the ideal gas law predicts, so the ideal '
                        'model stores about 50% too much mass at a given pressure. It also misses the warming across the valve.</p>'
                        '<p class="small" style="margin:8px 0 16px 0">Two fills, about five seconds.</p>', unsafe_allow_html=True)
            if st.button("Run the experiment", key="run_pm", type="primary"):
                st.session_state["ran_pm"] = True
            if st.session_state.get("ran_pm"):
                with st.spinner("Running both fills"):
                    res = _cached_property_study()
                a, b = res["ideal"], res["real"]
                view = st.segmented_control("View", ["Gas temperature", "Mass in tank"], default="Gas temperature", key="pm_view", label_visibility="collapsed") or "Gas temperature"
                st.plotly_chart(plots.fig_compare(view, a.series, b.series, "Ideal gas", "Real gas"), width="stretch", key="plot_inv_pm", config=plots.PLOT_CONFIG)
        if st.session_state.get("ran_pm"):
            gap(8)
            stat_row([("Ideal gas, peak temperature, °C", f"{a.T_peak - 273.15:.1f}", f"{a.m_added:.2f} kg in {a.fill_time:.0f} s"),
                      ("Real gas, peak temperature, °C", f"{b.T_peak - 273.15:.1f}", f"{b.m_added:.2f} kg in {b.fill_time:.0f} s"),
                      ("Mass difference, %", f"{100 * (a.m_added / b.m_added - 1):+.0f}", "ideal relative to real")])


@st.cache_resource(show_spinner=False)
def _cached_property_study():
    return inv.run_property_mode_study()


# ---------------------------------------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _cached_checks():
    return val.all_checks()


@st.cache_data(show_spinner=False)
def _cached_jrc():
    out = val.jrc_comparison()
    return {"test": out["test"], "best_h": out["best_h"],
            "runs": {h: {"t": r.series["t"], "T": r.series["T_car"] - 273.15, "T_end": r.series["T_car"][-1] - 273.15,
                         "t_end": r.fill_time, "T_peak": r.T_peak - 273.15} for h, r in out["runs"].items()}}


def render_accuracy() -> None:
    with st.container(key="explain_card_checks"):
        st.markdown('<h3>Physics checks</h3><p class="scene-text" style="max-width:68ch">An empty insulated tank must end at k times the inlet '
                    'temperature. The mass that leaves the banks must equal the mass that enters the car. The energy balance must close. Halving the time '
                    'step must change nothing that matters. A 141 L tank at 70 MPa and 15 °C must hold 5.7 kg.</p>'
                    '<p class="small" style="margin:8px 0 16px 0">They run live on this computer, for the ideal-gas and the real-gas model, in about 20 seconds.</p>', unsafe_allow_html=True)
        if st.button("Run the checks", type="primary", key="val_run") or "checks_done" in st.session_state:
            st.session_state["checks_done"] = True
            with st.spinner("Running the checks"):
                checks = _cached_checks()
            passed = sum(1 for c in checks if c["passed"])
            st.markdown(f'<p style="margin:16px 0 8px 0"><span class="{"pass" if passed == len(checks) else "fail"}">{passed} of {len(checks)} passed</span></p>',
                        unsafe_allow_html=True)
            rows = []
            for c in checks:
                ok = c["passed"]
                rows.append((pretty(c["name"]), f'<span class="{"pass" if ok else "fail"}">{"Pass" if ok else "Fail"}</span>'
                             f'<span class="muted" style="font-weight:400">, {_tidy_value(str(c["value"]))} against {_tidy_value(str(c["target"]))}</span>'))
            st.markdown(rows_html(rows), unsafe_allow_html=True)
    gap(16)
    t = val.JRC_TEST
    with st.container(key="explain_card_jrc"):
        st.markdown(f'<h3>Against a published fill test</h3><p class="scene-text" style="max-width:68ch">The JRC GasTeF laboratory, a European Commission '
                    f'hydrogen test site, filled a {t["volume_L"]} L tank twelve times from {t["P0_MPa"]} to {t["P_end_MPa"]} MPa at {t["aprr_MPa_min"]} MPa/min '
                    f'with no precooling [5]. The gas warmed from {t["T0_C"]} to {t["T_end_C"]} °C in {t["fill_time_s"]:.0f} s, a rise of {t["dT_K"]} K with '
                    f'a scatter of {t["dT_sd_K"]} K between tests.</p><p class="small" style="margin:8px 0 16px 0">Three fills, about ten seconds.</p>',
                    unsafe_allow_html=True)
        if st.button("Run the comparison", key="jrc", type="primary") or "jrc_done" in st.session_state:
            st.session_state["jrc_done"] = True
            with st.spinner("Running three fills with different wall coefficients"):
                out = _cached_jrc()
            curves = [(f"Model, h<sub>in</sub> = {h:.0f} W/(m² K)", r_["t"], r_["T"]) for h, r_ in sorted(out["runs"].items())]
            fig = plots.fig_family(curves, "°C", 85.0, "85 °C limit", height=380, limit_side="left")
            import plotly.graph_objects as go
            fig.add_trace(go.Scatter(x=[0, t["fill_time_s"]], y=[t["T0_C"], t["T_end_C"]], mode="markers", name="JRC test, start and end",
                                     marker=dict(color="#1D1D1F", size=10, symbol="diamond"),
                                     error_y=dict(type="data", array=[0, t["dT_sd_K"]], visible=True, color="#1D1D1F"), hoverinfo="skip"))
            st.plotly_chart(fig, width="stretch", key="plot_jrc", config=plots.PLOT_CONFIG)
            rows = [{"Gas to wall, W/(m² K)": h, f"Model at {t['fill_time_s']:.0f} s, °C": round(r_["T_end"], 1), "Model peak, °C": round(r_["T_peak"], 1),
                     f"Test at {t['fill_time_s']:.0f} s, °C": t["T_end_C"], "Difference, K": round(r_["T_end"] - t["T_end_C"], 1)}
                    for h, r_ in sorted(out["runs"].items())]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            best = out["runs"][out["best_h"]]
            lit = out["runs"][80.0]
            st.markdown(f'<h3 style="margin-top:16px">Reading the result</h3><p style="max-width:68ch">The model has one fitted number, the gas-to-wall heat transfer '
                        f'coefficient. With the published value of 80 W/(m² K), fitted to 117 and 249 L tanks [7], the {t["volume_L"]} L test tank ends '
                        f'{minus(format(lit["T_end"] - t["T_end_C"], "+.1f"))} K too hot. With {out["best_h"]:.0f} W/(m² K) the model ends at {best["T_end"]:.1f} °C against '
                        f'{t["T_end_C"]} °C measured, a difference of {minus(format(best["T_end"] - t["T_end_C"], "+.1f"))} K when the test itself scatters by {t["dT_sd_K"]} K. '
                        f'A small tank has more wall area per kilogram of gas and a stronger inlet jet, so a higher coefficient is the expected direction.</p>'
                        f'<p style="max-width:68ch">The shape differs. The model heats to near its end value within the first 30 s, because one uniform gas '
                        f'temperature with a constant coefficient cannot reproduce the gradual mixing of cold incoming gas that the sensors see. The end state, '
                        f'which decides whether a fill is legal, is reproduced within the test scatter once the coefficient is fitted. The early part errs on '
                        f'the hot side. The 141 L tank in the levels keeps the published 80 W/(m² K), since it sits in the size range that value was fitted to.</p>',
                        unsafe_allow_html=True)


# ---------------------------------------------------------------------------------------------------------------
ASSUMPTIONS = [
    ("Working fluid", [
        ("Ideal gas with constant specific heats, in textbook mode",
         "R = 4.1243 kJ/kg K, c<sub>p</sub> = 14.209 kJ/kg K, c<sub>v</sub> = 10.085 kJ/kg K and k = 1.409 from Table A.5 at 300 K [1].",
         "It matches the hand calculations of the course.",
         "Hydrogen's c<sub>p</sub> is nearly flat from 250 to 400 K, so the constant-c<sub>p</sub> error is small. The equation of state is the problem: "
         "at 70 MPa and 15 °C the compressibility factor is 1.5, so ideal-gas mode stores about 50% too much mass and the fill ends at 100% charge near 53 MPa."),
        ("Real gas from CoolProp, in real-gas mode",
         "Helmholtz-energy equation of state for normal hydrogen [11, 12].",
         "It is the formulation NIST uses and the default for every level and study.",
         "Reference-state offsets make absolute u and h differ from the textbook tables; every difference and every balance agrees."),
    ]),
    ("Storage banks and vehicle tank", [
        ("Uniform state in each tank",
         "One pressure and one temperature for the gas in a tank at any instant.",
         "It is the control-volume assumption of the course and of the SAE J2601 lumped models [2].",
         "Real tanks stratify: late in a fill the gas near the top can run several kelvin above the average [9]."),
        ("Rigid tanks, no kinetic or potential energy",
         "W = 0 for every tank; velocity and height terms are dropped.",
         "The hose velocity head is a few kJ/kg against enthalpy changes of hundreds.",
         "Negligible."),
        ("Lumped tank wall",
         "The liner and composite are one mass at one temperature, exchanging heat with the gas through h<sub>in</sub>A and with the ambient through "
         "h<sub>out</sub>A. Defaults h<sub>in</sub> = 80 W/(m² K) and h<sub>out</sub> = 20 W/(m² K) [7]; liner and composite properties from [8].",
         "A one-temperature wall keeps the energy equation to the three unknowns the course uses.",
         "The composite only warms through about 14 mm in four minutes, so lumping slightly overstates the early heat sink; a constant coefficient makes "
         "the first seconds too hot. With the published 80 W/(m² K) the 29 L lab test ends about 21 K too hot; it matches within 1 K only with h<sub>in</sub> raised to 200 (Accuracy checks)."),
        ("Banks are insulated during a fill",
         "No heat transfer for the storage banks over a three-minute fill.",
         "Large steel vessels change temperature slowly against their mass.",
         "Bank gas cools a few kelvin more than it would with wall heat input; the valve inlet temperature is slightly low."),
        ("Cascade switching",
         "The station draws from the lowest bank whose pressure exceeds the car pressure by the switch margin, then moves up. Gas leaves at the bank's own state.",
         "That is how cascade stations run; it keeps the high bank for the end of the fill.",
         "Bank sizes and pressures are design choices, not cited values."),
    ]),
    ("Dispenser valve", [
        ("Steady flow at each time step",
         "The valve holds negligible mass, so it is solved with the steady-flow energy equation while the tanks it connects change state.",
         "This is the category 6 structure: steady devices between transient control volumes.",
         "Exact for a device whose residence time is milliseconds."),
        ("Throttle: h<sub>e</sub> = h<sub>i</sub>, choked isentropic flow",
         "Exit at the hose pressure, taken equal to the car pressure. Flow follows the isentropic nozzle relation with the ideal-gas k and the real upstream "
         "density, with a fixed discharge coefficient of 0.85.",
         "A throttle does no work and exchanges no heat; choked flow makes the rate depend on the upstream state alone.",
         "The seat area and discharge coefficient are design choices; the controller compensates for them."),
    ]),
    ("Precooler and refrigeration cycle", [
        ("Precooler holds a set point up to a capacity",
         "Hydrogen leaves at the set point while the load stays below the refrigeration capacity; above it the exit enthalpy is h<sub>in</sub> minus "
         "Q<sub>max</sub>/ṁ. Pressure drop neglected.",
         "J2601 dispensers hold the gas inside a delivery temperature window [10]; the chiller behind it has a fixed capacity.",
         "Capacity limits show up as a warm delivery on hot days, which is the physics behind the hot-day level."),
        ("Ideal vapor-compression cycle",
         "Saturated vapour at the evaporator exit, saturated liquid at the condenser exit, isenthalpic throttle, compressor with an isentropic efficiency.",
         "It is the cycle of the course [1] and gives a COP and a compressor power for every kilowatt removed.",
         "Superheat, subcooling and pressure drops are left out; the evaporator has to sit below the hydrogen set point and the condenser above ambient, "
         "and an impossible pair is reported, not computed."),
    ]),
    ("Station compressor", [
        ("Two adiabatic stages with equal pressure ratio and an intercooler",
         "Isentropic efficiency 0.70 per stage; intercooler back to ambient plus 10 K.",
         "Equal pressure ratios minimise two-stage work with ideal intercooling; 0.70 is a design choice, not a cited value.",
         "Used after each fill to work out the electricity that lifting the hydrogen into the banks took."),
    ]),
    ("Limits and control", [
        ("SAE J2601 limits as hard stops",
         "85 °C gas, 87.5 MPa and 100% charge stop the fill; 60 g/s clips the valve; the delivery window (T40: −40 to −33 °C) and a 10 K temperature "
         "margin raise warnings [2, 3, 4].",
         "A real dispenser aborts on these limits.",
         "The 18.5 MPa/min default ramp is the look-up table example in [3]; real tables depend on tank size, ambient and delivery temperature."),
    ]),
    ("Numerical method", [
        ("Explicit midpoint integration",
         "Second-order Runge-Kutta on (m, U, T<sub>wall</sub>) for each tank, default step 0.1 s; the property model recovers T and P from (ρ, u) at every stage.",
         "Second order keeps the error proportional to the square of the step.",
         "Halving the step changes the peak temperature by less than 0.2 K (Accuracy checks)."),
    ]),
]


def render_assumptions() -> None:
    for n, (group, items) in enumerate(ASSUMPTIONS):
        with st.container(key=f"explain_card_assume_{n}"):
            html = f"<h2>{group}</h2>"
            for title, what, why, changes in items:
                html += f'<h3 style="margin-top:24px">{title}</h3>' + rows_html([("Assumed", what.replace("ṁ", MDOT)), ("Why", why), ("What it changes", changes)], left=True)
            st.markdown(html, unsafe_allow_html=True)
        gap(16)


REFERENCES = [
    ("C. Borgnakke and R. E. Sonntag, <i>Fundamentals of Thermodynamics</i>, Wiley. Control-volume chapter, refrigeration cycles, Table A.5 (hydrogen) and Table B.5 (R-134a).", ""),
    ("SAE International, <i>SAE J2601 (May 2020): Fueling Protocols for Light Duty Gaseous Hydrogen Surface Vehicles</i>, 2020. T40, T30 and T20 categories; "
     "three-minute and 95 to 100% charge targets.", "https://www.sae.org/standards/content/j2601_202005/"),
    ("K. Reddi, A. Elgowainy, N. Rustagi and E. Gupta, 'Impact of hydrogen SAE J2601 fueling methods on fueling time of light-duty fuel cell electric vehicles', "
     "<i>International Journal of Hydrogen Energy</i>, vol. 42, 2017. Limits of −40 to 85 °C, 87.5 MPa and 60 g/s; 18.5 MPa/min ramp example; 129 L tank at 40.2 kg/m³.",
     "https://www.osti.gov/pages/servlets/purl/1389635"),
    ("U.S. Department of Energy, <i>Light Duty Fuel Cell Electric Vehicle Hydrogen Fueling Protocol</i>, overview slides. 85 °C, 87.5 MPa, three-minute ramp, never 100% charge.",
     "https://www.energy.gov/eere/fuelcells/downloads/light-duty-fuel-cell-electric-vehicle-hydrogen-fueling-protocol"),
    ("B. Acosta-Iborra, P. Moretto, N. De Miguel, R. Ortiz, F. Harskamp and C. Bonato, 'JRC reference data from experiments of on-board hydrogen tanks fast filling', "
     "<i>5th International Conference on Hydrogen Safety</i>, Brussels, 2013. The 28.9 L Type IV repeatability test used under Accuracy checks.",
     "https://h2tools.org/sites/default/files/2019-08/presentation_111.pdf"),
    ("N. De Miguel, B. Acosta, P. Moretto, F. Harskamp and C. Bonato, 'Experimental study of the thermal behaviour of hydrogen tanks during hydrogen cycling', "
     "<i>5th International Conference on Hydrogen Safety</i>, Brussels, 2013. 87.5 MPa as 125% of nominal working pressure; 40.2 g/L at 70 MPa and 15 °C.",
     "https://h2tools.org/sites/default/files/2019-08/paper_228.pdf"),
    ("'Lumped Parameter Modeling of SAE J2601 Hydrogen Fueling Tests', <i>Sustainability</i>, vol. 15, no. 2, 1448, 2023. Dual-zone lumped model: 80 W/(m² K) gas to wall "
     "averaged over a fill, 20 W/(m² K) wall to ambient.", "https://www.mdpi.com/2071-1050/15/2/1448"),
    ("Saga University, Institute of Ocean Energy, <i>CFD of real-time filling of a 39.1 L Type IV hydrogen tank at 70 MPa</i>. Liner 1286 kg/m³, 1578 J/kg K, 1.17 W/m K; "
     "CFRP 1375 kg/m³, 1075 J/kg K, 1.14 W/m K; 3 mm liner, 22 mm laminate.", "https://www.ioes.saga-u.ac.jp/jp/files/uploads/19-5.pdf"),
    ("N. Klopcic, T. Hafner, D. Schiffer, P. Pertl and A. Trattner, 'Experimental and Simulative Evaluation of Temperature Increase During Fast Filling of CGH2 Tanks', "
     "<i>Hydrogen Safety</i>, vol. 2, 2025. Stratification in 60 to 320 L tanks; the on-tank sensor under-reads the average.", "https://doi.org/10.58895/hysafe.28"),
    ("U.S. Patent 10,794,538, <i>Process for refilling a gas tank and gas supply system</i>. The J2601 T40 delivery window of −33 to −40 °C after about 40 s of fuelling.",
     "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10794538"),
    ("I. H. Bell, J. Wronski, S. Quoilin and V. Lemort, 'Pure and pseudo-pure fluid thermophysical property evaluation and the open-source library CoolProp', "
     "<i>Industrial and Engineering Chemistry Research</i>, vol. 53, 2014. Property source for real-gas hydrogen and the refrigerants.", "https://coolprop.org"),
    ("J. W. Leachman, R. T. Jacobsen, S. G. Penoncello and E. W. Lemmon, 'Fundamental equations of state for parahydrogen, normal hydrogen and orthohydrogen', "
     "<i>Journal of Physical and Chemical Reference Data</i>, vol. 38, 2009. The hydrogen equation of state inside CoolProp.", ""),
    ("M. Koleva and M. Melaina, <i>Hydrogen Fueling Stations Cost</i>, DOE Hydrogen Program Record 21002, U.S. Department of Energy, 2020. "
     "Median capital cost of about $1.9 million; $1,200 to $3,000 per kg/day of capacity.", "https://www.hydrogen.energy.gov/pdfs/21002-hydrogen-fueling-station-cost.pdf"),
    ("California Air Resources Board, <i>2025 Annual Evaluation of Fuel Cell Electric Vehicle Deployment and Hydrogen Fuel Station Network Development</i>, "
     "2025. 61 stations as of 29 August 2025; 14,128 registered fuel cell cars by April 2025.", "https://ww2.arb.ca.gov/resources/documents/annual-hydrogen-evaluation"),
    ("U.S. Department of Energy, <i>Energy Requirements for Hydrogen Gas Compression and Liquefaction as Related to Vehicle Storage Needs</i>, "
     "DOE Hydrogen Program Record 9013. 1.35 kWh/kg ideal to 700 bar; about 3.1 kWh/kg measured at demonstration stations; 33.3 kWh/kg lower heating value.",
     "https://www.hydrogen.energy.gov/pdfs/9013_energy_requirements_for_hydrogen_gas_compression.pdf"),
    ("A. Elgowainy and K. Reddi, <i>Hydrogen Fueling Station Pre-Cooling Analysis</i>, Argonne National Laboratory, DOE Annual Merit Review, 2015. "
     "Precooler plus heat exchanger about 10% of station equipment cost.", "https://www.hydrogen.energy.gov/pdfs/review15/pd107_elgowainy_2015_o.pdf"),
    ("Hydrogen Central, reporting S&amp;P Global Platts, <i>California hydrogen pump prices for light-duty vehicles reach new highs</i>, October 2024. "
     "Monthly average $34.55/kg on 1 October 2024.", "https://hydrogen-central.com/california-hydrogen-pump-prices-for-light-duty-vehicles-reach-new-highs/"),
    ("California Energy Commission, <i>Joint Agency Staff Report on Assembly Bill 126</i>, CEC-600-2025-025, 2025. Station downtime from maintenance, "
     "equipment failures, supply chain constraints and hydrogen supply disruptions.", "https://www.energy.ca.gov/sites/default/files/2025-06/CEC-600-2025-025.pdf"),
    ("International Renewable Energy Agency (IRENA), <i>Green Hydrogen Cost Reduction: Scaling up Electrolysers to Meet the 1.5 °C Climate Goal</i>, 2020. "
     "Electricity used by a whole electrolyser system in 2020: 50 to 83 kWh/kg for PEM, 57 to 69 kWh/kg for AEM.", "https://www.irena.org/Publications/2020/Dec/Green-hydrogen-cost-reduction"),
    ("E. Padgett and G. Kleen, <i>Automotive Fuel Cell Targets and Status</i>, DOE Hydrogen and Fuel Cells Program Record 20005, U.S. Department of Energy, 2020. "
     "Toyota Mirai fuel cell system: peak efficiency 64%.", "https://www.hydrogen.energy.gov/pdfs/20005-automotive-fuel-cell-targets-status.pdf"),
    ("California Air Resources Board, <i>DriveClean: 2024 Toyota Mirai XLE</i>. U.S. EPA rating of 402 miles of range and 74 MPGe combined; "
     "the tank holds 5.6 kg (Toyota specification).", "https://driveclean.ca.gov/taxonomy/term/42472"),
    ("U.S. Department of Energy, Hydrogen and Fuel Cell Technologies Office, <i>Technical Targets for Proton Exchange Membrane Electrolysis</i>. "
     "System energy use, 2022 status: 55 kWh per kg of hydrogen.", "https://www.energy.gov/eere/fuelcells/technical-targets-proton-exchange-membrane-electrolysis"),
    ("D. Peterson, J. Vickers and D. DeSantis, <i>Hydrogen Production Cost From PEM Electrolysis - 2019</i>, DOE Hydrogen and Fuel Cells Program Record 19009, "
     "U.S. Department of Energy, 2020. Electrolyser outlet pressure 300 psi, about 2 MPa.", "https://www.hydrogen.energy.gov/pdfs/19009_h2_production_cost_pem_electrolysis_2019.pdf"),
]


def render_references() -> None:
    body = ""
    for i, (text, url) in enumerate(REFERENCES, 1):
        link = f'<br><a href="{url}">{url.split("/")[2].replace("www.", "")}</a>' if url else ""
        body += f'<tr><td class="k ref-n">[{i}]</td><td class="v">{text}{link}</td></tr>'
    with st.container(key="explain_card_refs"):
        st.markdown(f'<table class="rows left">{body}</table>', unsafe_allow_html=True)
    st.markdown('<p class="small" style="margin-top:16px">Bank sizes and pressures, the valve seat area and the station compressor flow are design choices, '
                'marked as such under Assumptions.</p>', unsafe_allow_html=True)
