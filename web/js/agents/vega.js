// VEGA — desktop-style file manager: folder tree, file list, preview, info and file operations.
import { h, fmtBytes, fmtDate, clear, backButton } from '../dom.js';

const IMG = /\.(png|jpe?g|gif|webp)$/i;
const sep = (p) => (p.includes('\\') && !p.includes('/') ? '\\' : '/');
const join = (a, b) => a.replace(/[\\/]+$/, '') + sep(a) + b;

export function unmount() {}

export async function mount(root, ctx) {
  const st = { path: null, items: [], sel: null, clip: null, view: 'list', query: '' };
  const crumbs = h('div', { class: 'f-crumbs' });
  const list = h('div', { class: 'f-list', role: 'listbox', 'aria-label': 'Files' });
  const tree = h('div', { class: 'f-tree', role: 'tree', 'aria-label': 'Folders' });
  const preview = h('div', { class: 'f-preview' });
  const info = h('div', { class: 'f-info' });
  const status = h('div', { class: 'f-status' });
  const search = h('input', { type: 'text', placeholder: 'Find in this folder…', 'aria-label': 'Search files', class: 'f-search' });
  const msg = (t) => { status.textContent = t; };
  const btn = (label, fn, cls = '') => h('button', { type: 'button', class: 'f-btn ' + cls, onclick: fn }, label);
  const selected = () => st.items.find((i) => i.path === st.sel);

  // ---- inline dialog (window.prompt is not reliable in desktop webviews)
  function ask(title, value = '') {
    return new Promise((resolve) => {
      const input = h('input', { type: 'text', value, 'aria-label': title });
      const done = (v) => { dlg.remove(); resolve(v); };
      const dlg = h('div', { class: 'f-dialog' }, h('div', { class: 'f-dbox', role: 'dialog', 'aria-label': title }, h('b', {}, title), input,
        h('div', { class: 'row' }, btn('OK', () => done(input.value.trim() || null), 'primary'), btn('Cancel', () => done(null)))));
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') done(input.value.trim() || null); if (e.key === 'Escape') { e.stopPropagation(); done(null); } });
      root.append(dlg); input.focus(); input.select();
    });
  }

  async function run(label, path, opts) {
    try {
      const r = await ctx.act(path, opts);
      if (r.declined) msg('Cancelled.');
      else if (!r.ok) msg(r.message || 'That did not work.');
      else { msg(r.message || r.result?.message || `${label} done.`); await load(st.path); }
      return r;
    } catch (e) { msg(e.message); }
  }

  // ---- loading
  async function load(path) {
    try {
      const r = await ctx.act('/api/files/list?path=' + encodeURIComponent(path));
      if (!r.result) { msg(r.message || 'Waiting for permission.'); return; }
      st.path = r.result.path; st.items = r.result.items.map((i) => ({ ...i, path: join(r.result.path, i.name) })); st.parent = r.result.parent; st.query = '';
      search.value = ''; st.sel = null;
      draw(); showSel();
    } catch (e) { msg(e.message); }
  }

  function draw() {
    const parts = st.path.split(/[\\/]/).filter(Boolean);
    let acc = st.path.startsWith('/') ? '' : '';
    clear(crumbs).append(...parts.map((p, i) => { acc = (st.path.startsWith('/') ? '/' : '') + parts.slice(0, i + 1).join(sep(st.path)); const target = acc; return h('button', { type: 'button', class: 'crumb', onclick: () => load(target) }, p); }));
    const q = st.query.toLowerCase();
    const rows = st.items.filter((i) => !q || i.name.toLowerCase().includes(q));
    clear(list).className = 'f-list ' + st.view;
    if (st.view === 'list') list.append(h('div', { class: 'f-row head' }, h('span', {}, 'Name'), h('span', {}, 'Size'), h('span', {}, 'Modified')));
    for (const it of rows) {
      list.append(h('div', { class: 'f-row' + (it.path === st.sel ? ' sel' : ''), role: 'option', tabindex: '0', 'aria-selected': String(it.path === st.sel),
        onclick: () => { st.sel = it.path; draw(); showSel(); }, ondblclick: () => openItem(it),
        onkeydown: (e) => { if (e.key === 'Enter') openItem(it); } },
        h('span', { class: 'nm' }, h('i', { class: 'ico ' + (it.type === 'folder' ? 'folder' : IMG.test(it.name) ? 'img' : 'file') }), it.name),
        h('span', {}, it.type === 'folder' ? '—' : fmtBytes(it.size)), h('span', {}, fmtDate(it.modified))));
    }
    if (!rows.length) list.append(h('div', { class: 'f-empty' }, q ? 'No matching items here.' : 'This folder is empty.'));
    msg(`${rows.length} item(s)` + (st.sel ? ` · selected: ${st.sel.split(/[\\/]/).pop()}` : '') + (st.clip ? ` · clipboard: ${st.clip.op} ${st.clip.path.split(/[\\/]/).pop()}` : ''));
    up.disabled = !st.parent; paste.disabled = !st.clip;
  }

  function openItem(it) { if (it.type === 'folder') load(it.path); else showSel(); }

  async function showSel() {
    clear(preview); clear(info);
    const it = selected();
    if (!it) { preview.append(h('div', { class: 'f-empty' }, 'Select a file or folder to preview it.')); return; }
    try {
      const i = await ctx.act('/api/files/info?path=' + encodeURIComponent(it.path));
      if (i.result) {
        const d = i.result;
        info.append(h('table', {}, ...[['Name', d.name], ['Type', d.type === 'folder' ? `folder (${d.items ?? '?'} items)` : d.mime || 'file'], ['Size', d.size != null ? fmtBytes(d.size) : '—'],
          ['Modified', fmtDate(d.modified)], ['Permissions', d.permissions], ['Readable', d.readable ? 'yes' : 'no'], ['Writable', d.writable ? 'yes' : 'no'], ['Path', d.path]].map(([k, v]) => h('tr', {}, h('th', {}, k), h('td', {}, String(v))))));
      }
    } catch (e) { info.append(h('div', { class: 'f-empty' }, e.message)); }
    if (it.type === 'folder') { preview.append(h('div', { class: 'f-empty' }, 'Folder — double-click to open.')); return; }
    if (IMG.test(it.name)) { preview.append(h('img', { src: '/api/files/image?path=' + encodeURIComponent(it.path), alt: `Preview of ${it.name}` })); return; }
    try {
      const r = await ctx.act('/api/files/read?path=' + encodeURIComponent(it.path));
      if (r.result) preview.append(h('pre', {}, r.result.text.slice(0, 6000) + (r.result.text.length > 6000 ? '\n… (truncated)' : '')));
      else preview.append(h('div', { class: 'f-empty' }, r.message || 'Waiting for permission.'));
    } catch (e) { preview.append(h('div', { class: 'f-empty' }, 'No preview: ' + e.message)); }
  }

  // ---- toolbar actions
  const up = btn('▲ Up', () => st.parent && load(st.parent));
  const paste = btn('Paste', async () => {
    if (!st.clip) return;
    const op = st.clip.op === 'cut' ? 'move' : 'copy';
    const r = await run(op, `/api/files/${op}`, { method: 'POST', body: { src: st.clip.path, dst: st.path } });
    if (r?.ok && op === 'move') st.clip = null;
  });
  const need = () => { const it = selected(); if (!it) msg('Select something first.'); return it; };

  const toolbar = h('div', { class: 'f-toolbar' }, backButton(ctx), h('div', { class: 'f-logo' }, h('b', {}, 'VEGA'), h('small', {}, 'Computer Intelligence')),
    btn('◀', () => history.length && load(st.path), 'icon'), up, btn('⟳', () => load(st.path), 'icon'), crumbs, search,
    btn(st.view === 'list' ? '▦ Grid' : '☰ List', (e) => { st.view = st.view === 'list' ? 'grid' : 'list'; e.target.textContent = st.view === 'list' ? '▦ Grid' : '☰ List'; draw(); }),
    btn('🔒 Permissions', () => ctx.open('computer')));
  const ops = h('div', { class: 'f-ops' },
    btn('＋ Folder', async () => { const n = await ask('New folder name'); if (n) run('Create folder', '/api/files/mkdir', { method: 'POST', body: { path: join(st.path, n) } }); }),
    btn('＋ File', async () => { const n = await ask('New file name'); if (n) run('Create file', '/api/files/write', { method: 'POST', body: { path: join(st.path, n), content: '' } }); }),
    btn('Open', () => { const it = need(); if (!it) return; if (it.type === 'folder') load(it.path); else run('Open', '/api/files/open', { method: 'POST', body: { path: it.path } }); }, 'primary'),
    btn('Rename', async () => { const it = need(); if (!it) return; const n = await ask('Rename to', it.name); if (n) run('Rename', '/api/files/rename', { method: 'POST', body: { path: it.path, new_name: n } }); }),
    btn('Copy', () => { const it = need(); if (it) { st.clip = { op: 'copy', path: it.path }; draw(); } }),
    btn('Cut', () => { const it = need(); if (it) { st.clip = { op: 'cut', path: it.path }; draw(); } }), paste,
    btn('Delete', () => { const it = need(); if (it) run('Delete', '/api/files/delete', { method: 'POST', body: { path: it.path } }); }, 'danger'));
  search.addEventListener('input', () => { st.query = search.value; draw(); });
  search.addEventListener('keydown', async (e) => {
    if (e.key !== 'Enter' || !search.value.trim()) return;
    const r = await ctx.act(`/api/files/find?name=${encodeURIComponent(search.value.trim())}&root=${encodeURIComponent(st.path)}`).catch((x) => ({ message: x.message }));
    if (!r.result) return msg(r.message);
    st.items = r.result.matches.map((p) => ({ name: p.slice(st.path.length + 1) || p, path: p, type: 'file', size: null, modified: null })); st.query = ''; st.sel = null; draw();
    msg(`${r.result.matches.length} match(es) under this folder` + (r.result.complete ? '' : ' (search stopped early)'));
  });

  root.append(toolbar, ops, h('div', { class: 'f-body' },
    h('aside', { class: 'f-side' }, h('div', { class: 'f-title' }, 'PLACES'), tree), h('main', { class: 'f-main' }, list),
    h('aside', { class: 'f-right' }, h('div', { class: 'f-title' }, 'PREVIEW'), preview, h('div', { class: 'f-title' }, 'INFORMATION'), info)), status);

  // ---- folder tree (lazy)
  function node(label, path, depth = 0) {
    const kids = h('div', { class: 'kids', hidden: true });
    let loaded = false;
    const caret = h('span', { class: 'caret' }, '▸');
    const row = h('div', { class: 'f-node', style: `padding-left:${6 + depth * 12}px`, role: 'treeitem', tabindex: '0',
      onclick: async () => { load(path); if (!loaded) { loaded = true; try { const r = await ctx.act('/api/files/list?path=' + encodeURIComponent(path)); (r.result?.items || []).filter((i) => i.type === 'folder' && !i.name.startsWith('.')).slice(0, 60).forEach((i) => kids.append(node(i.name, join(path, i.name), depth + 1))); } catch { /* ignore */ } }
        kids.hidden = !kids.hidden; caret.textContent = kids.hidden ? '▸' : '▾'; } }, caret, label);
    return h('div', {}, row, kids);
  }
  let places;
  try { places = (await ctx.act('/api/files/places')).result; } catch (e) { msg(e.message); }
  if (places) {
    for (const s of places.special) tree.append(node('📁 ' + s.name, s.path));
    if (places.project) tree.append(node('🛠 ' + places.project.split(/[\\/]/).pop(), places.project));
    for (const a of places.approved) tree.append(node('🗂 ' + (a.split(/[\\/]/).pop() || a), a));
    await load(places.project || places.approved[0]);
  }
}
