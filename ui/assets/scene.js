// Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
// H2 Fast-Fill Lab, ui/assets/scene.js: the station scene.
//
// Python sends the recorded time series of one fill (already in display
// units). This file draws the station on a canvas and animates hydrogen
// molecules from those numbers:
//   - molecules in the car tank  = mass stored
//   - how fast they move         = gas temperature
//   - their colour               = gas temperature (cool blue to warm)
//   - molecules in each bank     = mass left in that bank
//   - dots moving in the pipes   = mass flow; slower and bluer after the precooler
// The chart under the scene shares one time cursor with the animation.
// Nothing here changes the physics; it only draws what the model computed.

const W = 1200, H = 580, GROUND = 500, HEADER_Y = 150;
const C = { ink: "#1D1D1F", muted: "#6E6E73", faint: "#A1A1A6", line: "#D2D2D7", grid: "#ECECEF", accent: "#0071E3", red: "#FF3B30", glass: "#F5F5F7", body: "#FAFAFC" };
const FONT = '"Instrument Sans", -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif';
const BANK_X = [92, 192, 292], BANK_R = 34, BANK_BOTTOM = 486, BANK_HMAX = 300;
const DISP = { x: 352, y: 230, w: 76, h: 270, cx: 390, outY: 360 };
const COOL = { x: 474, y: 300, w: 140, h: 200, wx: 488, wy: 322, ww: 112, wh: 76 };
const TANK = { ax: 872, ay: 418, bx: 992, by: 418, R: 34 };
const CAR_DX = -34;   // the car outline below is drawn 34 units left of where it was first sketched
const GAUGE = { x: 932, y: 250, r: 28 };
const REG = (window.__h2scenes = window.__h2scenes || {});

const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const lerp = (a, b, f) => a + (b - a) * f;

// Gas temperature in °C to a colour: blue at -40, violet near ambient, rose, then orange at 85. Red past the limit.
function tempColor(T) {
  if (T >= 85) return C.red;
  const stops = [[-40, [0, 113, 227]], [20, [120, 125, 225]], [55, [226, 110, 150]], [85, [255, 149, 0]]];
  const t = clamp(T, -40, 85);
  const i = t < 20 ? 0 : t < 55 ? 1 : 2;
  const f = (t - stops[i][0]) / (stops[i + 1][0] - stops[i][0]);
  const a = stops[i][1], b = stops[i + 1][1];
  return `rgb(${Math.round(lerp(a[0], b[0], f))},${Math.round(lerp(a[1], b[1], f))},${Math.round(lerp(a[2], b[2], f))})`;
}
// Gas temperature to on-screen molecule speed (scene units per second).
const agitation = (T) => 14 + 86 * clamp((T + 40) / 125, 0, 1.3);

// ---- a capsule-shaped vessel full of molecules -------------------------------------------------------------
class Gas {
  constructor(cap) { this.cap = cap; this.mols = []; }
  randomPoint(margin) {
    const c = this.cap, lim = c.R - margin;
    const f = Math.random(), a = Math.random() * 6.283, r = lim * Math.sqrt(Math.random());
    return [lerp(c.ax, c.bx, f) + r * Math.cos(a), lerp(c.ay, c.by, f) + r * Math.sin(a)];
  }
  add(point) {
    const [x, y] = point || this.randomPoint(5);
    const a = Math.random() * 6.283, u = 0.55 + 0.9 * Math.random();
    this.mols.push({ x, y, vx: Math.cos(a) * u, vy: Math.sin(a) * u, a: Math.random() * 6.283, w: (Math.random() - 0.5) * 5 });
  }
  setCount(n, inlet) {
    n = Math.max(0, Math.round(n));
    while (this.mols.length < n) this.add(inlet && this.mols.length > 0 ? [inlet[0] + Math.random() * 6, inlet[1] + (Math.random() - 0.5) * 20] : null);
    while (this.mols.length > n) this.mols.splice((Math.random() * this.mols.length) | 0, 1);
  }
  step(dt, speed) {
    const c = this.cap, lim = c.R - 5, dx = c.bx - c.ax, dy = c.by - c.ay, L2 = dx * dx + dy * dy || 1;
    for (const m of this.mols) {
      m.x += m.vx * speed * dt; m.y += m.vy * speed * dt; m.a += m.w * dt * (0.4 + speed / 60);
      const f = clamp(((m.x - c.ax) * dx + (m.y - c.ay) * dy) / L2, 0, 1);
      const qx = c.ax + f * dx, qy = c.ay + f * dy;
      let nx = m.x - qx, ny = m.y - qy; const d = Math.hypot(nx, ny);
      if (d > lim) {
        nx /= d; ny /= d; m.x = qx + nx * lim; m.y = qy + ny * lim;
        const vn = m.vx * nx + m.vy * ny;
        if (vn > 0) { m.vx -= 2 * vn * nx; m.vy -= 2 * vn * ny; }
      }
    }
  }
  draw(ctx, color) {
    ctx.fillStyle = color; ctx.beginPath();
    for (const m of this.mols) pair(ctx, m.x, m.y, m.a, 3.0, 2.5);
    ctx.fill();
  }
}
// One H2 molecule: two small spheres that overlap, which reads as a bond.
function pair(ctx, x, y, a, r, d) {
  const cx = Math.cos(a) * d, cy = Math.sin(a) * d;
  ctx.moveTo(x - cx + r, y - cy); ctx.arc(x - cx, y - cy, r, 0, 6.283);
  ctx.moveTo(x + cx + r, y + cy); ctx.arc(x + cx, y + cy, r, 0, 6.283);
}

