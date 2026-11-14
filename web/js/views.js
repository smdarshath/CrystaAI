import { api } from './api.js';
import { h, rich, safeUrl, fmtDate } from './dom.js';

export const TITLES = { chat: 'Chat', agents: 'All agents', devices: 'Devices', computer: 'Permissions & audit', settings: 'Settings' };

// ---------- shared message rendering
export function renderEntry(e) {
  if (e.role === 'user') return h('div', { class: 'msg user' }, e.text);
  const box = h('div', { class: 'msg bot' }, rich(e.text));
  const r = e.resp;
  if (r) {
    const multi = (r.results || []).length > 1;
    for (const res of r.results || []) {
      if (res.sources?.length) {
        const list = h('ol', { class: 'src' });
        for (const s of res.sources) {
          const url = safeUrl(s.url);
          list.append(h('li', {}, url ? h('a', { href: url, target: '_blank', rel: 'noopener noreferrer' }, s.title || url) : (s.title || 'source'), ' ', s.note ? h('small', {}, '· ' + s.note) : null));
        }
        box.append(h('div', { class: 'meta' }, multi ? `${res.agent_name} sources` : 'Sources'), list);
      }
    }
    if (r.limitations?.length) box.append(h('details', {}, h('summary', {}, 'Limitations (' + r.limitations.length + ')'), h('ul', {}, r.limitations.map((l) => h('li', {}, l)))));
    box.append(h('div', { class: 'meta' }, (r.results || []).filter((x) => x.ui_view && x.ui_view !== 'home' && x.agent !== 'crysta').map((x) => h('button', { type: 'button', class: 'btn', onclick: () => window.dispatchEvent(new CustomEvent('crysta-open', { detail: x.ui_view })) }, `OPEN ${x.agent_name} ▸`))));
    box.append(h('div', { class: 'meta' }, (r.results || []).map((x) => h('span', { class: 'tag ' + x.status, title: x.summary.slice(0, 80) }, `${x.agent_name} · ${x.status} · ${(x.duration_ms / 1000).toFixed(1)}s`))));
  }
  return box;
}

// ---------- chat
function chat(ctx, body) {
  const log = h('div', { class: 'log', role: 'log', 'aria-live': 'polite' });
  for (const e of ctx.history) log.append(renderEntry(e));
  if (!ctx.history.length) log.append(h('p', { class: 'note' }, 'Type below. Chat history lives only in this browser tab unless you turn on Memory in Settings.'));
  ctx.chatLog = log;
  const input = h('input', { type: 'text', 'aria-label': 'Message to Crysta', placeholder: 'Ask Crysta…', autocomplete: 'off', maxlength: '2000' });
  const send = () => { const t = input.value.trim(); if (t) { input.value = ''; ctx.send(t); } };
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });
  body.append(log, h('div', { class: 'compose' }, input, h('button', { class: 'btn primary', type: 'button', onclick: send }, 'SEND'),
    h('button', { class: 'btn', type: 'button', onclick: () => ctx.cancel() }, 'CANCEL')));
  setTimeout(() => { log.scrollTop = log.scrollHeight; input.focus(); }, 30);
}

// ---------- agents (launcher: every card opens that agent's own workspace)
async function agents(ctx, body) {
  const { agents: list, loaded, extensions } = await api('/api/agents');
  body.append(h('p', { class: 'note' }, `${list.length} agents registered. Agents load on first use to save memory (loaded now: ${loaded.join(', ') || 'none'}). Each opens its own workspace.`));
  const grid = h('div', { class: 'cards' });
  for (const a of list) {
    grid.append(h('div', { class: 'card' }, h('h3', {}, `${a.name} · ${a.title}`), h('p', {}, a.description),
      h('p', { class: 'note' }, 'Capabilities: ' + a.capabilities.join(', ')),
      h('p', { class: 'note' }, 'Tools: ' + (a.permitted_tools || []).join(', ')),
      h('p', { class: 'note' }, a.last_run ? `Last run: ${a.last_run.intent} → ${a.last_run.status} (${a.last_run.ms} ms)` : 'Not used yet this session.'),
      h('div', { class: 'row' }, h('button', { class: 'btn primary', type: 'button', onclick: () => ctx.open(a.ui_view) }, a.ui_view === 'home' ? 'CRYSTA HOME' : 'OPEN ' + a.name))));
  }
  body.append(grid);
  if (extensions?.length) body.append(h('h3', { class: 'note' }, 'Extensions found in extensions/'), ...extensions.map((e) => h('div', { class: 'card' }, h('b', {}, e.id || e.folder), h('p', { class: 'note' }, e.valid ? (e.enabled ? 'valid · enabled' : 'valid · disabled (enable it in Settings → extensions_enabled)') : 'INVALID: ' + e.errors.join('; ')))));
}

