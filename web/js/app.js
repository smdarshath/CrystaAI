import { api } from './api.js';
import { createOrb } from './orb.js';
import * as speech from './speech.js';
import { h } from './dom.js';
import { TITLES, VIEWS, renderEntry } from './views.js';

const AGENT_VIEWS = ['zykron', 'nova', 'astra', 'vega', 'echo', 'nexus', 'orion', 'volt'];
const wsEl = document.getElementById('workspace');
let wsMod = null;

const $ = (id) => document.getElementById(id);
const orb = createOrb($('orb'));
const ctx = { history: [], chatLog: null, settings: {}, mode: 'idle', backendUp: true };
let abort = null, convId = 'c-' + Math.random().toString(36).slice(2, 10), pendingConfirm = null, welcomed = false;

// ---------- state / status
const LABEL = { idle: 'STANDBY', listening: 'LISTENING', processing: 'PROCESSING', speaking: 'SPEAKING', offline: 'BACKEND OFFLINE', error: 'ERROR' };
function setMode(m) {
  ctx.mode = m; orb.setState(m); $('state-label').textContent = LABEL[m] || 'STANDBY';
  const mic = $('mic'), listening = m === 'listening';
  mic.setAttribute('aria-pressed', String(listening));
  mic.setAttribute('aria-label', listening ? 'Stop listening' : 'Start voice input');
  $('ro-activity').textContent = { idle: 'IDLE', listening: 'LISTENING', processing: 'WORKING', speaking: 'SPEAKING', offline: 'OFFLINE', error: 'ERROR' }[m] || 'IDLE';
  setChip('chip-mic', listening ? 'MIC · LISTENING' : speech.canListen ? 'MIC · READY' : 'MIC · UNAVAILABLE', listening ? 'ok' : speech.canListen ? '' : 'warn');
}
ctx.speechApi = speech;
ctx.setMode = (m) => setMode(m === 'idle' && !ctx.backendUp ? 'offline' : m);
function setChip(id, text, cls = '') { const e = $(id); e.textContent = text; e.className = 'chip ' + cls; }
function caption(text, dim = false) { const c = $('caption'); c.textContent = text; c.classList.toggle('dim', dim); }
ctx.toast = (t) => caption(t);

async function refreshSettings() {
  try {
    const r = await api('/api/settings');
    ctx.settings = r.settings;
    document.body.classList.toggle('reduce-motion', !!r.settings.reduce_motion);
    orb.setReduced(!!r.settings.reduce_motion || matchMedia('(prefers-reduced-motion: reduce)').matches);
    $('ro-voice').textContent = !speech.canListen ? 'NO MIC API' : r.settings.speak_responses ? r.settings.voice_lang : 'TEXT ONLY';
  } catch { /* handled by status poll */ }
}
ctx.refreshSettings = refreshSettings;

async function pollStatus() {
  try {
    const s = await api('/api/status');
    ctx.backendUp = true;
    if (ctx.mode === 'offline') setMode('idle');
    setChip('chip-net', s.internet ? 'NET · ONLINE' : s.internet_enabled ? 'NET · OFFLINE' : 'NET · DISABLED', s.internet ? 'ok' : 'warn');
    setChip('chip-brain', s.llm.available ? `BRAIN · ${String(s.llm.model).split(':')[0].toUpperCase()}` : 'BRAIN · BASIC', s.llm.available ? 'ok' : 'warn');
    $('ro-agents').textContent = `${s.agents} / 9 READY`; $('ro-mem').textContent = s.memory_enabled ? 'ON' : 'OFF';
    $('ro-ver').textContent = s.version; if (s.process?.rss) $('ro-rss').textContent = `${(s.process.rss / 1048576).toFixed(0)} MB`; $('ro-up').textContent = s.uptime_s > 3600 ? `${(s.uptime_s / 3600).toFixed(1)} H` : `${Math.floor(s.uptime_s / 60)} MIN`;
    if (!welcomed) { welcomed = true; caption(`Hi ${s.user_name}, welcome to Crysta AI.`); }
  } catch (e) {
    if (e.status === 401) { location.href = '/pair.html'; return; }
    ctx.backendUp = false; setMode('offline'); setChip('chip-net', 'LINK · DOWN', 'bad'); setChip('chip-brain', 'BRAIN · —', 'warn');
    caption('I can’t reach the Crysta backend. Make sure run.py is still running in your terminal.', true);
  }
}

