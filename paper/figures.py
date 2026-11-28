"""
Draws every figure of the manuscript from the results written by run_all.py.
Usage:  python paper/figures.py
"""
import os, pickle, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Ellipse

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)
C0 = 273.15
# categorical colours in fixed order (validated palette), each paired with its own line style and marker
BLUE, ORANGE, AQUA, YELLOW, VIOLET, INK, GREY = "#257de0", "#f47230", "#00b894", "#f2a600", "#6a4ce2", "#191919", "#8a8a8a"
plt.rcParams.update({
    "font.family": "DejaVu Serif", "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9, "legend.fontsize": 8,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.linewidth": 0.6, "lines.linewidth": 1.6, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#e3e3e3", "grid.linewidth": 0.5, "legend.frameon": False,
    "savefig.dpi": 300, "figure.dpi": 110, "mathtext.fontset": "dejavuserif"})


def load(name):
    with open(os.path.join(RES, name + ".pkl"), "rb") as f:
        return pickle.load(f)


def tag(ax, s):
    ax.text(-0.14, 1.04, "(" + s + ")", transform=ax.transAxes, fontsize=10, fontweight="bold", va="bottom")


def out(fig, name):
    fig.savefig(os.path.join(FIG, name + ".png"), bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


# ---------------------------------------------------------------------------------------------------------
def fig_process():
    fig, ax = plt.subplots(figsize=(7.6, 3.9))
    ax.set_xlim(0, 120); ax.set_ylim(0, 56); ax.axis("off")

    def box(x, y, w, h, text, fs=7):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3", fc="white", ec=INK, lw=0.9))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs)

    def arrow(p, q, color=INK, ls="-", lw=1.1):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=9, color=color, lw=lw, ls=ls))

    ax.add_patch(Rectangle((16, 3), 76, 51, fill=False, ec=GREY, ls=(0, (5, 3)), lw=1.0))
    ax.text(17, 51.3, "station system boundary", fontsize=7.5, color="#555555")
    box(0.5, 23, 12.5, 10, "hydrogen\nsupply\n2 MPa, $T_{amb}$")
    box(18, 23, 14, 10, "compressor\n$N$ stages,\nintercooled")
    for lab, y in (("high bank\n95 MPa, 0.5 m$^3$", 38), ("medium bank\n60 MPa, 1.0 m$^3$", 24), ("low bank\n35 MPa, 1.0 m$^3$", 10)):
        box(38, y, 17, 8, lab)
        arrow((32.3, 28), (37.7, y + 4))
        arrow((55.3, y + 4), (60.7, 28))
    box(60.5, 23, 13, 10, "dispenser\nvalve,\nramp control", fs=6.5)
    box(77, 23, 12, 10, "precooler\n$T_{pc}(P)$")
    box(77, 6, 12, 8, "refrigeration\ncycle", fs=6.5)
    box(97, 18, 22.5, 20, "")
    ax.add_patch(Ellipse((108.25, 32), 19.5, 7, fc="#f6d9c9", ec=INK, lw=0.6))
    ax.add_patch(Ellipse((108.25, 24), 19.5, 7, fc="#cfe2f8", ec=INK, lw=0.6))
    ax.text(108.25, 32, "upper zone\n$m_u,\\ U_u,\\ T_u$", ha="center", va="center", fontsize=6.5)
    ax.text(108.25, 24, "lower zone\n$m_l,\\ U_l,\\ T_l$", ha="center", va="center", fontsize=6.5)
    ax.text(108.25, 39.6, "vehicle tank, 141 L", ha="center", fontsize=7.5)
    arrow((13.3, 28), (17.7, 28)); arrow((73.3, 28), (76.7, 28)); arrow((89.3, 28), (96.7, 25))
    ax.text(93, 31.5, r"$\dot m,\ h_{in}$", fontsize=7.5, ha="center")
    arrow((83, 22.7), (83, 14.3), color=ORANGE); ax.text(84, 18, r"$\dot Q_{pc}$", fontsize=7.5, color="#b24a12")
    arrow((25, 46), (25, 33.4), color=BLUE, ls="--"); ax.text(25, 47, r"$\dot W_{c}$, electricity", fontsize=7.5, color="#1757ac", ha="center")
    arrow((68, 10), (76.7, 10), color=BLUE, ls="--"); ax.text(67.5, 12, r"$\dot W_{r}$, electricity", fontsize=7.5, color="#1757ac", ha="center")
    arrow((25, 22.7), (25, 15), color=ORANGE); ax.text(25, 10.5, "intercooler and\naftercooler heat", fontsize=7, color="#b24a12", ha="center")
    arrow((89.3, 10), (97, 10), color=ORANGE); ax.text(107, 9.3, "condenser heat\nto ambient", fontsize=7, color="#b24a12", ha="center")
    arrow((108.25, 17.7), (108.25, 13.5), color=ORANGE); ax.text(110, 14.8, r"wall heat $\dot Q_w$", fontsize=7, color="#b24a12", ha="left")
    ax.plot([], [], color=INK, label="hydrogen"); ax.plot([], [], color=BLUE, ls="--", label="electricity"); ax.plot([], [], color=ORANGE, label="heat")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, -0.07), ncol=3)
    out(fig, "fig01_process")


