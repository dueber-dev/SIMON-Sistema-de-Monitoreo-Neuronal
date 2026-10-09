// Punto de entrada: tema, fondo, router por hash y bucle en vivo a 1 Hz.
import { prefs, config, bus } from './store.js';
import { live, stepLive } from './sim.js';
import { $, $$ } from './ui.js';
import { INFO } from './info.js';
import live$ from './views/live.js';
import analisis from './views/analisis.js';
import prediccion from './views/prediccion.js';
import sesiones from './views/sesiones.js';
import configuracion from './views/configuracion.js';

const root = document.documentElement;
const VIEWS = { 'en-vivo': live$, analisis, prediccion, sesiones, configuracion };
const TITLES = { 'en-vivo': 'En vivo', analisis: 'Análisis', prediccion: 'Predicción ML', sesiones: 'Sesiones', configuracion: 'Configuración' };
let current = null;

/* ---------- Tema ---------- */
const osDark = matchMedia('(prefers-color-scheme: dark)');
export function applyTheme(choice = prefs.get('theme', 'system')) {
  prefs.set('theme', choice);
  root.dataset.theme = choice === 'system' ? (osDark.matches ? 'dark' : 'light') : choice;
  $$('[data-theme-set]').forEach(b => b.setAttribute('aria-pressed', b.dataset.themeSet === root.dataset.theme));
  $$('[data-theme-choice]').forEach(b => b.setAttribute('aria-pressed', b.dataset.themeChoice === choice));
  current?.render?.();
}
osDark.addEventListener('change', () => prefs.get('theme', 'system') === 'system' && applyTheme('system'));
document.addEventListener('click', e => {
  const b = e.target.closest('[data-theme-set]'); if (b) applyTheme(b.dataset.themeSet);
  const c = e.target.closest('[data-theme-choice]'); if (c) applyTheme(c.dataset.themeChoice);
});

/* ---------- Fondo ---------- */
export function applyBg(bg) {
  document.body.dataset.bg = bg;
  if (bg !== 'custom') prefs.set('bg', bg);
  $$('[data-bg-set]').forEach(b => b.setAttribute('aria-pressed', b.dataset.bgSet === bg));
}
function applySliders(blur, dim) {
  root.style.setProperty('--bg-blur', blur + 'px');
  root.style.setProperty('--bg-dim', dim / 100);
  $$('.js-blur').forEach(i => { i.value = blur; }); $$('.js-dim').forEach(i => { i.value = dim; });
  $$('.js-blur-v').forEach(s => { s.textContent = blur + ' px'; }); $$('.js-dim-v').forEach(s => { s.textContent = dim + ' %'; });
  prefs.set('blur', +blur); prefs.set('dim', +dim);
}
export const syncBgControls = () => { applySliders(prefs.get('blur', 0), prefs.get('dim', 10)); applyBg(document.body.dataset.bg); };
applyBg(prefs.get('bg', 'foto'));
applySliders(prefs.get('blur', 0), prefs.get('dim', 10));
document.addEventListener('click', e => { const b = e.target.closest('[data-bg-set]'); if (b) applyBg(b.dataset.bgSet); });
document.addEventListener('input', e => {
  if (e.target.matches('.js-blur')) applySliders(e.target.value, prefs.get('dim', 10));
  if (e.target.matches('.js-dim')) applySliders(prefs.get('blur', 0), e.target.value);
});
document.addEventListener('change', e => {
  if (!e.target.matches('.js-bg-file')) return;
  const f = e.target.files[0]; if (!f) return;
  root.style.setProperty('--custom-bg', `url("${URL.createObjectURL(f)}")`);
  applyBg('custom');
});

