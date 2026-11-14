// VOLT — hardware monitoring dashboard. Every number comes from /api/hardware; unavailable data says so.
import { h, svg, fmtBytes, fmtDur, clear, backButton } from '../dom.js';

let timer = null;
export function unmount() { clearInterval(timer); timer = null; }

const arc = (pct, size = 120, label = '') => {
  const r = 48, c = 2 * Math.PI * r * 0.75, v = Math.max(0, Math.min(100, pct ?? 0));
  return svg('svg', { viewBox: '0 0 120 110', class: 'gauge', role: 'img', 'aria-label': `${label} ${pct == null ? 'unavailable' : v.toFixed(0) + ' percent'}` },
    svg('circle', { cx: 60, cy: 62, r, class: 'g-track', 'stroke-dasharray': `${c} 999`, transform: 'rotate(135 60 62)' }),
    svg('circle', { cx: 60, cy: 62, r, class: 'g-val', 'stroke-dasharray': `${c * v / 100} 999`, transform: 'rotate(135 60 62)' }),
    svg('text', { x: 60, y: 66, class: 'g-text' }, pct == null ? 'N/A' : `${v.toFixed(0)}%`),
    svg('text', { x: 60, y: 84, class: 'g-sub' }, label));
};
const spark = (vals, max = 100) => {
  const w = 220, hh = 40, n = Math.max(vals.length, 2);
  const pts = vals.map((v, i) => `${(i / (n - 1)) * w},${hh - (Math.min(v, max) / max) * hh}`).join(' ');
  return svg('svg', { viewBox: `0 0 ${w} ${hh}`, class: 'spark', preserveAspectRatio: 'none' }, svg('polyline', { points: pts || `0,${hh} ${w},${hh}`, fill: 'none' }));
};
const unavailable = (what, why) => h('div', { class: 'na' }, h('b', {}, `${what}: UNAVAILABLE`), h('div', { class: 'unavail' }, why));

