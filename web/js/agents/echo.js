// ECHO — voice studio: live microphone visualiser, voice/language selection, speed/pitch/volume faders, speech tests.
import { h, clear, backButton } from '../dom.js';

let raf = 0, stream = null, actx = null;
export function unmount() { cancelAnimationFrame(raf); stream?.getTracks().forEach((t) => t.stop()); stream = null; try { actx?.close(); } catch { /* ignore */ } actx = null; }

export async function mount(root, ctx) {
  const sp = ctx.speechApi, S = () => ctx.settings;
  const st = { analyser: null, data: null, micState: 'not enabled', speakingUntil: 0 };
  const cv = h('canvas', { width: 640, height: 640, class: 'e-canvas', role: 'img', 'aria-label': 'Audio visualisation' });
  const label = h('div', { class: 'e-vlabel' }, 'IDLE'), micInfo = h('div', { class: 'e-mic' }), engines = h('div', { class: 'e-eng' }), heard = h('div', { class: 'e-heard' }, 'Press LISTEN TEST and speak.');
  const text = h('textarea', { class: 'e-text', 'aria-label': 'Text to speak', rows: 2 }, 'Hello, I am Crysta. This is how I sound.');
  const save = (patch) => ctx.api('/api/settings', { method: 'PATCH', body: patch }).then(() => ctx.refreshSettings());
  const langSel = h('select', { 'aria-label': 'Voice language' }, [['en-IN', 'English (India)'], ['en-US', 'English (US)'], ['en-GB', 'English (UK)'], ['ta-IN', 'Tamil (தமிழ்)']].map(([k, l]) => h('option', { value: k, selected: S().voice_lang === k }, l)));
  const voiceSel = h('select', { 'aria-label': 'Voice' });
  const fader = (name, key, min, max, step, fmtv) => {
    const out = h('b', {}, fmtv(S()[key] ?? 1)), i = h('input', { type: 'range', min, max, step, value: S()[key] ?? 1, 'aria-label': name, class: 'e-fader' });
    i.addEventListener('input', () => { out.textContent = fmtv(+i.value); }); i.addEventListener('change', () => save({ [key]: +i.value }));
    return h('div', { class: 'e-ch' }, out, i, h('span', {}, name));
  };

  function fillVoices() {
    const all = sp.voices(), pre = langSel.value.slice(0, 2);
    clear(voiceSel);
    const match = all.filter((v) => v.lang.toLowerCase().startsWith(pre)), rest = all.filter((v) => !match.includes(v));
    if (!all.length) voiceSel.append(h('option', { value: '' }, 'No browser voices — using the operating-system engine'));
    voiceSel.append(h('option', { value: '' }, 'Automatic (best match for language)'), ...match.map((v) => h('option', { value: v.name, selected: S().voice_name === v.name }, `${v.name} (${v.lang})`)),
      ...(rest.length ? [h('optgroup', { label: 'Other languages' }, rest.map((v) => h('option', { value: v.name, selected: S().voice_name === v.name }, `${v.name} (${v.lang})`)))] : []));
    if (!match.length && all.length) micInfo.dataset.note = `No installed voice matches ${langSel.value}; install one in your OS to hear it.`;
  }
  langSel.addEventListener('change', () => { save({ voice_lang: langSel.value }); fillVoices(); });
  voiceSel.addEventListener('change', () => save({ voice_name: voiceSel.value }));
  if (sp.canSpeak) speechSynthesis.addEventListener?.('voiceschanged', fillVoices);

  const listen = async () => {
    clear(heard).append('Listening…');
    if (sp.canListen) {
      sp.listen({ lang: langSel.value, onStart: () => { st.listening = true; }, onInterim: (t) => { heard.textContent = t + ' …'; }, onFinal: (t) => { heard.textContent = '“' + t + '”'; },
        onError: (e) => { heard.textContent = ({ 'not-allowed': 'Microphone permission was blocked.', network: 'The browser speech service is unreachable (it needs internet).', 'no-speech': 'I heard nothing.', 'service-not-allowed': 'Speech recognition is blocked here.' })[e] || 'Speech error: ' + e; },
        onEnd: () => { st.listening = false; } });
      return;
    }
    try { const r = await ctx.api('/api/voice/listen', { method: 'POST', body: {} }); heard.textContent = r.text ? '“' + r.text + '”' : 'I heard nothing.'; }
    catch (e) { heard.textContent = 'Speech input is unavailable: ' + e.message; }
  };
  const speakTest = async () => { const r = await ctx.speak(text.value, { onStart: () => { st.speakingUntil = Infinity; }, onEnd: () => { st.speakingUntil = 0; } });
    if (!r.ok) { heard.textContent = r.message || 'No speech engine is available. On Linux: sudo apt install espeak-ng'; } else if (r.engine !== 'browser') { st.speakingUntil = performance.now() + Math.max(1500, text.value.length * 70); heard.textContent = `Speaking through the operating-system engine (${r.engine}).`; } };

  async function enableMic() {
    if (!navigator.mediaDevices?.getUserMedia) { st.micState = 'unsupported'; micInfo.textContent = 'This window cannot capture audio (no getUserMedia).'; return drawMic(); }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true }); actx = new (window.AudioContext || window.webkitAudioContext)();
      const src = actx.createMediaStreamSource(stream); st.analyser = actx.createAnalyser(); st.analyser.fftSize = 128; src.connect(st.analyser); st.data = new Uint8Array(st.analyser.frequencyBinCount); st.micState = 'live';
    } catch (e) { st.micState = 'blocked'; st.micErr = e.name === 'NotAllowedError' ? 'Permission denied — allow microphone access for this app in your system settings.' : `Could not open the microphone (${e.name}).`; }
    drawMic();
  }
  async function drawMic() {
    let perm = 'unknown'; try { perm = (await navigator.permissions.query({ name: 'microphone' })).state; } catch { /* not supported */ }
    let devs = []; try { devs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'audioinput'); } catch { /* ignore */ }
    clear(micInfo).append(h('div', { class: 'e-dot ' + st.micState }), h('b', {}, 'MICROPHONE: ' + ({ live: 'LIVE', blocked: 'BLOCKED', unsupported: 'UNSUPPORTED', 'not enabled': 'NOT ENABLED' })[st.micState]),
      h('div', { class: 'e-small' }, `Permission: ${perm} · Input devices: ${devs.length || 'none found'}${devs[0]?.label ? ' · ' + devs[0].label : ''}`), st.micErr && st.micState === 'blocked' ? h('div', { class: 'e-small bad' }, st.micErr) : null,
      st.micState !== 'live' ? h('button', { type: 'button', class: 'e-btn', onclick: enableMic }, 'ENABLE MIC LEVEL') : h('div', { class: 'e-small' }, 'The ring reacts to your real microphone input. Nothing is recorded or sent.'));
  }
  async function drawEngines() {
    const v = await ctx.api('/api/voice/status').catch(() => ({ tts_engine: null, stt: { available: false, reason: 'Backend not reachable.' } }));
    clear(engines).append(h('div', {}, h('b', {}, 'SPEECH OUTPUT')), h('div', { class: 'e-small' }, `Browser voices: ${sp.voices().length || 'none'}`), h('div', { class: 'e-small' }, `OS engine: ${v.tts_engine || 'none installed'}`),
      h('div', { style: 'margin-top:8px' }, h('b', {}, 'SPEECH INPUT')), h('div', { class: 'e-small' }, `Browser recognition: ${sp.canListen ? 'available (may use an online service)' : 'not available in this window'}`),
      h('div', { class: 'e-small' }, `Offline (Vosk): ${v.stt.available ? 'ready — ' + v.stt.model : 'not set up — ' + v.stt.reason}`));
  }

  const speakSwitch = h('input', { type: 'checkbox', id: 'e-sp', checked: !!S().speak_responses }); speakSwitch.addEventListener('change', () => save({ speak_responses: speakSwitch.checked }));
  root.append(h('header', { class: 'e-head' }, backButton(ctx), h('div', { class: 'e-logo' }, '◉ ECHO', h('small', {}, 'VOICE INTELLIGENCE')), h('div', { class: 'grow' }), h('label', { class: 'e-sw' }, speakSwitch, ' Speak replies')),
    h('div', { class: 'e-stage' },
      h('div', { class: 'e-left' }, micInfo, h('div', { class: 'e-faders' }, fader('SPEED', 'speech_rate', 0.5, 2, 0.1, (v) => v.toFixed(1) + '×'), fader('PITCH', 'speech_pitch', 0.5, 2, 0.1, (v) => v.toFixed(1)), fader('VOLUME', 'speech_volume', 0, 1, 0.05, (v) => Math.round(v * 100) + '%'))),
      h('div', { class: 'e-center' }, cv, label),
      h('div', { class: 'e-right' }, h('h4', {}, 'VOICE'), voiceSel, h('h4', {}, 'LANGUAGE'), langSel, h('h4', {}, 'TEST'), text,
        h('div', { class: 'row' }, h('button', { type: 'button', class: 'e-btn primary', onclick: speakTest }, '▶ SPEAK'), h('button', { type: 'button', class: 'e-btn', onclick: () => { sp.stopSpeaking(); ctx.api('/api/voice/stop', { method: 'POST', body: {} }).catch(() => {}); st.speakingUntil = 0; } }, '■ STOP'), h('button', { type: 'button', class: 'e-btn', onclick: listen }, '🎙 LISTEN TEST')),
        heard, engines)));
  fillVoices(); drawMic(); drawEngines();

  // ---- visualiser: real mic spectrum when live; speaking/idle states are labelled as animation
  const g = cv.getContext('2d');
  (function frame(now) {
    raf = requestAnimationFrame(frame);
    const W = cv.width, c = W / 2, t = now / 1000; g.clearRect(0, 0, W, W);
    const speaking = sp.speaking() || now < st.speakingUntil, live = st.micState === 'live' && st.analyser;
    if (live) st.analyser.getByteFrequencyData(st.data);
    const N = 96; let level = 0;
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2 - Math.PI / 2; let v;
      if (live) { v = st.data[Math.floor((i / N) * st.data.length * 0.8)] / 255; level += v; }
      else if (speaking) v = 0.35 + 0.35 * Math.abs(Math.sin(t * 7 + i * 0.5) * Math.sin(t * 3 + i * 0.13));
      else v = 0.06 + 0.04 * Math.sin(t * 1.4 + i * 0.3);
      const r0 = 180, r1 = r0 + 10 + v * 120; g.strokeStyle = `hsl(${310 + v * 60},100%,${55 + v * 25}%)`; g.lineWidth = 4; g.lineCap = 'round';
      g.beginPath(); g.moveTo(c + Math.cos(a) * r0, c + Math.sin(a) * r0); g.lineTo(c + Math.cos(a) * r1, c + Math.sin(a) * r1); g.stroke();
    }
    const grad = g.createRadialGradient(c, c, 10, c, c, 170); grad.addColorStop(0, 'rgba(255,94,200,.45)'); grad.addColorStop(1, 'rgba(255,94,200,0)'); g.fillStyle = grad; g.beginPath(); g.arc(c, c, 170, 0, 7); g.fill();
    g.strokeStyle = 'rgba(255,94,200,.7)'; g.lineWidth = 2; g.beginPath(); g.arc(c, c, 170 + (live ? level / N * 20 : 0), 0, 7); g.stroke();
    label.textContent = live ? `LIVE MICROPHONE · LEVEL ${Math.round((level / N) * 100)}%` : speaking ? 'SPEAKING (animation)' : st.listening ? 'LISTENING…' : 'IDLE — enable the mic level to see real input';
  })(performance.now());
}
