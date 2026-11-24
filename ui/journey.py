"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/journey.py

What this file does
    Draws what comes under a finished fill in Simulate, the way a plant's own
    paperwork is drawn:
      1. Station checks: seven checks a station must pass before hand-over (a
         punch list), read off the fill that just ran.
      2. Before and after the fill: a tagged process drawing (P&ID style) of
         the same hydrogen from the electrolyser to the fuel cell, with the
         electricity each step takes, the choices that change it, the two
         fuel cells side by side, and what one kilogram costs.

Where it fits in the model
    It only displays. Every number comes from h2lab/chain.py, which does the
    energy and cost bookkeeping on the finished FillResult. The hand check at
    the bottom repeats that bookkeeping with the course tables so a reader can
    follow it with a calculator.
"""

from __future__ import annotations

import streamlit as st

from h2lab import chain
from h2lab.simulation import FillResult

from . import fuelcell
from .glossary import TERMS
from .styles import asset, gap, rows_html, stat_row
from .text import minus

INK, ACCENT, MUTED = "#1D1D1F", "#0071E3", "#6E6E73"


# ---- the drawing ------------------------------------------------------------------------------------
def _pid(rc: dict, res: FillResult, inp: chain.ChainInputs) -> str:
    """The plant as a P&ID-style line drawing. Seven stations on one line, 160 units apart."""
    y, xs = 100, [80 + 160 * i for i in range(7)]
    half = [24, 24, 27, 16, 24, 34, 24]
    s = f'stroke="{INK}" stroke-width="1.5" fill="#FFFFFF"'
    ln = f'stroke="{INK}" stroke-width="1.5" fill="none"'
    banks = res.cfg.banks
    sh = rc["shares"]
    stations = [
        ("EL", "101", "Electrolyser", f'{rc["e_make"]:.1f} kWh/kg in', f'{100 * rc["eta_electrolyser"]:.0f}% kept in the gas'),
        ("K", "201", "Compressor", f'{rc["e_comp"]:.2f} kWh/kg in', f'from {inp.supply_pressure_pa / 1e6:.0f} MPa'),
        ("V", "301", "Storage banks", " / ".join(f"{b.pressure_pa / 1e6:.0f}" for b in banks) + " MPa", " / ".join(f"{100 * x:.0f}" for x in sh) + "% drawn"),
        ("PCV", "401", "Dispenser valve", "throttle, no work", f'up to {1000 * float(max(res.series["m_dot"])):.0f} g/s'),
        ("E", "501", "Precooler", f'{rc["e_chill"]:.2f} kWh/kg in', f'{rc["q_chill"]:.2f} kWh/kg heat out'),
        ("TK", "601", "Car tank", f'peak {minus(format(res.T_peak - 273.15, ".1f"))} °C', f'{res.P_final / 1e6:.1f} MPa in {res.fill_time:.0f} s'),
        ("FC", "701", "Fuel cell", f'{rc["e_out"]:.1f} kWh/kg out', f'{rc["km_per_kg"]:.0f} km of driving'),
    ]
    p = [f'<svg viewBox="0 0 1120 214" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Line drawing of the plant, from electrolyser to fuel cell">',
         f'<defs><marker id="pfarrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0.5 L7,4 L0,7.5 Z" fill="{INK}"/></marker></defs>']
    for i in range(6):
        dash = ' stroke-dasharray="6 5"' if i == 5 else ""
        p.append(f'<line x1="{xs[i] + half[i]}" y1="{y}" x2="{xs[i + 1] - half[i + 1] - 2}" y2="{y}" {ln}{dash} marker-end="url(#pfarrow)"/>')
    for i in (2, 5):  # the two transient control volumes
        p.append(f'<rect x="{xs[i] - 44}" y="{y - 38}" width="88" height="76" rx="4" fill="none" stroke="{ACCENT}" stroke-width="1.2" stroke-dasharray="5 4"/>')
    x = xs[0]
    p.append(f'<rect x="{x - 24}" y="{y - 24}" width="48" height="48" {s}/><line x1="{x - 8}" y1="{y - 15}" x2="{x - 8}" y2="{y + 15}" {ln}/><line x1="{x + 8}" y1="{y - 15}" x2="{x + 8}" y2="{y + 15}" {ln}/>')
    x = xs[1]
    p.append(f'<circle cx="{x}" cy="{y}" r="24" {s}/><line x1="{x - 17}" y1="{y - 17}" x2="{x + 22}" y2="{y - 9}" {ln}/><line x1="{x - 17}" y1="{y + 17}" x2="{x + 22}" y2="{y + 9}" {ln}/>')
    x = xs[2]
    p.append("".join(f'<rect x="{x - 27 + 20 * k}" y="{y - 24}" width="14" height="48" rx="7" {s}/>' for k in range(3)))
    x = xs[3]
    p.append(f'<polygon points="{x - 16},{y - 10} {x - 16},{y + 10} {x},{y}" {s}/><polygon points="{x + 16},{y - 10} {x + 16},{y + 10} {x},{y}" {s}/>'
             f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y - 18}" {ln}/><path d="M{x - 10},{y - 18} A10,10 0 0 1 {x + 10},{y - 18} Z" {s}/>')
    x = xs[4]
    p.append(f'<circle cx="{x}" cy="{y}" r="24" {s}/><polyline points="{x - 24},{y} {x - 12},{y} {x - 6},{y - 10} {x + 6},{y + 10} {x + 12},{y} {x + 24},{y}" {ln}/>')
    x = xs[5]
    p.append(f'<rect x="{x - 34}" y="{y - 17}" width="68" height="34" rx="17" {s}/>')
    x = xs[6]
    p.append(f'<rect x="{x - 24}" y="{y - 24}" width="48" height="48" {s}/>' + "".join(f'<line x1="{x + d}" y1="{y - 24}" x2="{x + d}" y2="{y + 24}" {ln}/>' for d in (-12, 0, 12)))
    for x, (a, b, name, v1, v2) in zip(xs, stations):
        p.append(f'<circle cx="{x}" cy="30" r="19" {s}/><line x1="{x - 19}" y1="30" x2="{x + 19}" y2="30" stroke="{INK}" stroke-width="1"/>'
                 f'<text x="{x}" y="25" text-anchor="middle" font-size="11" font-weight="600" fill="{INK}">{a}</text>'
                 f'<text x="{x}" y="43" text-anchor="middle" font-size="11" font-weight="600" fill="{INK}">{b}</text>'
                 f'<text x="{x}" y="164" text-anchor="middle" font-size="13" font-weight="600" fill="{INK}">{name}</text>'
                 f'<text x="{x}" y="184" text-anchor="middle" font-size="12" fill="{INK}">{v1}</text>'
                 f'<text x="{x}" y="202" text-anchor="middle" font-size="12" fill="{MUTED}">{v2}</text>')
    p.append("</svg>")
    return "".join(p)


def _sheet(doc: dict) -> str:
    rc, res, inp = doc["rc"], doc["res"], doc["inp"]
    block = [("Title", "One kilogram of hydrogen, electrolyser to fuel cell"), ("Drawn", "A. Chiripal"), ("Fill", f"{res.cfg.T_amb - 273.15:.0f} °C, {res.fill_time:.0f} s"), ("Values", "per kg in the car")]
    cells = "".join(f'<div><div class="l">{l}</div><div class="v">{v}</div></div>' for l, v in block)
    return ('<div class="pf-doc"><div class="pf-head"><span class="pf-name">Process drawing</span><span class="pf-no">H2-PID-001</span></div>'
            f'<div class="pf-body" style="padding-bottom:8px">{_pid(rc, res, inp)}</div>'
            '<div class="pf-notes"><b>NOTES</b> &nbsp;1. Solid line: hydrogen at the station. Dashed line: inside the car. &nbsp;2. Blue dashed box: a tank, whose '
            'pressure and temperature change during the fill (transient). Every other symbol is a steady-flow device. &nbsp;3. All values are for one kilogram '
            'put into the car.</div>'
            f'<div class="pf-block">{cells}</div></div>')



# ---- the station checks ---------------------------------------------------------------------------------
def _punch(doc: dict) -> str:
    items = doc["punch"]
    closed = sum(1 for p in items if p["closed"])
    body = "".join(f'<tr><td class="op">{p["n"]:02d}</td><td>{p["check"]}</td><td>{p["limit"]}</td><td class="n">{minus(p["measured"])}</td>'
                   f'<td><span class="pf-stamp {"" if p["closed"] else "open"}">{"Closed" if p["closed"] else "Open"}</span></td></tr>' for p in items)
    return ('<div class="pf-doc"><div class="pf-head"><span class="pf-name">Station checks</span>'
            f'<span class="pf-no">{closed} of {len(items)} closed</span></div><div class="pf-body"><table class="pf-table">'
            '<colgroup><col style="width:48px"><col><col style="width:136px"><col style="width:104px"><col style="width:104px"></colgroup>'
            '<tr><th>No</th><th>Check</th><th>Must be</th><th class="n">This fill</th><th>Status</th></tr>'
            f'{body}</table></div></div>')



# ---- the money and the hand check
def _money(doc: dict) -> str:
    rc, inp = doc["rc"], doc["inp"]
    d = lambda x: f"${x:.2f}"
    run = rows_html([("Electricity to make it (EL-101)", d(rc["cost_power_make"])), ("Electricity to compress it (K-201)", d(rc["cost_power_comp"])),
                     ("Electricity to chill it (E-501)", d(rc["cost_power_chill"]))])
    own = rows_html([("Precooler and its heat exchanger, about a tenth of the station [16]", d(rc["cost_capital_precooler"])),
                     ("Compressor, banks, dispenser and building it", d(rc["cost_capital_rest"]))])
    tot = rows_html([("Total for one kilogram, $", f"{rc['cost']:.2f}"), ("Per kilometre driven, $", f"{rc['cost_per_km']:.3f}"),
                     ("California pump price, October 2024 [17], $ per kg", f"{chain.PUMP_PRICE:.2f}")])
    return ('<div class="card"><h3>What the kilogram costs</h3>'
            f'<p class="pf-sub">Running cost, at ${inp.electricity_price:.2f} per kWh of electricity</p>{run}'
            f'<p class="pf-sub">Build cost of the station, shared over {rc["kg_year"]:,.0f} kg a year</p>{own}'
            f'<p class="pf-sub">Together</p>{tot}'
            f'<p class="small" style="margin-top:16px">Build cost: a $1.9 million station [13] repaid over {chain.LIFE_YEARS} years at {100 * chain.INTEREST:.0f}% interest '
            f'(both are my design choices), which is {100 * rc["crf"]:.1f}% of the price each year, divided by {inp.cars_per_day:.0f} cars a day at '
            f'{rc["kg_per_fill"]:.2f} kg each. Not included: the cost of the electrolyser itself, staff, maintenance, land and profit, which is most of the gap to the pump price.</p></div>')


def _hand(doc: dict) -> str:
    rc, res, inp = doc["rc"], doc["res"], doc["inp"]
    hi = rc["comp"]["rows"][-1]
    T = res.cfg.T_amb
    hhv, lhv = chain.HHV / chain.KWH, chain.LHV / chain.KWH
    eq = lambda t, muted=False: f'<p class="eq{" muted" if muted else ""}">{t}</p>'
    h = ['<div class="card pf-hand"><h3>1. The electrolyser cannot beat the heating value</h3>',
         eq("Burning hydrogen to liquid water releases 285,830 kJ per kmol (Table A.10 [1]). One kmol is 2.016 kg."),
         eq(f"HHV = 285,830 / 2.016 = 141,781 kJ/kg = 141,781 / 3600 = {hhv:.2f} kWh/kg"),
         eq(f"Share kept = {hhv:.2f} / {rc['e_make']:.1f} = {100 * rc['eta_electrolyser']:.0f}%. It must be under 100%, and it is."),
         '<h3>2. The compressor cannot beat constant-temperature compression</h3>',
         eq(f"Least work for an ideal gas, into the high bank: w = R T ln(P₂/P₁), with R = 4.124 kJ/kg K (Table A.5 [1]) and T = {T:.2f} K"),
         eq(f"w = 4.124 × {T:.2f} × ln({hi['P'] / 1e6:.0f} / {inp.supply_pressure_pa / 1e6:.0f}) = {hi['w_min'] / 1e3:,.0f} kJ/kg = {hi['w_min'] / chain.KWH:.2f} kWh/kg"),
         eq(f"The model's two-stage compressor at {100 * rc['comp']['eta_s']:.0f}% efficiency with real-gas properties gives {hi['w'] / chain.KWH:.2f} kWh/kg for the same lift, "
            f"{hi['w'] / hi['w_min']:.1f} times the floor. Across the three banks, weighted by how much this fill drew from each, it is {rc['e_comp']:.2f} kWh/kg."),
         '<h3>3. What the fuel cell gives back</h3>',
         eq("In a car the water leaves as vapour, so the lower heating value applies: 241,826 kJ per kmol (Table A.10 [1])."),
         eq(f"LHV = 241,826 / 2.016 = 119,953 kJ/kg = {lhv:.2f} kWh/kg"),
         eq(f"Electricity out = {inp.fuel_cell_eta:.2f} × {lhv:.2f} = {rc['e_out']:.2f} kWh/kg"),
         '<h3>4. Round trip and distance</h3>',
         eq(f"Electricity in = {rc['e_make']:.2f} + {rc['e_comp']:.2f} + {rc['e_chill']:.2f} = {rc['e_in']:.2f} kWh/kg"),
         eq(f"Round trip = {rc['e_out']:.2f} / {rc['e_in']:.2f} = {100 * rc['round_trip']:.0f}%"),
         eq(f"Distance = 115.5 km/kg × ({inp.fuel_cell_eta:.2f} / 0.64) = {rc['km_per_kg']:.0f} km/kg. The 115.5 comes from a Toyota Mirai rated at 402 miles on 5.6 kg [21], "
            "whose fuel cell reaches 64% at its best operating point [20]. A car spends most of its time near that point, but not all of it, so the electricity out is an "
            "upper figure; scaling distance with efficiency is my simplification.", True),
         "</div>"]
    return "".join(h)


def _reading(doc: dict) -> str:
    rc, inp = doc["rc"], doc["inp"]
    lines = [
        f"Making this hydrogen took {rc['e_make']:.1f} kWh of electricity for each kilogram, squeezing it into the banks {rc['e_comp']:.2f} and chilling it {rc['e_chill']:.2f}. "
        f"The fuel cell gives back {rc['e_out']:.1f} at its best, so about {100 * rc['round_trip']:.0f} of every 100 units come back.",
        f"The station is a small part of the energy and a large part of the cost. At {inp.cars_per_day:.0f} cars a day, building it adds ${rc['cost_capital']:.2f} to each "
        f"kilogram; the electricity for its compressor and precooler adds ${rc['cost_power_comp'] + rc['cost_power_chill']:.2f}. The equipment is cheap to run and expensive "
        "to own, which is why a quiet station sells expensive hydrogen.",
        "Try it: raise Cars per day. The energy does not move, and the cost falls, because the same station is shared by more cars.",
    ]
    return "".join(f"<p>{x}</p>" for x in lines)


def _fuel_cells(doc: dict) -> str:
    """The fuel cell in this car against the other one, for the fill that just ran and the choices above."""
    rc, res, inp = doc["rc"], doc["res"], doc["inp"]
    both = chain.compare_fuel_cells(res, inp)
    other = next(k for k in both if k != inp.fuel_cell)
    ro = both[other]
    return ('<div class="card fc-card"><div><h3>What the fuel cell changes</h3>'
            f'<p>The fuel cell in this car is the {inp.fuel_cell}, which {fuelcell.ABOUT[inp.fuel_cell]}. The fill above is the same for both fuel cells: the same '
            f'{res.m_added:.2f} kg, the same {rc["e_in"]:.1f} kWh/kg of electricity in and the same ${rc["cost"]:.2f} per kilogram. What changes is what the '
            f'kilogram gives back. With the {other} it would be {ro["e_out"]:.1f} kWh/kg out against {rc["e_out"]:.1f}, {ro["km_per_kg"]:.0f} km against '
            f'{rc["km_per_kg"]:.0f}, and ${ro["cost_per_km"]:.3f} a kilometre against ${rc["cost_per_km"]:.3f}.</p></div>'
            f'<div>{fuelcell.table_html(res, inp.fuel_cell, inp, efficiency=True)}</div></div>')


NOTE = ('<p class="small" style="margin-top:8px">Electrolyser electricity: PEWE 55 kWh/kg [22], inside the published 50 to 83 range [19]; AEWE has no published status, so '
        'its 63 is the middle of its 57 to 69 range [19] and my choice. PEFC: 64%, the best point of the Toyota Mirai system [20]. No car uses an AEFC yet, so its 55% is my '
        'choice. The electrolyser hands over hydrogen at about 2 MPa [23]. Only the 70 MPa car is modelled; buses and forklifts fill at 35 MPa under other rules. Numbers in '
        'square brackets are under How it works, Sources.</p>')


def render_after_fill(sim, ns: str) -> None:
    """The station checks and the before-and-after block for a finished fill."""
    from .run import choose, num  # imported here because run.py calls this function

    st.html(f"<style>{asset('journey.css')}</style>")
    res: FillResult = sim.result()
    j = f"{ns}_j"
    engineer = st.session_state.get("path") == "Engineer"

    with st.container(key=f"{ns}__checks"):
        st.markdown(_punch(dict(punch=chain.punch_list(res))), unsafe_allow_html=True)
    gap(24)
    with st.container(key=f"{ns}__journey"):
        st.markdown('<div class="pf-intro"><h2>Before and after the fill</h2><p>The fill is one step. Follow the same hydrogen back to the machine that made it '
                    'and forward to the fuel cell in the car, and see what each step takes.</p></div>', unsafe_allow_html=True)
        with st.container(key=f"{ns}__jpick"):
            c1, c2, c3, c4 = st.columns(4, gap="medium")
            with c1:
                etype = choose("Electrolyser type", TERMS["Electrolyser type (PEWE, AEWE)"], list(chain.ELECTROLYSERS), 0, f"{j}_etype",
                               format_func=lambda k: chain.ELECTROLYSERS[k]["name"])
            with c2:
                # Preselected from the Guided card. If it is changed here, the whole page is drawn again so the
                # panel beside the scene names the same fuel cell.
                kinds = list(chain.FUEL_CELLS)
                picked = fuelcell.chosen(ns)
                if f"{j}_ftype" not in st.session_state or st.session_state.get(f"{j}_ftype_from") != picked:
                    st.session_state[f"{j}_ftype"] = st.session_state[f"{j}_ftype_from"] = picked
                ftype = choose("Fuel cell type", TERMS["Fuel cell type (PEFC, AEFC)"], kinds, 0, f"{j}_ftype", format_func=fuelcell.label)
                if fuelcell.choose(ns, ftype):
                    st.session_state[f"{j}_ftype_from"] = ftype
                    st.rerun()
            with c3:
                price = num(j, "price", "Electricity price, $/kWh", 0.02, 0.40, 0.15, 0.01, fmt="%.2f", help=TERMS["Electricity price"])
            with c4:
                cars = num(j, "cars", "Cars per day", 5, 200, 40, 5, help=TERMS["Cars per day"])
            e = chain.ELECTROLYSERS[etype]
            kwh, eta = chain.default_kwh(etype), 100 * chain.FUEL_CELLS[ftype]["eta"]
            if engineer:
                c1, c2 = st.columns(2, gap="medium")
                with c1:
                    kwh = num(j, f"kwh_{etype}", "Electrolyser electricity, kWh/kg", e["lo"], e["hi"], chain.default_kwh(etype), 0.5, fmt="%.1f",
                              help=TERMS["Electrolyser electricity"])
                with c2:
                    eta = num(j, f"eta_{ftype}", "Fuel cell efficiency, %", 40, 70, int(round(eta)), 1, help=TERMS["Fuel cell efficiency"])
        inp = chain.ChainInputs(electrolyser=etype, electrolyser_kwh_kg=float(kwh), fuel_cell=ftype, fuel_cell_eta=float(eta) / 100.0,
                                electricity_price=float(price), cars_per_day=float(cars))
        doc = dict(inp=inp, res=res, rc=chain.per_kilogram(res, inp))
        rc = doc["rc"]
        gap(8)
        st.markdown(_sheet(doc), unsafe_allow_html=True)
        gap(8)
        stat_row([("Electricity in, kWh/kg", f"{rc['e_in']:.1f}", "to make, squeeze and chill it"),
                  ("Comes back out, %", f"{100 * rc['round_trip']:.0f}", f"{rc['e_out']:.1f} kWh/kg from the fuel cell"),
                  ("Distance, km/kg", f"{rc['km_per_kg']:.0f}", "in a car like the Toyota Mirai"),
                  ("Cost, $/kg", f"{rc['cost']:.2f}", f"${rc['cost_per_km']:.3f} per km")])
        gap(8)
        with st.container(key=f"{ns}__fcell"):
            st.markdown(_fuel_cells(doc), unsafe_allow_html=True)
        gap(8)
        a, b = st.columns(2, gap="medium")
        a.markdown(f'<div class="card what"><h3>What this shows</h3>{_reading(doc)}</div>', unsafe_allow_html=True)
        b.markdown(_money(doc), unsafe_allow_html=True)
        gap(8)
        with st.expander("Check these numbers by hand"):
            st.markdown(_hand(doc), unsafe_allow_html=True)
        st.markdown(NOTE, unsafe_allow_html=True)