export async function mount(root, ctx) {
  const hist = { cpu: [], mem: [], rx: [], tx: [] };
  let prev = null;
  const grid = h('div', { class: 'v-grid' });
  const pulse = h('span', { class: 'v-pulse' });
  const stamp = h('span', { class: 'muted' }, 'connecting…');
  root.append(
    h('header', { class: 'v-head' }, backButton(ctx), h('div', { class: 'v-logo' }, h('span', { class: 'bolt' }, '⚡'), 'VOLT', h('small', {}, 'HARDWARE INTELLIGENCE')), h('div', { class: 'grow' }), pulse, stamp),
    grid);

  async function tick() {
    if (document.hidden) return;
    let d;
    try { d = await ctx.api('/api/hardware'); } catch (e) { stamp.textContent = e.message; pulse.classList.add('bad'); return; }
    pulse.classList.remove('bad'); stamp.textContent = 'live · ' + new Date(d.time * 1000).toLocaleTimeString();
    const cpu = d.cpu.usage, mem = d.memory;
    if (cpu.available) hist.cpu.push(cpu.value);
    if (mem.ok && mem.percent != null) hist.mem.push(mem.percent);
    const n = d.network;
    if (prev && n.bytes_received != null) {
      const dt = d.time - prev.time;
      hist.rx.push(Math.max(0, (n.bytes_received - prev.rx) / dt)); hist.tx.push(Math.max(0, (n.bytes_sent - prev.tx) / dt));
    }
    prev = { time: d.time, rx: n.bytes_received, tx: n.bytes_sent };
    for (const k of Object.keys(hist)) if (hist[k].length > 60) hist[k].shift();
    render(d);
  }

  function tile(title, ...kids) { return h('section', { class: 'v-tile' }, h('h3', {}, title), ...kids); }

  function render(d) {
    const cpu = d.cpu, mem = d.memory, sys = d.system, b = d.battery, net = d.network;
    const rate = (a) => (a.length ? fmtBytes(a[a.length - 1]) + '/s' : 'measuring…');
    clear(grid).append(
      tile('CPU', arc(cpu.usage.available ? cpu.usage.value : null, 120, 'USAGE'), spark(hist.cpu),
        h('div', { class: 'kv' }, h('span', {}, 'Model'), h('b', {}, cpu.model.available ? cpu.model.value : 'unavailable'),
          h('span', {}, 'Cores'), h('b', {}, `${sys.cores_logical} logical${sys.cores_physical ? ` / ${sys.cores_physical} physical` : ''}`),
          h('span', {}, 'Temperature'), h('b', {}, cpu.temperature.available ? `${cpu.temperature.value} °C` : 'unavailable')),
        cpu.temperature.available ? null : h('div', { class: 'unavail' }, cpu.temperature.reason),
        cpu.usage.available ? null : unavailable('CPU usage', cpu.usage.reason)),
      tile('MEMORY', mem.ok ? arc(mem.percent, 120, 'RAM') : unavailable('RAM', mem.reason), spark(hist.mem),
        mem.ok ? h('div', { class: 'kv' }, h('span', {}, 'Total'), h('b', {}, fmtBytes(mem.total)), h('span', {}, 'Used'), h('b', {}, fmtBytes(mem.used)),
          h('span', {}, 'Available'), h('b', {}, fmtBytes(mem.available)), h('span', {}, 'Swap'), h('b', {}, mem.swap_total ? `${fmtBytes(mem.swap_used)} / ${fmtBytes(mem.swap_total)}` : 'none')) : null),
      tile('STORAGE', ...(d.disks.length ? d.disks.map((x) => h('div', { class: 'disk' },
        h('div', { class: 'row' }, h('b', {}, x.mount), h('span', { class: 'muted' }, x.fstype)),
        h('div', { class: 'bar' }, h('i', { style: `width:${x.percent}%`, class: x.percent > 90 ? 'hot' : '' })),
        h('div', { class: 'muted' }, `${fmtBytes(x.free)} free of ${fmtBytes(x.total)} · ${x.percent}% used`))) : [unavailable('Storage', 'No readable disks were reported.')])),
      tile('BATTERY', b.available ? h('div', { class: 'batt' }, h('div', { class: 'cell' }, h('i', { style: `width:${b.percent}%`, class: b.percent < 20 ? 'hot' : '' })),
        h('b', {}, `${b.percent}%`), h('span', {}, b.charging ? '⚡ charging' : 'on battery'), b.minutes_left ? h('span', { class: 'muted' }, `~${b.minutes_left} min left`) : null)
        : unavailable('Battery', b.reason)),
      tile('NETWORK', h('div', { class: 'kv' }, h('span', {}, 'Internet'), h('b', { class: net.internet ? 'good' : 'bad' }, net.internet == null ? 'unknown' : net.internet ? 'reachable' : 'not reachable'),
        h('span', {}, 'Local IP'), h('b', {}, net.local_ip || 'unknown'), h('span', {}, 'Host'), h('b', {}, net.hostname),
        h('span', {}, 'Interfaces'), h('b', {}, net.interfaces.length ? net.interfaces.map((i) => `${i.name}:${i.state}`).join(' ') : 'unavailable'),
        h('span', {}, 'Download'), h('b', {}, rate(hist.rx)), h('span', {}, 'Upload'), h('b', {}, rate(hist.tx))),
        net.bytes_received == null ? h('div', { class: 'unavail' }, 'Traffic counters are not available on this OS without psutil.') : spark(hist.rx, Math.max(1, ...hist.rx))),
      tile('SYSTEM', h('div', { class: 'kv' }, h('span', {}, 'OS'), h('b', {}, sys.os), h('span', {}, 'Architecture'), h('b', {}, sys.architecture),
        h('span', {}, 'Host'), h('b', {}, sys.hostname), h('span', {}, 'Uptime'), h('b', {}, sys.uptime.available ? fmtDur(sys.uptime.value) : 'unavailable'),
        h('span', {}, 'Python'), h('b', {}, sys.python), h('span', {}, 'psutil'), h('b', {}, d.psutil ? 'installed' : 'not installed (optional)'))),
      tile('CRYSTA PROCESS', h('div', { class: 'kv' }, h('span', {}, 'Memory (RSS)'), h('b', {}, d.crysta.rss ? fmtBytes(d.crysta.rss) : 'unavailable'),
        h('span', {}, 'Threads'), h('b', {}, d.crysta.threads), h('span', {}, 'PID'), h('b', {}, d.crysta.pid)),
        h('div', { class: 'unavail' }, 'This is the CRYSTA backend itself — useful on low-RAM machines.')));
  }
  await tick();
  timer = setInterval(tick, 2000);
}
