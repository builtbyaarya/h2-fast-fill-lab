# H₂ Fast-Fill Lab

Aarya Chiripal. AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.

Live app: https://h2-fast-fill-lab.streamlit.app

Code: https://github.com/builtbyaarya/h2-fast-fill-lab

## What it is

This is my course project: a model of a hydrogen station filling a fuel-cell
car. Three storage banks empty through a dispenser valve and a precooler into
the car's 141 L tank, and the fill has to stay inside the limits of SAE J2601,
the fuelling standard for hydrogen cars (gas below 85 °C, pressure below
87.5 MPa, flow at most 60 g/s). The banks and the car's tank are transient
control volumes; the valve and the precooler are steady-flow devices between
them, which is project category 6.

The problem the station solves is one piece of thermodynamics. Gas pushed into
a closed tank carries its flow work in with it, so the tank heats up; an empty
insulated tank filled from 25 °C would reach about 147 °C (T₂ = k Tᵢ). The
precooler and a controlled pressure ramp are how a real station keeps a
three-minute fill under 85 °C, and the app lets you see each of them work.

After the fill I follow the same kilogram back to the electrolyser that made
it and forward to the fuel cell in the car, with the electricity each step
takes, the round trip, the distance and the cost.

## How to run it

macOS: double-click `run.command`. Windows: double-click `run.bat`. The first
run makes a private virtual environment and installs the pinned packages;
later runs start the app in the browser at `localhost:8501`.

On any computer with Python 3.10 or newer:

    pip install -r requirements.txt
    streamlit run app.py

## What is in the app

- Opening screen: the station animation, then two cards, Guided and Engineer.
  The mode can be switched at any time from the control panel.
- Guided asks one question per card and explains it in plain words: the
  weather, how empty the car is, how fast to fill, when to stop, and which
  fuel cell is in the car. The fuel cell card shows the two types side by
  side (electricity out, round trip, distance, cost per kilometre), worked out
  by the model for the standard fill. Then you run the fill.
- Engineer gives every parameter in tabs (banks, dispenser, cooling, tank,
  solver), as sliders or as exact numbers.
- Simulate: the animated station with the control panel beside it and one
  chart below, with a time cursor that moves with the animation. When the fill
  ends, the page continues downward:
  - What happened, and why: the result in plain words.
  - Station checks: seven checks a station must pass before hand-over (a punch
    list), read off the fill: 85 °C, 87.5 MPa, 60 g/s, no safety stop, 180 s,
    and the energy and mass balances.
  - Before and after the fill: a tagged process drawing (P&ID style) from the
    electrolyser to the fuel cell, with two electrolyser types and two fuel
    cell types to choose from. The fuel cell picked in Guided is already set
    here, and a table puts it against the other type for the fill that just
    ran. The cost of one kilogram is split into running cost and build cost.
  - Compare two fills: every finished fill is kept for the visit and set
    against the previous one, or against the same fill as an ideal gas.
- Levels: four fills with a job to do. The result leads with pass or fail and
  the reason, then the score by criterion.
- How it works: the idea in plain words, every term defined, a fill checked by
  hand with the course formulas, six one-variable experiments, the accuracy
  checks, the assumptions and the sources.
- A short tour explains the words on each screen, and every input has a ? with
  a one-sentence definition.

The two electrolyser types and two fuel cell types are the four technologies I
compared on lifecycle cost as a research intern at RWTH Aachen University, a
technical university in Germany, in summer 2026. The cost split follows the
models I built at RCT Solutions, a German solar consulting company, in 2025.
Every number is either cited in the app or marked as my design choice.

## Where each piece of thermodynamics lives

| Topic | File | What I do there |
| --- | --- | --- |
| Properties | `h2lab/properties.py` | Ideal gas with the Table A.5 constants (Pv = RT, u = cᵥT, h = cₚT), or real gas from CoolProp. One switch changes the whole station. |
| Mass balance and first law, transient control volume | `h2lab/tanks.py` | dm/dt = ṁᵢ − ṁₑ and dU/dt = Q̇ + ṁᵢhᵢ − ṁₑhₑ for a rigid tank, with a lumped wall for the heat transfer. |
| Throttling | `h2lab/devices.py`, `DispenserValve` | hₑ = hᵢ across the valve; the flow rate from the isentropic nozzle relation, choked for most of a fill. |
| Heat exchanger | `h2lab/devices.py`, `Precooler` | q = hₑ − hᵢ with no work. It holds a set-point outlet temperature, and the heat removed follows the flow up to a capacity. |
| Refrigeration cycle and COP | `h2lab/devices.py`, `RefrigerationCycle` | Vapor-compression cycle with an isentropic compressor efficiency; COP = (h₁ − h₄)/(h₂ − h₁). |
| Isentropic compression with an efficiency | `h2lab/devices.py`, `StationCompressor` | Two stages with an intercooler; hₑ = hᵢ + (hₑₛ − hᵢ)/ηₛ per stage. |
| Control | `h2lab/controller.py` | A PID loop moves the valve so the tank pressure follows a ramp; the J2601 limits stop the fill. |
| Time stepping and the energy balance | `h2lab/simulation.py` | Explicit midpoint method (second order); the whole-station energy and mass balances are checked at the end. |
| Heating values, round trip, cost | `h2lab/chain.py` | HHV and LHV from Table A.10, isothermal work R T ln(P₂/P₁) as the compressor's floor, fuel cell electricity as efficiency × LHV. |

