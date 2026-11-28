"""
Draws every figure of the manuscript from the results written by run_all.py.
Usage:  python paper/figures.py [name ...]

One theme for every figure, matched to the typeset article:
  - TeX Gyre Pagella for text and mathematics, 8 pt ticks and 8.5 pt labels at the printed size;
  - figures are drawn at their printed width (86 mm for one column, 178 mm for two), so nothing is rescaled;
  - one ink colour and two accents (petrol and brick), with every series also told apart by line style and
    marker, so that each figure reads in black-and-white print; no light grey fills (they fade in print),
    bands and bars use hatching or outlines instead;
  - line weights: data 1.1 pt, reference lines 0.7 pt, axes 0.6 pt; no grid;
  - axis labels are symbol and unit; panel letters sit above the top-left corner of each panel.
Each figure is written as a vector PDF (typeset article) and a 300 dpi PNG (Word file).
"""
import os, pickle, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Polygon
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)
C0 = 273.15
MM = 1 / 25.4
ONE, TWO = 86 * MM, 178 * MM

INK = "#1a1a1a"
PETROL = "#1f5a73"
BRICK = "#b5452b"
OCHRE = "#9a7413"
MID = "#5e5e5e"
LIMIT_LW = 0.9

plt.rcParams.update({
    "font.family": "TeX Gyre Pagella", "font.size": 8, "axes.labelsize": 8.5, "axes.titlesize": 8.5,
    "legend.fontsize": 7.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "mathtext.fontset": "custom", "mathtext.rm": "TeX Gyre Pagella", "mathtext.it": "TeX Gyre Pagella:italic",
    "mathtext.bf": "TeX Gyre Pagella:bold", "mathtext.default": "it",
    "axes.linewidth": 0.6, "axes.edgecolor": INK, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK, "ytick.color": INK, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 3, "ytick.major.size": 3, "xtick.minor.size": 1.8, "ytick.minor.size": 1.8,
    "xtick.direction": "out", "ytick.direction": "out",
    "lines.linewidth": 1.1, "lines.markersize": 4, "lines.markeredgewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
    "legend.frameon": False, "legend.handlelength": 2.2, "legend.borderaxespad": 0.3, "legend.labelspacing": 0.3,
    "hatch.linewidth": 0.5, "savefig.dpi": 300, "figure.dpi": 110, "axes.unicode_minus": True,
    "pdf.fonttype": 42,
})


def load(name):
    with open(os.path.join(RES, name + ".pkl"), "rb") as f:
        return pickle.load(f)


def tag(ax, s):
    ax.set_title("(" + s + ")", loc="left", fontsize=9, fontweight="bold", pad=4)


def out(fig, name):
    fig.savefig(os.path.join(FIG, name + ".pdf"))
    fig.savefig(os.path.join(FIG, name + ".png"))
    plt.close(fig)
    print("wrote", name)


def limit(ax, y=85.0, text="85 °C", x=None, ha="right", va="bottom"):
    ax.axhline(y, color=INK, lw=LIMIT_LW, ls=(0, (6, 2)))
    if text:
        xx = ax.get_xlim()[1] if x is None else x
        ax.text(xx, y + 0.6, text, ha=ha, va=va, fontsize=7.5)


# ---------------------------------------------------------------------------------------------------------
# schematics
def _box(ax, x, y, w, h, text, fs=7.5, lw=0.8, style="square,pad=0"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style, fc="white", ec=INK, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.15)


def _arrow(ax, p, q, color=INK, ls="-", lw=1.0, head=7):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=head, color=color, lw=lw, ls=ls,
                                 shrinkA=0, shrinkB=0, joinstyle="miter", capstyle="butt"))


def fig_process():
    """Process flow diagram: one row for hydrogen, electricity above it, heat below it."""
    fig = plt.figure(figsize=(TWO, 62 * MM))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 178); ax.set_ylim(0, 62); ax.axis("off")
    yc = 31
    H = 12
    # station boundary
    ax.add_patch(Rectangle((24, 6), 112, 50, fill=False, ec=INK, lw=0.7, ls=(0, (4, 2))))
    ax.text(134.5, 53.4, "station boundary", fontsize=7.5, va="center", ha="right", style="italic")
    _box(ax, 2, yc - H / 2, 18, H, "supply\n2 MPa, $T_{amb}$")
    _box(ax, 29, yc - H / 2, 19, H, "compressor\n5 stages")
    banks = (("high 95 MPa\n0.5 m$^3$", yc + 12), ("medium 60 MPa\n1.0 m$^3$", yc), ("low 35 MPa\n1.0 m$^3$", yc - 12))
    for lab, y in banks:
        _box(ax, 56, y - 4.5, 22, 9, lab, fs=7)
        _arrow(ax, (48, yc), (56, y))
        _arrow(ax, (78, y), (86, yc))
    _box(ax, 86, yc - H / 2, 20, H, "dispenser valve\nramp control")
    _box(ax, 112, yc - H / 2, 18, H, "precooler\n$T_{pc}(\\xi)$")
    _box(ax, 112, 9, 18, 9, "refrigeration\ncycle", fs=7)
    # vehicle tank: capsule with interface
    tank = FancyBboxPatch((144, yc - 9), 31, 18, boxstyle="round,pad=0,rounding_size=9", fc="white", ec=INK, lw=1.0)
    ax.add_patch(tank)
    ax.plot([145, 174], [yc, yc], color=INK, lw=0.6, ls=(0, (3, 2)))
    ax.text(159.5, yc + 4.3, "upper zone", ha="center", va="center", fontsize=7)
    ax.text(159.5, yc - 4.3, "lower zone", ha="center", va="center", fontsize=7)
    ax.text(159.5, yc + 12, "vehicle tank 141 L", ha="center", va="center", fontsize=7.5)
    # hydrogen path
    _arrow(ax, (20, yc), (29, yc), lw=1.3)
    _arrow(ax, (106, yc), (112, yc), lw=1.3)
    _arrow(ax, (130, yc), (144, yc - 4.3), lw=1.3)
    ax.text(137, yc + 5.0, "$\\dot m,\\ h_{in}$", ha="center", fontsize=7.5)
    # electricity (dashed), heat (dotted, brick)
    _arrow(ax, (38.5, 50), (38.5, yc + H / 2), color=PETROL, ls=(0, (4, 2)))
    ax.text(36.5, 47, "$\\dot W_c$ electricity", ha="right", va="center", fontsize=7.5, color=PETROL)
    _arrow(ax, (104, 13.5), (112, 13.5), color=PETROL, ls=(0, (4, 2)))
    ax.text(103, 13.5, "$\\dot W_r$ electricity", ha="right", va="center", fontsize=7.5, color=PETROL)
    _arrow(ax, (121, yc - H / 2), (121, 18), color=BRICK, ls=(0, (1.2, 1.2)))
    ax.text(122.5, 21.5, "$\\dot Q_{pc}$", fontsize=7.5, color=BRICK, va="center")
    _arrow(ax, (38.5, yc - H / 2), (38.5, 12), color=BRICK, ls=(0, (1.2, 1.2)))
    ax.text(38.5, 9.6, "intercooler heat", ha="center", fontsize=7, color=BRICK)
    _arrow(ax, (130, 13.5), (140, 13.5), color=BRICK, ls=(0, (1.2, 1.2)))
    ax.text(141, 13.5, "condenser heat", va="center", fontsize=7, color=BRICK)
    _arrow(ax, (159.5, yc - 9), (159.5, yc - 15), color=BRICK, ls=(0, (1.2, 1.2)))
    ax.text(161, yc - 13.5, "wall heat $\\dot Q_w$", fontsize=7, color=BRICK, va="center")
    # legend
    hs = [Line2D([], [], color=INK, lw=1.3), Line2D([], [], color=PETROL, lw=1.0, ls=(0, (4, 2))),
          Line2D([], [], color=BRICK, lw=1.0, ls=(0, (1.2, 1.2)))]
    ax.legend(hs, ["hydrogen", "electricity", "heat"], loc="lower left", bbox_to_anchor=(0.003, 0.0), ncol=3,
              fontsize=7.5, handlelength=2.6)
    out(fig, "fig01_process")


