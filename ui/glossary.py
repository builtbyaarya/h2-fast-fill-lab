"""
Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
H2 Fast-Fill Lab, ui/glossary.py

What this file does
    Plain-words definitions for every term the app uses, in one place, so the
    ? buttons, the tours and the Words chapter all say the same thing.

Where it fits in the model
    It is the dictionary for the model's vocabulary. Each definition is one or
    two short sentences that someone who has never seen a hydrogen station
    can follow.
"""

from __future__ import annotations

TERMS = {
    "Hydrogen car": "An electric car that makes its own electricity from hydrogen gas. The only thing that comes out of the exhaust is water.",
    "MPa (and bar)": "A unit of pressure. 1 MPa is about ten times the push of the air around you. 10 bar is the same as 1 MPa.",
    "700 bar (70 MPa)": "How hard the hydrogen is squeezed in a full car tank: about 700 times the air around you. Squeezing it this much is how enough fuel fits in the car.",
    "Why the gas heats up": "Squeezing gas makes it hot, like a bike pump that warms up as you pump. Filling a tank squeezes the gas, so the tank gets hot.",
    "85 °C limit": "The hottest the car's tank is allowed to get. Hotter than this and the tank could be damaged.",
    "State of charge (SOC)": "How full the tank is, like a fuel gauge. 100% is a completely full tank.",
    "Storage banks (cascade)": "Big tanks at the station that hold the hydrogen. The station uses the low-pressure one first, then the higher ones. Going in that order is called a cascade.",
    "Switch margin": "How close the car's pressure gets to a storage tank's pressure before the station switches to the next tank.",
    "Station compressor": "A pump that squeezes hydrogen back into the station's tanks between cars. It runs on electricity.",
    "Dispenser": "The pump you park next to, with the hose. A valve inside it controls how fast the gas flows into the car.",
    "Throttle valve": "A valve that is only partly open, so less gas gets through. Opening it more lets the gas in faster.",
    "Valve seat area": "The size of the hole in the valve when it is fully open. A bigger hole lets more gas through.",
    "Fill speed (ramp rate)": "How fast the pressure in the car's tank goes up, in MPa per minute. Faster means a shorter wait but a hotter tank.",
    "Controller and gains (Kp, Ki, Kd)": "The controller is the station's automatic hand on the valve. The gains set how strongly it reacts when the pressure is off target.",
    "Tracking error (RMS) and overshoot": "Tracking error is how far, on average, the pressure misses its target. Overshoot is the most it goes over.",
    "Flow limit (60 g/s)": "The fastest hydrogen is allowed to flow into a car: 60 grams every second.",
    "Precooler": "A fridge that chills the hydrogen to as cold as −40 °C before it goes into the car. Cold gas in keeps the tank from overheating. It runs by itself: you pick the temperature and it takes out just enough heat to hold it, up to its cooling capacity.",
    "Refrigeration cycle": "How the precooler's fridge works: a liquid boils to take heat out of the hydrogen, then a compressor pushes that heat out to the air.",
    "Delivery set point": "The temperature the precooler tries to chill the hydrogen to.",
    "Cooling capacity": "How much heat the precooler can take out each second, in kW. A small one cannot keep up with a fast fill.",
    "Compressor efficiency": "How well the fridge's compressor uses electricity. 1 would be perfect; real ones are around 0.7.",
    "kWh per kg": "How much electricity is used for each kilogram of hydrogen put in the car. It is what the station pays to run.",
    "SAE J2601": "The rulebook every hydrogen station follows when filling a car: how fast, how cold, and the safety limits.",
    "Station class (T40, T30, T20)": "How cold a station can make the hydrogen: T40 means −40 °C, T30 means −30 °C, T20 means −20 °C. Warmer stations must fill more slowly.",
    "87.5 MPa limit": "The highest pressure ever allowed in a car tank during a fill.",
    "Tank wall (liner and composite)": "The car tank is a plastic inner layer wrapped in carbon fibre. Some of the heat soaks into this wall.",
    "Gas to wall heat transfer (h_in)": "How easily heat moves from the hot gas into the tank wall. Higher means the gas cools faster.",
    "Wall to air heat transfer (h_out)": "How easily heat leaves the outside of the tank into the air.",
    "Real gas and ideal gas": "Ideal gas is the simple textbook formula. At these high pressures it is wrong by a lot, so real-gas mode uses measured hydrogen data.",
    "Time step": "The computer works out the fill in small slices of time. 0.1 s means ten slices every second.",
    "Energy balance": "A check that no energy appears or disappears in the model. Energy in must equal energy stored plus energy removed.",
    "Electrolyser": "A machine that splits water into hydrogen and oxygen using electricity. It is where the hydrogen is made.",
    "Electrolyser type (PEWE, AEWE)": "Two ways to build an electrolyser. PEWE uses an acid membrane and is sold today. AEWE uses an alkaline membrane and is newer and less proven.",
    "Electrolyser electricity": "How much electricity it takes to make one kilogram of hydrogen. Lower is better.",
    "Fuel cell": "The part of the car that turns hydrogen and air back into electricity and water.",
    "Fuel cell type (PEFC, AEFC)": "PEFC uses an acid membrane and is in every hydrogen car on sale. AEFC uses an alkaline membrane and is still a laboratory technology.",
    "What the fuel cell changes": "The fuel cell does not change how the tank fills. It changes what the hydrogen gives back: the electricity out, the round trip, the distance per kilogram and the cost per kilometre.",
    "Fuel cell efficiency": "The share of the hydrogen's energy that comes out of the fuel cell as electricity. The rest leaves as heat.",
    "Electricity price": "What the plant pays for one kWh of electricity.",
    "Cars per day": "How many cars the station fills in a day. The cost of building the station is shared across every kilogram it sells.",
    "Plant drawing (P&ID)": "The line drawing engineers use for a plant. Every tank, valve and machine has a symbol and a tag number, such as K-201 for the compressor.",
    "Station checks (punch list)": "The list of checks a new plant must pass before it is handed over, called a punch list. An open item is a check that has not passed yet.",
    "Round trip": "The electricity you get back from the fuel cell, divided by the electricity used to make, squeeze and chill the hydrogen.",
    "Heating value (HHV and LHV)": "The energy released when hydrogen reacts with oxygen. The higher value (HHV) counts the water as liquid, the lower (LHV) as vapour, as in a car's exhaust.",
    "Build cost and running cost (CapEx, OpEx)": "CapEx is what it costs to build the plant once. OpEx is what it costs to keep it running, here the electricity.",
}