def fig_twozone():
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    ax.set_xlim(-5, 112); ax.set_ylim(0, 50); ax.axis("off")
    shell = FancyBboxPatch((12, 9), 60, 30, boxstyle="round,pad=0,rounding_size=15", fc="#cfe2f8", ec=INK, lw=2.5)
    ax.add_patch(shell)
    up = Rectangle((10, 24), 64, 17, fc="#f6d9c9", ec="none")
    ax.add_patch(up); up.set_clip_path(shell)
    ax.add_patch(FancyBboxPatch((12, 9), 60, 30, boxstyle="round,pad=0,rounding_size=15", fc="none", ec=INK, lw=2.5))
    ax.plot([12.5, 71.5], [24, 24], color=INK, lw=0.8, ls="--")
    ax.text(42, 33.5, "upper zone:  $m_u,\\ U_u,\\ T_u,\\ V_u=\\phi V$", ha="center", fontsize=8.5)
    ax.text(42, 12.2, "lower zone:  $m_l,\\ U_l,\\ T_l,\\ V_l=(1-\\phi)V$", ha="center", fontsize=8.5)

    def arrow(p, q, color=INK, lw=1.2):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=10, color=color, lw=lw))
    arrow((-4, 20), (21, 20), lw=1.8); ax.text(-4, 15.5, r"$(1-\chi)\,\dot m,\ h_{in}$", fontsize=8)
    arrow((23, 19.7), (30, 17.7), color=GREY, lw=0.8); arrow((23, 20.3), (30, 22.2), color=GREY, lw=0.8)
    ax.text(31, 19.8, "jet entrains tank gas, $\\dot m_e$", fontsize=7, color="#555555", va="center")
    arrow((47, 21.5), (47, 27), color=AQUA); arrow((49.5, 27), (49.5, 21.5), color=AQUA)
    ax.text(42, 28.4, r"mixing $\dot m_x$", fontsize=8, color="#00846a")
    arrow((60, 21.5), (60, 27), color=VIOLET); ax.text(56, 28.4, r"net flow $\dot m_{lu}$", fontsize=8, color=VIOLET)
    arrow((30, 39.5), (30, 45.5), color=ORANGE); ax.text(31.5, 43.6, r"$\dot Q_u = h_u A_u (T_u - T_{s,u})$", fontsize=8, color="#b24a12")
    arrow((30, 8.5), (30, 2.5), color=ORANGE); ax.text(31.5, 3.3, r"$\dot Q_l = h_l A_l (T_l - T_{s,l})$", fontsize=8, color="#b24a12")
    ax.add_patch(Rectangle((86, 13), 4, 24, fc="#d9d9d9", ec=INK, lw=0.6)); ax.add_patch(Rectangle((90, 13), 14, 24, fc="#f1f1f1", ec=INK, lw=0.6))
    for x in (87, 88.2, 89.3, 91, 93, 95.5, 98.5, 102):
        ax.plot(x, 25, "o", ms=2.5, color=INK)
    ax.text(88, 38.2, "liner", ha="center", fontsize=7.5); ax.text(97, 38.2, "composite", ha="center", fontsize=7.5)
    ax.text(95, 3.5, "wall of each zone:\none-dimensional conduction,\nfinite volumes", ha="center", fontsize=7)
    ax.text(83.5, 25, "gas", ha="center", fontsize=7.5, rotation=90, va="center"); ax.text(106.5, 25, "air", ha="center", fontsize=7.5, rotation=90, va="center")
    ax.text(42, 47.6, "common pressure  $P(\\rho_u,u_u)=P(\\rho_l,u_l)$", ha="center", fontsize=8.5)
    out(fig, "fig02_twozone")


