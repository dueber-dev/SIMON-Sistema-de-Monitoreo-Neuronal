// Utilidades de interfaz compartidas por todas las vistas
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];
export const ic = (id, s = 16, attrs = '') => `<svg width="${s}" height="${s}" ${attrs} aria-hidden="true"><use href="#${id}"/></svg>`;

const toastEl = () => $('#toast');
let toastT;
export function toast(msg) {
  const el = toastEl(); el.textContent = msg; el.classList.add('show');
  clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove('show'), 2600);
}

export const infoBtn = (key, label) =>
  `<button class="info-btn" data-info="${key}" aria-label="Qué es: ${label}" aria-expanded="false">i</button>`;

export const statusPill = () =>
  `<span class="pill glass js-status"><span class="dot"></span><span><b class="js-status-txt">—</b><span class="js-status-meta"></span></span></span>`;
export const bgButton = () =>
  `<button class="icon-btn glass js-bg-btn" aria-label="Personalizar fondo" aria-expanded="false">${ic('i-image', 18)}</button>`;

export function viewHeader({ eyebrow, icon, title, sub, tools = '' }) {
  return `<header class="head head--view reveal">
    <div class="hello"><span class="eyebrow">${ic(icon, 14)} ${eyebrow}</span><h1>${title}</h1><p>${sub}</p></div>
    <div class="head__tools">${tools}${statusPill()}${bgButton()}</div>
  </header>`;
}

export function download(name, text, type = 'text/csv') {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// Números que se deslizan al nuevo valor
const shown = {};
const reduce = matchMedia('(prefers-reduced-motion: reduce)');
export function tween(el, to, dec, key = el.id) {
  const f = x => x.toLocaleString('es', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const from = shown[key] ?? to, t0 = performance.now();
  shown[key] = to;
  if (reduce.matches || from === to) { el.textContent = f(to); return; }
  (function step(now) {
    const k = Math.max(0, Math.min(1, (now - t0) / 600)), e = 1 - (1 - k) ** 3;
    el.textContent = f(from + (to - from) * e);
    if (k < 1) requestAnimationFrame(step);
  })(t0);
}

export const dateFmt = ts => new Date(ts).toLocaleDateString('es', { day: 'numeric', month: 'short' });
export const dayKey = ts => { const d = new Date(ts); return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`; };
export function relDay(ts) {
  const d = new Date(ts); d.setHours(0, 0, 0, 0);
  const t = new Date(); t.setHours(0, 0, 0, 0);
  const n = Math.round((t - d) / 864e5);
  return n === 0 ? 'Hoy' : n === 1 ? 'Ayer' : dateFmt(ts);
}
export const durFmt = s => { const h = Math.floor(s / 3600), m = Math.round(s % 3600 / 60); return h ? `${h} h ${String(m).padStart(2, '0')} min` : `${m} min`; };
export const timeFmt = ts => new Date(ts).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit', hour12: false });