// ---- the pipe run from a bank to the car tank --------------------------------------------------------------
function bankCap(i, vols) {
  const vmax = Math.max.apply(null, vols) || 1;
  const h = BANK_HMAX * clamp(vols[i] / vmax, 0.5, 1);
  return { ax: BANK_X[i], ay: BANK_BOTTOM - h + BANK_R, bx: BANK_X[i], by: BANK_BOTTOM - BANK_R, R: BANK_R, top: BANK_BOTTOM - h };
}
function buildPath(start) {
  const pts = [[start[0], start[1]], [start[0], HEADER_Y], [DISP.cx, HEADER_Y], [DISP.cx, DISP.y]];
  const marks = {};
  const len = () => { let s = 0; for (let i = 1; i < pts.length; i++) s += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); return s; };
  marks.hideA = len();
  pts.push([DISP.cx, DISP.outY], [DISP.x + DISP.w, DISP.outY]);
  marks.hideB = len();
  pts.push([COOL.wx + 4, DISP.outY]);
  marks.coilA = len();
  const n = 48, x0 = COOL.wx + 4, x1 = COOL.wx + COOL.ww - 4;
  for (let i = 1; i <= n; i++) pts.push([lerp(x0, x1, i / n), DISP.outY + 22 * Math.sin((i / n) * 6.283 * 3.5)]);
  pts[pts.length - 1][1] = DISP.outY;
  marks.coilB = len();
  pts.push([COOL.x + COOL.w + 10, DISP.outY]);
  const p0 = [COOL.x + COOL.w + 10, DISP.outY], p1 = [674, DISP.outY], p2 = [668, TANK.ay], p3 = [714, TANK.ay];
  for (let i = 1; i <= 20; i++) {
    const t = i / 20, u = 1 - t;
    pts.push([u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0], u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]]);
  }
  pts.push([TANK.ax - TANK.R + 2, TANK.ay]);
  const cum = [0];
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  return { pts, cum, total: cum[cum.length - 1], marks };
}
function pointAt(path, s) {
  const { pts, cum } = path; let lo = 0, hi = cum.length - 1;
  s = clamp(s, 0, path.total);
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (cum[mid] <= s) lo = mid; else hi = mid; }
  const f = (s - cum[lo]) / ((cum[hi] - cum[lo]) || 1), a = pts[lo], b = pts[hi];
  const tx = b[0] - a[0], ty = b[1] - a[1], tl = Math.hypot(tx, ty) || 1;
  return [lerp(a[0], b[0], f), lerp(a[1], b[1], f), -ty / tl, tx / tl];
}

// ---- reading the time series at any instant ----------------------------------------------------------------
function sample(d, t) {
  const ts = d.t, n = ts.length, out = {};
  if (!n) return out;
  let lo = 0, hi = n - 1;
  t = clamp(t, ts[0], ts[n - 1]);
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (ts[mid] <= t) lo = mid; else hi = mid; }
  const f = hi === lo ? 0 : (t - ts[lo]) / ((ts[hi] - ts[lo]) || 1);
  for (const k in d) { const a = d[k]; if (Array.isArray(a) && a.length === n) out[k] = k === "bi" ? a[f < 1 ? lo : hi] : lerp(a[lo], a[hi], f); }
  out.t = t;
  return out;
}