const pop = $('#pop');
let popBtn = null;
function closePop() { pop.classList.remove('open'); popBtn?.setAttribute('aria-expanded', false); popBtn = null; }
document.addEventListener('click', e => {
  const btn = e.target.closest('.js-bg-btn');
  if (btn) {
    e.stopPropagation();
    if (popBtn === btn) return closePop();
    popBtn = btn; btn.setAttribute('aria-expanded', true);
    const r = btn.getBoundingClientRect();
    if (innerWidth < 760) { pop.style.left = '12px'; pop.style.right = '12px'; pop.style.width = 'auto'; }
    else { pop.style.left = ''; pop.style.width = ''; pop.style.right = (innerWidth - r.right) + 'px'; }
    pop.style.top = (r.bottom + 10) + 'px';
    pop.classList.add('open');
    return;
  }
  if (!pop.contains(e.target)) closePop();
});
/* ---------- Ficha de indicador: qué mide, por qué, cómo, umbral ---------- */
const infoPop = $('#info-pop');
let infoFor = null;
function closeInfo() { infoPop.classList.remove('open'); infoFor?.setAttribute('aria-expanded', false); infoFor = null; }
document.addEventListener('click', e => {
  const b = e.target.closest('[data-info]');
  if (b) {
    e.stopPropagation();
    if (infoFor === b) return closeInfo();
    closeInfo();
    const f = INFO[b.dataset.info]?.(); if (!f) return;
    const row = (t, d) => d ? `<div><dt>${t}</dt><dd>${d}</dd></div>` : '';
    infoPop.innerHTML = `<h4>${f.title}</h4><dl>${row('Qué mide', f.que)}${row('Por qué está aquí', f.porque)}${row('Cómo se calcula', f.como)}${row('Umbral', f.umbral)}</dl>`;
    infoFor = b; b.setAttribute('aria-expanded', true);
    infoPop.classList.add('open');
    const r = b.getBoundingClientRect(), w = Math.min(340, innerWidth - 24), h = infoPop.offsetHeight;
    infoPop.style.width = w + 'px'; infoPop.style.right = 'auto';
    infoPop.style.left = Math.max(12, Math.min(r.left - 16, innerWidth - w - 12)) + 'px';
    infoPop.style.top = (r.bottom + 8 + h > innerHeight && r.top - h - 8 > 0 ? r.top - h - 8 : r.bottom + 8) + 'px';
    return;
  }
  if (!infoPop.contains(e.target)) closeInfo();
});

document.addEventListener('keydown', e => { if (e.key === 'Escape') { closePop(); closeInfo(); } });
addEventListener('scroll', () => { closePop(); closeInfo(); }, { passive: true });

/* ---------- Estado de conexión (todas las vistas) ---------- */
export function updateStatus() {
  const sim = config.conexion.modo === 'sim';
  $$('.js-status').forEach(p => p.classList.toggle('is-paused', live.paused));
  $$('.js-status-txt').forEach(b => { b.textContent = live.paused ? 'Vista en pausa' : sim ? 'Simulador activo' : 'ESP32 conectado'; });
  $$('.js-status-meta').forEach(s => { s.textContent = ` · 1 Hz${sim ? '' : ' · ' + config.conexion.ip}`; });
  $$('.js-team').forEach(b => { b.textContent = config.ui.equipo; });
  $$('.js-panel-name').forEach(b => { b.textContent = config.panel.nombre; });
}
bus.addEventListener('config', () => { updateStatus(); current?.render?.(); });

/* ---------- Router ---------- */
function route() {
  const [, name = 'en-vivo', param] = location.hash.match(/^#\/([\w-]+)(?:\/([\w-]+))?/) || [];
  const key = VIEWS[name] ? name : 'en-vivo';
  const view = VIEWS[key], el = $('#view-' + key);
  if (!view.mounted) { view.mount(el); view.mounted = true; }
  $$('.view').forEach(v => { v.hidden = v !== el; });
  $$('[data-route]').forEach(a => a.dataset.route === key ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
  document.title = `SIMON · ${TITLES[key]}`;
  current = view;
  closePop(); closeInfo();
  syncBgControls();
  $$('[data-theme-choice]').forEach(b => b.setAttribute('aria-pressed', b.dataset.themeChoice === prefs.get('theme', 'system')));
  updateStatus();
  view.show?.(param);
  if (!param) scrollTo({ top: 0 });
}
addEventListener('hashchange', route);

/* ---------- Bucle a 1 Hz (como el ESP32) ---------- */
setInterval(() => {
  stepLive();
  if (!live.paused) current?.tick?.();
  updateStatus();
}, 1000);

let rt;
new ResizeObserver(() => { clearTimeout(rt); rt = setTimeout(() => current?.render?.(), 80); }).observe($('.window'));

applyTheme();
route();
