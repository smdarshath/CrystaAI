// Canvas orb: concentric HUD rings inspired by the reference image. Pure 2D canvas, ~30fps, pauses when hidden.
const P = {
  idle:       { spin: .25, glow: .75, pulse: .03, col: [34, 228, 255] },
  listening:  { spin: .5,  glow: 1,   pulse: .08, col: [90, 242, 255] },
  processing: { spin: 1.8, glow: .95, pulse: .05, col: [40, 200, 255] },
  speaking:   { spin: .5,  glow: 1,   pulse: .12, col: [130, 236, 255] },
  offline:    { spin: .12, glow: .45, pulse: .02, col: [90, 170, 195] },
  error:      { spin: .2,  glow: .9,  pulse: .06, col: [255, 100, 85] },
};

export function createOrb(canvas) {
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, state = 'idle', reduced = false, raf = 0, last = 0;
  const t0 = performance.now();
  const cur = { ...P.idle, col: [...P.idle.col] };

  function resize() {
    const r = canvas.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = r.width; H = r.height;
    canvas.width = Math.max(1, W * dpr); canvas.height = Math.max(1, H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (reduced) draw(performance.now());
  }

  function draw(now) {
    const tgt = P[state] || P.idle, k = reduced ? 1 : 0.08;
    for (const key of ['spin', 'glow', 'pulse']) cur[key] += (tgt[key] - cur[key]) * k;
    for (let i = 0; i < 3; i++) cur.col[i] += (tgt.col[i] - cur.col[i]) * k;
    const t = reduced ? 4 : (now - t0) / 1000, a = t * cur.spin, g = cur.glow;
    const cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 * 0.96;
    const [r, gg, b] = cur.col.map(Math.round), c = (al) => `rgba(${r},${gg},${b},${Math.max(0, Math.min(1, al * g))})`;
    ctx.clearRect(0, 0, W, H);
    ctx.save(); ctx.translate(cx, cy);

    let grad = ctx.createRadialGradient(0, 0, 0, 0, 0, R);
    grad.addColorStop(0, c(.20)); grad.addColorStop(.6, c(.05)); grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(0, 0, R, 0, 7); ctx.fill();

    // faint crosshair lines
    ctx.strokeStyle = c(.12); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(-R, 0); ctx.lineTo(R, 0); ctx.moveTo(0, -R); ctx.lineTo(0, R); ctx.stroke();

    // outer ring + ticks
    ctx.strokeStyle = c(.6); ctx.lineWidth = 1.3; ctx.beginPath(); ctx.arc(0, 0, R * .98, 0, 7); ctx.stroke();
    ctx.save(); ctx.rotate(a * .3); ctx.strokeStyle = c(.5); ctx.lineWidth = 1;
    for (let i = 0; i < 180; i++) {
      const ang = i * Math.PI / 90, long = i % 5 === 0, r0 = R * .98, r1 = R * (long ? .93 : .955);
      ctx.beginPath(); ctx.moveTo(Math.cos(ang) * r0, Math.sin(ang) * r0); ctx.lineTo(Math.cos(ang) * r1, Math.sin(ang) * r1); ctx.stroke();
    }
    ctx.restore();

    // segmented ring
    ctx.save(); ctx.rotate(-a * .5); ctx.setLineDash([R * .07, R * .025]); ctx.strokeStyle = c(.55); ctx.lineWidth = R * .012;
    ctx.beginPath(); ctx.arc(0, 0, R * .88, 0, 7); ctx.stroke(); ctx.restore();
    ctx.setLineDash([]); ctx.strokeStyle = c(.28); ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(0, 0, R * .82, 0, 7); ctx.stroke();

    // bright arcs (glow)
    ctx.save(); ctx.rotate(a * 1.1); ctx.shadowColor = c(1); ctx.shadowBlur = reduced ? 0 : 16; ctx.strokeStyle = c(.95); ctx.lineWidth = R * .022; ctx.lineCap = 'round';
    for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.arc(0, 0, R * .74, i * 2.094, i * 2.094 + (.7 + .25 * i)); ctx.stroke(); }
    ctx.restore();

    // inner dashed ring reverse
    ctx.save(); ctx.rotate(-a * .8); ctx.setLineDash([R * .02, R * .03]); ctx.strokeStyle = c(.5); ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(0, 0, R * .64, 0, 7); ctx.stroke(); ctx.restore();

    // inner ticked ring
    ctx.save(); ctx.rotate(a * .6); ctx.strokeStyle = c(.45); ctx.lineWidth = 1;
    for (let i = 0; i < 90; i++) {
      const ang = i * Math.PI / 45, r0 = R * .55, r1 = R * (i % 3 === 0 ? .5 : .525);
      ctx.beginPath(); ctx.moveTo(Math.cos(ang) * r0, Math.sin(ang) * r0); ctx.lineTo(Math.cos(ang) * r1, Math.sin(ang) * r1); ctx.stroke();
    }
    ctx.restore();

    // crosshair gap ring
    ctx.save(); ctx.rotate(a * .35); ctx.strokeStyle = c(.7); ctx.lineWidth = 2;
    for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.arc(0, 0, R * .41, i * Math.PI / 2 + .25, (i + 1) * Math.PI / 2 - .25); ctx.stroke(); }
    ctx.restore();

    // listening waves / processing sweep
    if (state === 'listening') {
      for (let i = 0; i < 3; i++) { const ph = ((t * .9) + i / 3) % 1; ctx.strokeStyle = c((1 - ph) * .55); ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(0, 0, R * (.2 + .6 * ph), 0, 7); ctx.stroke(); }
    }
    if (state === 'processing') {
      ctx.save(); ctx.rotate(t * 3); ctx.strokeStyle = c(.9); ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(0, 0, R * .69, 0, 1.6); ctx.stroke(); ctx.restore();
    }

    // core
    const pul = cur.pulse * Math.sin(t * (state === 'speaking' ? 10 : 3)), cr = R * (.17 + pul);
    grad = ctx.createRadialGradient(0, 0, 0, 0, 0, cr * 1.9);
    grad.addColorStop(0, 'rgba(255,255,255,.95)'); grad.addColorStop(.25, c(.9)); grad.addColorStop(.6, c(.25)); grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(0, 0, cr * 1.9, 0, 7); ctx.fill();
    ctx.strokeStyle = c(.8); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(0, 0, R * .27, 0, 7); ctx.stroke();

    // orbiting dots
    ctx.fillStyle = c(.95);
    for (let i = 0; i < 14; i++) { const ang = -a * .6 + i * Math.PI * 2 / 14; ctx.beginPath(); ctx.arc(Math.cos(ang) * R * .93, Math.sin(ang) * R * .93, 1.8, 0, 7); ctx.fill(); }

    // lens flare (upper-left, like the reference)
    const fx = Math.cos(-2.4) * R * .9, fy = Math.sin(-2.4) * R * .9;
    grad = ctx.createRadialGradient(fx, fy, 0, fx, fy, R * .2);
    grad.addColorStop(0, 'rgba(255,255,255,.9)'); grad.addColorStop(.25, c(.55)); grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(fx, fy, R * .2, 0, 7); ctx.fill();
    ctx.strokeStyle = c(.7); ctx.lineWidth = 1; ctx.beginPath();
    ctx.moveTo(fx - R * .15, fy); ctx.lineTo(fx + R * .15, fy); ctx.moveTo(fx, fy - R * .1); ctx.lineTo(fx, fy + R * .1); ctx.stroke();

    ctx.restore();
  }

  function loop(now) {
    raf = requestAnimationFrame(loop);
    if (document.hidden || now - last < 33) return;
    last = now; draw(now);
  }
  function start() { cancelAnimationFrame(raf); if (reduced) draw(performance.now()); else raf = requestAnimationFrame(loop); }

  window.addEventListener('resize', resize);
  resize(); start();
  return {
    setState(s) { state = P[s] ? s : 'idle'; if (reduced) draw(performance.now()); },
    setReduced(v) { reduced = !!v; start(); },
  };
}
