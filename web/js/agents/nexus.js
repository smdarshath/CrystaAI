// NEXUS — memory intelligence: searchable archive of notes, project notes and memories with categories and a timeline.
import { h, clear, backButton, debounce, fmtDate } from '../dom.js';

export function unmount() {}
const CATS = ['general', 'project', 'idea', 'study', 'personal'];

export async function mount(root, ctx) {
  const st = { notes: [], memories: [], enabled: false, cat: null, project: null, q: '', found: null };
  const grid = h('div', { class: 'x-masonry' }), side = h('div', { class: 'x-side' }), tl = h('div', { class: 'x-timeline' }), banner = h('div', { class: 'x-banner', hidden: true }), foot = h('footer', { class: 'x-foot' });
  const search = h('input', { type: 'search', class: 'x-search', placeholder: 'Search your saved notes, memories and local knowledge…', 'aria-label': 'Search memory' });
  const btn = (l, fn, c = '') => h('button', { type: 'button', class: 'x-btn ' + c, onclick: fn }, l);
  root.append(h('header', { class: 'x-head' }, backButton(ctx), h('div', { class: 'x-logo' }, '❖ NEXUS', h('small', {}, 'MEMORY INTELLIGENCE')), search, btn('＋ NEW NOTE', () => edit(null), 'gold')), banner,
    h('div', { class: 'x-body' }, side, h('main', { class: 'x-main' }, grid), h('aside', { class: 'x-tl' }, h('h4', {}, 'TIMELINE'), tl)), foot);

  async function load() {
    const [n, m] = await Promise.all([ctx.api('/api/notes'), ctx.api('/api/memory')]);
    st.notes = n.notes; st.enabled = n.enabled; st.memories = m.memories; st.messages = m.messages; draw();
  }
  function dialog(title, body, actions) {
    const d = h('div', { class: 'x-modal' }, h('div', { class: 'x-box', role: 'dialog', 'aria-label': title }, h('h3', {}, title), body, h('div', { class: 'row' }, ...actions(() => d.remove()))));
    root.append(d); return d;
  }
  function edit(note) {
    const t = h('input', { type: 'text', value: note?.title || '', placeholder: 'Title', 'aria-label': 'Title' }), b = h('textarea', { rows: 7, 'aria-label': 'Note text', placeholder: 'Write your note…' }, note?.body || '');
    const c = h('input', { type: 'text', value: note?.category || 'general', list: 'x-cats', 'aria-label': 'Category' }), p = h('input', { type: 'text', value: note?.project || '', placeholder: 'Project (optional)', 'aria-label': 'Project' });
    const err = h('div', { class: 'x-err' });
    dialog(note ? 'Edit note' : 'New note', h('div', { class: 'x-form' }, t, b, h('datalist', { id: 'x-cats' }, CATS.map((x) => h('option', { value: x }))), c, p, err), (close) => [
      btn('Save', async () => { if (!b.value.trim()) return (err.textContent = 'Write something first.');
        try { await ctx.api('/api/notes', { method: note ? 'PATCH' : 'POST', body: { ...(note ? { id: note.id } : {}), title: t.value || b.value.slice(0, 40), body: b.value, category: c.value || 'general', project: p.value || null } }); close(); load(); }
        catch (e) { err.textContent = e.message; } }, 'gold'), btn('Cancel', close)]);
  }
  const confirmBox = (title, text, okLabel, fn) => dialog(title, h('p', {}, text), (close) => [btn(okLabel, async () => { close(); await fn(); }, 'danger'), btn('Cancel', close)]);

  function draw() {
    banner.hidden = st.enabled;
    clear(banner).append('Memory is OFF — nothing new can be saved. ', btn('Turn on memory', async () => { const r = await ctx.act('/api/memory/enable', { method: 'POST', body: { enabled: true } }); if (r.ok) load(); }, 'gold'));
    banner.hidden = st.enabled;
    // sidebar: categories + projects
    const cats = {}, projs = {}; st.notes.forEach((n) => { cats[n.category] = (cats[n.category] || 0) + 1; if (n.project) projs[n.project] = (projs[n.project] || 0) + 1; });
    const chip = (label, n, on, fn) => h('button', { type: 'button', class: 'x-chip' + (on ? ' on' : ''), onclick: fn }, label, h('b', {}, n));
    clear(side).append(h('h4', {}, 'CATEGORIES'), chip('All', st.notes.length + st.memories.length, !st.cat && !st.project, () => { st.cat = st.project = null; draw(); }),
      ...Object.entries(cats).map(([k, n]) => chip(k, n, st.cat === k, () => { st.cat = k; st.project = null; draw(); })), chip('memories', st.memories.length, st.cat === '@memories', () => { st.cat = '@memories'; st.project = null; draw(); }),
      h('h4', {}, 'PROJECT NOTES'), ...(Object.keys(projs).length ? Object.entries(projs).map(([k, n]) => chip(k, n, st.project === k, () => { st.project = k; st.cat = null; draw(); })) : [h('p', { class: 'x-small' }, 'Give a note a project name to group it here.')]));
    // cards
    clear(grid);
    if (st.found) {
      grid.append(h('div', { class: 'x-found' }, `Search results for “${st.q}”: ${st.found.notes.length} note(s), ${st.found.memories.length} memory item(s), ${st.found.knowledge.length} local knowledge match(es)`));
      st.found.notes.forEach((n) => grid.append(noteCard(n))); st.found.memories.forEach((m) => grid.append(memCard(m)));
      st.found.knowledge.forEach((k) => grid.append(h('article', { class: 'x-card know' }, h('span', { class: 'x-tag' }, 'LOCAL KNOWLEDGE · ' + k.source), h('p', {}, k.text.slice(0, 380)))));
    } else {
      let notes = st.notes.filter((n) => (!st.cat || n.category === st.cat) && (!st.project || n.project === st.project));
      let mems = st.cat && st.cat !== '@memories' || st.project ? [] : st.memories;
      if (st.cat === '@memories') notes = [];
      notes.forEach((n) => grid.append(noteCard(n))); mems.forEach((m) => grid.append(memCard(m)));
      if (!notes.length && !mems.length) grid.append(h('div', { class: 'x-empty' }, st.enabled ? 'Nothing saved here yet. Create a note, or say “remember that …” to CRYSTA.' : 'Memory is off, so the archive is empty. Turn it on to start saving.'));
    }
    // timeline
    const items = [...st.notes.map((n) => ({ t: n.created, label: n.title || n.body.slice(0, 40), kind: 'note', cat: n.category })), ...st.memories.map((m) => ({ t: m.created, label: m.value.slice(0, 40), kind: 'memory' }))].sort((a, b) => b.t - a.t);
    clear(tl); let day = '';
    items.slice(0, 60).forEach((i) => { const d = new Date(i.t * 1000).toDateString(); if (d !== day) { day = d; tl.append(h('div', { class: 'x-day' }, d)); } tl.append(h('div', { class: 'x-ev ' + i.kind }, h('i', {}), h('span', {}, i.label), h('small', {}, new Date(i.t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })))); });
    if (!items.length) tl.append(h('p', { class: 'x-small' }, 'Your timeline will appear here.'));
    // management footer
    clear(foot).append(h('span', {}, `Stored on this computer: ${st.notes.length} notes · ${st.memories.length} memories · ${st.messages ?? 0} chat messages`), h('div', { class: 'grow' }),
      h('a', { class: 'x-btn', href: '/api/memory/export', download: 'crysta-export.json' }, 'EXPORT'),
      st.enabled ? btn('TURN OFF MEMORY', async () => { await ctx.api('/api/settings', { method: 'PATCH', body: { memory_enabled: false } }); ctx.refreshSettings(); load(); }) : null,
      btn('DELETE EVERYTHING', () => confirmBox('Delete everything?', 'This permanently deletes all notes, memories and saved chat history stored by CRYSTA on this computer.', 'Delete all', async () => { await ctx.api('/api/memory', { method: 'DELETE', body: { scope: 'all' } }); load(); }), 'danger'));
  }
  const noteCard = (n) => h('article', { class: 'x-card' }, h('div', { class: 'x-ctop' }, h('span', { class: 'x-tag' }, n.category), n.project ? h('span', { class: 'x-tag proj' }, n.project) : null),
    h('h5', {}, n.title), h('p', {}, n.body), h('div', { class: 'x-cfoot' }, h('small', {}, fmtDate(n.created)), h('span', {}, btn('✎', () => edit(n)), btn('🗑', () => confirmBox('Delete this note?', n.title || n.body.slice(0, 50), 'Delete', async () => { await ctx.api('/api/notes', { method: 'DELETE', body: { id: n.id } }); load(); }), 'danger'))));
  const memCard = (m) => h('article', { class: 'x-card mem' }, h('span', { class: 'x-tag' }, 'memory'), h('p', {}, m.value), h('div', { class: 'x-cfoot' }, h('small', {}, fmtDate(m.created)),
    btn('🗑', async () => { await ctx.api('/api/memory', { method: 'DELETE', body: { id: m.id } }); load(); }, 'danger')));

  search.addEventListener('input', debounce(async () => {
    st.q = search.value.trim();
    if (!st.q) { st.found = null; return draw(); }
    try { st.found = await ctx.api('/api/memory/search?q=' + encodeURIComponent(st.q)); } catch { st.found = null; }
    draw();
  }, 250));
  await load(); search.focus();
}