// ---------- devices
async function devices(ctx, body) {
  const s = await api('/api/settings');
  const list = h('div', { class: 'cards' }), pend = h('div', { class: 'cards' }), codeBox = h('div');
  const refresh = async () => {
    const d = await api('/api/devices');
    pend.replaceChildren(...d.pending.map((p) => {
      const ctl = h('input', { type: 'checkbox', id: 'c' + p.id });
      return h('div', { class: 'card' }, h('h3', {}, 'PAIRING REQUEST'), h('p', {}, `"${p.name}" from ${p.ip} wants to connect.`),
        h('label', { class: 'check', for: 'c' + p.id }, ctl, 'Also allow this device to control this computer (apps, files, commands — each still needs your approval here)'),
        h('div', { class: 'row' }, h('button', { class: 'btn primary', type: 'button', onclick: async () => { await api('/api/devices/decide', { method: 'POST', body: { id: p.id, approve: true, can_control: ctl.checked } }); refresh(); } }, 'APPROVE'),
          h('button', { class: 'btn', type: 'button', onclick: async () => { await api('/api/devices/decide', { method: 'POST', body: { id: p.id, approve: false } }); refresh(); } }, 'DENY')));
    }));
    list.replaceChildren(...(d.devices.length ? d.devices.map((x) => h('div', { class: 'card' }, h('h3', {}, x.name.toUpperCase()),
      h('p', {}, `Paired ${fmtDate(x.created)} · last seen ${fmtDate(x.last_seen)}`), h('p', {}, x.can_control ? 'May request computer control' : 'Chat/research only'),
      h('div', { class: 'row' }, h('button', { class: 'btn', type: 'button', onclick: async () => { await api('/api/devices/control', { method: 'POST', body: { id: x.id, allowed: !x.can_control } }); refresh(); } }, x.can_control ? 'REMOVE CONTROL' : 'ALLOW CONTROL'),
        h('button', { class: 'btn danger', type: 'button', onclick: async () => { await api('/api/devices/disconnect', { method: 'POST', body: { id: x.id } }); refresh(); } }, 'DISCONNECT')))) : [h('p', { class: 'note' }, 'No paired devices.')]));
  };
  body.append(h('div', { class: 'card' }, h('h3', {}, 'THIS COMPUTER'), h('p', {}, 'Connected (local). Voice, chat and computer control work here.')),
    s.lan_enabled ? h('p', { class: 'note' }, `Network mode is ON (port ${s.port}). Phones on your network can open this address and enter a pairing code. Plain HTTP is not encrypted — use a network you trust.`)
      : h('div', { class: 'warnbox' }, 'Network mode is OFF, so phones cannot reach Crysta. To enable it, stop Crysta and start it with:  python3 run.py --lan'),
    h('div', { class: 'row' }, h('button', { class: 'btn primary', type: 'button', onclick: async () => {
      const c = await api('/api/devices/pair-code', { method: 'POST', body: {} });
      codeBox.replaceChildren(h('div', { class: 'code' }, c.code), h('p', { class: 'note' }, 'On your phone open Crysta in the browser (the address printed in the terminal), choose “Pair this device”, type this code. It expires in 5 minutes.'));
    } }, 'CREATE PAIRING CODE')), codeBox, h('h3', { class: 'note' }, 'Requests waiting for you'), pend, h('h3', { class: 'note' }, 'Paired devices'), list,
    h('p', { class: 'note' }, 'Phone support today: a paired phone uses Crysta through its browser (chat + research). A native Android companion is planned, not built — see docs/DEVICE_PAIRING.md.'));
  await refresh();
  const timer = setInterval(() => { if (!document.body.contains(list)) clearInterval(timer); else refresh().catch(() => {}); }, 4000);
}