# ---------------------------------------------------------------------------------------------------------
def fig_validation():
    v = load("validation")
    fig, axs = plt.subplots(2, 2, figsize=(7.4, 5.6))
    h = v["hist"]["amb"]; mc = v["mc"]
    ax = axs[0, 0]
    ax.fill_between(mc["t"], mc["p025"], mc["p975"], color=BLUE, alpha=0.16, lw=0, label="model, 95 % interval of input uncertainty")
    ax.plot(h["s"]["t"], h["s"]["T_bulk"] - C0, color=BLUE, label="model, nominal")
    ax.plot(h["s0"]["t"], h["s0"]["T_bulk"] - C0, color=GREY, ls=":", label="model without boss heat sink")
    ax.plot(h["case"]["t"], h["case"]["T"], "o", ms=4.5, mfc="white", mec=INK, label="measured, tank average [A13]")
    ax.set_xlabel("time, s"); ax.set_ylabel("gas temperature, °C"); ax.set_xlim(0, 270); ax.legend(loc="lower right", fontsize=6.8)
    ax.set_title("29 L tank, gas at 20 °C, 2 to 76.9 MPa", fontsize=8.5); tag(ax, "a")
    ax = axs[0, 1]; h = v["hist"]["pre"]
    ax.plot(h["s"]["t"], h["s"]["T_bulk"] - C0, color=BLUE, label="model, nominal")
    ax.plot(h["case"]["t"], h["case"]["T"], "o", ms=4.5, mfc="white", mec=INK, label="measured, tank average [A13]")
    ax.set_xlabel("time, s"); ax.set_ylabel("gas temperature, °C"); ax.set_xlim(0, 215); ax.legend(loc="lower right", fontsize=6.8)
    ax.set_title("29 L tank, gas precooled to −30 °C, 2 to 78.1 MPa", fontsize=8.5); tag(ax, "b")
    ax = axs[1, 0]; h = v["hist"]["fig5"]
    ax.plot(h["s"]["t"], h["s"]["T_u"] - C0, color=ORANGE, label="model, upper zone")
    ax.plot(h["s"]["t"], h["s"]["T_l"] - C0, color=BLUE, ls="--", label="model, lower zone")
    ax.plot(h["case"]["t"], h["case"]["T"], "s", ms=4.5, mfc="white", mec=INK, label="measured, TC-1 to TC-6 [A11]")
    ax.set_xlabel("time, s"); ax.set_ylabel("gas temperature, °C"); ax.set_xlim(0, 270); ax.legend(loc="lower right", fontsize=6.8)
    ax.set_title("29 L tank, gas at 20 °C, 3.86 to 72.06 MPa", fontsize=8.5); tag(ax, "c")
    ax = axs[1, 1]
    for key, col, ls, mk, lab in (("amb", BLUE, "-", "o", "gas at 20 °C"), ("pre", ORANGE, "--", "^", "gas at −30 °C")):
        h = v["hist"][key]
        ax.plot(h["s"]["t"], h["s"]["P"] / 1e6, color=col, ls=ls, label="model, " + lab)
        ax.plot(h["case"]["tP"], h["case"]["P"], mk, ms=4.5, mfc="white", mec=INK, label="measured, " + lab)
    ax.set_xlabel("time, s"); ax.set_ylabel("tank pressure, MPa"); ax.legend(loc="lower right", fontsize=6.8)
    ax.set_title("imposed pressure history", fontsize=8.5); tag(ax, "d")
    fig.tight_layout(); out(fig, "fig03_validation_histories")

    fig, axs = plt.subplots(2, 2, figsize=(7.0, 6.2))
    t = v["tab_two-stage"]; rows = t["rows"]
    grp = [("to 72 MPa", lambda r: r[2] > 70, BLUE, "o"), ("15 to 69 MPa", lambda r: 14 < r[1] < 16, ORANGE, "s"), ("to 30 MPa", lambda r: r[2] < 31, AQUA, "^")]
    for ax, key, col, title, lim, tg in ((axs[0, 0], "Tu", 5, "TC-5 at end of fill, °C", (30, 110), "a"),
                                          (axs[0, 1], "Ttop", 6, "outer wall maximum, °C", (25, 62), "b"),
                                          (axs[1, 0], "Tboss", 7, "boss maximum, °C", (15, 60), "c")):
        for lab, sel, c, mk in grp:
            ix = [i for i, r in enumerate(rows) if sel(r)]
            ax.plot([rows[i][col] for i in ix], [t[key][i] for i in ix], mk, ms=5, mfc="white", mec=c, mew=1.3, label=lab)
        ax.plot(lim, lim, color=INK, lw=0.8)
        ax.plot(lim, [lim[0] + 5, lim[1] + 5], color=GREY, lw=0.6, ls="--"); ax.plot(lim, [lim[0] - 5, lim[1] - 5], color=GREY, lw=0.6, ls="--")
        ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal"); ax.set_xlabel("measured " + title); ax.set_ylabel("model, °C"); tag(ax, tg)
    axs[0, 0].legend(loc="upper left", title="fill group", title_fontsize=7.5)
    ax = axs[1, 1]; p = v["table8"]
    ax.plot(p["meas"], p["pred"][:, 0], "D", ms=5, mfc="white", mec=VIOLET, mew=1.3)
    lim = (91, 101); ax.plot(lim, lim, color=INK, lw=0.8)
    ax.plot(lim, [lim[0] + 2, lim[1] + 2], color=GREY, lw=0.6, ls="--"); ax.plot(lim, [lim[0] - 2, lim[1] - 2], color=GREY, lw=0.6, ls="--")
    ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal"); ax.set_xlabel("measured final state of charge, %"); ax.set_ylabel("model, %"); tag(ax, "d")
    fig.tight_layout(); out(fig, "fig04_validation_parity")