def fig_twozone():
    """Two-zone model of the tank gas and the wall discretisation."""
    fig = plt.figure(figsize=(TWO, 58 * MM))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 178); ax.set_ylim(0, 58); ax.axis("off")
    x0, y0, w, h = 24, 10, 96, 36
    shell = FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=18", fc="white", ec=INK, lw=2.2)
    ax.add_patch(shell)
    ym = y0 + h / 2
    # upper zone hatched lightly with diagonal lines (prints in black and white)
    up = Rectangle((x0, ym), w, h / 2, fc="none", ec=INK, lw=0, hatch="////", alpha=0.6)
    ax.add_patch(up); up.set_clip_path(shell)
    ax.plot([x0 + 1.5, x0 + w - 1.5], [ym, ym], color=INK, lw=0.8, ls=(0, (4, 2)))
    ax.text(x0 + w / 2 + 6, ym + 10.5, "upper zone   $m_u,\\ U_u,\\ T_u,\\ V_u=\\phi V$", ha="center", va="center", fontsize=8,
            bbox=dict(fc="white", ec="none", pad=1.2))
    ax.text(x0 + w / 2 + 6, ym - 11.5, "lower zone   $m_l,\\ U_l,\\ T_l,\\ V_l=(1-\\phi)V$", ha="center", va="center", fontsize=8)
    ax.text(x0 + w / 2 - 14, y0 + h + 9.5, "one pressure:  $P(\\rho_u,u_u)=P(\\rho_l,u_l)$", ha="center", va="center", fontsize=8)
    # inlet jet on the axis, into the lower zone
    _arrow(ax, (2, ym - 3.5), (x0 + 12, ym - 3.5), lw=1.6, head=9)
    ax.text(2, ym - 7.5, "$(1-\\chi)\\,\\dot m,\\ h_{in}$", fontsize=8, va="center")
    ax.plot([x0 + 12, x0 + 34], [ym - 3.5, ym - 1.0], color=MID, lw=0.6)
    ax.plot([x0 + 12, x0 + 34], [ym - 3.5, ym - 6.0], color=MID, lw=0.6)
    ax.text(x0 + 35, ym - 3.6, "jet entrains $\\dot m_e$", fontsize=7.5, va="center", color=MID)
    # exchanges across the interface
    xa = x0 + 64
    _arrow(ax, (xa, ym - 5), (xa, ym + 5), color=PETROL)
    _arrow(ax, (xa + 3, ym + 5), (xa + 3, ym - 5), color=PETROL)
    ax.text(xa - 1.2, ym + 2.8, "$\\dot m_x$", fontsize=8, color=PETROL, ha="right", va="center",
            bbox=dict(fc="white", ec="none", pad=0.6))
    _arrow(ax, (xa + 14, ym - 5), (xa + 14, ym + 5), color=INK)
    ax.text(xa + 15.5, ym + 2.8, "$\\dot m_{lu}$", fontsize=8, va="center", bbox=dict(fc="white", ec="none", pad=0.6))
    # wall heat
    _arrow(ax, (x0 + 44, y0 + h + 1.2), (x0 + 44, y0 + h + 6.5), color=BRICK, lw=1.0, head=6)
    ax.text(x0 + 46, y0 + h + 4.0, "$\\dot Q_u$", fontsize=8, color=BRICK, va="center")
    _arrow(ax, (x0 + 44, y0 - 1.2), (x0 + 44, y0 - 6.5), color=BRICK, lw=1.0, head=6)
    ax.text(x0 + 46, y0 - 4.0, "$\\dot Q_l$", fontsize=8, color=BRICK, va="center")
    # wall section
    wx, wy, wh = 136, 12, 32
    ax.add_patch(Rectangle((wx, wy), 6, wh, fc="none", ec=INK, lw=0.7, hatch="....", alpha=1))
    ax.add_patch(Rectangle((wx + 6, wy), 22, wh, fc="none", ec=INK, lw=0.7, hatch="\\\\\\\\"))
    for x in (wx + 1.2, wx + 3.0, wx + 4.8, wx + 7.4, wx + 10.6, wx + 14.6, wx + 19.6, wx + 25.4):
        ax.plot(x, wy + wh / 2, "o", ms=2.6, mfc="white", mec=INK, mew=0.6)
    ax.text(wx + 3, wy + wh + 3, "liner", ha="center", fontsize=7.5)
    ax.text(wx + 17, wy + wh + 3, "composite", ha="center", fontsize=7.5)
    ax.text(wx - 2.5, wy + wh / 2, "gas", ha="right", va="center", fontsize=7.5)
    ax.text(wx + 30.5, wy + wh / 2, "air", ha="left", va="center", fontsize=7.5)
    ax.text(wx + 14, wy - 4.5, "finite volumes, graded to the gas side", ha="center", fontsize=7)
    out(fig, "fig02_twozone")