// ---------- overlay
const overlay = $('overlay');
let lastFocus = null;
async function openView(name) {
  if (name === 'home') return closeView();
  if (name === 'research') name = 'zykron';
  if (AGENT_VIEWS.includes(name)) return openWorkspace(name);
  if (!VIEWS[name]) return;
  closeWorkspace(false);
  lastFocus = document.activeElement;
  $('sheet-title').textContent = TITLES[name];
  const body = $('sheet-body'); body.replaceChildren(); ctx.chatLog = null;
  overlay.hidden = false; overlay.dataset.view = name; ctx.current = name;
  try { await VIEWS[name](ctx, body); } catch (e) { body.append(h('div', { class: 'warnbox' }, e.message)); }
  if (name !== 'chat') $('close').focus();
}
const loadedCss = new Set();
async function openWorkspace(name) {
  overlay.hidden = true; ctx.chatLog = null;
  closeWorkspace(false);
  if (!lastFocus || !wsEl.contains(lastFocus)) lastFocus = document.activeElement;
  if (!loadedCss.has(name)) { document.head.append(h('link', { rel: 'stylesheet', href: `/css/${name}.css` })); loadedCss.add(name); }
  const root = h('section', { class: `ws ws-${name}`, id: `ws-${name}`, 'data-agent': name });
  wsEl.replaceChildren(root); wsEl.hidden = false; ctx.current = name;
  try {
    wsMod = await import(`/js/agents/${name}.js`);
    await wsMod.mount(root, ctx);
  } catch (e) {
    root.replaceChildren(h('div', { class: 'ws-error' }, h('h2', {}, name.toUpperCase() + ' could not start'), h('p', {}, e.message), h('button', { class: 'ws-back', type: 'button', onclick: () => ctx.close() }, '◂ CRYSTA')));
  }
  root.querySelector('.ws-back')?.focus();
}
function closeWorkspace(restoreFocus = true) {
  try { wsMod?.unmount?.(); } catch { /* ignore */ }
  wsMod = null; wsEl.hidden = true; wsEl.replaceChildren();
  if (restoreFocus) (lastFocus && document.contains(lastFocus) ? lastFocus : $('mic')).focus();
}
function closeView() {
  const wasWs = !wsEl.hidden;
  overlay.hidden = true; ctx.chatLog = null; delete overlay.dataset.view; ctx.current = 'home';
  $('sheet-body').replaceChildren();
  if (wasWs) closeWorkspace(); else (lastFocus && document.contains(lastFocus) ? lastFocus : $('mic')).focus();
}
ctx.close = closeView;
window.addEventListener('crysta-open', (e) => openView(e.detail));
ctx.open = (name) => openView(name);
$('close').addEventListener('click', closeView);
document.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', () => openView(b.dataset.open)));

// ---------- confirmations (always require a real click; voice cannot approve)
function askConfirm(c) {
  return new Promise((resolve) => {
    pendingConfirm = { c, resolve }; $('confirm-desc').textContent = c.description;
    const r = $('confirm-risk'); r.textContent = `RISK: ${c.risk.toUpperCase()}`; r.className = 'risk ' + c.risk;
    $('confirm').hidden = false; $('confirm-no').focus();
  });
}
async function answerConfirm(approve) {
  const p = pendingConfirm; pendingConfirm = null; $('confirm').hidden = true; if (!p) return;
  try {
    const r = await api('/api/confirm', { method: 'POST', body: { token: p.c.token, approve } });
    p.resolve({ ...r, approved: approve });
  } catch (e) { p.resolve({ ok: false, approved: false, message: e.message }); }
}
/** Direct UI action against a permission-gated API. Resolves {ok, result} or {ok, confirmed, message}. */
ctx.act = async (path, opts) => {
  const r = await api(path, opts);
  if (r && r.status === 'needs_confirmation') {
    const res = await askConfirm(r.confirmation);
    if (!res.approved) return { ok: false, declined: true, message: res.message || 'Cancelled.' };
    return { ok: res.ok !== false, confirmed: true, message: res.message, data: res };
  }
  return { ok: true, result: r.result !== undefined ? r.result : r };
};
ctx.api = api;
ctx.ask = async (text) => (await api('/api/chat', { method: 'POST', body: { message: text, conversation_id: convId } }));
ctx.openExternal = async (url) => {
  try { const r = await ctx.act('/api/open-url', { method: 'POST', body: { url } }); if (!r.ok && !r.declined) window.open(url, '_blank', 'noopener'); }
  catch { window.open(url, '_blank', 'noopener'); }
};
document.addEventListener('click', (e) => {
  const a = e.target.closest?.('a[href^="http"]');
  if (a) { e.preventDefault(); ctx.openExternal(a.href); }
});
$('confirm-yes').addEventListener('click', () => answerConfirm(true));
$('confirm-no').addEventListener('click', () => answerConfirm(false));