# ---------------------------------------------------------------------------------------------------------
def fig_reference():
    r = load("reference"); s = r["ref"]["s"]; s1 = r["onezone"]["s"]; c = r["class"]
    fig, axs = plt.subplots(2, 2, figsize=(7.4, 5.2), sharex=True)
    ax = axs[0, 0]
    ax.plot(s["t"], s["P"] / 1e6, color=BLUE); ax.set_ylabel("tank pressure, MPa"); tag(ax, "a")
    sw = np.where(np.diff(s["bank"]) > 0)[0]
    for i in sw:
        ax.axvline(s["t"][i + 1], color=GREY, lw=0.7, ls=":")
    for x, lab in zip([0] + [s["t"][i + 1] for i in sw], ("low bank", "medium bank", "high bank")):
        ax.text(x + 3, 6, lab, fontsize=7, color="#555555", rotation=90, va="bottom")
    ax = axs[0, 1]
    ax.plot(s["t"], s["T_u"] - C0, color=ORANGE, label="upper zone")
    ax.plot(s["t"], s["T_l"] - C0, color=BLUE, ls="--", label="lower zone")
    ax.plot(s1["t"], s1["T_bulk"] - C0, color=AQUA, ls="-.", label="single-zone limit")
    ax.plot(s["t"], s["Ts_u"] - C0, color=GREY, ls=":", label="liner surface, upper")
    ax.set_ylabel("temperature, °C"); ax.legend(loc="lower right", fontsize=7); tag(ax, "b")
    ax = axs[1, 0]
    ax.plot(s["t"], s["mdot"] * 1e3, color=BLUE); ax.axhline(60, color=INK, lw=0.7, ls="--"); ax.text(2, 61, "60 g/s limit", fontsize=7)
    ax.set_ylabel("mass flow rate, g/s"); ax.set_xlabel("time, s"); ax.set_ylim(0, 66); tag(ax, "c")
    ax = axs[1, 1]
    ax.plot(s["t"], s["Q_pc"] / 1e3, color=BLUE, label="precooler duty"); ax.axhline(60, color=INK, lw=0.7, ls="--"); ax.text(2, 61, "capacity", fontsize=7)
    ax.set_ylabel("precooler heat rate, kW"); ax.set_xlabel("time, s"); ax.set_ylim(0, 66); tag(ax, "d")
    fig.tight_layout(); out(fig, "fig05_reference_fill")


