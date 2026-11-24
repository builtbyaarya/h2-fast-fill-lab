"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/tour.py

What this file does
    The tours (coach marks) that explain the words on each screen. A tour is a
    list of steps: which part to spotlight, a short title and one or two plain
    sentences. The script in assets/tour.js draws them.

Where it fits in the model
    It is explanation only. I wrote it so that someone who opens the app alone
    can follow the station without me talking over it.

When a tour plays
    Every time the page is opened or refreshed. Within one visit each tour
    plays once (switching Guided to Engineer plays the Engineer tour once,
    switching back does not replay Guided). Nothing is kept in the browser.
"""

from __future__ import annotations

import streamlit as st

from .styles import asset

_tour = st.components.v2.component("h2lab_tour", js=asset("tour.js"), isolate_styles=False)


NUMBER_WORDS = {4: "four", 5: "five"}


def inputs_tour(ns: str, n_steps: int = 4, with_fuel_cell: bool = False) -> list[dict]:
    """Guided: what the station is, how to read it, then the one-choice-per-screen panel."""
    k = f".st-key-{ns}__"
    scene = f".st-key-scene_{ns}"
    count = NUMBER_WORDS.get(n_steps, str(n_steps))
    last = (" The last question is which fuel cell is in the car, the part that turns the hydrogen back into electricity. It does not change the fill; "
            "it changes what the hydrogen gives back afterwards.") if with_fuel_cell else ""
    return [
        dict(sel=scene, title="A hydrogen station",
             text="Left to right: the station's three storage tanks, called banks, kept at different pressures. Then the dispenser, the pump you "
                  "park at, with a valve inside that controls the flow. Then the precooler, a fridge that chills the gas to as low as −40 °C and runs by itself. Then the car."),
        dict(sel=scene, title="Reading it",
             text="The dots are hydrogen. More dots in the car means more gas stored; faster, redder dots mean hotter gas. The gauge on the car "
                  "shows its charge: how full the tank is, 100% being full at 70 MPa. Pressure is in MPa, about ten times the air around you per MPa."),
        dict(sel=scene, title="The one rule",
             text="Squeezing gas into a tank heats it, like a bike pump. The car's tank must stay below 85 °C. Fill fast without crossing that line."),
        dict(sel=k + "gcard", title="One choice at a time",
             text="Each screen asks one question and says what it means. Drag the slider; the value and its unit sit beside it. Click the ? for a simple definition." + last, pad=6),
        dict(sel=k + "gnext button", title="Next",
             text=f"Move on to the next choice. After {count}, you press Start and watch what your choices do.", pad=6),
    ]


def engineer_tour(ns: str) -> list[dict]:
    """Only the tabs that Engineer adds, with the words each one uses."""
    panel = f".st-key-panel_{ns}"
    tab, box = panel + ' [role="tab"]', panel + " .stTabs"
    notes = [
        ("Banks", "The station's storage tanks. It fills from the low bank first, then the medium and high: this order is the cascade. The switch "
                  "margin is how close the car gets to a bank's pressure before the station moves on. Click the ? beside any input for a simple definition."),
        ("Dispenser", "The valve and its controller. Fill speed is the ramp rate in MPa per minute. Kp, Ki and Kd are the controller's gains: how hard "
                      "it reacts to the error now, built up, and changing. Station class (T40, T30, T20) is how cold the station delivers, under SAE J2601, "
                      "the rulebook for hydrogen fills."),
        ("Cooling", "The precooler and the fridge behind it. It runs by itself: the set point is the temperature it aims to deliver, typically −40 °C, "
                    "and it takes out just enough heat to hold that. Capacity is the most heat it can remove, in kW."),
        ("Tank", "The car's tank: a plastic liner wrapped in carbon fibre. Gas to wall is how easily heat soaks from the gas into that wall."),
        ("Solver", "Real gas uses measured hydrogen properties; ideal gas uses Pv = RT, which is off by tens of percent at 70 MPa. The time step is "
                   "how finely the fill is sliced, 0.1 s by default."),
    ]
    steps = [dict(sel=box, click=tab, clickIndex=i, title=name, text=text) for i, (name, text) in enumerate(notes)]
    steps[-1]["reset"] = tab
    steps.append(dict(sel=f".st-key-{ns}__exact_w", title="Sliders or exact numbers",
                      text="Every input is a slider. Switch this on to type exact values instead.", pad=6))
    return steps


LEVELS = [
    dict(sel='[class*="st-key-cardbtn_level_"]', title="Four levels", text="Each level is one fill with a job to do. Click a card to choose it."),
    dict(sel=".st-key-level_scene", title="The scene", text="This sets the day, the car and what counts as a pass. Any word you do not know is explained on the How it works page, under Words."),
    dict(sel='[class*="st-key-panel_m_"]', title="Your controls", text="Greyed inputs are fixed by the level. Change the others, then press Start."),
]


def results_tour(ns: str) -> list[dict]:
    """Plays once, after the first finished fill in Simulate."""
    k = f".st-key-{ns}__"
    return [
        dict(sel=k + "what", title="What happened, and why",
             text="The result in plain words: how hot the gas got, how full the tank is, how long it took, and one thing to try next."),
        dict(sel=k + "checks", title="Station checks",
             text="Seven checks a real station must pass before it is handed over, read off the fill you just ran. A red stamp means that check is still open."),
        dict(sel=k + "journey", title="Before and after the fill",
             text="The fill is one step. This drawing follows the same hydrogen from the machine that makes it to the fuel cell in the car. Every machine has a tag, "
                  "like K-201, and the electricity it takes. Blue dashed boxes are tanks, whose pressure and temperature change; the rest are steady-flow machines."),
        dict(sel=k + "jpick", title="Your choices",
             text="Pick how the hydrogen is made and used, what electricity costs and how busy the station is. The fuel cell you chose before the fill is "
                  "already set; you can change it here. The numbers update at once. Click any ? for a definition.", pad=6),
        dict(sel=k + "fcell", title="What the fuel cell changes",
             text="The fuel cell in this car beside the other kind, for the fill you just ran. The fill is the same for both. The electricity that comes back, "
                  "the round trip, the distance and the cost per kilometre are not.", pad=6),
        dict(sel=k + "cmp", title="Compare two fills",
             text="Run another fill with one thing changed and the two are set side by side here.", pad=6),
    ]


def request(name: str, steps: list[dict]) -> None:
    """Ask for a tour on this page. app.py mounts one tour per run with mount()."""
    st.session_state.setdefault("_tour_requests", []).append((name, steps))


def mount() -> None:
    """Mount the tour script once per run, with the first requested tour this visit has not offered yet.

    A browser refresh starts a new Streamlit session, so every tour plays again after a refresh.

    A tour is sent on two consecutive runs so a quick rerun cannot swallow it;
    the script itself makes sure it never starts twice.
    """
    requests = st.session_state.pop("_tour_requests", [])
    offered = st.session_state.setdefault("tours_offered", {})
    data = {"run": None, "steps": []}
    for name, steps in requests:
        if offered.get(name, 0) < 2:
            offered[name] = offered.get(name, 0) + 1
            data = {"run": name, "steps": steps}
            break
    _tour(key="h2lab_tour", data=data)