// ---------- computer
async function computer(ctx, body) {
  const s = await api('/api/settings');
  const set = async (patch) => { await api('/api/settings', { method: 'PATCH', body: patch }); ctx.refreshSettings(); };
  const rows = [['read_files', 'Read files in approved folders'], ['write_files', 'Create / change files'], ['open_apps', 'Open apps and websites'],
    ['run_commands', 'Run commands'], ['keyboard_mouse', 'Keyboard / mouse / screenshots (needs pyautogui)'], ['destructive', 'Delete / overwrite / risky changes']];
  const table = h('table', {}, h('tr', {}, h('th', {}, 'Permission'), h('th', {}, 'Level')));
  for (const [key, label] of rows) {
    const sel = h('select', { 'aria-label': label }, ['allow', 'confirm', 'deny'].filter((l) => !(key === 'destructive' && l === 'allow')).map((l) => h('option', { value: l, selected: s.settings['perm.' + key] === l }, l)));
    sel.addEventListener('change', () => set({ ['perm.' + key]: sel.value }));
    table.append(h('tr', {}, h('td', {}, label), h('td', {}, sel)));
  }
  const dirs = h('textarea', { rows: '3', 'aria-label': 'Approved folders, one per line' }, s.settings.approved_dirs.join('\n'));
  const trusted = h('input', { type: 'checkbox', id: 'trusted', checked: s.settings.autonomy === 'trusted' });
  trusted.addEventListener('change', () => set({ autonomy: trusted.checked ? 'trusted' : 'ask' }));
  const audit = h('div', { class: 'note' });
  const loadAudit = async () => { const a = await api('/api/audit'); audit.replaceChildren(...(a.events.length ? a.events.map((e) => h('div', {}, `${fmtDate(e.created)} · ${e.actor} · ${e.action} · ${e.outcome} · ${e.detail}`)) : ['No actions recorded yet.'])); };
  body.append(h('p', { class: 'note' }, 'Crysta can only do what is allowed here. "confirm" means a pop-up asks you every time. Say things like “open chrome”, “list files in Downloads”, “run git status”.'),
    table, h('h3', { class: 'note' }, 'Approved folders (Crysta cannot read or write outside these)'), dirs,
    h('div', { class: 'row' }, h('button', { class: 'btn', type: 'button', onclick: () => set({ approved_dirs: dirs.value.split('\n').map((x) => x.trim()).filter(Boolean) }) }, 'SAVE FOLDERS')),
    h('label', { class: 'check', for: 'trusted' }, trusted, 'Full-control mode: stop asking before opening apps, writing files, running commands and keyboard/mouse. Deleting/overwriting and risky commands STILL ask. A small never-run list (sudo, format, shutdown…) is always blocked.'),
    h('div', { class: 'row' }, h('button', { class: 'btn danger', type: 'button', onclick: async () => { const r = await api('/api/emergency-stop', { method: 'POST', body: {} }); ctx.refreshSettings(); ctx.toast(r.message); loadAudit(); } }, 'EMERGENCY STOP')),
    h('h3', { class: 'note' }, 'Recent actions'), audit,
    h('div', { class: 'row' }, h('button', { class: 'btn', type: 'button', onclick: async () => { await api('/api/audit', { method: 'DELETE' }); loadAudit(); } }, 'CLEAR LOG')));
  loadAudit();
}

// ---------- settings
async function settings(ctx, body) {
  const s = await api('/api/settings'), v = s.settings;
  const set = async (patch) => { await api('/api/settings', { method: 'PATCH', body: patch }); ctx.refreshSettings(); };
  const check = (key, label, extra) => {
    const id = 'k' + key, i = h('input', { type: 'checkbox', id, checked: !!v[key] });
    i.addEventListener('change', async () => { await set({ [key]: i.checked }); if (key === 'memory_enabled') mem(); });
    return h('label', { class: 'check', for: id }, i, h('span', {}, label, extra ? h('div', { class: 'note' }, extra) : null));
  };
  const name = h('input', { type: 'text', value: v.user_name, maxlength: '40', 'aria-label': 'Your name' });
  name.addEventListener('change', () => name.value.trim() && set({ user_name: name.value.trim() }));
  const lang = h('select', { 'aria-label': 'Voice language' }, [['en-IN', 'English (India)'], ['en-US', 'English (US)'], ['en-GB', 'English (UK)'], ['ta-IN', 'Tamil']].map(([k, l]) => h('option', { value: k, selected: v.voice_lang === k }, l)));
  lang.addEventListener('change', () => set({ voice_lang: lang.value }));
  const memBox = h('div');
  const mem = async () => {
    const m = await api('/api/memory');
    memBox.replaceChildren(h('p', { class: 'note' }, m.enabled ? `Memory is ON. Stored on this computer: ${m.memories.length} memories, ${m.notes.length} notes, ${m.messages} chat messages.` : 'Memory is OFF. Nothing is being saved.'),
      ...m.memories.slice(0, 20).map((x) => h('div', { class: 'row' }, h('span', { class: 'note' }, `#${x.id} ${x.value}`), h('button', { class: 'btn', type: 'button', onclick: async () => { await api('/api/memory', { method: 'DELETE', body: { id: x.id } }); mem(); } }, 'DELETE'))),
      h('div', { class: 'row' }, h('a', { class: 'btn', href: '/api/memory/export', download: 'crysta-export.json' }, 'EXPORT'),
        h('button', { class: 'btn danger', type: 'button', onclick: async () => { if (confirm('Delete ALL memories, notes and saved chats?')) { await api('/api/memory', { method: 'DELETE', body: { scope: 'all' } }); mem(); } } }, 'DELETE EVERYTHING')));
  };
  body.append(h('label', {}, 'Your name', name), h('label', {}, 'Voice language (needs matching browser/OS voices)', lang),
    check('speak_responses', 'Speak replies aloud'), check('reduce_motion', 'Reduce animation (saves battery and CPU)'),
    check('internet_enabled', 'Allow internet research', 'Off = Crysta never contacts the web.'),
    check('memory_enabled', 'Memory & chat history', 'Stores notes, “remember …” items and chat history in data/crysta.db on this computer only. Never passwords or files.'),
    memBox, h('h3', { class: 'note' }, 'Language model'),
    h('p', { class: 'note' }, s.llm.available ? `Connected: ${s.llm.provider} · ${s.llm.model}` : s.llm.detail),
    h('p', { class: 'note' }, 'Voice input uses your browser’s speech recognition (Chrome/Edge). In Chrome this may send audio to Google. Fully offline speech-to-text is planned, not built.'));
  mem();
}

export const VIEWS = { chat, agents, devices, computer, settings };