// ---- charts ------------------------------------------------------------------------------------------------
const VIEWS = {
  "Pressure": { unit: "MPa", limit: [87.5, "87.5 MPa limit"], zero: true, series: [["P", "Car tank", C.accent, 2.2], ["Pt", "Ramp set point", C.muted, 1.5, [2, 4]], ["Pb", "Active bank", C.faint, 1.5]] },
  "Temperature": { unit: "°C", limit: [85, "85 °C limit"], series: [["T", "Tank gas", C.accent, 2.2], ["Tw", "Tank wall", C.muted, 1.5], ["Td", "Delivered gas", C.faint, 1.5]] },
  "Mass and flow": { unit: "kg", unitR: "g/s", zero: true, series: [["m", "Mass in tank", C.accent, 2.2], ["md", "Flow", C.muted, 1.5, null, "r"]] },
  "Charge": { unit: "%", limit: [100, "100% limit"], zero: true, series: [["soc", "State of charge", C.accent, 2.2]] },
  "Controller": { unit: "% open", unitR: "MPa", zero: true, series: [["open", "Valve opening", C.accent, 2.2], ["err", "Ramp error", C.muted, 1.5, null, "r"]] },
  "Energy": { unit: "kW", zero: true, series: [["Hf", "Enthalpy into tank", C.accent, 2.2], ["Qp", "Removed in precooler", C.muted, 1.5], ["Qw", "Gas to wall", C.faint, 1.5], ["Wr", "Refrigeration compressor", C.ink, 1.2, [2, 4]]] },
};
function niceTicks(lo, hi, n) {
  if (!(hi > lo)) hi = lo + 1;
  const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), r = raw / mag;
  const step = (r < 1.5 ? 1 : r < 3 ? 2 : r < 7 ? 5 : 10) * mag;
  const a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step, ticks = [];
  for (let v = a; v <= b + step * 0.01; v += step) ticks.push(Math.abs(v) < step * 1e-6 ? 0 : v);
  return { lo: a, hi: b, ticks, step };
}
const fmtTick = (v, step) => (step >= 1 ? v.toFixed(0) : step >= 0.1 ? v.toFixed(1) : v.toFixed(2));
const fmtVal = (v) => (v === undefined || v !== v ? "" : Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));

