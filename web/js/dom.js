// Tiny DOM helpers. Text is always inserted as text nodes (never innerHTML) so model/web content can't inject markup.
// Native append() would print the text "null"/"false" for conditional children; skip them instead.
for (const proto of [Element.prototype, DocumentFragment.prototype]) {
  const native = proto.append;
  proto.append = function (...kids) { return native.apply(this, kids.flat().filter((k) => k != null && k !== false)); };
}

export function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === false || v == null) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'checked' || k === 'value' || k === 'disabled' || k === 'hidden') el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return el;
}

const URL_RE = /(https?:\/\/[^\s)]+)/g;
export function rich(text) {
  const frag = document.createDocumentFragment();
  for (const part of String(text).split(/(\*\*[^*]+\*\*)/g)) {
    const bold = part.startsWith('**') && part.endsWith('**') && part.length > 4;
    const node = bold ? h('strong') : frag;
    for (const seg of (bold ? part.slice(2, -2) : part).split(URL_RE)) {
      if (/^https?:\/\//.test(seg)) node.append(h('a', { href: seg, target: '_blank', rel: 'noopener noreferrer' }, seg));
      else if (seg) node.append(seg);
    }
    if (bold) frag.append(node);
  }
  return frag;
}
export const safeUrl = (u) => (/^https?:\/\//i.test(u || '') ? u : null);
export const fmtDate = (ts) => (ts ? new Date(ts * 1000).toLocaleString() : '—');

export const fmtBytes = (b) => (b == null ? '—' : b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : b < 1073741824 ? `${(b / 1048576).toFixed(1)} MB` : `${(b / 1073741824).toFixed(1)} GB`);
export const fmtDur = (s) => (s == null ? '—' : s >= 86400 ? `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h` : s >= 3600 ? `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m` : `${Math.floor(s / 60)}m`);
export const clear = (el) => { el.replaceChildren(); return el; };
export const svg = (tag, attrs = {}, ...kids) => {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  kids.flat().forEach((k) => k != null && e.append(k.nodeType ? k : document.createTextNode(String(k))));
  return e;
};
/** The same "return to CRYSTA" control in every workspace (look is styled per agent). */
export function backButton(ctx, label = '◂ CRYSTA') {
  return h('button', { type: 'button', class: 'ws-back', 'aria-label': 'Return to CRYSTA', onclick: () => ctx.close() }, label);
}
export function debounce(fn, ms = 250) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