// ---------- conversation
const backendTts = { checked: false, ok: false };
const settingsSpeak = () => ctx.settings.speak_responses && (speech.canSpeak || backendTts.ok);
/** Speak with browser voices when present, otherwise with the operating-system engine through the backend. */
ctx.speak = async (text, extra = {}) => {
  const s = ctx.settings, lang = s.voice_lang || 'en-IN';
  const opts = { rate: s.speech_rate ?? 1, pitch: s.speech_pitch ?? 1, volume: s.speech_volume ?? 1, voiceName: s.voice_name || '', ...extra };
  if (speech.canSpeak && speech.voices().length) return { engine: 'browser', ok: speech.speak(text, lang, opts) };
  try { const r = await api('/api/voice/speak', { method: 'POST', body: { text: speech.plainForSpeech(text), lang, rate: opts.rate } }); return { engine: r.engine, ok: r.ok }; }
  catch (e) { return { engine: null, ok: false, message: e.message }; }
};
api('/api/voice/status').then((v) => { backendTts.checked = true; backendTts.ok = !!v.tts_engine; backendTts.stt = v.stt; }).catch(() => {});
function pushBot(text, resp) {
  const e = { role: 'bot', text, resp }; ctx.history.push(e);
  if (ctx.chatLog) { ctx.chatLog.append(renderEntry(e)); ctx.chatLog.scrollTop = ctx.chatLog.scrollHeight; }
}
function pushUser(text) {
  ctx.history.push({ role: 'user', text });
  if (ctx.chatLog) { ctx.chatLog.append(renderEntry({ role: 'user', text })); ctx.chatLog.scrollTop = ctx.chatLog.scrollHeight; }
}
function handleActions(actions = []) {
  for (const a of actions) {
    if (a.type === 'open_view') openView(a.view);
    else if (a.type === 'refresh_settings') refreshSettings();
    else if (a.type === 'stop_speaking') speech.stopSpeaking();
  }
}
ctx.send = async (text) => {
  speech.stopSpeaking(); pushUser(text); caption(text, true); setMode('processing');
  abort = new AbortController(); const t0 = performance.now();
  try {
    const r = await api('/api/chat', { method: 'POST', body: { message: text, conversation_id: convId }, signal: abort.signal });
    $('ro-lat').textContent = `${((performance.now() - t0) / 1000).toFixed(1)} S`;
    pushBot(r.reply, r);
    const short = r.reply.length <= 280 && !r.results.some((x) => x.sources?.length);
    const goesToView = r.ui_actions.some((a) => a.type === 'open_view');
    if (short || goesToView) caption(r.reply.replace(/\*\*/g, '')); else { caption('Done — opening the full answer.'); if (overlay.hidden) openView('chat'); }
    handleActions(r.ui_actions);
    r.confirmations.forEach((c) => askConfirm(c).then((res) => { const m = res.message || 'Done.'; pushBot(m, null); caption(m); if (settingsSpeak()) ctx.speak(m); }));
    setMode('idle');
    if (settingsSpeak() && r.speech) ctx.speak(r.speech, { onStart: () => setMode('speaking'), onEnd: () => ctx.mode === 'speaking' && setMode('idle') });
  } catch (e) {
    if (e.name === 'AbortError') { caption('Cancelled.', true); setMode('idle'); return; }
    pushBot(e.message, null); caption(e.message); setMode(e.code === 'offline' ? 'offline' : 'error');
    if (e.code !== 'offline') setTimeout(() => ctx.mode === 'error' && setMode('idle'), 2500);
  } finally { abort = null; }
};
ctx.cancel = () => { abort?.abort(); api('/api/cancel', { method: 'POST', body: { conversation_id: convId } }).catch(() => {}); speech.stopSpeaking(); api('/api/voice/stop', { method: 'POST', body: {} }).catch(() => {}); speech.stopListening(); if (ctx.mode !== 'offline') setMode('idle'); };