def fig_maps():
    m = load("maps")
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.9), sharey=True)
    for ax, T, tg in zip(axs, (0.0, 25.0, 40.0), "abc"):
        d = m[T]; Z = d["Z"][:, :, 0]
        cs = ax.contourf(d["r"], d["tp"], Z, levels=np.arange(20, 126, 7.5), cmap="Blues", extend="both")
        ax.contour(d["r"], d["tp"], Z, levels=[85], colors=[INK], linewidths=1.6)
        cl = ax.contour(d["r"], d["tp"], d["Z"][:, :, 1], levels=[120, 150, 180, 240, 360], colors=["#ffffff"], linewidths=0.7, linestyles="--")
        ax.clabel(cl, fmt="%d s", fontsize=6.5)
        ax.set_title("ambient %d °C" % T, fontsize=8.5); ax.set_xlabel("ramp rate, MPa/min"); tag(ax, tg); ax.grid(False)
    axs[0].set_ylabel("precooler set point, °C")
    cb = fig.colorbar(cs, ax=axs, shrink=0.9, pad=0.02); cb.set_label("maximum local gas temperature, °C")
    out(fig, "fig06_envelope")


def fig_pareto():
    o = load("optimise")
    fig, axs = plt.subplots(2, 3, figsize=(7.6, 5.0))
    ax = axs[0, 0]
    for T, col, mk in ((0.0, BLUE, "o"), (25.0, ORANGE, "s"), (40.0, AQUA, "^")):
        F = o[T]["front"]["F"]; rf = o[T]["ref"]
        ax.plot(F[:, 0], F[:, 1], mk, ms=3, color=col, label="%d °C" % T)
        ax.plot(rf["t"], rf["e_station"], mk, ms=8, mfc="white", mec=col, mew=1.5)
    ax.plot([], [], "s", ms=7, mfc="white", mec=INK, label="reference fill")
    ax.set_xlabel("fill time, s"); ax.set_ylabel("station electricity, kWh/kg"); ax.set_ylim(1.95, 3.25); ax.legend(title="ambient", title_fontsize=7, fontsize=6.5, ncol=2, loc="upper right"); tag(ax, "a")
    F = o[25.0]["front"]["F"]; X = o[25.0]["front"]["X"]
    ax = axs[0, 1]
    ax.plot(F[:, 1], F[:, 2], "s", ms=3, color=ORANGE); ax.set_xlabel("station electricity, kWh/kg"); ax.set_ylabel("operating cost, $/kg"); tag(ax, "b")
    ax = axs[0, 2]
    F2 = o[25.0]["front_seed2"]["F"]
    ax.plot(F[:, 0], F[:, 1], "s", ms=3, color=ORANGE, label="seed 1"); ax.plot(F2[:, 0], F2[:, 1], "x", ms=3.5, color=INK, label="seed 2")
    ax.set_xlabel("fill time, s"); ax.set_ylabel("station electricity, kWh/kg"); ax.legend(fontsize=7); tag(ax, "c")
    ax = axs[1, 0]
    ax.plot(F[:, 0], X[:, 0], "o", ms=3, color=BLUE, label="first stage $r_1$"); ax.plot(F[:, 0], X[:, 1], "^", ms=3, color=ORANGE, label="second stage $r_2$")
    ax.axhline(18.5, color=INK, lw=0.7, ls="--"); ax.set_xlabel("fill time, s"); ax.set_ylabel("ramp rate, MPa/min"); ax.legend(fontsize=7); tag(ax, "d")
    ax = axs[1, 1]
    ax.plot(F[:, 0], X[:, 5], "o", ms=3, color=BLUE, label="start of fill $T_{pc,a}$"); ax.plot(F[:, 0], X[:, 6], "^", ms=3, color=ORANGE, label="end of fill $T_{pc,b}$")
    ax.axhline(-40, color=INK, lw=0.7, ls="--"); ax.set_xlabel("fill time, s"); ax.set_ylabel("precooler set point, °C"); ax.legend(fontsize=7); tag(ax, "e")
    ax = axs[1, 2]
    ax.plot(F[:, 0], X[:, 3], "o", ms=3, color=BLUE, label="low to medium"); ax.plot(F[:, 0], X[:, 4], "^", ms=3, color=ORANGE, label="medium to high")
    ax.axhline(2, color=INK, lw=0.7, ls="--"); ax.set_xlabel("fill time, s"); ax.set_ylabel("switching margin, MPa"); ax.legend(fontsize=7); tag(ax, "f")
    fig.tight_layout(); out(fig, "fig07_pareto")