# ---------------------------------------------------------------------------------------------------------
def fig_validation():
    v = load("validation")
    fig, axs = plt.subplots(2, 2, figsize=(TWO, 118 * MM))
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.085, top=0.94, wspace=0.26, hspace=0.42)
    h = v["hist"]["amb"]; mc = v["mc"]
    ax = axs[0, 0]
    ax.fill_between(mc["t"], mc["p025"], mc["p975"], fc="none", ec=PETROL, lw=0.0, hatch="//////", alpha=0.55)
    ax.plot(h["s"]["t"], h["s"]["T_bulk"] - C0, color=PETROL)
    ax.plot(h["s0"]["t"], h["s0"]["T_bulk"] - C0, color=INK, ls=(0, (1.2, 1.4)), lw=1.0)
    ax.plot(h["case"]["t"], h["case"]["T"], "o", mfc="white", mec=INK)
    ax.set_xlabel("$t$ [s]"); ax.set_ylabel("$T$ [°C]"); ax.set_xlim(0, 270); ax.set_ylim(0, 110); tag(ax, "a")
    hs = [Line2D([], [], color=PETROL), Rectangle((0, 0), 1, 1, fc="none", ec=PETROL, hatch="//////", lw=0),
          Line2D([], [], color=INK, ls=(0, (1.2, 1.4))), Line2D([], [], ls="", marker="o", mfc="white", mec=INK)]
    ax.legend(hs, ["model, mixed mean", "95 % input-uncertainty band", "model without boss", "measured, tank average"],
              loc="lower right", fontsize=7)
    ax = axs[0, 1]; h = v["hist"]["pre"]
    ax.plot(h["s"]["t"], h["s"]["T_bulk"] - C0, color=PETROL, label="model, mixed mean")
    ax.plot(h["case"]["t"], h["case"]["T"], "o", mfc="white", mec=INK, label="measured, tank average")
    ax.set_xlabel("$t$ [s]"); ax.set_ylabel("$T$ [°C]"); ax.set_xlim(0, 215); ax.set_ylim(0, 110)
    ax.legend(loc="upper left", fontsize=7); tag(ax, "b")
    ax = axs[1, 0]; h = v["hist"]["fig5"]
    ax.plot(h["s"]["t"], h["s"]["T_u"] - C0, color=BRICK, label="model, upper zone")
    ax.plot(h["s"]["t"], h["s"]["T_l"] - C0, color=PETROL, ls=(0, (5, 2)), label="model, lower zone")
    ax.plot(h["case"]["t"], h["case"]["T"], "s", mfc="white", mec=INK, label="measured, TC-1 to TC-6")
    ax.set_xlabel("$t$ [s]"); ax.set_ylabel("$T$ [°C]"); ax.set_xlim(0, 270); ax.set_ylim(0, 110)
    ax.legend(loc="lower right", fontsize=7); tag(ax, "c")
    ax = axs[1, 1]
    for key, col, ls, mk, lab in (("amb", PETROL, "-", "o", "gas at 20 °C"), ("pre", BRICK, (0, (5, 2)), "^", "gas at −30 °C")):
        h = v["hist"][key]
        ax.plot(h["s"]["t"], h["s"]["P"] / 1e6, color=col, ls=ls, label="model, " + lab)
        ax.plot(h["case"]["tP"], h["case"]["P"], mk, mfc="white", mec=INK, label="measured, " + lab)
    ax.set_xlabel("$t$ [s]"); ax.set_ylabel("$P$ [MPa]"); ax.set_xlim(0, 270); ax.set_ylim(0, 85)
    ax.legend(loc="upper left", fontsize=7); tag(ax, "d")
    out(fig, "fig03_validation_histories")

    fig, axs = plt.subplots(2, 2, figsize=(TWO, 150 * MM))
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.07, top=0.95, wspace=0.28, hspace=0.34)
    t = v["tab_two-stage"]; rows = t["rows"]
    grp = [("fills to 72 MPa", lambda r: r[2] > 70, "o", "white"), ("fills 15 to 69 MPa", lambda r: 14 < r[1] < 16, "s", INK),
           ("fills to 30 MPa", lambda r: r[2] < 31, "^", "white")]
    for ax, key, col, lab, lim, tg in ((axs[0, 0], "Tu", 5, "$T_{TC5}$", (30, 110), "a"),
                                        (axs[0, 1], "Ttop", 6, "$T_{wall,max}$", (25, 62), "b"),
                                        (axs[1, 0], "Tboss", 7, "$T_{boss,max}$", (15, 60), "c")):
        ax.plot(lim, lim, color=INK, lw=0.7)
        ax.plot(lim, [lim[0] + 5, lim[1] + 5], color=MID, lw=0.6, ls=(0, (4, 2)))
        ax.plot(lim, [lim[0] - 5, lim[1] - 5], color=MID, lw=0.6, ls=(0, (4, 2)))
        for name, sel, mk, fc in grp:
            ix = [i for i, r in enumerate(rows) if sel(r)]
            ax.plot([rows[i][col] for i in ix], [t[key][i] for i in ix], mk, ms=4.5, mfc=fc, mec=INK, mew=0.8, ls="", label=name)
        ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal")
        ax.set_xlabel("measured " + lab + " [°C]"); ax.set_ylabel("model " + lab + " [°C]"); tag(ax, tg)
    axs[0, 0].legend(loc="upper left", fontsize=7)
    ax = axs[1, 1]
    t8 = v["table8_T"]
    lim = (25, 100)
    ax.plot(lim, lim, color=INK, lw=0.7)
    ax.plot(lim, [lim[0] + 5, lim[1] + 5], color=MID, lw=0.6, ls=(0, (4, 2)))
    ax.plot(lim, [lim[0] - 5, lim[1] - 5], color=MID, lw=0.6, ls=(0, (4, 2)))
    ax.plot(t8["implied"], t8["pred"], "D", ms=4.2, mfc="white", mec=INK, ls="", label="29 L, precooled, mixed mean")
    for row, mk in zip(v["tank244"], ("o", "s")):
        runs = [r for r in row["runs"] if r[0] == 3.0]
        lo, hi = runs[0][2], runs[1][2]
        x = row["case"]["Tf"]
        ax.plot([x, x], [lo, hi], color=BRICK, lw=1.1)
        ax.plot(x, lo, mk, ms=4.5, mfc=BRICK, mec=BRICK, ls="")
        ax.plot(x, hi, mk, ms=4.5, mfc="white", mec=BRICK, ls="")
    ax.plot([], [], "o", mfc=BRICK, mec=BRICK, ls="", label="244 L fast fill, inlet at reported minimum")
    ax.plot([], [], "s", mfc=BRICK, mec=BRICK, ls="", label="244 L slow fill, inlet at reported minimum")
    ax.plot([], [], "o", mfc="white", mec=BRICK, ls="", label="244 L, open marks: inlet 10 K warmer")
    ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal")
    ax.set_xlabel("measured or implied $T$ [°C]"); ax.set_ylabel("model $T$ [°C]"); ax.legend(loc="lower right", fontsize=6.8); tag(ax, "d")
    out(fig, "fig04_validation_parity")


