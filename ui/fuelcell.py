"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.

The fuel cell choice: which fuel cell is in the car, and what that changes.

Where it fits: the fuel cell is not part of the fill model. The tank fills the
same way whichever one sits in the car, so nothing here touches h2lab/simulation.py.
The choice only matters after the fill, in h2lab/chain.py, where I follow one
kilogram to the fuel cell and work out the electricity that comes back
(efficiency times the lower heating value), the round trip, the distance and
the cost per kilometre. This file holds the choice for the visit and draws the
two fuel cells side by side, with every number read from chain.py when the
page is drawn.
"""

from __future__ import annotations

import threading

import streamlit as st

from h2lab import chain
from h2lab.properties import COOLPROP_AVAILABLE
from h2lab.simulation import FillConfig, FillResult, FillSimulation

DEFAULT = "PEFC"
# What each fuel cell is, in plain words. The same facts as the glossary and the note under the results;
# the efficiency itself is read from chain.FUEL_CELLS so the text can never disagree with the model.
ABOUT = {
    "PEFC": "uses an acid membrane and is in every hydrogen car on sale",
    "AEFC": "uses an alkaline membrane and is still a laboratory technology",
}


# ---- the choice, kept for the visit --------------------------------------------------------------------------
def key(ns: str) -> str:
    return f"{ns}__fuelcell"


def chosen(ns: str) -> str:
    """The fuel cell type picked on this screen, PEFC until the user says otherwise."""
    value = st.session_state.get(key(ns), DEFAULT)
    return value if value in chain.FUEL_CELLS else DEFAULT


def choose(ns: str, value: str | None) -> bool:
    """Remember a new choice. Returns True if it changed."""
    if value in chain.FUEL_CELLS and value != chosen(ns):
        st.session_state[key(ns)] = value
        return True
    st.session_state.setdefault(key(ns), chosen(ns))
    return False


def label(kind: str) -> str:
    return chain.FUEL_CELLS[kind]["name"]


def short_label(kind: str) -> str:
    """'PEFC, acid membrane' -> 'PEFC (acid)', short enough for the two buttons on the Guided card."""
    name, _, rest = label(kind).partition(", ")
    return f"{name} ({rest.split()[0]})" if rest else name


# ---- the standard fill, used before the user has run a fill of their own ----------------------------------------
_standard: dict = {}
_lock = threading.Lock()


def standard_fill() -> FillResult:
    """The default fill (25 °C, 5 MPa in the car, 18.5 MPa/min, to 70 MPa), run once and kept.

    The round trip and the cost per kilometre need a finished fill, because the compressor and precooler
    electricity come from it. Before the user has run their own, I use this one. It takes a few seconds, so it
    is run a single time for the whole app and every visitor reads the same result.
    """
    with _lock:
        if "res" not in _standard:
            mode = "real" if COOLPROP_AVAILABLE else "ideal"
            _standard["res"] = FillSimulation(FillConfig(property_mode=mode, dt=0.1)).run()
        return _standard["res"]


def warm() -> None:
    """Start the standard fill in the background, so it is ready by the time the fuel cell card is reached."""
    if "res" not in _standard and not _standard.get("started"):
        _standard["started"] = True
        threading.Thread(target=standard_fill, daemon=True).start()


# ---- the two fuel cells side by side -------------------------------------------------------------------------
def rows(res: FillResult, inp: chain.ChainInputs | None = None, efficiency: bool = False) -> list[tuple[str, dict]]:
    """One row per quantity the fuel cell changes: (label, {type: text}). Every value comes from chain.py."""
    both = chain.compare_fuel_cells(res, inp)
    out = [
        ("Electricity out, kWh/kg", {k: f"{rc['e_out']:.1f}" for k, rc in both.items()}),
        ("Round trip, %", {k: f"{100 * rc['round_trip']:.0f}" for k, rc in both.items()}),
        ("Distance, km/kg", {k: f"{rc['km_per_kg']:.0f}" for k, rc in both.items()}),
        ("Cost per km, $", {k: f"{rc['cost_per_km']:.3f}" for k, rc in both.items()}),
    ]
    if efficiency:
        # electricity out = efficiency x lower heating value, so I can read the efficiency back from the result
        eta = {k: rc["e_out"] * chain.KWH / chain.LHV for k, rc in both.items()}
        out.insert(0, ("Efficiency, %", {k: f"{100 * eta[k]:.0f}" for k in both}))
    return out


def table_html(res: FillResult, picked: str, inp: chain.ChainInputs | None = None, efficiency: bool = False) -> str:
    """The side-by-side as a small table. The picked column is bold and says 'in this car', so it never relies on colour."""
    kinds = list(chain.FUEL_CELLS)
    head = "".join(f'<th class="{"on" if k == picked else ""}">{k}<span>{"in this car" if k == picked else "&nbsp;"}</span></th>' for k in kinds)
    body = "".join(f'<tr><td class="k">{name}</td>' + "".join(f'<td class="{"on" if k == picked else ""}">{vals[k]}</td>' for k in kinds) + "</tr>"
                   for name, vals in rows(res, inp, efficiency))
    return f'<table class="fc-table"><tr><th></th>{head}</tr>{body}</table>'
