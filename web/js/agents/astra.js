// ASTRA — science lab: subject navigation, knowledge panels, interactive diagrams, formula solver, maths plotter.
import { h, svg, clear, backButton, debounce } from '../dom.js';

let raf = 0;
export function unmount() { cancelAnimationFrame(raf); }
const VISUAL = { Astronomy: 'orbit', Electronics: 'circuit', Waves: 'wave', Mechanics: 'projectile', Chemistry: 'gas', Relativity: 'mass', Mathematics: 'plot' };
const fmt = (x) => (Math.abs(x) >= 1e5 || (Math.abs(x) < 1e-3 && x !== 0) ? x.toExponential(3) : (+x.toPrecision(5)).toString());

export async function mount(root, ctx) {
  const lib = await ctx.api('/api/science/library');
  const st = { subject: lib.subjects.includes('Astronomy') ? 'Astronomy' : lib.subjects[0] };
  const nav = h('nav', { class: 'a-nav', 'aria-label': 'Science subjects' }), lab = h('div', { class: 'a-lab' }), topics = h('div', { class: 'a-topics' }), work = h('div', { class: 'a-work' });
  root.append(h('header', { class: 'a-head' }, backButton(ctx), h('div', { class: 'a-logo' }, '✦ ASTRA', h('small', {}, 'SCIENCE INTELLIGENCE'))),
    h('div', { class: 'a-body' }, nav, h('main', { class: 'a-center' }, lab, h('h4', {}, 'KNOWLEDGE PANELS'), topics), h('aside', { class: 'a-right' }, work)));

  function select(subject) {
    cancelAnimationFrame(raf); st.subject = subject;
    nav.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.s === subject));
    drawLab(); drawTopics(); drawWork();
  }
  lib.subjects.forEach((s) => nav.append(h('button', { type: 'button', 'data-s': s, onclick: () => select(s) }, h('span', { class: 'dot' }), s)));

  const slider = (label, min, max, step, val, on) => {
    const out = h('b', {}, val), i = h('input', { type: 'range', min, max, step, value: val, 'aria-label': label });
    i.addEventListener('input', () => { out.textContent = i.value; on(+i.value); });
    return h('label', { class: 'a-sl' }, h('span', {}, label), i, out);
  };
  const solve = async (formula, values, target) => ctx.api('/api/science/solve', { method: 'POST', body: { formula, values, target } });
  const readout = (...kids) => h('div', { class: 'a-read' }, ...kids);

  // ---------- diagrams
  function drawLab() {
    clear(lab);
    const kind = VISUAL[st.subject];
    lab.append(h('h4', {}, `${st.subject.toUpperCase()} · INTERACTIVE DIAGRAM`));
    ({ orbit, circuit, wave, projectile, gas, mass, plot }[kind] || (() => {}))();
  }

  function canvas(w = 560, hgt = 260) { const c = h('canvas', { width: w, height: hgt, class: 'a-canvas', role: 'img', 'aria-label': 'Diagram' }); return c; }

  function orbit() {
    const c = canvas(), g = c.getContext('2d'), S = { a: 1, e: 0.3 }, info = readout('…');
    const GM = 1.32712440018e20, AU = 1.495978707e11;
    const upd = debounce(async () => {
      try { const r = await solve('orbital_period', { a: S.a * AU, M: 1.989e30 }, 'T'); const rp = S.a * (1 - S.e), ra = S.a * (1 + S.e);
        const v = (r_) => Math.sqrt(GM * (2 / (r_ * AU) - 1 / (S.a * AU))) / 1000;
        clear(info).append(h('span', {}, `Period T = ${fmt(r.result / 86400 / 365.25)} years (solver)`), h('span', {}, `Perihelion ${rp.toFixed(2)} AU · speed ${v(rp).toFixed(1)} km/s`), h('span', {}, `Aphelion ${ra.toFixed(2)} AU · speed ${v(ra).toFixed(1)} km/s`)); }
      catch (e) { info.textContent = e.message; } }, 200);
    upd();
    const t0 = performance.now();
    (function frame(now) {
      raf = requestAnimationFrame(frame);
      const W = c.width, H = c.height, a = S.a, e = S.e, scale = (H / 2 - 18) / (Math.max(a * (1 + e), 1.2) * 1.05);
      g.clearRect(0, 0, W, H); const cx = W / 2 - a * e * scale, cy = H / 2;
      g.strokeStyle = 'rgba(167,139,250,.55)'; g.lineWidth = 1.5; g.beginPath(); g.ellipse(cx, cy, a * scale, a * Math.sqrt(1 - e * e) * scale, 0, 0, 7); g.stroke();
      const sx = cx + a * e * scale; const star = g.createRadialGradient(sx, cy, 0, sx, cy, 16); star.addColorStop(0, '#fff6c8'); star.addColorStop(1, 'rgba(255,200,60,0)'); g.fillStyle = star; g.beginPath(); g.arc(sx, cy, 16, 0, 7); g.fill();
      const T = Math.pow(a, 1.5) * 8 /* seconds per orbit on screen */, M = ((now - t0) / 1000 / T) * 2 * Math.PI; let E = M; for (let i = 0; i < 6; i++) E -= (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
      const x = cx + a * (Math.cos(E)) * scale, y = cy + a * Math.sqrt(1 - e * e) * Math.sin(E) * scale;
      g.fillStyle = '#a78bfa'; g.shadowColor = '#a78bfa'; g.shadowBlur = 12; g.beginPath(); g.arc(x, y, 6, 0, 7); g.fill(); g.shadowBlur = 0;
    })(t0);
    lab.append(c, h('div', { class: 'a-sliders' }, slider('Semi-major axis (AU)', 0.4, 5, 0.1, 1, (v) => { S.a = v; upd(); }), slider('Eccentricity', 0, 0.9, 0.05, 0.3, (v) => { S.e = v; upd(); })), info,
      h('p', { class: 'a-cap' }, 'Planet speed on screen follows Kepler’s second law (faster near the star). Orbit period is computed by the formula solver for a one-solar-mass star.'));
  }

  function circuit() {
    const S = { V: 12, R: 100 }, out = readout('…'), dots = [];
    const wire = svg('svg', { viewBox: '0 0 360 190', class: 'a-svg', role: 'img', 'aria-label': 'Simple circuit' },
      svg('rect', { x: 40, y: 30, width: 280, height: 130, rx: 8, fill: 'none', stroke: '#a78bfa', 'stroke-width': 3 }),
      svg('rect', { x: 20, y: 70, width: 40, height: 50, fill: '#1b1030', stroke: '#c4b5fd', 'stroke-width': 2 }), svg('text', { x: 40, y: 100, fill: '#e9e0ff', 'font-size': 14, 'text-anchor': 'middle' }, 'V'),
      svg('rect', { x: 260, y: 50, width: 120, height: 30, fill: '#1b1030', stroke: '#f0abfc', 'stroke-width': 2, transform: 'translate(-60 0)' }), svg('text', { x: 260, y: 70, fill: '#f0abfc', 'font-size': 13, 'text-anchor': 'middle' }, 'R'));
    for (let i = 0; i < 10; i++) { const d = svg('circle', { r: 4, fill: '#7df9ff' }); dots.push(d); wire.append(d); }
    const upd = debounce(async () => { try { const i = await solve('ohm', { V: S.V, R: S.R }, 'I'); const p = await solve('power', { V: S.V, I: i.result }, 'P');
      clear(out).append(h('span', {}, `I = V/R = ${fmt(i.result * 1000)} mA`), h('span', {}, `P = V×I = ${fmt(p.result * 1000)} mW`), h('span', {}, i.steps[1])); S.I = i.result; } catch (e) { out.textContent = e.message; } }, 150);
    upd();
    const t0 = performance.now(), perim = 2 * (280 + 130);
    (function frame(now) { raf = requestAnimationFrame(frame); const speed = Math.min(220, (S.I || 0) * 4000 + 8); const off = ((now - t0) / 1000) * speed;
      dots.forEach((d, i) => { let s = (off + (i * perim) / dots.length) % perim, x, y; if (s < 280) { x = 40 + s; y = 30; } else if ((s -= 280) < 130) { x = 320; y = 30 + s; } else if ((s -= 130) < 280) { x = 320 - s; y = 160; } else { s -= 280; x = 40; y = 160 - s; } d.setAttribute('cx', x); d.setAttribute('cy', y); d.setAttribute('opacity', S.I ? 1 : .2); }); })(t0);
    lab.append(wire, h('div', { class: 'a-sliders' }, slider('Voltage (V)', 1, 48, 1, 12, (v) => { S.V = v; upd(); }), slider('Resistance (Ω)', 1, 1000, 1, 100, (v) => { S.R = v; upd(); })), out,
      h('p', { class: 'a-cap' }, 'The moving dots speed up with current (animation scaled, not to physical drift velocity).'));
  }

  function wave() {
    const c = canvas(), g = c.getContext('2d'), S = { f: 2, lam: 1 }, out = readout('…');
    const upd = debounce(async () => { try { const r = await solve('wave', { f: S.f, lam: S.lam }, 'v'); clear(out).append(h('span', {}, `v = f × λ = ${fmt(r.result)} m/s`), h('span', {}, `Period T = ${(1 / S.f).toFixed(2)} s`)); } catch (e) { out.textContent = e.message; } }, 150);
    upd(); const t0 = performance.now();
    (function frame(now) { raf = requestAnimationFrame(frame); const W = c.width, H = c.height, t = (now - t0) / 1000; g.clearRect(0, 0, W, H);
      g.strokeStyle = 'rgba(167,139,250,.25)'; g.beginPath(); g.moveTo(0, H / 2); g.lineTo(W, H / 2); g.stroke();
      g.strokeStyle = '#7df9ff'; g.lineWidth = 2.5; g.beginPath(); for (let x = 0; x <= W; x++) { const y = H / 2 - Math.sin((2 * Math.PI * x) / (S.lam * 120) - 2 * Math.PI * S.f * t * 0.5) * 70; x ? g.lineTo(x, y) : g.moveTo(x, y); } g.stroke();
      g.strokeStyle = '#f0abfc'; g.lineWidth = 1; g.beginPath(); g.moveTo(10, H - 24); g.lineTo(10 + S.lam * 120, H - 24); g.stroke(); g.fillStyle = '#f0abfc'; g.fillText('λ', 10 + S.lam * 60, H - 28); })(t0);
    lab.append(c, h('div', { class: 'a-sliders' }, slider('Frequency (Hz)', 0.5, 6, 0.5, 2, (v) => { S.f = v; upd(); }), slider('Wavelength (m, drawn at 120 px/m)', 0.4, 3, 0.1, 1, (v) => { S.lam = v; upd(); })), out);
  }

  function projectile() {
    const c = canvas(), g = c.getContext('2d'), S = { v: 25, th: 45 }, out = readout('…'); let R = 0;
    const upd = debounce(async () => { try { const r = await solve('projectile_range', { v: S.v, theta: S.th }, 'R'); R = r.result; const hmax = (S.v * Math.sin(S.th * Math.PI / 180)) ** 2 / (2 * 9.80665);
      clear(out).append(h('span', {}, `Range R = v² sin(2θ)/g = ${fmt(R)} m`), h('span', {}, `Max height ≈ ${fmt(hmax)} m (v² sin²θ / 2g)`)); } catch (e) { out.textContent = e.message; } }, 150);
    upd(); const t0 = performance.now();
    (function frame(now) { raf = requestAnimationFrame(frame); const W = c.width, H = c.height; g.clearRect(0, 0, W, H); const g0 = 9.80665, th = S.th * Math.PI / 180, vx = S.v * Math.cos(th), vy = S.v * Math.sin(th);
      const Tf = (2 * vy) / g0, hm = vy * vy / (2 * g0), sc = Math.min((W - 40) / Math.max(R, 1), (H - 40) / Math.max(hm * 1.2, 1));
      g.strokeStyle = 'rgba(167,139,250,.5)'; g.beginPath(); g.moveTo(20, H - 20); g.lineTo(W - 10, H - 20); g.stroke(); g.strokeStyle = '#f0abfc'; g.setLineDash([4, 4]); g.beginPath();
      for (let i = 0; i <= 60; i++) { const t = (Tf * i) / 60; const x = 20 + vx * t * sc, y = H - 20 - (vy * t - 0.5 * g0 * t * t) * sc; i ? g.lineTo(x, y) : g.moveTo(x, y); } g.stroke(); g.setLineDash([]);
      const t = (((now - t0) / 1000) % (Tf + 0.6)); const tt = Math.min(t, Tf); g.fillStyle = '#7df9ff'; g.beginPath(); g.arc(20 + vx * tt * sc, H - 20 - (vy * tt - 0.5 * g0 * tt * tt) * sc, 7, 0, 7); g.fill(); })(t0);
    lab.append(c, h('div', { class: 'a-sliders' }, slider('Launch speed (m/s)', 5, 80, 1, 25, (v) => { S.v = v; upd(); }), slider('Angle (°)', 5, 85, 1, 45, (v) => { S.th = v; upd(); })), out, h('p', { class: 'a-cap' }, 'Flat ground, no air resistance.'));
  }

  function gas() {
    const S = { T: 300, V: 0.0224 }, out = readout('…'), piston = svg('rect', { x: 30, y: 20, width: 200, height: 80, fill: 'rgba(240,171,252,.25)', stroke: '#f0abfc' });
    const svgEl = svg('svg', { viewBox: '0 0 260 130', class: 'a-svg', role: 'img', 'aria-label': 'Gas in a cylinder' }, svg('rect', { x: 25, y: 15, width: 210, height: 100, fill: 'none', stroke: '#a78bfa', 'stroke-width': 3 }), piston);
    const upd = debounce(async () => { try { const r = await solve('ideal_gas', { V: S.V, n: 1, T: S.T }, 'P'); piston.setAttribute('width', 40 + (S.V / 0.05) * 190);
      clear(out).append(h('span', {}, `P = nRT/V = ${fmt(r.result / 1000)} kPa (1 mol)`), h('span', {}, `${fmt(r.result / 101325)} atm`)); } catch (e) { out.textContent = e.message; } }, 150);
    upd(); lab.append(svgEl, h('div', { class: 'a-sliders' }, slider('Temperature (K)', 100, 800, 10, 300, (v) => { S.T = v; upd(); }), slider('Volume (m³)', 0.005, 0.05, 0.0005, 0.0224, (v) => { S.V = v; upd(); })), out);
  }

  function mass() {
    const out = readout('…'); let m = 1;
    const upd = debounce(async () => { try { const r = await solve('mass_energy', { m: m / 1000 }, 'E'); clear(out).append(h('span', {}, `E = m c² = ${fmt(r.result)} J`), h('span', {}, `≈ ${fmt(r.result / 4.184e12)} kilotons of TNT`)); } catch (e) { out.textContent = e.message; } }, 150);
    upd(); lab.append(h('div', { class: 'a-big' }, 'E = mc²'), h('div', { class: 'a-sliders' }, slider('Mass (grams)', 0.001, 100, 0.001, 1, (v) => { m = v; upd(); })), out);
  }

  function plot() {
    const c = canvas(), g = c.getContext('2d'), expr = h('input', { type: 'text', value: 'sin(x)', 'aria-label': 'Function of x', class: 'a-in' }), msg = h('div', { class: 'a-read' });
    const lo = h('input', { type: 'number', value: -10, 'aria-label': 'x minimum', class: 'a-num' }), hi = h('input', { type: 'number', value: 10, 'aria-label': 'x maximum', class: 'a-num' });
    async function draw() {
      try { const r = await ctx.api('/api/science/plot', { method: 'POST', body: { expr: expr.value, lo: +lo.value, hi: +hi.value } }); const pts = r.points, ys = pts.map((p) => p[1]).filter((y) => y != null), ymin = Math.min(...ys), ymax = Math.max(...ys), pad = (ymax - ymin || 1) * .1;
        const W = c.width, H = c.height, X = (x) => ((x - +lo.value) / (+hi.value - +lo.value)) * W, Y = (y) => H - ((y - ymin + pad) / (ymax - ymin + 2 * pad)) * H;
        g.clearRect(0, 0, W, H); g.strokeStyle = 'rgba(167,139,250,.3)'; g.beginPath(); if (ymin <= 0 && ymax >= 0) { g.moveTo(0, Y(0)); g.lineTo(W, Y(0)); } if (+lo.value <= 0 && +hi.value >= 0) { g.moveTo(X(0), 0); g.lineTo(X(0), H); } g.stroke();
        g.strokeStyle = '#7df9ff'; g.lineWidth = 2; g.beginPath(); let pen = false; for (const [x, y] of pts) { if (y == null) { pen = false; continue; } pen ? g.lineTo(X(x), Y(y)) : g.moveTo(X(x), Y(y)); pen = true; } g.stroke();
        msg.textContent = `y from ${fmt(ymin)} to ${fmt(ymax)} on x ∈ [${lo.value}, ${hi.value}]`; } catch (e) { msg.textContent = e.message; } }
    expr.addEventListener('keydown', (e) => e.key === 'Enter' && draw()); draw();
    lab.append(c, h('div', { class: 'row' }, h('span', {}, 'y ='), expr, h('span', {}, 'x:'), lo, hi, h('button', { type: 'button', class: 'a-btn', onclick: draw }, 'PLOT')), msg);
  }

  // ---------- knowledge panels
  function drawTopics() {
    clear(topics);
    const list = lib.topics.filter((t) => t.subject === st.subject || (st.subject === 'Mathematics' && false));
    if (!list.length) topics.append(h('p', { class: 'a-cap' }, st.subject === 'Mathematics' ? 'Use the plotter above and the calculator on the right.' : 'No topic cards for this subject yet.'));
    list.forEach((t) => {
      const body = h('div', { class: 'a-tbody', hidden: true }, h('p', {}, t.text));
      const ans = h('div', { class: 'a-ans' });
      body.append(h('button', { type: 'button', class: 'a-btn', onclick: async () => { ans.textContent = 'Asking ASTRA…'; const r = await ctx.ask('explain ' + t.title).catch((e) => ({ reply: e.message })); clear(ans).append(h('p', {}, r.reply)); } }, 'MORE FROM ASTRA'), ans);
      topics.append(h('article', { class: 'a-card' }, h('button', { type: 'button', class: 'a-ttl', 'aria-expanded': 'false', onclick: (e) => { body.hidden = !body.hidden; e.currentTarget.setAttribute('aria-expanded', String(!body.hidden)); } }, t.title), body));
    });
  }

  // ---------- formula workspace + calculator
  function drawWork() {
    clear(work).append(h('h4', {}, 'FORMULA WORKSPACE'));
    const fs = lib.formulas.filter((f) => f.subject === st.subject);
    if (st.subject === 'Mathematics') {
      const inp = h('input', { type: 'text', class: 'a-in', placeholder: 'e.g. 25*4+sqrt(81) or 20% of 150 or 10 km to miles', 'aria-label': 'Calculator' }), res = h('div', { class: 'a-read' });
      const go = async () => { try { const r = await ctx.api('/api/calc', { method: 'POST', body: { text: inp.value } }); res.textContent = r.result.includes('=') ? r.result : `${r.expression} = ${r.result}`; } catch (e) { res.textContent = e.message; } };
      inp.addEventListener('keydown', (e) => e.key === 'Enter' && go());
      work.append(inp, h('button', { type: 'button', class: 'a-btn', onclick: go }, 'CALCULATE'), res, h('p', { class: 'a-cap' }, 'Uses a safe expression evaluator (no code execution). Trig functions use radians.')); return;
    }
    if (!fs.length) return work.append(h('p', { class: 'a-cap' }, 'No formulas for this subject.'));
    const sel = h('select', { 'aria-label': 'Formula', class: 'a-in' }, fs.map((f) => h('option', { value: f.id }, f.name))), form = h('div', { class: 'a-form' }), res = h('div', { class: 'a-read' });
    function build() {
      const f = fs.find((x) => x.id === sel.value); clear(form).append(h('div', { class: 'a-eq' }, f.equation));
      const target = h('select', { 'aria-label': 'Solve for', class: 'a-in' }, f.variables.filter((v) => v.solvable).map((v) => h('option', { value: v.symbol }, `${v.symbol} — ${v.name}`)));
      const inputs = {}; const holder = h('div');
      const rebuild = () => { clear(holder); f.variables.filter((v) => v.symbol !== target.value).forEach((v) => { inputs[v.symbol] = h('input', { type: 'number', step: 'any', class: 'a-in', placeholder: `${v.name} (${v.unit})`, 'aria-label': `${v.name} in ${v.unit}` }); holder.append(h('label', { class: 'a-lab' }, h('span', {}, `${v.symbol} (${v.unit})`), inputs[v.symbol])); }); };
      target.addEventListener('change', rebuild); rebuild();
      form.append(h('label', { class: 'a-lab' }, h('span', {}, 'Solve for'), target), holder,
        Object.keys(f.constants).length ? h('p', { class: 'a-cap' }, 'Constants: ' + Object.entries(f.constants).map(([k, v]) => `${k} = ${v}`).join(', ')) : null,
        h('button', { type: 'button', class: 'a-btn primary', onclick: async () => { const vals = {}; for (const [k, el] of Object.entries(inputs)) if (el.value !== '' && el.isConnected) vals[k] = +el.value;
          try { const r = await solve(f.id, vals, target.value); clear(res).append(h('b', {}, `${r.target} = ${fmt(r.result)} ${r.unit}`), ...r.steps.map((s) => h('div', {}, s))); } catch (e) { clear(res).append(h('span', { class: 'err' }, e.message)); } } }, 'SOLVE'));
    }
    sel.addEventListener('change', build); work.append(sel, form, res); build();
  }

  select(st.subject);
}