# ---------------------------------------------------------------------------------------------------------
def fig_reference():
    r = load("reference"); s = r["ref"]["s"]; s1 = r["onezone"]["s"]
    fig, axs = plt.subplots(2, 2, figsize=(TWO, 112 * MM), sharex=True)
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.09, top=0.94, wspace=0.26, hspace=0.25)
    sw = np.where(np.diff(s["bank"]) > 0)[0]
    tsw = [s["t"][i + 1] for i in sw]
    ax = axs[0, 0]
    ax.plot(s["t"], s["P"] / 1e6, color=PETROL)
    for x in tsw:
        for a in axs.flat:
            a.axvline(x, color=MID, lw=0.6, ls=(0, (1.2, 1.4)))
    edges = [0.0] + tsw + [s["t"][-1]]
    for (a0, a1), lab in zip(zip(edges[:-1], edges[1:]), ("low bank", "medium bank", "high bank")):
        ax.text(0.5 * (a0 + a1), 82, lab, ha="center", fontsize=7)
    ax.set_ylabel("$P$ [MPa]"); ax.set_ylim(0, 90); tag(ax, "a")
    ax = axs[0, 1]
    ax.plot(s["t"], s["T_u"] - C0, color=BRICK, label="upper zone $T_u$")
    ax.plot(s["t"], s["T_l"] - C0, color=PETROL, ls=(0, (5, 2)), label="lower zone $T_l$")
    ax.plot(s1["t"], s1["T_bulk"] - C0, color=INK, ls=(0, (6, 1.5, 1.5, 1.5)), lw=0.9, label="single-zone limit")
    ax.plot(s["t"], s["Ts_u"] - C0, color=INK, ls=(0, (1.2, 1.4)), lw=0.9, label="liner surface, upper")
    ax.set_ylabel("$T$ [°C]"); ax.set_ylim(0, 95); ax.legend(loc="lower right", fontsize=7); tag(ax, "b")
    limit(ax, x=s["t"][-1] * 0.03, ha="left")
    ax = axs[1, 0]
    ax.plot(s["t"], s["mdot"] * 1e3, color=PETROL)
    limit(ax, 60, "60 g/s", x=s["t"][-1] * 0.03, ha="left")
    ax.set_ylabel("$\\dot m$ [g/s]"); ax.set_xlabel("$t$ [s]"); ax.set_ylim(0, 70); tag(ax, "c")
    ax = axs[1, 1]
    ax.plot(s["t"], s["Q_pc"] / 1e3, color=PETROL)
    limit(ax, 60, "60 kW capacity", x=s["t"][-1] * 0.03, ha="left")
    ax.set_ylabel("$\\dot Q_{pc}$ [kW]"); ax.set_xlabel("$t$ [s]"); ax.set_ylim(0, 70); tag(ax, "d")
    for a in axs.flat:
        a.set_xlim(0, s["t"][-1])
    out(fig, "fig05_reference_fill")


def fig_maps():
    m = load("maps"); ref = load("reference")
    fig, axs = plt.subplots(1, 3, figsize=(TWO, 72 * MM), sharey=True)
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.29, top=0.9, wspace=0.12)
    for ax, T, tg in zip(axs, (0.0, 25.0, 40.0), "abc"):
        d = m[T]; Z = d["Z"][:, :, 0]
        cl = ax.contour(d["r"], d["tp"], Z, levels=np.arange(40, 130, 10), colors=[MID], linewidths=0.6)
        ax.clabel(cl, fmt="%d", fontsize=6.5, inline_spacing=2)
        ax.contour(d["r"], d["tp"], Z, levels=[85], colors=[INK], linewidths=1.6)
        ct = ax.contour(d["r"], d["tp"], d["Z"][:, :, 1], levels=[120, 180, 240, 360], colors=[PETROL], linewidths=0.9,
                        linestyles=[(0, (4, 2))])
        ax.clabel(ct, fmt="%d s", fontsize=6.5, inline_spacing=2)
        j = ref["j2601"][T]
        ax.plot(j["x"][0], -40, marker="*", ms=9, mfc="white", mec=BRICK, mew=1.0, clip_on=False, zorder=5)
        ax.set_xlabel("$r$ [MPa/min]"); tag(ax, tg)
        ax.text(0.98, 1.02, "$T_{amb}$ = %d °C" % T, transform=ax.transAxes, ha="right", va="bottom", fontsize=8)
    axs[0].set_ylabel("$T_{pc}$ [°C]")
    hs = [Line2D([], [], color=MID, lw=0.6), Line2D([], [], color=INK, lw=1.6), Line2D([], [], color=PETROL, lw=0.9, ls=(0, (4, 2))),
          Line2D([], [], ls="", marker="*", ms=8, mfc="white", mec=BRICK)]
    fig.legend(hs, ["$T_{hot}$ [°C]", "$T_{hot}$ = 85 °C", "fill time $t_f$", "SAE J2601 table fill"], loc="lower center",
               ncol=4, bbox_to_anchor=(0.53, -0.01), fontsize=7.5)
    out(fig, "fig06_envelope")