// ---- one scene ---------------------------------------------------------------------------------------------
function createScene(key) {
  const S = { key, data: null, tView: 0, scrub: null, view: "Pressure", last: 0, runId: null, parts: [], spawn: 0, holdUntil: 0, lost: 0, running: false, clock: 0 };
  S.reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  S.bind = function (root) {
    if (S.root === root) return;
    S.root = root;
    S.canvas = root.querySelector(".h2s-canvas"); S.plot = root.querySelector(".h2s-plot");
    S.elP = root.querySelector('[data-k="P"]'); S.elT = root.querySelector('[data-k="T"]'); S.elClock = root.querySelector('[data-k="clock"]');
    S.elLegend = root.querySelector(".h2s-legend"); S.elAt = root.querySelector(".h2s-at");
    const seg = root.querySelector(".h2s-seg"); seg.innerHTML = "";
    for (const name of Object.keys(VIEWS)) {
      const b = document.createElement("button"); b.type = "button"; b.textContent = name; b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", name === S.view ? "true" : "false");
      b.onclick = () => { S.view = name; seg.querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", x === b ? "true" : "false")); S.legendFor = null; S.kick(); };
      seg.appendChild(b);
    }
    const tAt = (ev) => { const r = S.plot.getBoundingClientRect(), g = S.geom; if (!g) return null; return clamp(((ev.clientX - r.left - g.l) / (g.w || 1)) * g.xmax, 0, S.tData()); };
    S.plot.onpointermove = (ev) => { if (!S.data || S.data.playing || S.data.hero) return; S.scrub = tAt(ev); S.kick(); };
    S.plot.onpointerleave = () => { S.scrub = null; S.kick(); };
    if (S.ro) S.ro.disconnect();
    S.ro = new ResizeObserver(() => { S.sized = false; S.kick(); }); S.ro.observe(root);
    S.sized = false;
  };

  S.tData = () => { const t = S.data && S.data.series.t; return t && t.length ? t[t.length - 1] : 0; };

  S.update = function (data) {
    const fresh = !S.data || data.run !== S.runId;
    S.data = data; S.runId = data.run;
    S.root.classList.toggle("hero", !!data.hero);
    const vols = data.banks.map((b) => b.V);
    if (fresh || !S.caps || S.volKey !== vols.join()) {
      S.volKey = vols.join();
      S.caps = vols.map((_, i) => bankCap(i, vols));
      S.bankGas = S.caps.map((c) => new Gas(c)); S.tankGas = new Gas(TANK);
      S.paths = S.caps.map((c) => buildPath([c.ax, c.top]));
      S.parts = []; S.spawn = 0; S.legendFor = null;
      S.tView = data.hero ? 0 : S.tData();
    }
    S.kick();
  };

  S.kick = function () {
    if (S.reduced) { S.tView = S.data && S.data.hero ? S.tData() * 0.62 : S.tData(); requestAnimationFrame((now) => S.frame(now, true)); return; }
    if (!S.running) { S.running = true; S.last = 0; requestAnimationFrame((now) => S.frame(now, false)); }
  };

  S.size = function () {
    const dpr = Math.min(window.devicePixelRatio || 1, 2), w = S.canvas.clientWidth;
    if (!w) return false;
    S.crop = S.data && S.data.hero ? { y: 104, h: 468 } : { y: 0, h: H };   // the opening screen leaves out the empty band kept for the numbers
    S.scale = w / W; S.canvas.style.height = Math.round(w * S.crop.h / W) + "px";
    S.canvas.width = Math.round(w * dpr); S.canvas.height = Math.round(w * S.crop.h / W * dpr); S.dpr = dpr;
    const pw = S.plot.clientWidth, ph = S.plot.clientHeight;
    S.plot.width = Math.round(pw * dpr); S.plot.height = Math.round(ph * dpr); S.pw = pw; S.ph = ph;
    S.sized = true; S.chartSig = null; return true;   // resizing clears a canvas, so the chart must be drawn again
  };

  S.frame = function (now, once) {
    if (!S.root || !S.root.isConnected) {            // the page moved on: stop, and forget the scene after a few seconds
      if (!S.lost) S.lost = now;
      if (now - S.lost > 4000 || once) { S.running = false; if (S.ro) S.ro.disconnect(); delete REG[S.key]; return; }
      requestAnimationFrame((n) => S.frame(n, false)); return;
    }
    S.lost = 0;
    if (!S.sized && !S.size()) { if (!once) requestAnimationFrame((n) => S.frame(n, false)); return; }
    const dt = S.last ? Math.min(0.05, (now - S.last) / 1000) : 0; S.last = now; S.clock += dt;
    const d = S.data, tEnd = S.tData(), speed = d.speed || 1;
    if (!once) {
      if (d.hero) {                                  // opening screen: replay the reference fill in a loop
        if (S.tView >= tEnd) { if (!S.holdUntil) S.holdUntil = now + 2600; if (now > S.holdUntil) { S.holdUntil = 0; S.tView = 0; S.parts = []; S.tankGas.mols = []; S.bankGas.forEach((g) => (g.mols = [])); } }
        else S.tView = Math.min(tEnd, S.tView + dt * speed);
      } else {                                       // live run: follow the model smoothly, a fraction of a second behind
        const gap = tEnd - S.tView, lag = speed * 0.6;
        if (gap < 0 || gap > lag * 8) S.tView = tEnd;
        else if (gap > 0) S.tView = Math.min(tEnd, S.tView + dt * speed * (d.playing ? clamp(1 + 0.8 * (gap - lag) / lag, 0.3, 2.5) : 3));
      }
    }
    const tShow = S.scrub !== null && !d.playing && !d.hero ? S.scrub : S.tView;
    const st = sample(d.series, tShow);
    S.simulate(st, once ? 0 : dt, d.playing || d.hero || S.tView < tEnd);
    S.draw(st);
    S.overlays(st);
    if (!d.hero) S.chart(st);
    if (!once) requestAnimationFrame((n) => S.frame(n, false));
  };

  // move the molecules: counts from mass, speed from temperature, pipe flow from the mass flow rate
  S.simulate = function (st, dt, flowing) {
    const d = S.data;
    S.tankGas.setCount(clamp(230 * (st.soc || 0) / 100, 0, 250), [TANK.ax - TANK.R + 8, TANK.ay]);
    S.tankGas.step(dt, agitation(st.T));
    const m0 = Math.max.apply(null, d.banks.map((b) => b.m0)) || 1, bi = st.bi | 0;
    S.bankGas.forEach((g, i) => { g.setCount(120 * (st["bm" + i] || 0) / m0); g.step(dt, agitation(i === bi ? st.Tb : d.amb)); });
    const path = S.paths[bi], flow = flowing ? clamp((st.md || 0) / 60, 0, 1) : 0;
    if (flow > 0.003) { S.spawn += dt * (5 + 34 * flow); while (S.spawn >= 1) { S.spawn -= 1; S.parts.push({ e: path.total, ph: Math.random() * 6.283, a: Math.random() * 6.283 }); } }
    const eCoilB = path.total - path.marks.coilB;
    for (const p of S.parts) { if (flow > 0.003) p.e -= dt * (40 + 300 * flow) * (p.e < eCoilB ? 0.5 : 1); p.a += dt * 3; }
    S.parts = S.parts.filter((p) => p.e > 0 && p.e <= path.total);
  };

  S.draw = function (st) {
    const ctx = S.canvas.getContext("2d"), k = S.scale * S.dpr, d = S.data, px = 1 / S.scale, bi = st.bi | 0;
    ctx.setTransform(k, 0, 0, k, 0, -S.crop.y * k); ctx.clearRect(0, 0, W, H);
    ctx.lineJoin = "round"; ctx.lineCap = "round";
    const text = (s, x, y, size, color, weight, align) => { ctx.font = `${weight || 400} ${size * px}px ${FONT}`; ctx.fillStyle = color; ctx.textAlign = align || "center"; ctx.textBaseline = "alphabetic"; ctx.fillText(s, x, y); };
    const rr = (x, y, w, h, r) => { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); };
    const stroke = (c, w) => { ctx.strokeStyle = c; ctx.lineWidth = w * px; ctx.stroke(); };
    const label = (x, a, b) => { text(a, x, GROUND + 18 * px + 8, 13, C.ink, 500); text(b, x, GROUND + 36 * px + 8, 13, C.muted, 400); };

    // ground
    ctx.beginPath(); ctx.moveTo(40, GROUND); ctx.lineTo(W - 40, GROUND); stroke(C.line, 1);

    // pipes: a pale tube with a white bore
    const tube = (pts) => { ctx.beginPath(); pts.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]))); ctx.strokeStyle = C.line; ctx.lineWidth = 12; ctx.stroke(); ctx.strokeStyle = "#FFFFFF"; ctx.lineWidth = 9; ctx.stroke(); };
    S.caps.forEach((c) => tube([[c.ax, c.top + 4], [c.ax, HEADER_Y]]));
    tube([[S.caps[0].ax, HEADER_Y], [DISP.cx, HEADER_Y], [DISP.cx, DISP.y + 8]]);

    // precooler cabinet and its window, then the line through it
    rr(COOL.x, COOL.y, COOL.w, COOL.h, 14); ctx.fillStyle = "#FFFFFF"; ctx.fill(); stroke(C.ink, 1.5);
    rr(COOL.wx, COOL.wy, COOL.ww, COOL.wh, 12); ctx.fillStyle = C.glass; ctx.fill(); stroke(C.line, 1);
    for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.moveTo(COOL.x + 28, 432 + i * 14); ctx.lineTo(COOL.x + COOL.w - 28, 432 + i * 14); stroke(C.line, 1.5); }
    const main = S.paths[bi], iB = main.cum.findIndex((s) => s >= main.marks.hideB);
    tube(main.pts.slice(iB));

    // molecules in the banks
    S.caps.forEach((c, i) => {
      rr(c.ax - c.R, c.top, c.R * 2, BANK_BOTTOM - c.top, c.R); ctx.fillStyle = "#FFFFFF"; ctx.fill(); stroke(i === bi ? C.ink : C.faint, 1.5);
      S.bankGas[i].draw(ctx, tempColor(i === bi ? st.Tb : d.amb));
      rr(c.ax - 14, BANK_BOTTOM, 28, GROUND - BANK_BOTTOM, 2); ctx.fillStyle = C.line; ctx.fill();
      ctx.beginPath(); ctx.arc(c.ax, HEADER_Y, 7, 0, 6.283); ctx.fillStyle = i === bi ? C.accent : "#FFFFFF"; ctx.fill(); stroke(i === bi ? C.accent : C.faint, 1.5);
      const p = st["bp" + i]; label(c.ax, d.banks[i].name, (p === undefined ? d.banks[i].P0 : p).toFixed(1) + " MPa");
    });

    // gas moving through the line
    const m = main.marks;
    for (const p of S.parts) {
      const s = main.total - p.e;
      if (s > m.hideA - 4 && s < m.hideB + 4) continue;
      const T = s < m.hideA ? st.Tb : s < m.coilA ? st.Tv : s < m.coilB ? lerp(st.Tv, st.Td, (s - m.coilA) / (m.coilB - m.coilA)) : st.Td;
      const q = pointAt(main, s), j = Math.sin(p.ph + S.clock * agitation(T) * 0.22) * 2.0;
      ctx.fillStyle = tempColor(T); ctx.beginPath(); pair(ctx, q[0] + q[2] * j, q[1] + q[3] * j, p.a, 2.3, 1.9); ctx.fill();
    }

    // dispenser
    rr(DISP.x, DISP.y, DISP.w, DISP.h, 14); ctx.fillStyle = "#FFFFFF"; ctx.fill(); stroke(C.ink, 1.5);
    rr(DISP.x + 12, DISP.y + 20, DISP.w - 24, 64, 10); ctx.fillStyle = C.glass; ctx.fill();
    text((st.md || 0).toFixed(0), DISP.cx, DISP.y + 20 + 30 + 4 * px, 17, C.ink, 600); text("g/s", DISP.cx, DISP.y + 20 + 36 + 16 * px, 11, C.muted, 500);
    const open = clamp((st.open || 0) / 100, 0, 1), bx = DISP.x + 12, bw = DISP.w - 24, by = DISP.y + 108;
    ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx + bw, by); stroke(C.grid, 4);
    if (open > 0.01) { ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx + bw * open, by); stroke(C.accent, 4); }
    label(DISP.cx, "Dispenser", "valve " + (open * 100).toFixed(0) + "%");
    label(COOL.x + COOL.w / 2, "Precooler", d.cooling ? "out at " + (st.Td === undefined ? 0 : st.Td).toFixed(0).replace("-", "−") + " °C" : "off");

    // the car, its tank and the charge gauge
    const over = st.T >= 85;
    ctx.save(); ctx.translate(CAR_DX, 0);
    ctx.beginPath(); ctx.moveTo(748, 470); ctx.lineTo(748, 418); ctx.bezierCurveTo(748, 396, 760, 386, 790, 380); ctx.lineTo(836, 372);
    ctx.bezierCurveTo(880, 330, 910, 318, 960, 316); ctx.lineTo(1030, 316); ctx.bezierCurveTo(1075, 318, 1100, 345, 1128, 372); ctx.lineTo(1172, 384);
    ctx.bezierCurveTo(1190, 388, 1194, 404, 1194, 424); ctx.lineTo(1194, 470); ctx.closePath(); ctx.fillStyle = C.body; ctx.fill(); stroke(C.ink, 1.5);
    ctx.beginPath(); ctx.moveTo(856, 370); ctx.bezierCurveTo(892, 340, 918, 330, 960, 328); ctx.lineTo(1026, 328); ctx.bezierCurveTo(1060, 330, 1082, 350, 1100, 370); ctx.closePath(); ctx.fillStyle = C.glass; ctx.fill(); stroke(C.line, 1);
    for (const wx of [826, 1106]) { ctx.beginPath(); ctx.arc(wx, 464, 41, 0, 6.283); ctx.fillStyle = "#FFFFFF"; ctx.fill(); ctx.beginPath(); ctx.arc(wx, 464, 35, 0, 6.283); ctx.fillStyle = "#FFFFFF"; ctx.fill(); stroke(C.ink, 1.5); ctx.beginPath(); ctx.arc(wx, 464, 13, 0, 6.283); stroke(C.line, 1.5); }
    ctx.restore();
    rr(TANK.ax - TANK.R, TANK.ay - TANK.R, TANK.bx - TANK.ax + 2 * TANK.R, 2 * TANK.R, TANK.R); ctx.fillStyle = "#FFFFFF"; ctx.fill(); stroke(over ? C.red : C.ink, over ? 2 : 1.5);
    S.tankGas.draw(ctx, tempColor(st.T));
    rr(704, TANK.ay - 9, 16, 18, 4); ctx.fillStyle = C.ink; ctx.fill();
    const soc = clamp((st.soc || 0) / 100, 0, 1);
    ctx.beginPath(); ctx.moveTo(GAUGE.x, GAUGE.y + GAUGE.r + 6); ctx.lineTo(GAUGE.x, 315); stroke(C.line, 1);
    ctx.beginPath(); ctx.arc(GAUGE.x, GAUGE.y, GAUGE.r, 0, 6.283); ctx.fillStyle = "#FFFFFF"; ctx.fill(); stroke(C.grid, 5);
    if (soc > 0.005) { ctx.beginPath(); ctx.arc(GAUGE.x, GAUGE.y, GAUGE.r, -1.5708, -1.5708 + 6.283 * soc); stroke(soc >= 1 ? C.red : C.accent, 5); }
    text((soc * 100).toFixed(0) + "%", GAUGE.x, GAUGE.y + 5 * px, 15, C.ink, 600);
    text("State of charge", GAUGE.x, GAUGE.y - GAUGE.r - 12 * px, 12, C.muted, 500);
    label(GAUGE.x, "Car tank", (st.m || 0).toFixed(2) + " kg");
  };

  S.overlays = function (st) {
    const t = st.t || 0, mm = Math.floor(t / 60), ss = t - mm * 60;
    const clock = mm + ":" + (ss < 10 ? "0" : "") + ss.toFixed(1);
    if (S.elClock.textContent !== clock) S.elClock.textContent = clock;
    const P = (st.P || 0).toFixed(1), T = (st.T || 0).toFixed(1).replace("-", "−");
    if (S.elP.textContent !== P) S.elP.textContent = P;
    if (S.elT.textContent !== T) S.elT.textContent = T;
    S.elT.classList.toggle("over", st.T >= 85);
    S.elP.classList.toggle("over", st.P >= 87.5);
  };

  S.chart = function (st) {
    const v = VIEWS[S.view], d = S.data.series, n = d.t.length, tEnd = S.tData();
    const sig = [S.view, n, tEnd, st.t, S.pw, S.data.finished].join("|");
    if (sig === S.chartSig) return; S.chartSig = sig;
    if (S.legendFor !== S.view) {
      S.legendFor = S.view; S.elLegend.innerHTML = "";
      S.legVals = v.series.map((s) => { const it = document.createElement("span"); it.className = "it"; const sw = document.createElement("span"); sw.className = "sw"; sw.style.borderTopColor = s[2]; sw.style.borderTopStyle = s[4] ? "dotted" : "solid";
        const nm = document.createElement("span"); nm.textContent = s[1]; const b = document.createElement("b"); it.append(sw, nm, b); S.elLegend.appendChild(it); return b; });
    }
    const unitOf = (s) => (s[5] === "r" ? v.unitR : v.unit).replace("% open", "%");
    v.series.forEach((s, i) => { const val = st[s[0]]; S.legVals[i].textContent = val === undefined ? "" : fmtVal(val).replace("-", "−") + (unitOf(s) === "%" ? "%" : " " + unitOf(s)); });
    S.elAt.textContent = "at " + (st.t || 0).toFixed(1) + " s";

    const ctx = S.plot.getContext("2d"), dpr = S.dpr, hasR = !!v.unitR;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, S.pw, S.ph);
    const l = 40, r = hasR ? 44 : 8, top = 26, bot = 28, w = S.pw - l - r, h = S.ph - top - bot;
    const xmax = S.data.finished ? Math.max(tEnd, 1) : Math.max(60, tEnd * 1.2);
    S.geom = { l, w, xmax };
    const range = (axis) => { let lo = Infinity, hi = -Infinity; for (const s of v.series) { if ((s[5] === "r") !== (axis === "r")) continue; const a = d[s[0]] || []; for (let i = 0; i < a.length; i++) { if (a[i] < lo) lo = a[i]; if (a[i] > hi) hi = a[i]; } }
      if (axis !== "r" && v.limit) hi = Math.max(hi, v.limit[0] * 1.04); if (lo === Infinity) { lo = 0; hi = 1; } if (v.zero || axis === "r") lo = Math.min(lo, 0); if (hi <= lo) hi = lo + 1; return niceTicks(lo, hi, 4); };
    const yl = range("l"), yr = hasR ? range("r") : null;
    const X = (t) => l + (t / xmax) * w, Y = (val, ax) => top + h - ((val - ax.lo) / (ax.hi - ax.lo)) * h;
    ctx.font = `400 12px ${FONT}`; ctx.textBaseline = "middle"; ctx.lineWidth = 1;
    for (const tk of yl.ticks) { const y = Math.round(Y(tk, yl)) + 0.5; ctx.strokeStyle = C.grid; ctx.beginPath(); ctx.moveTo(l, y); ctx.lineTo(l + w, y); ctx.stroke(); ctx.fillStyle = C.muted; ctx.textAlign = "right"; ctx.fillText(fmtTick(tk, yl.step).replace("-", "−"), l - 8, y); }
    if (yr) for (const tk of yr.ticks) { ctx.fillStyle = C.muted; ctx.textAlign = "left"; ctx.fillText(fmtTick(tk, yr.step).replace("-", "−"), l + w + 8, Y(tk, yr)); }
    ctx.textAlign = "left"; ctx.fillStyle = C.muted; ctx.fillText(v.unit, 0, 7); if (hasR) { ctx.textAlign = "right"; ctx.fillText(v.unitR, S.pw, 7); }
    const xt = niceTicks(0, xmax, 6); ctx.textBaseline = "top";
    for (const tk of xt.ticks) { if (tk > xmax) continue; ctx.textAlign = tk === 0 ? "left" : "center"; ctx.fillStyle = C.muted; ctx.fillText(tk.toFixed(0) + (tk === 0 ? " s" : ""), X(tk), top + h + 10); }
    ctx.strokeStyle = C.line; ctx.beginPath(); ctx.moveTo(l, top + h + 0.5); ctx.lineTo(l + w, top + h + 0.5); ctx.stroke();
    if (v.limit) { const y = Math.round(Y(v.limit[0], yl)) + 0.5; ctx.strokeStyle = C.red; ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(l, y); ctx.lineTo(l + w, y); ctx.stroke(); ctx.setLineDash([]); ctx.fillStyle = C.red; ctx.textAlign = "right"; ctx.textBaseline = "bottom"; ctx.fillText(v.limit[1], l + w, y - 4); }
    ctx.save(); ctx.beginPath(); ctx.rect(l, top - 4, w, h + 8); ctx.clip(); ctx.lineJoin = "round";
    for (let si = v.series.length - 1; si >= 0; si--) { const s = v.series[si], a = d[s[0]]; if (!a) continue; const ax = s[5] === "r" ? yr : yl; ctx.strokeStyle = s[2]; ctx.lineWidth = s[3]; ctx.setLineDash(s[4] || []); ctx.beginPath(); for (let i = 0; i < n; i++) { const x = X(d.t[i]), y = Y(a[i], ax); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); }
    ctx.setLineDash([]); ctx.restore();
    const cx = Math.round(X(st.t || 0)) + 0.5; ctx.strokeStyle = C.ink; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(cx, top); ctx.lineTo(cx, top + h); ctx.stroke();
    for (const s of v.series) { const val = st[s[0]]; if (val === undefined) continue; const ax = s[5] === "r" ? yr : yl; ctx.beginPath(); ctx.arc(cx, Y(val, ax), 4, 0, 6.283); ctx.fillStyle = "#FFFFFF"; ctx.fill(); ctx.strokeStyle = s[2]; ctx.lineWidth = 2; ctx.stroke(); }
  };
  return S;
}

export default function (component) {
  const { data, parentElement } = component;
  const root = parentElement.querySelector(".h2s");
  if (!root || !data) return;
  const S = REG[data.key] || (REG[data.key] = createScene(data.key));
  S.bind(root);
  S.update(data);
  window.__h2sceneState = () => ({ key: data.key, t: S.tView, tank: S.tankGas.mols.length, parts: S.parts.length, banks: S.bankGas.map((g) => g.mols.length) });
}
