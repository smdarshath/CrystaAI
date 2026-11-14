// NOVA — development intelligence: IDE-style workspace (explorer, editor, terminal, problems, logs, run/test).
import { h, clear, backButton, fmtBytes } from '../dom.js';

const sep = (p) => (p.includes('\\') && !p.includes('/') ? '\\' : '/');
const join = (a, b) => a.replace(/[\\/]+$/, '') + sep(a) + b;
const LANG = { py: 'Python', js: 'JavaScript', ts: 'TypeScript', html: 'HTML', css: 'CSS', json: 'JSON', md: 'Markdown', sh: 'Shell', txt: 'Text', java: 'Java', c: 'C', cpp: 'C++' };
const RUN = { py: (p) => `python3 "${p}"`, js: (p) => `node "${p}"`, sh: (p) => `bash "${p}"` };
export function unmount() {}

export async function mount(root, ctx) {
  const st = { rootDir: null, tabs: [], active: -1, hist: [], hi: 0, lastOut: '' };
  const explorer = h('div', { class: 'n-tree', role: 'tree', 'aria-label': 'Project files' });
  const tabsEl = h('div', { class: 'n-tabs', role: 'tablist' });
  const empty = h('div', { class: 'n-empty' }, h('b', {}, 'No file open'), h('div', {}, 'Choose a file in the explorer, or press ＋ New file.'), h('div', { class: 'muted' }, 'Ctrl+S saves. Writes ask for your approval unless Full-control mode is on (Permissions). Run ▶ and Test ✓ use the terminal below.'));
  const gutter = h('div', { class: 'n-gutter', 'aria-hidden': 'true' });
  const ta = h('textarea', { class: 'n-ta', spellcheck: 'false', wrap: 'off', 'aria-label': 'Code editor', disabled: true });
  const status = { lang: h('span'), pos: h('span', {}, 'Ln 1, Col 1'), saved: h('span'), msg: h('span', { class: 'grow' }) };
  const rootSel = h('select', { 'aria-label': 'Project folder', class: 'n-sel', onchange: () => openRoot(rootSel.value) });
  const panelTabs = ['TERMINAL', 'PROBLEMS', 'OUTPUT', 'LOGS'];
  const panels = Object.fromEntries(panelTabs.map((n) => [n, h('div', { class: 'n-pane', hidden: true, role: 'tabpanel' })]));
  const termOut = h('div', { class: 'n-termout' }), termIn = h('input', { type: 'text', class: 'n-termin', placeholder: 'type a command and press Enter', 'aria-label': 'Terminal command', spellcheck: 'false' });
  panels.TERMINAL.append(termOut, h('div', { class: 'n-termline' }, h('span', {}, '$'), termIn));
  const problems = panels.PROBLEMS, output = panels.OUTPUT, logs = panels.LOGS;
  const ptabs = panelTabs.map((n) => h('button', { type: 'button', class: 'n-ptab', role: 'tab', onclick: () => showPanel(n), 'data-p': n }, n));
  function showPanel(n) { panelTabs.forEach((k) => { panels[k].hidden = k !== n; }); ptabs.forEach((b) => b.classList.toggle('on', b.dataset.p === n)); if (n === 'LOGS') loadLogs(); if (n === 'TERMINAL') termIn.focus(); }
  const say = (t) => { status.msg.textContent = t; };
  const btn = (label, fn, cls = '') => h('button', { type: 'button', class: 'n-btn ' + cls, onclick: fn }, label);

  root.append(
    h('header', { class: 'n-menu' }, backButton(ctx), h('div', { class: 'n-logo' }, '◢ NOVA', h('small', {}, 'DEVELOPMENT INTELLIGENCE')), rootSel,
      btn('＋ New file', newFile), btn('💾 Save', save, 'primary'), btn('▶ Run', runFile, 'run'), btn('✓ Test', runTests), btn('⌕ Inspect project', inspectProject)),
    h('div', { class: 'n-main' }, h('aside', { class: 'n-side' }, h('div', { class: 'n-cap' }, 'EXPLORER'), explorer),
      h('section', { class: 'n-editor' }, tabsEl, h('div', { class: 'n-code' }, gutter, ta, empty))),
    h('section', { class: 'n-bottom' }, h('div', { class: 'n-ptabs' }, ptabs), ...Object.values(panels)),
    h('footer', { class: 'n-status' }, status.lang, status.pos, status.saved, status.msg, h('span', {}, 'NOVA · CRYSTA')));
  showPanel('TERMINAL');

  // ---------- explorer
  function node(name, path, isDir, depth) {
    const kids = h('div', { hidden: true }); let loaded = false;
    const row = h('div', { class: 'n-node' + (isDir ? ' dir' : ''), role: 'treeitem', tabindex: '0', style: `padding-left:${8 + depth * 12}px`,
      onclick: async () => {
        if (!isDir) return openFile(path);
        if (!loaded) { loaded = true; const r = await ctx.act('/api/files/list?path=' + encodeURIComponent(path)).catch((e) => ({ message: e.message })); (r.result?.items || []).filter((i) => !i.name.startsWith('.') && i.name !== 'node_modules' && i.name !== '__pycache__').forEach((i) => kids.append(node(i.name, join(path, i.name), i.type === 'folder', depth + 1))); }
        kids.hidden = !kids.hidden; row.firstChild.textContent = kids.hidden ? '▸ ' : '▾ '; },
      onkeydown: (e) => e.key === 'Enter' && row.click() }, h('span', {}, isDir ? '▸ ' : '  '), name);
    return h('div', {}, row, kids);
  }
  async function openRoot(path) {
    st.rootDir = path; clear(explorer);
    const r = await ctx.act('/api/files/list?path=' + encodeURIComponent(path)).catch((e) => ({ message: e.message }));
    if (!r.result) return say(r.message || 'Waiting for permission.');
    explorer.append(h('div', { class: 'n-node root' }, '📂 ' + (path.split(/[\\/]/).pop() || path)));
    r.result.items.filter((i) => !i.name.startsWith('.') && i.name !== 'node_modules' && i.name !== '__pycache__').forEach((i) => explorer.append(node(i.name, join(path, i.name), i.type === 'folder', 1)));
    say(`Opened ${path}`);
  }

  // ---------- editor
  const cur = () => st.tabs[st.active];
  function renderTabs() {
    clear(tabsEl).append(...st.tabs.map((t, i) => h('div', { class: 'n-tab' + (i === st.active ? ' on' : ''), role: 'tab', 'aria-selected': String(i === st.active), onclick: () => activate(i) },
      t.path.split(/[\\/]/).pop() + (t.dirty ? ' ●' : ''), h('button', { type: 'button', class: 'x', 'aria-label': 'Close tab', onclick: (e) => { e.stopPropagation(); closeTab(i); } }, '×'))));
  }
  function activate(i) {
    st.active = i; const t = cur(); renderTabs();
    ta.disabled = !t; empty.hidden = !!t; ta.value = t ? t.text : ''; updateGutter(); updateStatus();
    if (t) ta.focus();
  }
  function closeTab(i) { st.tabs.splice(i, 1); activate(Math.min(st.active, st.tabs.length - 1)); }
  async function openFile(path) {
    const ex = st.tabs.findIndex((t) => t.path === path); if (ex >= 0) return activate(ex);
    const r = await ctx.act('/api/files/read?path=' + encodeURIComponent(path)).catch((e) => ({ message: e.message }));
    if (!r.result) return say(r.message || 'Could not open that file.');
    st.tabs.push({ path, text: r.result.text, dirty: false }); activate(st.tabs.length - 1); say('Opened ' + path);
  }
  function updateGutter() { const n = ta.value.split('\n').length; gutter.textContent = Array.from({ length: n }, (_, i) => i + 1).join('\n'); gutter.scrollTop = ta.scrollTop; }
  function updateStatus() {
    const t = cur(); const ext = t ? t.path.split('.').pop().toLowerCase() : '';
    status.lang.textContent = t ? (LANG[ext] || 'Plain text') : 'No file'; status.saved.textContent = t ? (t.dirty ? 'Modified' : 'Saved') : '';
    const before = ta.value.slice(0, ta.selectionStart).split('\n'); status.pos.textContent = `Ln ${before.length}, Col ${before[before.length - 1].length + 1}`;
  }
  ta.addEventListener('input', () => { const t = cur(); if (t) { t.text = ta.value; t.dirty = true; renderTabs(); } updateGutter(); updateStatus(); });
  ta.addEventListener('scroll', () => { gutter.scrollTop = ta.scrollTop; });
  ta.addEventListener('keyup', updateStatus); ta.addEventListener('click', updateStatus);
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') { e.preventDefault(); const s = ta.selectionStart; ta.setRangeText('    ', s, ta.selectionEnd, 'end'); ta.dispatchEvent(new Event('input')); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
  });
  async function save() {
    const t = cur(); if (!t) return say('Nothing to save.');
    const r = await ctx.act('/api/files/write', { method: 'POST', body: { path: t.path, content: t.text } }).catch((e) => ({ ok: false, message: e.message }));
    if (r.ok) { t.dirty = false; renderTabs(); updateStatus(); say(r.message || 'Saved.'); } else say(r.declined ? 'Save cancelled.' : r.message || 'Save failed.');
  }
  async function newFile() {
    if (!st.rootDir) return say('Choose a project folder first.');
    const input = h('input', { type: 'text', class: 'n-newname', placeholder: 'new file name, e.g. app.py', 'aria-label': 'New file name' });
    tabsEl.append(input); input.focus();
    input.addEventListener('keydown', async (e) => {
      if (e.key === 'Escape') { input.remove(); }
      if (e.key !== 'Enter' || !input.value.trim()) return;
      const path = join(st.rootDir, input.value.trim()); input.remove();
      const r = await ctx.act('/api/files/write', { method: 'POST', body: { path, content: '' } }).catch((x) => ({ ok: false, message: x.message }));
      if (r.ok) { await openRoot(st.rootDir); await openFile(path); } else say(r.message || 'Could not create the file.');
    });
  }

  // ---------- terminal / run / test
  const logLine = (cls, text) => { termOut.append(h('div', { class: cls }, text)); termOut.scrollTop = termOut.scrollHeight; };
  async function exec(command) {
    logLine('cmd', '$ ' + command);
    const r = await ctx.act('/api/terminal/run', { method: 'POST', body: { command } }).catch((e) => ({ ok: false, message: e.message }));
    const d = r.result || (r.confirmed && r.data && 'returncode' in r.data ? r.data : null);   // approved commands come back via the confirm step
    if (d) {
      if (d.stdout) logLine('out', d.stdout.trimEnd()); if (d.stderr) logLine('err', d.stderr.trimEnd());
      logLine(d.ok ? 'ok' : 'bad', d.message + (d.returncode != null ? ` (exit ${d.returncode})` : ''));
      st.lastOut = `$ ${command}\n${d.stdout || ''}${d.stderr || ''}\n${d.message}`; clear(output).append(h('pre', {}, st.lastOut));
      if (!d.ok) await analyse((d.stderr || d.stdout || d.message)); else clear(problems).append(h('p', { class: 'muted' }, 'No problems: the last command succeeded.'));
      return d;
    }
    logLine(r.declined ? 'bad' : 'err', r.declined ? 'Cancelled.' : r.message || 'That did not run.');
  }
  termIn.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && termIn.value.trim()) { const c = termIn.value.trim(); st.hist.push(c); st.hi = st.hist.length; termIn.value = ''; if (c === 'clear') clear(termOut); else exec(c); }
    if (e.key === 'ArrowUp' && st.hi > 0) termIn.value = st.hist[--st.hi]; if (e.key === 'ArrowDown') termIn.value = st.hist[++st.hi] || '';
  });
  function runFile() {
    const t = cur(); if (!t) return say('Open a file to run.');
    const ext = t.path.split('.').pop().toLowerCase();
    if (t.dirty) say('Tip: save first — Run uses the file on disk.');
    if (ext === 'html') return ctx.act('/api/files/open', { method: 'POST', body: { path: t.path } }).then((r) => say(r.message || r.result?.message || 'Opened.')).catch((e) => say(e.message));
    if (!RUN[ext]) return say(`No run command is known for .${ext} files. Use the terminal.`);
    showPanel('TERMINAL'); exec(RUN[ext](t.path));
  }
  async function runTests() {
    if (!st.rootDir) return say('Choose a project folder first.');
    const r = await ctx.act('/api/project/commands?path=' + encodeURIComponent(st.rootDir)).catch((e) => ({ message: e.message }));
    const cmd = r.result?.test?.[0]; showPanel('TERMINAL');
    if (!cmd) return logLine('bad', 'No test command detected in this folder (looked for tests/, test_*.py and an npm "test" script).');
    exec(cmd.command);
  }
  async function inspectProject() {
    if (!st.rootDir) return say('Choose a project folder first.');
    const r = await ctx.act('/api/project/inspect?path=' + encodeURIComponent(st.rootDir)).catch((e) => ({ message: e.message }));
    showPanel('OUTPUT');
    if (!r.result) return clear(output).append(h('p', {}, r.message || 'Waiting for permission.'));
    const d = r.result; clear(output).append(h('pre', {}, `Project: ${d.root}\nFiles seen: ${d.files_seen}\nTypes: ${d.top_extensions.map((x) => x.join(' × ')).join(', ')}\nDetected: ${d.detected.join(', ') || 'nothing recognisable'}\n` + (d.npm_scripts ? `npm scripts: ${d.npm_scripts.join(', ')}\n` : '')));
  }
  async function analyse(text) {
    clear(problems);
    const r = await ctx.api('/api/error/explain', { method: 'POST', body: { text: text.slice(0, 6000) } }).catch(() => null);
    if (r?.matched) problems.append(h('div', { class: 'n-prob' }, h('b', {}, '⚠ ' + r.meaning), h('ol', {}, r.steps.map((s) => h('li', {}, s)))));
    else problems.append(h('p', {}, 'The last command failed, but this error is not in my built-in list. See OUTPUT for details.'));
    const locs = [...text.matchAll(/File "([^"]+)", line (\d+)/g)].map((m) => [m[1], +m[2]]).concat([...text.matchAll(/\(([^()\s]+):(\d+):\d+\)/g)].map((m) => [m[1], +m[2]]));
    locs.slice(-6).forEach(([f, ln]) => problems.append(h('button', { type: 'button', class: 'n-loc', onclick: async () => { await openFile(f); ta.focus(); const lines = ta.value.split('\n'); const pos = lines.slice(0, ln - 1).join('\n').length + 1; ta.setSelectionRange(pos, pos); ta.scrollTop = (ln - 5) * 18; updateStatus(); } }, `${f}:${ln}`)));
    const box = h('textarea', { class: 'n-paste', placeholder: 'Paste any error here to explain it…', 'aria-label': 'Paste an error message' });
    problems.append(box, btn('Explain', async () => { if (box.value.trim()) analyse(box.value); }));
    showPanel('PROBLEMS');
  }
  async function loadLogs() {
    const r = await ctx.api('/api/logs?lines=200').catch((e) => ({ lines: [e.message] }));
    clear(logs).append(btn('⟳ Refresh', loadLogs), h('pre', {}, r.lines.length ? r.lines.join('\n') : r.note || 'The log is empty.'));
  }
  clear(problems).append(h('p', { class: 'muted' }, 'Problems appear here when a run/test fails, or paste an error below.'),
    h('textarea', { class: 'n-paste', placeholder: 'Paste any error here to explain it…', 'aria-label': 'Paste an error message' }), btn('Explain', () => { const b = problems.querySelector('.n-paste'); if (b.value.trim()) analyse(b.value); }));
  clear(output).append(h('p', { class: 'muted' }, 'Output of the last run or test shows here.'));

  // ---------- start
  const places = (await ctx.act('/api/files/places').catch(() => ({}))).result;
  if (places) {
    const roots = [...(places.project ? [places.project] : []), ...places.approved, ...places.special.map((s) => s.path)];
    roots.forEach((p) => rootSel.append(h('option', { value: p }, p.split(/[\\/]/).slice(-2).join('/'))));
    await openRoot(roots[0]);
  }
}