def fig_mixing():
    """Predicted end-of-fill spread between the zones for the JRC fill against the two closure parameters."""
    m = load("mixing")
    fig, ax = plt.subplots(figsize=(ONE, 66 * MM))
    fig.subplots_adjust(left=0.16, right=0.97, bottom=0.17, top=0.93)
    B, R = np.meshgrid(m["betas"], m["rics"], indexing="ij")
    lv = [2, 4, 10, 20, 30]
    cl = ax.contour(R, B, m["spread"], levels=lv, colors=[MID], linewidths=0.6)
    ax.clabel(cl, fmt="%d K", fontsize=6.5, inline_spacing=2)
    ax.contour(R, B, m["spread"], levels=[m["measured"]], colors=[PETROL], linewidths=1.1, linestyles=[(0, (4, 2))])
    ax.contour(R, B, m["spread"], levels=[m["spread_max"]], colors=[INK], linewidths=1.6)
    ax.plot(1.0, 0.35, "o", ms=5, mfc="white", mec=INK)
    ax.annotate("calibrated", (1.0, 0.35), xytext=(2.6, 0.66), fontsize=7, arrowprops=dict(arrowstyle="-", lw=0.5, color=INK))
    b, r = m["contour"][0]
    ax.plot(r, b, "s", ms=5, mfc=INK, mec=INK)
    ax.annotate("weakest mixing\nconsistent with data", (r, b), xytext=(5.0, 0.41), fontsize=7, va="center", ha="center",
                arrowprops=dict(arrowstyle="-", lw=0.5, color=INK))
    ax.plot(0.1, 0.15, "^", ms=5.5, mfc=BRICK, mec=BRICK, clip_on=False, zorder=5)
    ax.annotate("box corner", (0.1, 0.15), xytext=(0.14, 0.27), fontsize=7, color=BRICK,
                arrowprops=dict(arrowstyle="-", lw=0.5, color=BRICK))
    ax.set_xscale("log"); ax.set_xlim(0.1, 10); ax.set_ylim(0.13, 1.02)
    ax.set_xticks([0.1, 0.3, 1, 3, 10]); ax.set_xticklabels(["0.1", "0.3", "1", "3", "10"]); ax.minorticks_off()
    ax.set_xlabel("$Ri_c$"); ax.set_ylabel("$\\beta$")
    hs = [Line2D([], [], color=PETROL, lw=1.1, ls=(0, (4, 2))), Line2D([], [], color=INK, lw=1.6)]
    ax.legend(hs, ["measured spread, %.0f K" % m["measured"], "plausible bound, %.0f K" % m["spread_max"]],
              loc="upper right", fontsize=7)
    out(fig, "fig07_mixing")


# ---------------------------------------------------------------------------------------------------------
def _front(ax, F, style, label, every=1):
    o = np.argsort(F[:, 0])
    ax.plot(F[o, 0], F[o, 1], label=label, **style)


def fig_robust():
    """The main result: the price of robustness to weak mixing at 25 degC."""
    o = load("optimise"); b = o[25.0]; ref = b["ref"]
    fig, axs = plt.subplots(1, 3, figsize=(TWO, 66 * MM))
    fig.subplots_adjust(left=0.065, right=0.99, bottom=0.30, top=0.90, wspace=0.34)
    ax = axs[0]
    st = {"nominal": dict(color=INK, ls="-", lw=1.1),
          "robust": dict(color=PETROL, ls=(0, (5, 2)), lw=1.3),
          "box": dict(color=BRICK, ls=(0, (1.2, 1.4)), lw=1.3)}
    lab = {"nominal": "nominal mixing", "robust": "robust, data-consistent weak mixing", "box": "robust, box corner"}
    for k in ("nominal", "robust", "box"):
        _front(ax, b[k]["F"], st[k], lab[k])
    ax.plot(ref["t"], ref["e_station"], "*", ms=10, mfc="white", mec=INK, mew=1.0, ls="", label="SAE J2601 table fill")
    Fb = b["box"]["F"]; ib = int(np.argmax(Fb[:, 0]))
    ax.plot(Fb[ib, 0], Fb[ib, 1], "|", ms=8, mew=1.3, color=BRICK)
    ax.annotate("box corner:\nno feasible fill\nbeyond %.0f s" % Fb[ib, 0], (Fb[ib, 0], Fb[ib, 1]), xytext=(262, 2.36), fontsize=7,
                color=BRICK, arrowprops=dict(arrowstyle="-", lw=0.5, color=BRICK))
    ax.set_xlabel("$t_f$ [s]"); ax.set_ylabel("$e_{st}$ [kWh/kg]"); ax.set_xlim(100, 420); tag(ax, "a")
    # (b) penalty of robustness: extra electricity at equal fill time, robust minus nominal
    ax = axs[1]
    Fn = b["nominal"]["F"][np.argsort(b["nominal"]["F"][:, 0])]
    tg = np.linspace(max(Fn[0, 0], b["robust"]["F"][:, 0].min()), 420, 120)
    def lower_env(F, t):
        F = F[np.argsort(F[:, 0])]
        return np.array([F[F[:, 0] <= x + 1e-9, 1].min() if (F[:, 0] <= x + 1e-9).any() else np.nan for x in t])
    en = lower_env(Fn, tg)
    for k in ("robust", "box"):
        er = lower_env(b[k]["F"], tg)
        er[tg > b[k]["F"][:, 0].max() + 1e-9] = np.nan
        ax.plot(tg, 100 * (er / en - 1), **st[k])
    ax.axhline(0, color=INK, lw=0.6)
    ax.axvline(ref["t"], color=MID, lw=0.6, ls=(0, (1.2, 1.4)))
    ax.set_ylim(-0.2, 2.0)
    ax.text(ref["t"] + 4, 1.9, "J2601\nfill time", fontsize=7, va="top")
    ax.set_xlabel("$t_f$ [s]"); ax.set_ylabel("$\\Delta e_{st}$ at equal $t_f$ [%]"); ax.set_xlim(tg[0], tg[-1]); tag(ax, "b")
    # (c) maximum local temperature of the selected designs: nominal mixing and worst plausible weak mixing
    ax = axs[2]
    names = [("fast", "shortest"), ("knee", "compromise"), ("lean", "least $e_{st}$")]
    x = np.arange(len(names))
    for j, (k, mk, off) in enumerate((("nominal", "o", -0.17), ("robust", "s", 0.17))):
        ch = b[k]["checks"]
        for i, (nm, _) in enumerate(names):
            rows = ch[nm]
            nom = [r[2] for r in rows if abs(r[0] - 0.35) < 1e-9 and abs(r[1] - 1.0) < 1e-9][0]
            plaus = max(r[2] for r in rows[:-2])
            col = INK if k == "nominal" else PETROL
            ax.plot([i + off, i + off], [nom, plaus], color=col, lw=1.0)
            ax.plot(i + off, nom, mk, ms=4.5, mfc="white", mec=col, ls="")
            ax.plot(i + off, plaus, mk, ms=4.5, mfc=col, mec=col, ls="")
    ax.set_xticks(x); ax.set_xticklabels([n[1] for n in names]); ax.set_xlim(-0.6, 2.6)
    ax.set_ylabel("$T_{hot}$ [°C]"); tag(ax, "c")
    lo, hi = ax.get_ylim(); ax.set_ylim(lo - 1, max(hi, 86.5) + 1)
    limit(ax, x=2.55)
    hs = [Line2D([], [], **st["nominal"]), Line2D([], [], **st["robust"]), Line2D([], [], **st["box"]),
          Line2D([], [], ls="", marker="*", ms=9, mfc="white", mec=INK),
          Line2D([], [], ls="", marker="o", mfc="white", mec=INK), Line2D([], [], ls="", marker="o", mfc=INK, mec=INK)]
    fig.legend(hs, ["optimised for nominal mixing", "robust to data-consistent weak mixing", "robust to box-corner mixing",
                    "SAE J2601 table fill", "(c) evaluated with nominal mixing", "(c) evaluated with weakest plausible mixing"],
               loc="lower center", ncol=3, bbox_to_anchor=(0.52, 0.0), fontsize=7.2, columnspacing=1.6)
    out(fig, "fig08_robust")


