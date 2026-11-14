// ORION — planning intelligence: project workspace with kanban, milestones, roadmap, timeline and progress.
import { h, svg, clear, backButton } from '../dom.js';

export function unmount() {}
const COLS = [['pending', 'TO DO'], ['doing', 'IN PROGRESS'], ['done', 'DONE']];
const DAY = 86400;

export async function mount(root, ctx) {
  const st = { project: localStorage.getItem('orion_project') || 'General', tasks: [], projects: [] };
  const sel = h('select', { class: 'o-sel', 'aria-label': 'Project', onchange: () => { st.project = sel.value; localStorage.setItem('orion_project', st.project); load(); } });
  const ring = h('div', { class: 'o-ring' }), roadmap = h('div', { class: 'o-road' }), board = h('div', { class: 'o-board' }), gantt = h('div', { class: 'o-gantt' }), side = h('aside', { class: 'o-side' });
  const title = h('input', { type: 'text', placeholder: 'Add a task or milestone…', 'aria-label': 'New task title', class: 'o-in' }), due = h('input', { type: 'date', 'aria-label': 'Due date', class: 'o-in o-date' });
  const kind = h('select', { 'aria-label': 'Type', class: 'o-in o-kind' }, h('option', { value: 'task' }, 'Task'), h('option', { value: 'milestone' }, 'Milestone'));
  const msg = h('span', { class: 'o-msg' });
  const btn = (l, fn, c = '', label) => h('button', { type: 'button', class: 'o-btn ' + c, 'aria-label': label || l, onclick: fn }, l);

  async function add() {
    if (!title.value.trim()) return (msg.textContent = 'Give it a title first.');
    try { await ctx.api('/api/tasks', { method: 'POST', body: { title: title.value.trim(), due: due.value ? new Date(due.value + 'T17:00:00').getTime() / 1000 : null, project: st.project, kind: kind.value } }); title.value = ''; due.value = ''; msg.textContent = ''; load(); }
    catch (e) { msg.textContent = e.message; }
  }
  title.addEventListener('keydown', (e) => e.key === 'Enter' && add());
  async function newProject() {
    const name = (await askName()); if (!name) return;
    st.project = name; localStorage.setItem('orion_project', name); await ctx.api('/api/tasks', { method: 'POST', body: { title: 'Project kickoff', project: name, kind: 'milestone', due: Date.now() / 1000 + 7 * DAY } }); load();
  }
  function askName() {
    return new Promise((res) => { const i = h('input', { type: 'text', class: 'o-in', 'aria-label': 'Project name', placeholder: 'Project name' }); const done = (v) => { d.remove(); res(v); };
      const d = h('div', { class: 'o-modal' }, h('div', { class: 'o-box', role: 'dialog', 'aria-label': 'New project' }, h('b', {}, 'NEW PROJECT'), i, h('div', { class: 'row' }, btn('Create', () => done(i.value.trim() || null), 'primary'), btn('Cancel', () => done(null)))));
      i.addEventListener('keydown', (e) => { if (e.key === 'Enter') done(i.value.trim() || null); if (e.key === 'Escape') { e.stopPropagation(); done(null); } }); root.append(d); i.focus(); });
  }
  const patch = (id, body) => ctx.api('/api/tasks', { method: 'PATCH', body: { id, ...body } }).then(load);

  async function load() {
    const r = await ctx.api('/api/tasks?project=' + encodeURIComponent(st.project)), all = await ctx.api('/api/tasks');
    st.tasks = r.tasks; st.projects = all.projects.some((p) => p.name === st.project) ? all.projects : [...all.projects, { name: st.project, total: 0, done: 0 }];
    clear(sel).append(...st.projects.map((p) => h('option', { value: p.name, selected: p.name === st.project }, `${p.name} (${p.done}/${p.total})`))); draw(all);
  }

  function draw(all) {
    const T = st.tasks, done = T.filter((t) => t.status === 'done').length, pct = T.length ? Math.round((done / T.length) * 100) : 0, now = Date.now() / 1000;
    // progress ring
    clear(ring).append(svg('svg', { viewBox: '0 0 90 90', width: 90, height: 90, role: 'img', 'aria-label': `${pct} percent complete` }, svg('circle', { cx: 45, cy: 45, r: 38, class: 'rg-t' }),
      svg('circle', { cx: 45, cy: 45, r: 38, class: 'rg-v', 'stroke-dasharray': `${(pct / 100) * 238.76} 999`, transform: 'rotate(-90 45 45)' }), svg('text', { x: 45, y: 51, class: 'rg-x' }, pct + '%')), h('div', {}, h('b', {}, st.project), h('div', { class: 'o-small' }, `${done} of ${T.length} done`)));
    // roadmap = milestones
    const ms = T.filter((t) => t.kind === 'milestone').sort((a, b) => (a.due ?? 1e12) - (b.due ?? 1e12));
    clear(roadmap).append(h('h4', {}, 'ROADMAP'), h('div', { class: 'o-chev' }, ...(ms.length ? ms.map((m) => h('div', { class: 'o-ms ' + (m.status === 'done' ? 'done' : m.due && m.due < now ? 'late' : '') }, h('b', {}, m.title), h('small', {}, m.due ? new Date(m.due * 1000).toLocaleDateString() : 'no date'),
      h('span', {}, btn(m.status === 'done' ? '↺' : '✓', () => patch(m.id, { status: m.status === 'done' ? 'pending' : 'done' }), '', m.status === 'done' ? 'Reopen milestone' : 'Complete milestone')))) :
      [h('p', { class: 'o-small' }, 'No milestones yet — add one above, or generate a starter plan.'), btn('Generate starter plan', async () => { await ctx.api('/api/orion/starter-plan', { method: 'POST', body: { project: st.project } }); load(); }, 'primary')])));
    // kanban
    clear(board);
    COLS.forEach(([key, label]) => {
      const col = h('section', { class: 'o-col', 'data-status': key, 'aria-label': label }, h('h4', {}, label, h('b', {}, T.filter((t) => t.status === key).length)));
      col.addEventListener('dragover', (e) => { e.preventDefault(); col.classList.add('over'); }); col.addEventListener('dragleave', () => col.classList.remove('over'));
      col.addEventListener('drop', (e) => { e.preventDefault(); col.classList.remove('over'); const id = +e.dataTransfer.getData('text/plain'); if (id) patch(id, { status: key }); });
      T.filter((t) => t.status === key).forEach((t) => col.append(card(t, key, now)));
      board.append(col);
    });
    // timeline
    const dated = T.filter((t) => t.due), un = T.filter((t) => !t.due);
    clear(gantt).append(h('h4', {}, 'TIMELINE'));
    if (dated.length) {
      const lo = Math.min(now - 3 * DAY, ...dated.map((t) => t.created)), hi = Math.max(now + 7 * DAY, ...dated.map((t) => t.due)), span = hi - lo, X = (t) => ((t - lo) / span) * 100;
      const track = h('div', { class: 'o-track' }, h('i', { class: 'o-today', style: `left:${X(now)}%`, title: 'Today' }));
      dated.sort((a, b) => a.due - b.due).forEach((t) => track.append(h('div', { class: 'o-bar ' + t.status + (t.kind === 'milestone' ? ' ms' : '') + (t.due < now && t.status !== 'done' ? ' late' : ''), style: `left:${X(Math.min(t.created, t.due))}%;width:${Math.max(1.5, X(t.due) - X(Math.min(t.created, t.due)))}%`, title: `${t.title} — due ${new Date(t.due * 1000).toLocaleDateString()}` }, h('span', {}, t.title))));
      gantt.append(track, h('div', { class: 'o-axis' }, h('span', {}, new Date(lo * 1000).toLocaleDateString()), h('span', {}, 'today ▲'), h('span', {}, new Date(hi * 1000).toLocaleDateString())));
    } else gantt.append(h('p', { class: 'o-small' }, 'Give tasks a due date to see them on the timeline.'));
    if (un.length) gantt.append(h('p', { class: 'o-small' }, `${un.length} task(s) have no date.`));
    // side: all projects progress
    clear(side).append(h('h4', {}, 'ALL PROJECTS'), ...all.projects.map((p) => { const pc = p.total ? Math.round((p.done / p.total) * 100) : 0; return h('button', { type: 'button', class: 'o-proj' + (p.name === st.project ? ' on' : ''), onclick: () => { st.project = p.name; localStorage.setItem('orion_project', p.name); load(); } }, h('span', {}, p.name), h('div', { class: 'o-pbar' }, h('i', { style: `width:${pc}%` })), h('small', {}, `${pc}% · ${p.done}/${p.total}`)); }),
      h('h4', {}, 'UPCOMING'), ...T.filter((t) => t.due && t.status !== 'done').sort((a, b) => a.due - b.due).slice(0, 5).map((t) => h('div', { class: 'o-up ' + (t.due < now ? 'late' : '') }, t.title, h('small', {}, new Date(t.due * 1000).toLocaleDateString()))));
  }

  function card(t, key, now) {
    const c = h('article', { class: 'o-card ' + (t.kind === 'milestone' ? 'ms ' : '') + (t.due && t.due < now && key !== 'done' ? 'late' : ''), draggable: 'true', tabindex: '0' },
      h('div', { class: 'o-ct' }, t.kind === 'milestone' ? '◆ ' : '', h('span', { class: 'ttl' }, t.title)), t.due ? h('small', {}, '📅 ' + new Date(t.due * 1000).toLocaleDateString()) : null,
      h('div', { class: 'o-acts' }, key !== 'pending' ? btn('◀', () => patch(t.id, { status: key === 'done' ? 'doing' : 'pending' }), '', 'Move left') : null, key !== 'done' ? btn('▶', () => patch(t.id, { status: key === 'pending' ? 'doing' : 'done' }), '', 'Move right') : null,
        btn('✎', () => { const s = c.querySelector('.ttl'); const i = h('input', { type: 'text', value: t.title, class: 'o-in', 'aria-label': 'Rename' }); s.replaceWith(i); i.focus(); const save = () => i.value.trim() && i.value !== t.title ? patch(t.id, { title: i.value.trim() }) : load(); i.addEventListener('blur', save); i.addEventListener('keydown', (e) => e.key === 'Enter' && i.blur()); }, '', 'Rename'),
        btn('🗑', async () => { await ctx.api('/api/tasks', { method: 'DELETE', body: { id: t.id } }); load(); }, 'danger', 'Delete')));
    c.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/plain', String(t.id)); c.classList.add('drag'); }); c.addEventListener('dragend', () => c.classList.remove('drag'));
    return c;
  }

  root.append(h('header', { class: 'o-head' }, backButton(ctx), h('div', { class: 'o-logo' }, '◈ ORION', h('small', {}, 'PLANNING INTELLIGENCE')), sel, btn('＋ Project', newProject, 'primary'), ring),
    h('div', { class: 'o-add' }, title, kind, due, btn('ADD', add, 'primary'), msg),
    h('div', { class: 'o-body' }, h('main', { class: 'o-main' }, roadmap, board, gantt), side));
  await load();
}