## How the code is laid out

    app.py                  entry point: opening screen, navigation, page routing
    h2lab/                  the model; it never imports the interface
      properties.py         hydrogen (ideal gas or CoolProp) and refrigerant properties
      tanks.py              transient control volumes with a lumped wall
      devices.py            valve, precooler, refrigeration cycle, station compressor
      controller.py         PID pressure-ramp controller and the J2601 limit checks
      simulation.py         the fill: cascade, time stepping, energy balance
      chain.py              around the fill: electrolyser, compression, fuel cell, cost, station checks
      missions.py           the levels and their scores
      investigations.py     parameter studies and report graphs
      validation.py         accuracy checks and the comparison with a published fill test
    ui/                     the interface; it reads the model's state and draws it
      run.py                the run screen: scene, Guided cards, Engineer tabs
      fuelcell.py           the fuel cell choice and the two types side by side
      journey.py            after a fill: station checks and the before-and-after drawing
      compare.py            after a fill: this fill against an earlier one
      levels.py             the four levels
      explained.py, handcalc.py   the How it works page
      home.py               opening screen
      tour.py, glossary.py  tours, ? definitions and the words they use
      scene.py, plots.py    numbers for the animation, and the Plotly charts
      styles.py, text.py    shared building blocks, units and subscripts
      assets/               app.css, journey.css, scene.css, scene.html, scene.js, tour.js
    static/                 Instrument Sans and Instrument Serif (SIL Open Font License, licence files included)
    tests/                  pytest checks
    investigations/         saved study graphs

## How the animation reads the model

Hydrogen is drawn as molecules. Everything they do comes from the simulation:
the number in the car's tank follows the stored mass, their speed and colour
follow the gas temperature, the dots in the pipes follow the mass flow rate
and turn blue after the precooler, and each bank loses molecules as its mass
falls. The drawing never feeds back into the model.

## Tests

    pytest -q

28 tests. `tests/test_physics.py` checks the fill model: T₂ = k Tᵢ for an
empty insulated tank, mass leaving the banks equal to mass entering the car,
the energy balance closing within 0.1%, the same answer when the time step is
halved, 5.7 kg in a 141 L tank at 70 MPa and 15 °C, and each device on its
own. `tests/test_chain.py` checks the bookkeeping around the fill, including
that the fuel cell table shows the model's own numbers.

## Sources

The full numbered list is in the app under How it works, Sources. The main
ones: Borgnakke and Sonntag, *Fundamentals of Thermodynamics* (Tables A.5,
A.10 and B.5, and the control-volume and refrigeration chapters); SAE J2601
as described by Reddi, Elgowainy, Rustagi and Gupta (2017); CoolProp for
real-gas properties; the hydrogen tank fill tests of the European
Commission's Joint Research Centre (Acosta-Iborra et al., 2013) for the
comparison; and the U.S. Department of Energy Hydrogen Program Records for
the fuel cell, electrolyser and station cost figures.

## Putting it online

The live app runs on Streamlit Community Cloud from the GitHub repository
above: branch `main`, file `app.py`. The pinned `requirements.txt` and
`.python-version` are what it installs from.

## Research model (h2lab/research)

The Research model page and the scripts in `paper/` use a second tank model, kept beside the class model so the two can be compared.

- `h2lab/research/twozone.py`: the gas in the car's tank is split into an upper and a lower zone at one pressure, each with its own mass, internal energy and temperature. The zones exchange mass through jet entrainment (Ricou and Spalding) reduced by a Richardson number, and the wall is solved through its thickness by one-dimensional conduction. The 85 °C limit is checked against the hotter zone.
- `h2lab/research/props.py`: real-gas hydrogen properties from CoolProp, tabulated on a density and temperature grid.
- `h2lab/research/station.py`: station electricity on one system boundary. Compressor stages, intercooling, real-gas enthalpy, isentropic, mechanical and motor efficiency, and the hydrogen drawn from each bank, with every kilogram compressed once.
- `h2lab/research/optimize.py`: NSGA-II over two ramp rates, their change point, two bank switching margins and two precooler set points, for fill time and station electricity, compared with the SAE J2601 table fill for the same tank. The robust version also keeps the hotter zone below 85 °C when zone mixing is as weak as the JRC thermocouple spread allows.
- `h2lab/research/uq.py`: Sobol sensitivity indices and Monte Carlo propagation.
- `h2lab/research/jrc.py`: the JRC GasTeF validation data, transcribed from the two conference papers, two 244 L fills from the SAE J2601 validation programme, and the error metrics.

To regenerate every number and figure of the manuscript:

    pip install -r requirements-paper.txt
    python paper/run_all.py
    python paper/figures.py

`run_all.py` takes part names (for example `python paper/run_all.py optimise_25 optimise_0_40 optimise_merge`) so the 25 °C optimisation and the 0 and 40 °C optimisations can run in two processes.

Which parameters are taken from independent sources, which are assumed and which are fitted is listed at the top of `h2lab/research/jrc.py`.