def fig_effectiveness():
    o = load("optimise"); m = load("maps")
    b = o[25.0]; ref = b["ref"]
    fig, axs = plt.subplots(2, 2, figsize=(7.6, 6.4))
    # (a) temperature effectiveness of precooling over the operating envelope
    ax = axs[0, 0]; d = m[25.0]
    T_hot = d["Z"][:, :, 0]; T0 = d["Z0"][:, 0][None, :]
    eff = (T0 - T_hot) / (T0 - d["tp"][:, None])
    cs = ax.contourf(d["r"], d["tp"], eff, levels=np.linspace(0.12, 0.40, 15), cmap="Blues", extend="both")
    ax.contour(d["r"], d["tp"], T_hot, levels=[85], colors=[INK], linewidths=1.6)
    ax.text(0.97, 0.93, "85 °C", transform=ax.transAxes, fontsize=7.5, ha="right")
    cb = fig.colorbar(cs, ax=ax, pad=0.02); cb.set_label(r"temperature effectiveness $\varepsilon_T$")
    ax.set_xlabel("pressure ramp rate, MPa/min"); ax.set_ylabel("precooler set point, °C"); ax.grid(False); tag(ax, "a")
    # (b) specific electricity against fill time
    ax = axs[0, 1]
    sty = (("precooling", BLUE, "o", "adaptive precooling only"), ("cascade", ORANGE, "s", "bank switching only"), ("ramp", AQUA, "^", "ramp control only"))
    for key, col, mk, lab in sty:
        F = b["subsets"][key]["front"]["F"]
        ax.plot(F[:, 0], F[:, 1], mk, ms=3.5, color=col, label=lab)
    F = b["front"]["F"]
    ax.plot(F[:, 0], F[:, 1], "D", ms=3, color=VIOLET, label="integrated")
    ax.plot(ref["t"], ref["e_station"], "*", ms=12, mfc="white", mec=INK, mew=1.2, label="reference fill")
    ax.set_xlabel("fill time, s"); ax.set_ylabel("station electricity, kWh/kg"); ax.legend(fontsize=7); ax.set_xlim(90, 420); tag(ax, "b")
    # (c) maximum local temperature of the selected designs
    ax = axs[1, 0]
    names = ["reference"] + [k for k, *_ in sty] + ["integrated"]
    labels = ["reference", "pre-\ncooling", "switch-\ning", "ramp", "all"]
    picks = [None] + [b["subsets"][k]["picks"] for k, *_ in sty] + [b["picks"]]
    x = np.arange(len(names)); w = 0.36
    for j, (which, col, lab) in enumerate((("fast", BLUE, "shortest fill time"), ("lean10", ORANGE, "least electricity"))):
        hot = [ref["T_hot"] if p is None else p[which]["T_hot"] for p in picks]
        blk = [ref["T_bulk"] if p is None else p[which]["T_bulk"] for p in picks]
        ax.bar(x + (j - 0.5) * (w + 0.03), hot, w, color=col, label=lab + ": hotter zone")
        ax.plot(x + (j - 0.5) * (w + 0.03), blk, "_", ms=12, mew=2, color=INK, label="mixed-mean temperature" if j == 0 else None)
        for xi, hv in zip(x + (j - 0.5) * (w + 0.03), hot):
            ax.text(xi, hv + 1.2, "%.0f" % hv, ha="center", fontsize=7)
    ax.axhline(85, color=INK, lw=0.9, ls="--"); ax.text(-0.45, 86, "85 °C limit", fontsize=7.5)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7.5); ax.set_ylabel("maximum gas temperature, °C"); ax.set_ylim(0, 100)
    ax.legend(fontsize=6.8, loc="upper center", bbox_to_anchor=(0.5, 1.17), ncol=3, columnspacing=0.8, handlelength=1.2); ax.grid(axis="x"); tag(ax, "c")
    # (d) improvement relative to the reference fill
    ax = axs[1, 1]
    cases = [("pre-\ncooling", b["subsets"]["precooling"]["picks"], ref), ("switch-\ning", b["subsets"]["cascade"]["picks"], ref),
             ("ramp", b["subsets"]["ramp"]["picks"], ref), ("all,\n25 °C", b["picks"], ref),
             ("all,\n0 °C", o[0.0]["picks"], o[0.0]["ref"]), ("all,\n40 °C", o[40.0]["picks"], o[40.0]["ref"])]
    x = np.arange(len(cases)); w = 0.26
    dt = [100 * (1 - p["fast"]["t"] / r["t"]) for _, p, r in cases]
    de = [100 * (1 - p["lean10"]["e_station"] / r["e_station"]) for _, p, r in cases]
    dc = [100 * (1 - p["lean10"]["c_op"] / r["c_op"]) for _, p, r in cases]
    for j, (vals, col, lab) in enumerate(((dt, BLUE, "fill time, shortest-time design"), (de, ORANGE, "electricity, least-electricity design"), (dc, AQUA, "operating cost, least-electricity design"))):
        ax.bar(x + (j - 1) * (w + 0.02), vals, w, color=col, label=lab)
        for xi, v in zip(x + (j - 1) * (w + 0.02), vals):
            if abs(v) >= 0.05:
                ax.text(xi, v + 0.8, "%.0f" % v if abs(v) >= 9.5 else "%.1f" % v, ha="center", fontsize=6)
    ax.set_xticks(x); ax.set_xticklabels([c[0] for c in cases], fontsize=7); ax.set_ylabel("reduction relative to reference fill, %")
    ax.legend(fontsize=6.8, loc="upper left"); ax.grid(axis="x"); ax.set_ylim(0, max(dt) * 1.35); tag(ax, "d")
    fig.tight_layout(); out(fig, "fig08_effectiveness")