def fig_pareto():
    o = load("optimise")
    b = o[25.0]
    fig, axs = plt.subplots(2, 2, figsize=(TWO, 118 * MM))
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.085, top=0.95, wspace=0.26, hspace=0.42)
    ax = axs[0, 0]
    sty = {0.0: dict(color=PETROL, ls=(0, (5, 2))), 25.0: dict(color=INK, ls="-"), 40.0: dict(color=BRICK, ls=(0, (1.2, 1.4)), lw=1.3)}
    mk = {0.0: "o", 25.0: "s", 40.0: "^"}
    for T in (0.0, 25.0, 40.0):
        F = o[T]["robust"]["F"]; rf = o[T]["ref"]
        _front(ax, F, sty[T], "%d °C" % T)
        ax.plot(rf["t"], rf["e_station"], mk[T], ms=5.5, mfc="white", mec=sty[T]["color"], mew=1.0, ls="")
    F2 = b["robust_seed2"]["F"]
    ax.plot(F2[:, 0], F2[:, 1], "x", ms=3.2, color=INK, mew=0.6, ls="", label="25 °C, second seed")
    ax.plot([], [], "s", ms=5.5, mfc="white", mec=INK, ls="", label="J2601 fill (open marks)")
    ax.set_xlabel("$t_f$ [s]"); ax.set_ylabel("$e_{st}$ [kWh/kg]"); ax.set_xscale("log")
    ax.set_xticks([100, 200, 400, 800]); ax.set_xticklabels(["100", "200", "400", "800"]); ax.minorticks_off()
    ax.set_ylim(1.95, 3.25)
    ax.legend(loc="upper right", fontsize=7, ncol=2, columnspacing=1.0); tag(ax, "a")
    F = b["robust"]["F"]; X = b["robust"]["X"]
    o_ = np.argsort(F[:, 0]); F, X = F[o_], X[o_]
    x0 = b["ref_x"]
    for ax, (i, j), (la, lb), yl, ref_v, tg in ((axs[0, 1], (0, 1), ("first stage $r_1$", "second stage $r_2$"), "$r$ [MPa/min]", x0[0], "b"),
                                                (axs[1, 0], (5, 6), ("start of fill $T_{pc,a}$", "end of fill $T_{pc,b}$"), "$T_{pc}$ [°C]", x0[5], "c"),
                                                (axs[1, 1], (3, 4), ("low to medium $\\Delta P_1$", "medium to high $\\Delta P_2$"), "$\\Delta P$ [MPa]", x0[3], "d")):
        ax.plot(F[:, 0], X[:, i], "o", ms=3.2, mfc="white", mec=PETROL, ls="", label=la)
        ax.plot(F[:, 0], X[:, j], "^", ms=3.2, mfc=BRICK, mec=BRICK, ls="", label=lb)
        ax.axhline(ref_v, color=INK, lw=0.7, ls=(0, (6, 2)))
        ax.set_xlabel("$t_f$ [s]"); ax.set_ylabel(yl); tag(ax, tg)
        ax.legend(loc="best", fontsize=7)
    out(fig, "fig09_pareto")


