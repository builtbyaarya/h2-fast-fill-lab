"""
Two-zone real-gas model of the vehicle tank, coupled to the cascade station.

What this file does
    Integrates one fill. The vehicle tank gas is split into two zones that
    share one pressure and have separate mass, internal energy and
    temperature. Each zone exchanges heat with its own part of the tank wall,
    and the wall is resolved through its thickness (liner and composite) by
    one-dimensional transient conduction. The station side (banks, dispenser
    valve, ramp controller, precooler) follows the class model, with three
    additions: a two-stage pressure ramp, a precooler set point that can
    change during the fill, and a separate switching margin for each bank.

Zones
    l   lower zone. It contains the axis of the inlet jet and receives the
        fraction (1 - chi) of the inlet flow. chi = 0 by default.
    u   upper zone. It receives the fraction chi of the inlet flow.
    The zone volumes are fixed fractions of the tank volume, V_u = phi V and
    V_l = (1 - phi) V. The default phi = 0.5 places the interface on the
    horizontal mid-plane of the cylinder.

Balances (stagnation enthalpy h_in at the inlet, rigid tank, no shaft work)
    dm_l/dt = (1 - chi) m_in - m_lu
    dm_u/dt =      chi  m_in + m_lu
    dU_l/dt = (1 - chi) m_in h_in - m_lu h* - m_x (h_l - h_u) - Q_l
    dU_u/dt =      chi  m_in h_in + m_lu h* + m_x (h_l - h_u) - Q_u
    P(rho_l, u_l) = P(rho_u, u_u)

    m_lu  net flow from the lower to the upper zone. It is not modelled by a
          rate law; it is the flow that keeps the two pressures equal, and it
          carries the enthalpy h* of the zone it leaves.
    m_x   mixing exchange: equal and opposite mass flows between the zones.

Mixing closure
    The inlet jet entrains tank gas. For a turbulent free jet Ricou and
    Spalding (1961) measured
        m_e = 0.32 m_in (x / d) sqrt(rho_gas / rho_jet)
    at a distance x from a nozzle of diameter d. Molkov et al. (2019) use the
    same relation to estimate the gas velocity in a tank during fuelling. I
    evaluate it at x = L (tank inner length) to obtain the circulating flow,
    and take
        m_x = beta F(Ri) m_e,      F = 1 / (1 + Ri / Ri_c)
        Ri  = g (rho_l - rho_u) D / (rho_mean u_c^2)   (zero when rho_u > rho_l)
        u_c = m_in u_in / (m_in + m_e)                  (jet momentum conserved)
    beta is a mixing efficiency and Ri_c a critical Richardson number. Both
    are closure parameters. They are calibrated against one subset of JRC
    fills and tested against the rest (jrc.py).

Wall heat transfer
    Gas side: the mixed-convection correlation of Woodfield, Monde and
    Mitsutake (2007), Nu = 0.56 Re_d^0.67 + 0.104 Ra^0.352, with Re_d based on
    the injector diameter and the inlet mass flow, and Nu and Ra based on the
    tank inner diameter. The forced term of the upper zone is multiplied by
    F(Ri), because the same jet circulation drives it. f_h multiplies the
    result and is 1 unless the uncertainty analysis changes it.
    Wall: finite-volume conduction through liner and composite, explicit in
    time. The surface temperature follows from equal convective and
    conductive flux at the surface.
    Outside: a constant coefficient h_out to ambient air.

Numerical method
    Explicit Euler in time with operator splitting: (1) flows, heat transfer
    and mixing at the old state, (2) update of masses, energies and wall
    temperatures, (3) projection onto equal zone pressures by moving mass
    between the zones at the donor enthalpy (secant iteration, tolerance
    1 Pa). The method is first order in the time step; the step-size study
    in the manuscript reports the measured convergence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .props import (R_H2, interp, P_rhoT, T_rhou, rho_PT, h_PT, T_Ph, load_table, njit)

G = 9.80665
RHO_FULL = 40.2          # kg/m3, 100 % state of charge (70 MPa, 15 degC), SAE J2601
C_RS = 0.32              # Ricou-Spalding entrainment coefficient
NU_C1, NU_N1 = 0.56, 0.67      # Woodfield et al. (2007), forced term
NU_C2, NU_N2 = 0.104, 0.352    # Woodfield et al. (2007), natural term
NSER = 16                # number of stored time-series channels


@njit(cache=True)
def _equalise(tab, mu, Uu, ml, Ul, Vu, Vl, Tu, Tl):
    """Move mass between the zones at the donor enthalpy until the two pressures are equal."""
    Tu = T_rhou(tab, mu / Vu, Uu / mu, Tu)
    Tl = T_rhou(tab, ml / Vl, Ul / ml, Tl)
    Pu = P_rhoT(tab, mu / Vu, Tu)
    Pl = P_rhoT(tab, ml / Vl, Tl)
    f0 = Pu - Pl
    if abs(f0) < 1.0:
        return mu, Uu, ml, Ul, Tu, Tl, 0.5 * (Pu + Pl), 0.0
    if f0 < 0.0:      # lower zone at higher pressure: flow from l to u at h_l
        hd = Ul / ml + Pl * Vl / ml
    else:
        hd = Uu / mu + Pu * Vu / mu
    d0 = 0.0
    d1 = -f0 / (1.4 * Pu / mu + 1.4 * Pl / ml)
    P = 0.5 * (Pu + Pl)
    for _ in range(12):
        a, b, c, e = mu + d1, Uu + d1 * hd, ml - d1, Ul - d1 * hd
        Tu = T_rhou(tab, a / Vu, b / a, Tu)
        Tl = T_rhou(tab, c / Vl, e / c, Tl)
        Pu = P_rhoT(tab, a / Vu, Tu)
        Pl = P_rhoT(tab, c / Vl, Tl)
        f1 = Pu - Pl
        P = 0.5 * (Pu + Pl)
        if abs(f1) < 1.0 or f1 == f0:
            break
        d2 = d1 - f1 * (d1 - d0) / (f1 - f0)
        d0, f0, d1 = d1, f1, d2
    return mu + d1, Uu + d1 * hd, ml - d1, Ul - d1 * hd, Tu, Tl, P, d1


@njit(cache=True)
def _valve_flow(tab, CdA, x, P_up, T_up, rho_up, P_dn):
    """Isentropic nozzle relation of the class model (choked or subsonic), with real-gas density and k."""
    if x <= 0.0 or P_up <= P_dn:
        return 0.0
    k = interp(tab, 3, rho_up, T_up) / interp(tab, 2, rho_up, T_up)
    Pr = P_dn / P_up
    Pc = (2.0 / (k + 1.0)) ** (k / (k - 1.0))
    if Pr <= Pc:
        psi = math.sqrt(k) * (2.0 / (k + 1.0)) ** ((k + 1.0) / (2.0 * (k - 1.0)))
    else:
        psi = math.sqrt(max(0.0, 2.0 * k / (k - 1.0) * (Pr ** (2.0 / k) - Pr ** ((k + 1.0) / k))))
    return CdA * x * math.sqrt(rho_up * P_up) * psi


@njit(cache=True)
def _simulate(tab, tk, wdx, wk, wrc, sdx, sk, src, bV, bP0, ct, cop, dt, ndec, nmax):
    # ---- unpack -------------------------------------------------------------------------------
    V, D, L, d_inj, A_w, phi, chi, beta, Ri_c, f_h, h_out, T_amb, T_g0, P0, T_w0 = tk[:15]
    bank_T0, supply_T, inlet_mode = tk[15], tk[16], tk[17]
    A_boss, t_hold = tk[18], tk[19]
    (r1, r2, xi_b, Kp, Ki, flow_lim, CdA, P_cap, soc_tgt, P_stop, t_max, dsw1, dsw2,
     Tpc_a, Tpc_b, Q_max, pc_on, P_ref, pinch, eta_ref_drive) = ct[:20]
    cop_T0, cop_dT = cop[0], cop[1]
    ncop = cop.shape[0] - 2
    N = wdx.shape[0]
    nb = bV.shape[0]
    Vu, Vl = phi * V, (1.0 - phi) * V
    Au, Al = phi * (A_w - A_boss), (1.0 - phi) * (A_w - A_boss)
    Nb = sdx.shape[0]
    A_inj = 0.25 * math.pi * d_inj * d_inj

    # ---- initial state ------------------------------------------------------------------------
    rho0 = rho_PT(tab, P0, T_g0)
    u0 = interp(tab, 1, rho0, T_g0)
    mu, ml = rho0 * Vu, rho0 * Vl
    Uu, Ul = mu * u0, ml * u0
    Tu, Tl = T_g0, T_g0
    Twu = np.full(N, T_w0)
    Twl = np.full(N, T_w0)
    Tsu, Tsl = T_w0, T_w0
    Tbs = np.full(Nb, T_w0)     # metallic end bosses, one slab
    Tsb = T_w0
    bm = np.zeros(nb)
    bU = np.zeros(nb)
    bT = np.full(nb, bank_T0)
    for i in range(nb):
        r = rho_PT(tab, bP0[i], bank_T0)
        bm[i] = r * bV[i]
        bU[i] = bm[i] * interp(tab, 1, r, bank_T0)
    bm0 = bm.copy()
    m0 = mu + ml
    U0 = Uu + Ul
    Ew0 = 0.0
    for i in range(N):
        Ew0 += wrc[i] * wdx[i] * (Au * Twu[i] + Al * Twl[i])
    for i in range(Nb):
        Ew0 += src[i] * sdx[i] * A_boss * Tbs[i]

    ser = np.zeros((nmax // ndec + 3, NSER))
    ns = 0
    t = 0.0
    P = P0
    ib = 0
    integ = 0.0
    sat = False
    out_prev = 0.0
    E_cool = 0.0
    E_ref = 0.0
    Q_wall = 0.0
    Q_out = 0.0
    Q_boss = 0.0
    H_in = 0.0
    Tu_max, Tl_max, Tb_max, Ts_max = T_g0, T_g0, T_g0, T_w0
    Qpc_max = 0.0
    Wref_max = 0.0
    mdot_max = 0.0
    P_max = P0
    Tdel_sum, Tdel_w = 0.0, 0.0
    reason = 0   # 1 SOC target, 2 pressure target, 3 time limit, 4 banks equalised
    bank_used = np.zeros(nb)
    xi_span = max(P_ref - P0, 1.0)
    step = 0
    T_del = T_amb
    mdot = 0.0
    Qpc = 0.0
    mx = 0.0
    Ri = 0.0
    hu_c, hl_c = 0.0, 0.0
    dPdm = 1.4 * P0 / m0
    holding = False
    t_fill = 0.0
    Tout_max, Tboss_max = T_w0, T_w0
    fin = np.zeros(6)

    while True:
        # ---- store ----------------------------------------------------------------------------
        if step % ndec == 0:
            rb = (mu + ml) / V
            Tb = T_rhou(tab, rb, (Uu + Ul) / (mu + ml), 0.5 * (Tu + Tl))
            s = ser[ns]
            s[0], s[1], s[2], s[3], s[4] = t, P, Tu, Tl, Tb
            s[5], s[6], s[7], s[8] = mdot, T_del, Qpc, ib
            s[9], s[10], s[11] = Tsu, Tsl, 100.0 * rb / RHO_FULL
            s[12], s[13], s[14], s[15] = hl_c, mx, Ri, Twu[N - 1]
            ns += 1
        if step >= nmax:
            break
        if reason != 0 and not holding:
            # end of the fill: keep the end-of-fill values, then follow the closed tank for t_hold seconds
            holding = True
            t_fill = t
            fin[0], fin[1], fin[2], fin[3], fin[4], fin[5] = t, mu + ml - m0, P, 100.0 * (mu + ml) / V / RHO_FULL, Tu, Tl
        if holding and t >= t_fill + t_hold:
            break

        if holding:
            mdot = 0.0
            Qpc = 0.0
            W_ref = 0.0
            h_in = 0.0
            hb = 0.0
            x = 0.0
        else:
            # ---- cascade selection ----------------------------------------------------------------
            rb_ = bm[ib] / bV[ib]
            bT[ib] = T_rhou(tab, rb_, bU[ib] / bm[ib], bT[ib])
            Pb = P_rhoT(tab, rb_, bT[ib])
            while ib < nb - 1:
                marg = dsw1 if ib == 0 else dsw2
                if Pb - P < marg:
                    ib += 1
                    rb_ = bm[ib] / bV[ib]
                    bT[ib] = T_rhou(tab, rb_, bU[ib] / bm[ib], bT[ib])
                    Pb = P_rhoT(tab, rb_, bT[ib])
                else:
                    break
            hb = bU[ib] / bm[ib] + Pb / rb_
            if inlet_mode > 0.5:           # supply line held at a set temperature upstream of the valve
                T_up = supply_T
                rho_up = rho_PT(tab, Pb, T_up)
                hb_flow = interp(tab, 1, rho_up, T_up) + Pb / rho_up
            else:
                T_up, rho_up, hb_flow = bT[ib], rb_, hb

            # ---- ramp controller (two-stage average pressure ramp rate, PI with anti-windup) --------
            P_break = P0 + xi_b * xi_span
            t_break = (P_break - P0) / r1
            if t <= t_break:
                P_tgt = P0 + r1 * t
            else:
                P_tgt = P_break + r2 * (t - t_break)
            if P_tgt > P_cap:
                P_tgt = P_cap
            if Kp < 0.0:
                # Test-rig mode: the measured pressure history is imposed. The flow is the one that moves the
                # pressure to the target of the next step, using the pressure rise per unit mass of the last step.
                P_next = P_tgt + (r1 if t < t_break else r2) * dt
                if P_next > P_cap:
                    P_next = P_cap
                mdot = 0.7 * (P_next - P) / (dPdm * dt)
                if mdot < 0.0:
                    mdot = 0.0
                x = 1.0 if mdot > 0.0 else 0.0
            else:
                e = (P_tgt - P) * 1.0e-6
                if (not sat) or (e * out_prev < 0.0):
                    integ += e * dt
                raw = Kp * e + Ki * integ
                x = min(1.0, max(0.0, raw))
                sat = x != raw
                out_prev = x
                mdot = _valve_flow(tab, CdA, x, Pb, T_up, rho_up, P)
            if mdot > flow_lim:
                mdot = flow_lim

            # ---- throttle (h constant) and precooler (isobaric at tank pressure) ---------------------
            xi = (P - P0) / xi_span
            if xi < 0.0:
                xi = 0.0
            if xi > 1.0:
                xi = 1.0
            T_set = Tpc_a + (Tpc_b - Tpc_a) * xi
            h_in = hb_flow
            Qpc = 0.0
            W_ref = 0.0
            if pc_on > 0.5 and mdot > 0.0:
                h_set = h_PT(tab, P, T_set)
                if h_in > h_set:
                    Qpc = mdot * (h_in - h_set)
                    if Qpc > Q_max:
                        Qpc = Q_max
                    h_in = h_in - Qpc / mdot
                    jc = (T_set - pinch - cop_T0) / cop_dT
                    if jc < 0.0:
                        jc = 0.0
                    if jc > ncop - 1.000001:
                        jc = ncop - 1.000001
                    j0 = int(jc)
                    c = cop[2 + j0] * (1 - (jc - j0)) + cop[3 + j0] * (jc - j0)
                    W_ref = Qpc / c / eta_ref_drive
            if inlet_mode > 1.5 and mdot > 0.0:   # test rig: gas temperature measured at the tank inlet
                h_in = h_PT(tab, P, supply_T)
            if mdot > 0.0:
                T_del = T_Ph(tab, P, h_in, T_del)

        # ---- jet entrainment, Richardson number, mixing exchange -------------------------------
        rho_u, rho_l = mu / Vu, ml / Vl
        rho_m = (mu + ml) / V
        F = 1.0
        mx = 0.0
        Ri = 0.0
        Re_d = 0.0
        if mdot > 0.0:
            rho_in = rho_PT(tab, P, T_del)
            u_in = mdot / (rho_in * A_inj)
            kk = interp(tab, 3, rho_in, T_del) / interp(tab, 2, rho_in, T_del)
            a_s = math.sqrt(kk * interp(tab, 0, rho_in, T_del) * R_H2 * T_del)
            if u_in > a_s:
                u_in = a_s
            m_e = C_RS * mdot * (L / d_inj) * math.sqrt(rho_m / rho_in)
            u_c = mdot * u_in / (mdot + m_e)
            if rho_l > rho_u:
                Ri = G * (rho_l - rho_u) * D / (rho_m * u_c * u_c)
            F = 1.0 / (1.0 + Ri / Ri_c)
            mx = beta * F * m_e
            cap = 0.4 * min(mu, ml) / dt
            if mx > cap:
                mx = cap
            Re_d = 4.0 * mdot / (math.pi * d_inj * interp(tab, 4, rho_in, T_del))
        Nu_f = NU_C1 * Re_d ** NU_N1 if Re_d > 0.0 else 0.0

        # ---- gas-side coefficients and wall surface temperatures -----------------------------
        lam_u = interp(tab, 5, rho_u, Tu)
        lam_l = interp(tab, 5, rho_l, Tl)
        Ra_u = (G * interp(tab, 6, rho_u, Tu) * abs(Tu - Tsu) * D ** 3 * rho_u ** 2
                * interp(tab, 3, rho_u, Tu) / (interp(tab, 4, rho_u, Tu) * lam_u))
        Ra_l = (G * interp(tab, 6, rho_l, Tl) * abs(Tl - Tsl) * D ** 3 * rho_l ** 2
                * interp(tab, 3, rho_l, Tl) / (interp(tab, 4, rho_l, Tl) * lam_l))
        hu_c = f_h * (F * Nu_f + NU_C2 * Ra_u ** NU_N2) * lam_u / D
        hl_c = f_h * (Nu_f + NU_C2 * Ra_l ** NU_N2) * lam_l / D
        g0 = 2.0 * wk[0] / wdx[0]
        Tsu = (hu_c * Tu + g0 * Twu[0]) / (hu_c + g0)
        Tsl = (hl_c * Tl + g0 * Twl[0]) / (hl_c + g0)
        qu = hu_c * (Tu - Tsu)      # W/m2, gas to wall
        ql = hl_c * (Tl - Tsl)
        # end bosses: one metal slab, half of its wetted area in each zone
        qbu, qbl = 0.0, 0.0
        if A_boss > 0.0:
            gb = 2.0 * sk[0] / sdx[0]
            Tsb = (0.5 * hu_c * Tu + 0.5 * hl_c * Tl + gb * Tbs[0]) / (0.5 * hu_c + 0.5 * hl_c + gb)
            qbu = hu_c * (Tu - Tsb)
            qbl = hl_c * (Tl - Tsb)
            q_left = 0.5 * (qbu + qbl)
            for i in range(Nb):
                if i < Nb - 1:
                    q_right = (Tbs[i] - Tbs[i + 1]) / (0.5 * sdx[i] / sk[i] + 0.5 * sdx[i + 1] / sk[i + 1])
                else:
                    q_right = (Tbs[i] - T_amb) / (0.5 * sdx[i] / sk[i] + 1.0 / h_out)
                    Q_out += q_right * A_boss * dt
                Tnew = Tbs[i] + dt * (q_left - q_right) / (src[i] * sdx[i])
                q_left = q_right
                Tbs[i] = Tnew
            if Tbs[Nb - 1] > Tboss_max:
                Tboss_max = Tbs[Nb - 1]

        # ---- wall conduction (explicit finite volumes) -------------------------------------------
        for z in range(2):
            Tw = Twu if z == 0 else Twl
            qin = qu if z == 0 else ql
            q_left = qin
            for i in range(N):
                if i < N - 1:
                    gc = 1.0 / (0.5 * wdx[i] / wk[i] + 0.5 * wdx[i + 1] / wk[i + 1])
                    q_right = gc * (Tw[i] - Tw[i + 1])
                else:
                    go = 1.0 / (0.5 * wdx[i] / wk[i] + 1.0 / h_out)
                    q_right = go * (Tw[i] - T_amb)
                    Q_out += q_right * (Au if z == 0 else Al) * dt
                Tnew = Tw[i] + dt * (q_left - q_right) / (wrc[i] * wdx[i])
                q_left = q_right
                Tw[i] = Tnew

        # ---- gas update without the net inter-zone flow ---------------------------------------
        hu = Uu / mu + P / rho_u
        hl = Ul / ml + P / rho_l
        ex = mx * (hl - hu)
        ml += dt * (1.0 - chi) * mdot
        mu += dt * chi * mdot
        Ul += dt * ((1.0 - chi) * mdot * h_in - ex - ql * Al - 0.5 * qbl * A_boss)
        Uu += dt * (chi * mdot * h_in + ex - qu * Au - 0.5 * qbu * A_boss)
        bm[ib] -= dt * mdot
        bU[ib] -= dt * mdot * hb
        bank_used[ib] += dt * mdot
        E_cool += Qpc * dt
        E_ref += W_ref * dt
        Q_wall += (qu * Au + ql * Al + 0.5 * (qbu + qbl) * A_boss) * dt
        Q_boss += 0.5 * (qbu + qbl) * A_boss * dt
        if Twu[N - 1] > Tout_max:
            Tout_max = Twu[N - 1]
        H_in += mdot * h_in * dt
        Tdel_sum += T_del * mdot * dt
        Tdel_w += mdot * dt

        # ---- projection onto equal pressures ------------------------------------------------------
        P_old = P
        mu, Uu, ml, Ul, Tu, Tl, P, _d = _equalise(tab, mu, Uu, ml, Ul, Vu, Vl, Tu, Tl)
        if mdot > 1.0e-9:
            est = (P - P_old) / (mdot * dt)
            ref = 1.4 * P / (mu + ml)
            dPdm = min(3.0 * ref, max(0.3 * ref, est))
        t += dt
        step += 1

        if not holding:
            # ---- extrema and end conditions --------------------------------------------------------
            if Tu > Tu_max:
                Tu_max = Tu
            if Tl > Tl_max:
                Tl_max = Tl
            if max(Tsu, Tsl) > Ts_max:
                Ts_max = max(Tsu, Tsl)
            if Qpc > Qpc_max:
                Qpc_max = Qpc
            if W_ref > Wref_max:
                Wref_max = W_ref
            if mdot > mdot_max:
                mdot_max = mdot
            if P > P_max:
                P_max = P
            rb = (mu + ml) / V
            Tb = T_rhou(tab, rb, (Uu + Ul) / (mu + ml), 0.5 * (Tu + Tl))
            if Tb > Tb_max:
                Tb_max = Tb
            if 100.0 * rb / RHO_FULL >= soc_tgt:
                reason = 1
            elif P >= P_stop:
                reason = 2
            elif t >= t_max:
                reason = 3
            elif Kp >= 0.0 and ib == nb - 1 and t > 5.0 and mdot < 1.0e-6 and x >= 1.0:
                reason = 4

    # ---- closing balances -----------------------------------------------------------------------
    Ew = 0.0
    for i in range(N):
        Ew += wrc[i] * wdx[i] * (Au * Twu[i] + Al * Twl[i])
    for i in range(Nb):
        Ew += src[i] * sdx[i] * A_boss * Tbs[i]
    dU = Uu + Ul - U0
    clos_gas = abs(dU - (H_in - Q_wall)) / max(abs(H_in), 1.0)
    clos_wall = abs((Ew - Ew0) - (Q_wall - Q_out)) / max(abs(Q_wall), 1.0)
    res = np.zeros(30)
    if not holding:
        fin[0], fin[1], fin[2], fin[3], fin[4], fin[5] = t, mu + ml - m0, P, 100.0 * (mu + ml) / V / RHO_FULL, Tu, Tl
    res[0], res[1], res[2], res[3] = fin[0], fin[1], Tu_max, Tl_max
    res[4], res[5], res[6], res[7] = Tb_max, fin[2], fin[3], E_cool
    res[8], res[9], res[10], res[11] = E_ref, Qpc_max, Wref_max, mdot_max
    res[12], res[13], res[14], res[15] = P_max, reason, clos_gas, clos_wall
    res[16] = Tdel_sum / Tdel_w if Tdel_w > 0 else T_amb
    res[17], res[18], res[19] = fin[4], fin[5], Ts_max
    res[20], res[21], res[22], res[23] = Q_wall, Q_boss, Tout_max, Tboss_max
    return res, ser[:ns], bank_used, bm, bm0


# ---- Python interface ------------------------------------------------------------------------------

@dataclass
class Wall:
    """Liner and composite of the vehicle tank. Values and sources are listed in the manuscript, Table 2."""
    t_liner: float = 0.003
    t_cfrp: float = 0.022
    k_liner: float = 0.385      # W/m K, HDPE (Molkov et al. 2019, Table 3)
    rho_liner: float = 945.0
    cp_liner: float = 1580.0
    k_cfrp: float = 0.74        # W/m K (Molkov et al. 2019, Table 3)
    rho_cfrp: float = 1494.0
    cp_cfrp: float = 1120.0
    n_liner: int = 8
    n_cfrp: int = 10
    h_out: float = 6.0          # W/m2 K, outer surface to air (Molkov et al. 2019)

    def grid(self, dt: float = 0.05):
        """Node thicknesses, conductivities and volumetric heat capacities; nodes are finer near the gas side.

        The explicit conduction step is stable when dt < rho c dx^2 / (3 k) for the node at the gas surface,
        so the number of nodes in a layer is reduced until its first node satisfies that limit with a margin.
        """
        def graded(total, n, k, rc, ratio):
            dx_min = math.sqrt(4.0 * k / rc * dt)
            while True:
                w = ratio ** np.arange(n)
                dx = total * w / w.sum()
                if dx[0] >= dx_min or n == 1:
                    return dx
                n -= 1
        rl, rcf = self.rho_liner * self.cp_liner, self.rho_cfrp * self.cp_cfrp
        dl = graded(self.t_liner, self.n_liner, self.k_liner, rl, 1.25)
        dc = graded(self.t_cfrp, self.n_cfrp, self.k_cfrp, rcf, 1.25)
        dx = np.concatenate([dl, dc])
        k = np.concatenate([np.full(len(dl), self.k_liner), np.full(len(dc), self.k_cfrp)])
        rc = np.concatenate([np.full(len(dl), rl), np.full(len(dc), rcf)])
        return dx, k, rc


@dataclass
class Tank:
    """Vehicle tank geometry. Default: the 141 L Type IV tank of the class model, length to diameter ratio 3."""
    volume: float = 0.141
    D: float | None = None      # inner diameter, m (None: from volume and aspect ratio)
    L: float | None = None      # inner length, m
    aspect: float = 3.0
    d_inj: float = 0.005        # injector diameter, m
    wall: Wall = field(default_factory=Wall)
    boss_area: float = 0.0      # m2 of metallic end boss wetted by the gas (0: no boss heat sink)
    boss_mass: float = 0.0      # kg of boss metal
    boss_k: float = 15.0        # W/m K (stainless steel 15, aluminium alloy 167)
    boss_rho: float = 7900.0
    boss_cp: float = 500.0

    def boss_grid(self, dt):
        """The bosses as one slab whose thickness follows from their mass and wetted area."""
        if self.boss_area <= 0.0 or self.boss_mass <= 0.0:
            return np.array([0.01]), np.array([self.boss_k]), np.array([self.boss_rho * self.boss_cp])
        tb = self.boss_mass / (self.boss_rho * self.boss_area)
        n = int(max(1, min(8, tb / math.sqrt(4.0 * self.boss_k / (self.boss_rho * self.boss_cp) * dt))))
        return np.full(n, tb / n), np.full(n, self.boss_k), np.full(n, self.boss_rho * self.boss_cp)

    def geometry(self):
        """Inner diameter, inner length and inner surface area of a cylinder with hemispherical ends."""
        if self.D is None:
            r = (self.volume / (math.pi * (2.0 * (self.aspect - 1.0) + 4.0 / 3.0))) ** (1.0 / 3.0)
            D, L = 2.0 * r, 2.0 * r * self.aspect
        else:
            D = self.D
            r = 0.5 * D
            L = self.L if self.L is not None else (self.volume - 4.0 / 3.0 * math.pi * r ** 3) / (math.pi * r * r) + D
        Lc = max(L - D, 0.0)
        return D, L, math.pi * D * Lc + math.pi * D * D


@dataclass
class Closure:
    """Two-zone closure parameters."""
    phi: float = 0.5      # upper-zone volume fraction
    chi: float = 0.0      # fraction of the inlet flow delivered to the upper zone
    beta: float = 0.35    # mixing efficiency (fitted, see jrc.py)
    Ri_c: float = 1.0     # critical Richardson number (assumed; not identifiable from the JRC data)
    f_h: float = 1.0      # multiplier on the gas-side heat transfer coefficient


@dataclass
class Control:
    """Dispenser and precooler settings: the decision variables of the optimisation are r1, r2, xi_b, dsw1, dsw2, Tpc_a, Tpc_b."""
    r1: float = 18.5            # MPa/min, pressure ramp rate of the first stage
    r2: float = 18.5            # MPa/min, second stage
    xi_b: float = 0.5           # (P - P0)/(P_ref - P0) at which the ramp rate changes
    dsw1: float = 2.0e6         # Pa, switching margin low to medium bank
    dsw2: float = 2.0e6         # Pa, medium to high bank
    Tpc_a: float = 233.15       # K, precooler set point at the start of the fill
    Tpc_b: float = 233.15       # K, set point when the tank reaches P_ref
    precool: bool = True
    Q_max: float = 60.0e3       # W
    Kp: float = 0.6             # a negative value selects the test-rig mode that imposes the pressure history
    Ki: float = 0.08
    flow_limit: float = 0.060   # kg/s
    CdA: float = 0.85 * 2.0e-6  # m2
    P_cap: float = 87.0e6       # Pa, the ramp target never exceeds this
    soc_target: float = 95.0    # %
    P_stop: float = 87.5e6      # Pa
    t_max: float = 900.0        # s
    P_ref: float = 70.0e6       # Pa


@dataclass
class Station:
    """Banks and refrigeration. Defaults are the class-model station."""
    bank_V: tuple = (1.0, 1.0, 0.5)
    bank_P: tuple = (35.0e6, 60.0e6, 95.0e6)
    bank_T: float | None = None     # None: ambient
    supply_T: float | None = None   # if set, the gas reaches the valve at this temperature (test-rig mode)
    inlet_T: float | None = None    # if set, the gas enters the tank at this temperature (measured inlet temperature)
    refrigerant: str = "R134a"
    eta_s_ref: float = 0.75
    pinch: float = 8.0              # K, set point minus evaporating temperature
    cond_approach: float = 15.0     # K, condensing temperature minus ambient
    eta_ref_drive: float = 1.0      # mechanical x motor efficiency of the refrigeration compressor (applied in station.py)


_TAB = None
_COP_CACHE: dict = {}


def table():
    global _TAB
    if _TAB is None:
        _TAB = load_table()
    return _TAB


def cop_curve(st: Station, T_amb: float) -> np.ndarray:
    """COP of the vapour-compression cycle against evaporating temperature, [T0, dT, COP...]."""
    key = (st.refrigerant, st.eta_s_ref, round(T_amb + st.cond_approach, 2))
    if key not in _COP_CACHE:
        from ..devices import RefrigerationCycle
        T0, dT, n = 205.0, 5.0, 20
        vals = []
        for i in range(n):
            Te = T0 + i * dT
            Tc = max(T_amb + st.cond_approach, Te + 10.0)
            vals.append(RefrigerationCycle(st.refrigerant, Te, Tc, st.eta_s_ref).solve(1.0)["COP"])
        _COP_CACHE[key] = np.array([T0, dT] + vals)
    return _COP_CACHE[key]


@dataclass
class Fill:
    """One fill of the research model."""
    tank: Tank = field(default_factory=Tank)
    closure: Closure = field(default_factory=Closure)
    control: Control = field(default_factory=Control)
    station: Station = field(default_factory=Station)
    T_amb: float = 298.15
    P0: float = 5.0e6
    T0: float | None = None         # initial gas temperature (None: ambient)
    T_wall0: float | None = None    # initial wall temperature (None: equal to the gas)
    dt: float = 0.05
    store_every: float = 0.5        # s between stored samples
    t_hold: float = 0.0             # s simulated after the end of the fill with the tank closed

    def run(self, tab=None) -> "FillOut":
        tab = table() if tab is None else tab
        D, L, A = self.tank.geometry()
        c, k, s = self.closure, self.control, self.station
        T0 = self.T_amb if self.T0 is None else self.T0
        Tw0 = T0 if self.T_wall0 is None else self.T_wall0
        tk = np.array([self.tank.volume, D, L, self.tank.d_inj, A, c.phi, c.chi, c.beta, c.Ri_c, c.f_h,
                       self.tank.wall.h_out, self.T_amb, T0, self.P0, Tw0,
                       self.T_amb if s.bank_T is None else s.bank_T,
                       s.inlet_T if s.inlet_T is not None else (0.0 if s.supply_T is None else s.supply_T),
                       2.0 if s.inlet_T is not None else (0.0 if s.supply_T is None else 1.0),
                       self.tank.boss_area if self.tank.boss_mass > 0 else 0.0, self.t_hold])
        ct = np.array([k.r1 * 1e6 / 60.0, k.r2 * 1e6 / 60.0, k.xi_b, k.Kp, k.Ki, k.flow_limit, k.CdA, k.P_cap,
                       k.soc_target, k.P_stop, k.t_max, k.dsw1, k.dsw2, k.Tpc_a, k.Tpc_b, k.Q_max,
                       1.0 if k.precool else 0.0, k.P_ref, s.pinch, 1.0])
        dx, wk, wrc = self.tank.wall.grid(self.dt)
        ndec = max(1, int(round(self.store_every / self.dt)))
        nmax = int((k.t_max + self.t_hold) / self.dt) + 2
        sdx, sk, src = self.tank.boss_grid(self.dt)
        res, ser, used, bm, bm0 = _simulate(tab, tk, dx, wk, wrc, sdx, sk, src, np.array(s.bank_V, float),
                                            np.array(s.bank_P, float), ct, cop_curve(s, self.T_amb),
                                            self.dt, ndec, nmax)
        return FillOut(self, res, ser, used, bm, bm0)


SER = ("t", "P", "T_u", "T_l", "T_bulk", "mdot", "T_del", "Q_pc", "bank", "Ts_u", "Ts_l", "soc", "h_l",
       "m_x", "Ri", "T_outer")
REASONS = {0: "step limit", 1: "state of charge target reached", 2: "pressure limit reached",
           3: "time limit reached", 4: "banks equalised with the tank"}


class FillOut:
    """Result of one fill: scalar results as attributes, time series in .s[name]."""

    def __init__(self, fill, res, ser, used, bm, bm0):
        self.fill = fill
        self.t_fill, self.m_added = res[0], res[1]
        self.Tu_max, self.Tl_max, self.Tbulk_max = res[2], res[3], res[4]
        self.T_hot = max(res[2], res[3])            # maximum local (zone) gas temperature, K
        self.P_end, self.soc, self.E_cool, self.E_ref = res[5], res[6], res[7], res[8]
        self.Qpc_max, self.Wref_max, self.mdot_max, self.P_max = res[9], res[10], res[11], res[12]
        self.reason = REASONS[int(res[13])]
        self.complete = int(res[13]) == 1
        self.closure_gas, self.closure_wall = res[14], res[15]
        self.T_del_mean, self.Tu_end, self.Tl_end, self.Ts_max = res[16], res[17], res[18], res[19]
        self.Q_wall, self.Q_boss, self.T_outer_max, self.T_boss_max = res[20], res[21], res[22], res[23]
        self.s = {n: ser[:, i] for i, n in enumerate(SER)}
        self.bank_used = used           # kg drawn from each bank
        self.bank_m_end, self.bank_m0 = bm, bm0
