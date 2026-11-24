// Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
// H2 Fast-Fill Lab, ui/assets/tour.js
// Coach-mark tours, plus the ? definitions beside every input. The steps and the wording come from
// ui/tour.py and ui/glossary.py; this file only draws them. It has no part in the model.
//
// A tour dims the page, puts a spotlight on one part at a time and shows a
// short note beside it with Next and Skip. Each tour runs once per page load:
// the flag lives only in memory on this window, so a refresh plays it again.
// Python keeps the same rule for the visit.

const DONE = (window.__h2toursDone = window.__h2toursDone || {});
const seen = (name) => !!DONE[name];
const mark = (name) => { DONE[name] = true; };

function find(step) {
  const all = document.querySelectorAll(step.sel);
  const el = all[step.index || 0];
  return el && el.getClientRects().length ? el : null;
}

function startTour(name, steps) {
  if (window.__h2tour) return;
  mark(name);
  const T = (window.__h2tour = { name, i: -1 });
  const block = document.createElement("div"); block.className = "h2-tour-block";
  const spot = document.createElement("div"); spot.className = "h2-tour-spot";
  const tip = document.createElement("div"); tip.className = "h2-tour-tip"; tip.setAttribute("role", "dialog"); tip.setAttribute("aria-label", "Tour");
  tip.innerHTML = '<h4></h4><p></p><div class="row"><span class="count"></span><button type="button" class="skip">Skip</button><button type="button" class="next">Next</button></div>';
  document.body.append(block, spot, tip);
  const h = tip.querySelector("h4"), p = tip.querySelector("p"), count = tip.querySelector(".count"), next = tip.querySelector(".next");

  function place() {
    const step = steps[T.i]; if (!step) return;
    const el = find(step);
    if (!el) return;
    const r = el.getBoundingClientRect(), pad = step.pad === undefined ? 8 : step.pad;
    spot.style.left = r.left - pad + "px"; spot.style.top = r.top - pad + "px"; spot.style.width = r.width + 2 * pad + "px"; spot.style.height = r.height + 2 * pad + "px";
    const tw = 304, th = tip.offsetHeight, vw = window.innerWidth, vh = window.innerHeight, g = 24;
    let x, y;
    if (r.left - pad - g - tw > 8) { x = r.left - pad - g - tw; y = r.top + r.height / 2 - th / 2; }            // left of the control
    else if (r.right + pad + g + tw < vw - 8) { x = r.right + pad + g; y = r.top + r.height / 2 - th / 2; }      // right of it
    else if (r.bottom + pad + g + th < vh - 48) { x = r.left + r.width / 2 - tw / 2; y = r.bottom + pad + g; }  // below
    else { x = r.left + r.width / 2 - tw / 2; y = r.top - pad - g - th; }                                       // above
    tip.style.left = Math.max(16, Math.min(vw - tw - 16, x)) + "px"; tip.style.top = Math.max(16, Math.min(vh - th - 56, y)) + "px";
  }
  function show(i) {
    while (i < steps.length) {                      // skip any step whose control is not on the page
      const step = steps[i];
      if (step.click) { const c = document.querySelectorAll(step.click)[step.clickIndex || 0]; if (c) c.click(); }
      if (find(step) || step.click) break;
      i++;
    }
    if (i >= steps.length) return end();
    T.i = i; const step = steps[i];
    h.textContent = step.title; p.textContent = step.text;
    count.textContent = i + 1 + " of " + steps.length; next.textContent = i === steps.length - 1 ? "Done" : "Next";
    const el = find(step); if (el && el.scrollIntoView) el.scrollIntoView({ block: "center", behavior: "auto" });
    place(); next.focus({ preventScroll: true });
  }
  function end() {
    clearInterval(T.timer); document.removeEventListener("keydown", onKey, true);
    const last = steps[steps.length - 1];
    if (last && last.reset) { const c = document.querySelectorAll(last.reset)[0]; if (c) c.click(); }
    block.remove(); spot.remove(); tip.remove(); window.__h2tour = null;
  }
  function onKey(ev) { if (ev.key === "Escape") { ev.preventDefault(); end(); } else if (ev.key === "ArrowRight") { ev.preventDefault(); show(T.i + 1); } }
  next.onclick = () => show(T.i + 1);
  tip.querySelector(".skip").onclick = end;
  document.addEventListener("keydown", onKey, true);
  T.timer = setInterval(place, 120);                // the page can re-render under the tour; keep the spotlight on its control
  show(0);
}

// The ? beside an input: click (or tap, or Enter) to show its plain-words definition, click anywhere else to close.
function wireHelp() {
  if (window.__h2help) return;
  window.__h2help = true;
  const pop = document.createElement("div");
  pop.className = "h2-help-pop"; pop.setAttribute("role", "tooltip"); pop.hidden = true;
  pop.innerHTML = "<b></b><p></p>";
  document.body.append(pop);
  let open = null;
  const close = () => { pop.hidden = true; if (open) open.setAttribute("aria-expanded", "false"); open = null; };
  const show = (q) => {
    if (open === q) return close();
    open = q; q.setAttribute("aria-expanded", "true");
    pop.querySelector("b").textContent = q.dataset.term || "";
    pop.querySelector("p").textContent = q.dataset.def || "";
    pop.hidden = false;
    const r = q.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    const x = Math.max(12, Math.min(window.innerWidth - w - 12, r.right - w));
    const y = r.bottom + 8 + h < window.innerHeight - 12 ? r.bottom + 8 : r.top - 8 - h;
    pop.style.left = x + "px"; pop.style.top = y + "px";
  };
  document.addEventListener("click", (ev) => {
    const q = ev.target.closest && ev.target.closest(".q-help");
    if (q) { ev.preventDefault(); ev.stopPropagation(); show(q); }
    else if (!pop.contains(ev.target)) close();
  }, true);
  document.addEventListener("keydown", (ev) => {
    const q = ev.target.closest && ev.target.closest(".q-help");
    if (q && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); show(q); }
    else if (ev.key === "Escape") close();
  }, true);
  window.addEventListener("scroll", close, true);
  window.addEventListener("resize", close);
}

export default function (component) {
  const data = component.data || {};
  window.__h2tourReset = () => { for (const k in DONE) delete DONE[k]; };
  wireHelp();
  if (!data.run || seen(data.run)) return;
  // wait until the first control of the tour is on the page, then start
  let tries = 0;
  const wait = setInterval(() => {
    tries++;
    if (window.__h2tour) { if (tries > 300) clearInterval(wait); return; }
    const first = data.steps.find((s) => find(s) || s.click);
    if (first && (find(first) || document.querySelector(first.click))) { clearInterval(wait); if (!seen(data.run)) startTour(data.run, data.steps); }
    else if (tries > 50) clearInterval(wait);
  }, 120);
}
