// ZYKRON — research command centre: search, result cards, source verification, YouTube workspace, history.
import { h, rich, clear, backButton } from '../dom.js';

let timer = null;
export function unmount() { clearInterval(timer); }
const TIER_CLASS = { official: 'official', organisation: 'org', other: 'other', 'community / social': 'comm', 'encyclopedia (background)': 'wiki' };

export async function mount(root, ctx) {
  const st = { mode: 'web', busy: false, sessions: [], current: null };
  const q = h('input', { type: 'text', placeholder: 'Research anything — try “student competitions 2026”', 'aria-label': 'Research query', maxlength: '300' });
  const deep = h('input', { type: 'checkbox', id: 'z-deep' }), verify = h('input', { type: 'checkbox', id: 'z-verify' });
  const net = h('span', { class: 'z-net' }, 'NET …');
  const answer = h('div', { class: 'z-answer' }), cards = h('div', { class: 'z-cards' }), verifyPane = h('div', { class: 'z-vpane' }), histEl = h('div', { class: 'z-hist' });
  const banner = h('div', { class: 'z-banner', hidden: true });
  const tabs = ['web', 'youtube', 'video'].map((m) => h('button', { type: 'button', class: 'z-tab', 'data-mode': m, onclick: () => setMode(m) }, { web: 'WEB', youtube: 'YOUTUBE', video: 'VIDEO LINK' }[m]));
  const go = h('button', { type: 'button', class: 'z-go', onclick: () => search() }, 'SEARCH');

  function setMode(m) {
    st.mode = m; tabs.forEach((t) => t.classList.toggle('on', t.dataset.mode === m));
    q.placeholder = { web: 'Research anything — try “student competitions 2026”', youtube: 'Find YouTube videos about…', video: 'Paste a YouTube link to read its captions' }[m];
    go.textContent = m === 'web' ? 'SEARCH' : m === 'youtube' ? 'FIND VIDEOS' : 'ANALYZE';
    verify.parentElement.hidden = m !== 'youtube';
  }

  root.append(
    h('header', { class: 'z-head' }, backButton(ctx), h('div', { class: 'z-logo' }, h('span', { class: 'z-radar' }), 'ZYKRON', h('small', {}, 'RESEARCH INTELLIGENCE')), h('div', { class: 'grow' }), net),
    banner,
    h('div', { class: 'z-body' },
      h('aside', { class: 'z-left' }, h('div', { class: 'z-tabs' }, tabs), h('div', { class: 'z-form' }, q, go),
        h('label', { class: 'z-opt' }, deep, ' Deeper (reads more pages)'), h('label', { class: 'z-opt' }, verify, ' Compare video with web sources'),
        h('p', { class: 'z-note' }, 'Official sources (.gov, .edu, organisations) are ranked first. Wikipedia is only labelled background. Nothing is invented: unreadable pages are reported.'),
        h('h4', {}, 'RESEARCH HISTORY'), histEl),
      h('main', { class: 'z-main' }, answer, cards),
      h('aside', { class: 'z-right' }, h('h4', {}, 'SOURCE VERIFICATION'), verifyPane)));
  setMode('web');
  q.addEventListener('keydown', (e) => { if (e.key === 'Enter') search(); });

  async function checkNet() {
    try { const s = await ctx.api('/api/status'); net.textContent = s.internet ? 'NET ● ONLINE' : s.internet_enabled ? 'NET ○ OFFLINE' : 'NET ○ DISABLED'; net.className = 'z-net ' + (s.internet ? 'on' : 'off');
      banner.hidden = s.internet; banner.textContent = s.internet_enabled ? 'No internet connection — live research and YouTube need one. Everything else in CRYSTA keeps working offline.' : 'Internet access is switched off in Settings.'; }
    catch { net.textContent = 'BACKEND DOWN'; }
  }
  await checkNet(); timer = setInterval(checkNet, 15000);

  async function search(arg) {
    const text = (arg?.text ?? q.value).trim(); if (!text || st.busy) return;
    const mode = arg?.mode ?? st.mode;
    st.busy = true; root.classList.add('busy'); go.disabled = true;
    clear(answer).append(h('div', { class: 'z-wait' }, 'Searching real sources and reading pages… this can take 10–30 seconds.'));
    clear(cards);
    try {
      const body = mode === 'video' ? { mode, url: text } : { mode, query: text, deep: deep.checked, verify: arg?.verify ?? (mode === 'youtube' && verify.checked) };
      const r = await ctx.api('/api/research', { method: 'POST', body });
      st.sessions.unshift({ text, mode, r, at: new Date() }); st.sessions = st.sessions.slice(0, 30);
      show(r, mode); drawHist();
    } catch (e) { clear(answer).append(h('div', { class: 'z-err' }, e.message)); }
    st.busy = false; root.classList.remove('busy'); go.disabled = false;
  }

  function show(r, mode) {
    const res = r.results[0], d = res.data || {};
    st.current = res;
    clear(answer).append(h('div', { class: 'z-status ' + res.status }, res.status.toUpperCase()), h('div', { class: 'z-text' }, rich(res.summary)));
    if (res.limitations?.length) answer.append(h('details', {}, h('summary', {}, `Limitations (${res.limitations.length})`), h('ul', {}, res.limitations.map((l) => h('li', {}, l)))));
    clear(cards);
    if (d.cards) d.cards.forEach((c) => cards.append(webCard(c)));
    if (d.videos) d.videos.forEach((v) => cards.append(videoCard(v)));
    if (d.points) cards.append(h('div', { class: 'z-card' }, h('h5', {}, 'CAPTION HIGHLIGHTS'), ...d.points.map((p) => h('p', {}, h('b', {}, `[${Math.floor(p.t / 60)}:${String(p.t % 60).padStart(2, '0')}] `), p.text))));
    verifyOverview(res);
  }

  function webCard(c) {
    return h('article', { class: 'z-card tier-' + (TIER_CLASS[c.tier] || 'other') },
      h('div', { class: 'z-ctop' }, h('span', { class: 'z-n' }, c.n), h('span', { class: 'z-tier' }, c.tier.toUpperCase()), h('span', { class: 'z-acc' }, c.access === 'read' ? 'READ' : 'SNIPPET ONLY')),
      h('h5', {}, h('a', { href: c.url }, c.title || c.url)), h('div', { class: 'z-host' }, c.host), h('p', {}, c.snippet),
      c.fresh != null && c.access === 'read' ? h('div', { class: 'z-fresh ' + (c.fresh ? 'ok' : 'old') }, c.fresh ? '✓ mentions the current year' : '⚠ no current-year date — may be outdated') : null,
      ...(c.deadlines || []).slice(0, 2).map((d) => h('div', { class: 'z-date' }, '📅 ' + d)),
      h('div', { class: 'row' }, ...(c.reg_links || []).map((l) => h('a', { class: 'z-reg', href: l.href }, '↗ ' + (l.text || 'Register').slice(0, 28))),
        h('button', { type: 'button', class: 'z-small', onclick: () => inspect(c) }, 'INSPECT')));
  }

  function videoCard(v) {
    return h('article', { class: 'z-card z-video' }, h('h5', {}, h('a', { href: v.url }, v.title)), h('div', { class: 'z-host' }, [v.channel, v.duration, v.views].filter(Boolean).join(' · ')),
      h('p', { class: 'muted' }, v.snippet || 'Search-result details only (title, channel, length). Not watched.'),
      h('div', { class: 'row' }, h('button', { type: 'button', class: 'z-small', onclick: () => { q.value = v.url; setMode('video'); search({ text: v.url, mode: 'video' }); } }, 'READ CAPTIONS'),
        h('a', { class: 'z-reg', href: v.url }, '▶ Open on YouTube')));
  }

  function verifyOverview(res) {
    clear(verifyPane);
    const cs = res.data?.cards || [];
    if (!cs.length) { verifyPane.append(h('p', { class: 'z-note' }, res.sources?.length ? `${res.sources.length} source(s) listed.` : 'No sources for this result.')); return; }
    const counts = {}; cs.forEach((c) => { counts[c.tier] = (counts[c.tier] || 0) + 1; });
    verifyPane.append(h('p', { class: 'z-note' }, `${cs.filter((c) => c.access === 'read').length} of ${cs.length} pages read in full.`),
      ...Object.entries(counts).map(([t, n]) => h('div', { class: 'z-meter' }, h('span', {}, t), h('div', { class: 'z-bar tier-' + (TIER_CLASS[t] || 'other') }, h('i', { style: `width:${(n / cs.length) * 100}%` })), h('b', {}, n))),
      h('p', { class: 'z-note' }, 'Click INSPECT on a card to see why it was ranked where it was.'));
  }
  function inspect(c) {
    clear(verifyPane).append(h('h5', {}, c.title), h('div', { class: 'z-host' }, c.url),
      h('table', {}, ...[['Source type', c.tier], ['Access', c.access === 'read' ? 'page read in full' : 'search snippet only'], ['Relevance to your question', `${Math.round(c.relevance * 100)}%`],
        ['Years mentioned', (c.years || []).join(', ') || 'none found'], ['Current-year mention', c.fresh == null ? 'n/a' : c.fresh ? 'yes' : 'no']].map(([k, v]) => h('tr', {}, h('th', {}, k), h('td', {}, v)))),
      c.deadlines?.length ? h('div', {}, h('b', {}, 'Dates found'), ...c.deadlines.map((d) => h('p', {}, d))) : h('p', { class: 'z-note' }, 'No deadline sentences found on this page.'),
      c.reg_links?.length ? h('div', {}, h('b', {}, 'Registration / apply links'), ...c.reg_links.map((l) => h('p', {}, h('a', { href: l.href }, l.text || l.href)))) : null,
      h('button', { type: 'button', class: 'z-small', onclick: () => verifyOverview(st.current) }, '◂ OVERVIEW'));
  }

  function drawHist() {
    clear(histEl);
    if (!st.sessions.length) histEl.append(h('p', { class: 'z-note' }, 'This session is empty. With Memory ON, research is saved here across sessions.'));
    st.sessions.forEach((s) => histEl.append(h('button', { type: 'button', class: 'z-h', onclick: () => { setMode(s.mode); q.value = s.text; show(s.r, s.mode); } },
      h('b', {}, s.mode.toUpperCase()), ' ', s.text.slice(0, 40), h('small', {}, s.r.results[0].status))));
    ctx.api('/api/research/history').then((r) => r.history.slice(0, 15).forEach((x) => histEl.append(h('button', { type: 'button', class: 'z-h saved', onclick: () => { q.value = x.query; setMode(x.kind === 'video' ? 'video' : x.kind); clear(answer).append(h('div', { class: 'z-text' }, rich(x.summary))); clear(cards); } },
      h('b', {}, '💾 ' + x.kind.toUpperCase()), ' ', x.query.slice(0, 36))))).catch(() => {});
  }
  const ex = ['student competitions 2026', 'scholarships for engineering students in India', 'ISRO student programs', 'international science olympiad registration'];
  clear(answer).append(h('div', { class: 'z-text' }, h('b', {}, 'Research command centre'), '\nAsk anything. For competitions and scholarships I rank official sources first, read the pages, pull out deadlines and registration links, and tell you when information may be out of date.\n\nTry:'),
    h('div', { class: 'row', style: 'margin-top:8px' }, ex.map((t) => h('button', { type: 'button', class: 'z-small', onclick: () => { q.value = t; search(); } }, t))));
  drawHist();
  q.focus();
}