def fig_effectiveness():
    o = load("optimise"); m = load("maps")
    b = o[25.0]; ref = b["ref"]
    fig, axs = plt.subplots(2, 2, figsize=(TWO, 128 * MM))
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.075, top=0.95, wspace=0.27, hspace=0.45)
    # (a) temperature effectiveness of precooling over the operating envelope
    ax = axs[0, 0]; d = m[25.0]
    T_hot = d["Z"][:, :, 0]; T0 = d["Z0"][:, 0][None, :]
    eff = (T0 - T_hot) / (T0 - d["tp"][:, None])
    cl = ax.contour(d["r"], d["tp"], eff, levels=np.arange(0.15, 0.41, 0.05), colors=[PETROL], linewidths=0.8)
    ax.clabel(cl, fmt="%.2f", fontsize=6.5, inline_spacing=2)
    ax.contour(d["r"], d["tp"], T_hot, levels=[85], colors=[INK], linewidths=1.6)
    ax.set_xlabel("$r$ [MPa/min]"); ax.set_ylabel("$T_{pc}$ [°C]"); tag(ax, "a")
    hs = [Line2D([], [], color=PETROL, lw=0.8), Line2D([], [], color=INK, lw=1.6)]
    ax.legend(hs, ["$\\varepsilon_T$", "$T_{hot}$ = 85 °C"], loc="lower right", fontsize=7, ncol=2, bbox_to_anchor=(1.0, 1.0),
              borderaxespad=0.1)
    # (b) fronts of each strategy alone and integrated
    ax = axs[0, 1]
    sty = (("precooling", dict(color=PETROL, ls=(0, (5, 2))), "precooling only"),
           ("cascade", dict(color=OCHRE, ls=(0, (1.2, 1.4)), lw=1.4), "bank switching only"),
           ("ramp", dict(color=BRICK, ls=(0, (6, 1.5, 1.5, 1.5))), "ramp only"))
    for key, s_, lab in sty:
        F = b["subsets"][key]["front"]["F"]
        _front(ax, F, s_, lab)
        if len(F) == 1:
            ax.plot(F[:, 0], F[:, 1], "o", ms=3.5, color=s_["color"])
    _front(ax, b["robust"]["F"], dict(color=INK, ls="-", lw=1.3), "integrated")
    ax.plot(ref["t"], ref["e_station"], "*", ms=10, mfc="white", mec=INK, mew=1.0, ls="", label="J2601 table fill")
    ax.set_xlabel("$t_f$ [s]"); ax.set_ylabel("$e_{st}$ [kWh/kg]"); ax.set_xlim(90, 420); tag(ax, "b")
    ax.legend(loc="upper right", fontsize=7)
    # (c) maximum local and mixed-mean temperature of the shortest-time and least-electricity designs
    ax = axs[1, 0]
    keys = ["ref", "precooling", "cascade", "ramp", "all"]
    labels = ["J2601", "precool", "switch", "ramp", "all"]
    picks = [None] + [b["subsets"][k]["picks"] for k in ("precooling", "cascade", "ramp")] + [b["robust"]["picks"]]
    x = np.arange(len(keys)); w = 0.34
    for j, (which, hatch, lab) in enumerate((("fast", "", "shortest-time design"), ("lean10", "//////", "least-electricity design"))):
        hot = [ref["T_hot"] if p is None else p[which]["T_hot"] for p in picks]
        blk = [ref["T_bulk"] if p is None else p[which]["T_bulk"] for p in picks]
        xx = x + (j - 0.5) * (w + 0.04)
        ax.bar(xx, hot, w, fc="white" if hatch else INK, ec=INK, lw=0.7, hatch=hatch, label=lab)
        ax.plot(xx, blk, "_", ms=9, mew=1.6, color=BRICK, ls="", label="mixed mean $T_{mix}$" if j == 0 else None)
    ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylabel("$T_{hot}$ [°C]"); ax.set_ylim(0, 125)
    ax.axhline(85, color=INK, lw=LIMIT_LW, ls=(0, (6, 2)))
    ax.text(4.62, 86.2, "85 °C", ha="right", va="bottom", fontsize=7.5)
    ax.legend(loc="upper left", fontsize=7, ncol=2, bbox_to_anchor=(0.0, 1.02), columnspacing=1.0, handlelength=1.6)
    tag(ax, "c")
    # (d) reductions relative to the J2601 fill (robust designs)
    ax = axs[1, 1]
    cases = [("precool", b["subsets"]["precooling"]["picks"], ref), ("switch", b["subsets"]["cascade"]["picks"], ref),
             ("ramp", b["subsets"]["ramp"]["picks"], ref), ("all\n25 °C", b["robust"]["picks"], ref),
             ("all\n0 °C", o[0.0]["robust"]["picks"], o[0.0]["ref"]), ("all\n40 °C", o[40.0]["robust"]["picks"], o[40.0]["ref"])]
    x = np.arange(len(cases)); w = 0.36
    dt = [100 * (1 - p["fast"]["t"] / r["t"]) for _, p, r in cases]
    de = [100 * (1 - p["lean10"]["e_station"] / r["e_station"]) for _, p, r in cases]
    for j, (vals, hatch, lab) in enumerate(((dt, "", "fill time, shortest-time design"), (de, "//////", "electricity, least-electricity design"))):
        xx = x + (j - 0.5) * (w + 0.04)
        ax.bar(xx, vals, w, fc="white" if hatch else INK, ec=INK, lw=0.7, hatch=hatch, label=lab)
        for xi, v_ in zip(xx, vals):
            if abs(v_) < 0.05:
                continue
            ax.text(xi, v_ + (1.2 if v_ >= 0 else -1.2), ("%.0f" % v_) if abs(v_) >= 9.5 else ("%.1f" % v_), ha="center",
                    va="bottom" if v_ >= 0 else "top", fontsize=6.5)
    ax.axhline(0, color=INK, lw=0.6)
    ax.set_xticks(x); ax.set_xticklabels([c[0] for c in cases]); ax.set_ylabel("reduction from J2601 fill [%]")
    ax.set_ylim(min(0, min(dt + de)) - 4, max(dt + de) * 1.28)
    ax.legend(loc="upper left", fontsize=7, bbox_to_anchor=(0.0, 1.03)); tag(ax, "d")
    out(fig, "fig10_effectiveness")


def fig_sobol():
    s = load("sensitivity")
    names = [i[0] for i in s["inputs"]]
    pretty = {"f_h": "gas-side coefficient $f_h$", "k_liner": "liner conductivity", "cp_liner": "liner specific heat", "k_cfrp": "composite conductivity",
              "T0": "initial tank temperature", "P0": "initial tank pressure", "dT_in": "precooler set point error", "eta_s": "compressor efficiency",
              "dZ": "compressibility $Z$", "dcv": "caloric properties", "beta": "mixing efficiency $\\beta$", "Ri_c": "critical Richardson $Ri_c$", "phi": "zone volume fraction $\\phi$"}
    fig, axs = plt.subplots(1, 2, figsize=(TWO, 72 * MM), sharey=False)
    fig.subplots_adjust(left=0.19, right=0.985, bottom=0.14, top=0.92, wspace=0.95)
    for ax, key, tg, xl in zip(axs, ("T_hot", "T_hot_minus_bulk"), "ab", ("Sobol index for $T_{hot}$", "Sobol index for $T_{hot}-T_{mix}$")):
        j = s["outputs"].index(key)
        ST = np.clip(s["ST"][:, j], 0, None); S1 = np.clip(s["S"][:, j], 0, None)
        o = np.argsort(ST)
        y = np.arange(len(names))
        ax.barh(y, ST[o], 0.62, fc="white", ec=INK, lw=0.7)
        ax.plot(S1[o], y, "o", ms=3.8, mfc=PETROL, mec=PETROL, ls="")
        ax.set_yticks(y); ax.set_yticklabels([pretty[names[i]] for i in o])
        ax.set_xlim(0, 1); ax.set_xlabel(xl); ax.set_ylim(-0.7, len(names) - 0.3); tag(ax, tg)
        ax.tick_params(axis="y", length=0)
    hs = [Rectangle((0, 0), 1, 1, fc="white", ec=INK, lw=0.7), Line2D([], [], ls="", marker="o", mfc=PETROL, mec=PETROL)]
    axs[0].legend(hs, ["total index $S_T$", "first-order index $S_1$"], loc="lower right", fontsize=7.5)
    out(fig, "fig11_sobol")


