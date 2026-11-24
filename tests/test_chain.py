"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, tests/test_chain.py

What this file does
    Checks on the kilogram's route in h2lab/chain.py: the heating values
    against Table A.10, the electrolyser staying under the heating value, the
    compressor staying above the isothermal floor, the sums adding up, and the
    two fuel cells set side by side.

Where it fits in the model
    chain.py is bookkeeping around a finished fill, so these tests run one
    fill and check the bookkeeping. The fill model itself is tested in
    test_physics.py.
"""

import math

import pytest

from h2lab import chain
from h2lab.simulation import FillConfig, FillSimulation


@pytest.fixture(scope="module")
def res():
    return FillSimulation(FillConfig(property_mode="real", dt=0.25)).run()


def test_heating_values_match_table_a10():
    assert chain.HHV / 1e6 == pytest.approx(141.78, abs=0.02)
    assert chain.LHV / 1e6 == pytest.approx(119.95, abs=0.02)
    assert chain.HHV / chain.KWH == pytest.approx(39.38, abs=0.01)


def test_electrolyser_never_beats_the_heating_value():
    for e in chain.ELECTROLYSERS.values():
        assert (chain.HHV / chain.KWH) / e["lo"] < 1.0


def test_bank_shares_add_to_one(res):
    assert sum(chain.bank_shares(res)) == pytest.approx(1.0, abs=1e-9)


def test_compression_is_above_the_isothermal_floor(res):
    c = chain.compression(res, chain.SUPPLY_PRESSURE)
    assert c["w"] > c["w_min"] > 0
    for r in c["rows"]:
        assert r["w"] > r["w_min"]
    assert chain.isothermal_work(3e6, 95e6, 298.15) == pytest.approx(4124.3 * 298.15 * math.log(95 / 3), rel=1e-12)


def test_per_kilogram_adds_up(res):
    inp = chain.ChainInputs()
    rc = chain.per_kilogram(res, inp)
    assert rc["e_in"] == pytest.approx(rc["e_make"] + rc["e_comp"] + rc["e_chill"])
    assert rc["e_out"] == pytest.approx(0.64 * chain.LHV / chain.KWH)
    assert 0 < rc["round_trip"] < 1
    assert rc["cost"] == pytest.approx(rc["cost_power"] + rc["cost_capital"])
    assert rc["km_per_kg"] == pytest.approx(115.5, abs=0.1)


def test_busier_station_spreads_its_cost(res):
    quiet = chain.per_kilogram(res, chain.ChainInputs(cars_per_day=10))
    busy = chain.per_kilogram(res, chain.ChainInputs(cars_per_day=100))
    assert busy["cost_capital"] == pytest.approx(quiet["cost_capital"] / 10)


def test_punch_list_reads_the_fill(res):
    items = {p["check"]: p for p in chain.punch_list(res)}
    assert len(items) == 7
    assert items["Gas in the car's tank stays below 85 °C"]["closed"]
    assert items["Energy books balance"]["closed"]
    assert items["Fill is done within three minutes"]["closed"] == (res.fill_time <= 180.0)


def test_defaults_sit_inside_the_published_ranges():
    for key, e in chain.ELECTROLYSERS.items():
        assert e["lo"] <= chain.default_kwh(key) <= e["hi"]
    assert chain.ChainInputs().electrolyser_kwh_kg == chain.default_kwh("PEWE")


def test_fuel_cells_side_by_side_match_per_kilogram(res):
    """The side-by-side is nothing more than per_kilogram() run once for each fuel cell type."""
    both = chain.compare_fuel_cells(res)
    assert list(both) == list(chain.FUEL_CELLS)
    for key, cell in chain.FUEL_CELLS.items():
        alone = chain.per_kilogram(res, chain.ChainInputs(fuel_cell=key, fuel_cell_eta=cell["eta"]))
        for name in ("e_out", "round_trip", "km_per_kg", "cost_per_km"):
            assert both[key][name] == pytest.approx(alone[name], rel=1e-12)
        assert both[key]["e_out"] == pytest.approx(cell["eta"] * chain.LHV / chain.KWH)


def test_fuel_cell_changes_only_what_comes_after_the_fill(res):
    """Same fill, same electricity in, same cost per kilogram; the electricity out, the distance and the cost per km move."""
    both = chain.compare_fuel_cells(res)
    pefc, aefc = both["PEFC"], both["AEFC"]
    assert pefc["e_in"] == aefc["e_in"] and pefc["cost"] == aefc["cost"] and pefc["kg_per_fill"] == aefc["kg_per_fill"]
    ratio = chain.FUEL_CELLS["AEFC"]["eta"] / chain.FUEL_CELLS["PEFC"]["eta"]
    assert aefc["e_out"] / pefc["e_out"] == pytest.approx(ratio)
    assert aefc["round_trip"] / pefc["round_trip"] == pytest.approx(ratio)
    assert aefc["km_per_kg"] / pefc["km_per_kg"] == pytest.approx(ratio)
    assert aefc["cost_per_km"] / pefc["cost_per_km"] == pytest.approx(1.0 / ratio)


def test_fuel_cell_table_shows_the_model_numbers(res):
    """The numbers printed on the Guided card and under the results are chain.py's own, only formatted."""
    from ui import fuelcell

    both = chain.compare_fuel_cells(res)
    shown = dict(fuelcell.rows(res, efficiency=True))
    for key, rc in both.items():
        assert shown["Efficiency, %"][key] == f"{100 * chain.FUEL_CELLS[key]['eta']:.0f}"
        assert shown["Electricity out, kWh/kg"][key] == f"{rc['e_out']:.1f}"
        assert shown["Round trip, %"][key] == f"{100 * rc['round_trip']:.0f}"
        assert shown["Distance, km/kg"][key] == f"{rc['km_per_kg']:.0f}"
        assert shown["Cost per km, $"][key] == f"{rc['cost_per_km']:.3f}"
    assert fuelcell.short_label("PEFC") == "PEFC (acid)" and fuelcell.short_label("AEFC") == "AEFC (alkaline)"