def fig_sobol():
    s = load("sensitivity")
    names = [i[0] for i in s["inputs"]]
    pretty = {"f_h": "heat transfer coefficient", "k_liner": "liner conductivity", "cp_liner": "liner specific heat", "k_cfrp": "composite conductivity",
              "T0": "initial tank temperature", "P0": "initial tank pressure", "dT_in": "inlet (precooler) temperature", "eta_s": "compressor efficiency",
              "dZ": "property: compressibility", "dcv": "property: caloric", "beta": "mixing efficiency", "Ri_c": "critical Richardson number", "phi": "zone volume fraction"}
    outs = (("T_hot", "maximum local\ntemperature"), ("T_hot_minus_bulk", "local minus\nmixed-mean"), ("t_fill", "fill time\n"), ("e_station", "station\nelectricity"))
    fig, axs = plt.subplots(1, 4, figsize=(7.6, 3.5), sharey=True)
    y = np.arange(len(names))[::-1]
    for ax, (key, title), tg in zip(axs, outs, "abcd"):
        j = s["outputs"].index(key)
        ax.barh(y + 0.19, np.clip(s["ST"][:, j], 0, None), 0.36, color=BLUE, label="total index $S_{T}$")
        ax.barh(y - 0.19, np.clip(s["S"][:, j], 0, None), 0.36, color=ORANGE, label="first-order index $S_1$")
        ax.set_title(title, fontsize=8); ax.set_xlim(0, 1); ax.grid(axis="y"); ax.set_xlabel("Sobol index")
        ax.text(0.02, 1.17, "(" + tg + ")", transform=ax.transAxes, fontsize=9, fontweight="bold")
    axs[0].set_yticks(y); axs[0].set_yticklabels([pretty[n] for n in names], fontsize=7.5)
    axs[3].legend(fontsize=7, loc="lower right")
    fig.tight_layout(); out(fig, "fig09_sobol")