def fig_energy():
    e = load("energy"); r = load("reference")
    fig, axs = plt.subplots(1, 2, figsize=(TWO, 70 * MM))
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.31, top=0.92, wspace=0.28)
    ax = axs[0]
    a2 = r["stop70_2stage"]; a = e["ref"]
    cols = [("earlier\naccounting", r["class"]["e_comp"], 0.0, r["class"]["e_chill"], 0.0),
            ("2 stages,\nrefill path", a2["e_comp_gas"], a2["e_comp"] - a2["e_comp_gas"], a2["e_ref_shaft"], a2["e_ref"] - a2["e_ref_shaft"]),
            ("5 stages,\nrefill path", a["e_comp_gas"], a["e_comp"] - a["e_comp_gas"], a["e_ref_shaft"], a["e_ref"] - a["e_ref_shaft"])]
    x = np.arange(len(cols)); bot = np.zeros(len(cols))
    parts = (("compressor, gas-side work", "white", ""), ("compressor, drive losses", "white", "//////"),
             ("refrigeration, shaft work", INK, ""), ("refrigeration, drive losses", "white", "xxxx"))
    for k, (lab, fc, hatch) in enumerate(parts):
        vals = np.array([c[k + 1] for c in cols])
        ax.bar(x, vals, 0.52, bottom=bot, fc=fc, ec=INK, lw=0.7, hatch=hatch, label=lab); bot += vals
    for xi, b_ in zip(x, bot):
        ax.text(xi, b_ + 0.05, "%.2f" % b_, ha="center", va="bottom", fontsize=7.5)
    ax.set_xticks(x); ax.set_xticklabels([c[0] for c in cols]); ax.set_ylabel("$e$ [kWh/kg]"); ax.set_ylim(0, 3.0); tag(ax, "a")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=2, fontsize=7, columnspacing=1.0)
    ax = axs[1]; u = e["util"]
    op_ = u[:, 3] + u[:, 4] + u[:, 5]
    ax.plot(u[:, 1], u[:, 2] + op_, "-", color=INK, lw=1.4, label="total, $n$ = 0.7")
    ax.plot(u[:, 1], u[:, 9] + op_, color=INK, lw=0.7, ls=(0, (4, 2)), label="total, $n$ = 0.6 and 0.8")
    ax.plot(u[:, 1], u[:, 8] + op_, color=INK, lw=0.7, ls=(0, (4, 2)))
    ax.plot(u[:, 1], u[:, 2], color=PETROL, marker="o", ms=3.2, mfc="white", label="capital and fixed O&M")
    ax.plot(u[:, 1], u[:, 3], color=BRICK, ls=(0, (5, 2)), marker="s", ms=3.2, mfc="white", label="energy charge")
    ax.plot(u[:, 1], u[:, 4], color=OCHRE, ls=(0, (6, 1.5, 1.5, 1.5)), marker="^", ms=3.2, mfc="white", label="demand charge")
    ax.plot(u[:, 1], u[:, 5], color=INK, ls=(0, (1.2, 1.4)), marker="D", ms=3.0, mfc="white", label="precooler standby")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("station throughput [kg/day]"); ax.set_ylabel("$c$ [\\$/kg]")
    ax.set_xticks([30, 100, 300, 1000]); ax.set_xticklabels(["30", "100", "300", "1000"])
    ax.set_yticks([0.01, 0.1, 1.0]); ax.set_yticklabels(["0.01", "0.1", "1"])
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=2, fontsize=7, columnspacing=1.0); tag(ax, "b")
    out(fig, "fig12_energy_cost")


def fig_graphical():
    """Graphical abstract: the two-zone tank, the robust and nominal fronts and the J2601 point."""
    o = load("optimise"); b = o[25.0]; ref = b["ref"]
    fig = plt.figure(figsize=(TWO, 70 * MM))
    ax0 = fig.add_axes([0.0, 0.0, 0.42, 1.0]); ax0.set_xlim(0, 75); ax0.set_ylim(0, 70); ax0.axis("off")
    shell = FancyBboxPatch((8, 18), 60, 30, boxstyle="round,pad=0,rounding_size=15", fc="white", ec=INK, lw=2.0)
    ax0.add_patch(shell)
    up = Rectangle((8, 33), 60, 15, fc="none", ec=INK, lw=0, hatch="////", alpha=0.35); ax0.add_patch(up); up.set_clip_path(shell)
    ax0.plot([9, 67], [33, 33], color=INK, lw=0.7, ls=(0, (4, 2)))
    ax0.text(38, 40.5, "hot upper zone, $T_u$", ha="center", fontsize=8, bbox=dict(fc="white", ec="none", pad=1))
    ax0.text(38, 25, "lower zone with inlet jet, $T_l$", ha="center", fontsize=8)
    _arrow(ax0, (0, 29), (16, 29), lw=1.5, head=9)
    ax0.text(38, 55, "two-zone real-gas tank model", ha="center", fontsize=8.5, fontweight="bold")
    ax0.text(38, 9, "limit applied to max($T_u$, $T_l$) under\nweak mixing consistent with JRC data", ha="center", fontsize=7.5)
    ax = fig.add_axes([0.52, 0.2, 0.46, 0.68])
    _front(ax, b["nominal"]["F"], dict(color=INK, ls="-"), "nominal mixing")
    _front(ax, b["robust"]["F"], dict(color=PETROL, ls=(0, (5, 2)), lw=1.3), "robust")
    ax.plot(ref["t"], ref["e_station"], "*", ms=10, mfc="white", mec=INK, ls="", label="SAE J2601 table fill")
    ax.set_xlim(90, 420); ax.set_xlabel("$t_f$ [s]"); ax.set_ylabel("$e_{st}$ [kWh/kg]")
    ax.legend(loc="upper right", fontsize=7)
    ax.set_title("optimised fills, 25 °C ambient", fontsize=8.5, loc="left")
    out(fig, "graphical_abstract")


if __name__ == "__main__":
    which = sys.argv[1:] or ["process", "twozone", "validation", "reference", "maps", "mixing", "robust", "pareto",
                             "effectiveness", "sobol", "energy", "graphical"]
    for w in which:
        globals()["fig_" + w]()
