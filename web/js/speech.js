// Browser-native speech. Recognition runs only while the user has pressed the mic; no background listening.
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
export const canListen = !!SR;
export const canSpeak = 'speechSynthesis' in window;

let rec = null;
export function listen({ lang, onStart, onInterim, onFinal, onError, onEnd }) {
  if (!SR) return onError('unsupported');
  rec = new SR();
  rec.lang = lang; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
  let finalText = '';
  rec.onstart = () => onStart();
  rec.onresult = (e) => {
    let interim = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalText += t; else interim += t;
    }
    if (interim) onInterim(interim);
  };
  rec.onerror = (e) => onError(e.error);
  rec.onend = () => { rec = null; finalText.trim() ? onFinal(finalText.trim()) : null; onEnd(!!finalText.trim()); };
  try { rec.start(); } catch (e) { onError('start-failed'); }
}
export function stopListening() { try { rec && rec.abort(); } catch { /* ignore */ } rec = null; }

export function plainForSpeech(text) {
  return text.replace(/\*\*/g, '').replace(/https?:\/\/\S+/g, '').replace(/\[\d+\]/g, '').replace(/[`#•]/g, '').replace(/\s+/g, ' ').trim().slice(0, 500);
}
export const voices = () => (canSpeak ? speechSynthesis.getVoices() : []);
export const speaking = () => canSpeak && speechSynthesis.speaking;
export function speak(text, lang, { onStart, onEnd, rate = 1, pitch = 1, volume = 1, voiceName = '' } = {}) {
  if (!canSpeak || !text) return false;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(plainForSpeech(text));
  u.lang = lang; u.rate = rate; u.pitch = pitch; u.volume = volume;
  const v = speechSynthesis.getVoices().find((x) => voiceName && x.name === voiceName) || speechSynthesis.getVoices().find((x) => x.lang === lang) || speechSynthesis.getVoices().find((x) => x.lang.startsWith(lang.slice(0, 2)));
  if (v) u.voice = v;
  u.onstart = () => onStart && onStart();
  u.onend = u.onerror = () => onEnd && onEnd();
  speechSynthesis.speak(u);
  return true;
}
export function stopSpeaking() { if (canSpeak) speechSynthesis.cancel(); }