def fig_energy():
    e = load("energy"); r = load("reference")
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.2))
    ax = axs[0]
    a2 = r["stop70_2stage"]; a = e["ref"]
    cols = [("earlier\naccounting", r["class"]["e_comp"], 0.0, r["class"]["e_chill"], 0.0),
            ("2 stages,\nrefill path", a2["e_comp_gas"], a2["e_comp"] - a2["e_comp_gas"], a2["e_ref_shaft"], a2["e_ref"] - a2["e_ref_shaft"]),
            ("5 stages,\nrefill path", a["e_comp_gas"], a["e_comp"] - a["e_comp_gas"], a["e_ref_shaft"], a["e_ref"] - a["e_ref_shaft"])]
    x = np.arange(len(cols)); bot = np.zeros(len(cols))
    for k, (lab, col) in enumerate((("compressor, gas-side work", BLUE), ("compressor, mechanical and motor losses", "#84b9f3"),
                                     ("refrigeration compressor, shaft work", ORANGE), ("refrigeration, drive losses", "#f9b995"))):
        vals = np.array([c[k + 1] for c in cols])
        ax.bar(x, vals, 0.55, bottom=bot, color=col, label=lab, edgecolor="white", linewidth=1.2); bot += vals
    for xi, b in zip(x, bot):
        ax.text(xi, b + 0.04, "%.2f" % b, ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels([c[0] for c in cols], fontsize=7.5); ax.set_ylabel("specific electricity, kWh/kg"); ax.set_ylim(0, 3.9)
    ax.legend(fontsize=6.6, loc="upper left"); ax.grid(axis="x"); tag(ax, "a")
    ax = axs[1]; u = e["util"]
    tot = u[:, 2] + u[:, 3] + u[:, 4] + u[:, 5]
    ax.plot(u[:, 1], tot, "-", color=INK, lw=2, label="total")
    for col, lab, c, ls, mk in ((2, "capital and fixed O&M", BLUE, "-", "o"), (3, "energy charge", ORANGE, "--", "s"), (4, "demand charge", AQUA, "-.", "^"), (5, "precooler standby", YELLOW, ":", "D")):
        ax.plot(u[:, 1], u[:, col], ls, color=c, marker=mk, ms=3.5, label=lab)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("hydrogen dispensed, kg/day"); ax.set_ylabel("station cost, $/kg (production excluded)")
    ax.legend(fontsize=7, loc="lower left"); tag(ax, "b")
    fig.tight_layout(); out(fig, "fig10_energy_cost")


if __name__ == "__main__":
    which = sys.argv[1:] or ["process", "twozone", "validation", "reference", "maps", "pareto", "effectiveness", "sobol", "energy"]
    for w in which:
        globals()["fig_" + w]()