// ---------- voice
const ERR = { 'not-allowed': 'Microphone permission is blocked. Allow it in the browser address bar, or press T to type.', 'service-not-allowed': 'The browser blocked speech recognition here.',
  'no-speech': 'I didn’t hear anything. Press the mic and try again.', 'audio-capture': 'No microphone was found.', network: 'Speech recognition needs the browser’s online speech service, which isn’t reachable. Press T to type.',
  unsupported: 'Voice input isn’t supported in this browser. Use Chrome or Edge, or press T to type.', 'start-failed': 'Could not start the microphone.' };
function toggleMic() {
  if (ctx.mode === 'listening') { speech.stopListening(); setMode('idle'); return; }
  if (!speech.canListen) {
    if (backendTts.stt?.available) {  // offline recogniser (Vosk) running in the backend
      setMode('listening'); caption('Listening (offline, about 6 seconds)…', true);
      api('/api/voice/listen', { method: 'POST', body: {} }).then((r) => { setMode('idle'); r.text ? ctx.send(r.text) : caption('I heard nothing. Press the mic and try again.'); }).catch((e) => { setMode('error'); caption(e.message); setTimeout(() => setMode('idle'), 2500); });
      return;
    }
    caption(backendTts.stt ? `This window has no built-in speech recognition. ${backendTts.stt.reason} You can still type: press T.` : ERR.unsupported); return;
  }
  if (!ctx.backendUp) { caption('The backend is offline, so I can’t answer yet.'); return; }
  speech.stopSpeaking();
  speech.listen({
    lang: ctx.settings.voice_lang || 'en-IN',
    onStart: () => { setMode('listening'); caption('Listening…', true); },
    onInterim: (t) => caption(t, true),
    onFinal: (t) => ctx.send(t),
    onError: (e) => { if (e !== 'aborted') { caption(ERR[e] || `Voice error: ${e}`); setMode('error'); setTimeout(() => ctx.mode === 'error' && setMode('idle'), 2500); } },
    onEnd: (had) => { if (ctx.mode === 'listening') setMode('idle'); if (!had && ctx.mode === 'idle' && $('caption').textContent === 'Listening…') caption(''); },
  });
}
$('mic').addEventListener('click', toggleMic);
if (!speech.canListen) $('mic').title = 'Voice input is not supported in this browser — use T to type.';

// ---------- keyboard
document.addEventListener('keydown', (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
  if (e.key === 'Escape') { if (!$('confirm').hidden) return answerConfirm(false); if (!overlay.hidden || !wsEl.hidden) return closeView(); ctx.cancel(); return; }
  if (typing || e.ctrlKey || e.metaKey || e.altKey || !$('confirm').hidden) return;
  if (e.key === ' ' && overlay.hidden && document.activeElement !== $('mic')) { e.preventDefault(); toggleMic(); }
  else if ((e.key === 't' || e.key === 'T' || e.key === '/') && overlay.hidden && wsEl.hidden) { e.preventDefault(); openView('chat'); }
});

// ---------- reminders (only fire while this page is open)
async function pollReminders() {
  if (!ctx.backendUp) return;
  try {
    const { due } = await api('/api/tasks/due');
    for (const t of due) {
      const msg = `Reminder: ${t.title}`; caption(msg); pushBot(msg, null);
      if (settingsSpeak()) ctx.speak(msg);
      await api('/api/tasks/ack', { method: 'POST', body: { id: t.id } });
    }
  } catch { /* ignore */ }
}

setMode('idle');
refreshSettings().then(pollStatus);
setInterval(pollStatus, 30000); setInterval(pollReminders, 15000);
setInterval(() => { $('ro-clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }, 1000);
if (speech.canSpeak) speechSynthesis.getVoices();
