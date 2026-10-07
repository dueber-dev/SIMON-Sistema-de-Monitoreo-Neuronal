import { live, METRICS as M, SESSIONS, sessionData, summarize } from '../sim.js';
import { config } from '../store.js';
import { lineChart, scatter, spark, ring, fmt, hhmmss } from '../charts.js';
import { polyfit, getModel, efficiency } from '../ml.js';
import { $, $$, ic, tween, relDay, durFmt } from '../ui.js';

let root, win = 300;
const WIN_LBL = { 60: 'último minuto', 300: 'últimos 5 min', 900: 'últimos 15 min', 0: 'toda la sesión' };

function mount(el) {
  root = el;
  const kpis = $('#kpis', el);
  Object.entries(M).forEach(([k, m], idx) => {
    const a = document.createElement('article');
    a.className = 'card glass kpi reveal' + (k === 'p' ? ' kpi--hero' : '');
    a.style.setProperty('--i', idx + 2);
    a.innerHTML = `
      <div class="kpi__top"><span class="kpi__label">${m.label}</span>
        <span class="badge" style="--mc:var(--c-${k})"><svg><use href="#${m.icon}"/></svg></span></div>
      <div class="kpi__spark" id="sp-${k}"></div>
      <div class="kpi__value"><span class="kpi__num" id="kv-${k}">—</span><span class="kpi__unit">${m.unit}</span></div>
      <div class="kpi__delta" id="kd-${k}"></div>`;
    kpis.appendChild(a);
  });

  $$('[data-win]', el).forEach(b => b.addEventListener('click', () => {
    win = +b.dataset.win;
    $$('[data-win]', el).forEach(x => x.setAttribute('aria-pressed', x === b));
    render();
  }));
  const pause = $('#pause', el);
  pause.addEventListener('click', () => {
    live.paused = !live.paused;
    pause.innerHTML = ic(live.paused ? 'i-play' : 'i-pause', 16);
    pause.setAttribute('aria-label', live.paused ? 'Reanudar' : 'Pausar');
    render();
  });

  // Últimas sesiones (enlazan al análisis)
  $('#live-sessions', el).innerHTML = SESSIONS.slice(0, 3).map(s => {
    const meta = s.live ? 'Hoy · en curso' : `${relDay(s.start)} · ${durFmt(s.n)} · ${s.n.toLocaleString('es')} muestras`;
    const right = s.live ? '<span class="tag tag--live">En vivo</span>' : `<span class="row__meta tnum">${fmt(summarize(sessionData(s)).energyWh, 2)} Wh</span>`;
    return `<li><a class="row" href="#/analisis/${s.id}"><span class="row__icon">${ic('i-sessions', 16, 'style="color:var(--ink-2)"')}</span>
      <span class="row__main"><b>Sesión ${s.id}</b><span>${meta}</span></span>${right}</a></li>`;
  }).join('');
}

function clock() {
  const now = new Date(), h = now.getHours();
  $('#clock', root).textContent = hhmmss(now);
  $('#greet', root).textContent = h < 12 ? 'Buenos días' : h < 19 ? 'Buenas tardes' : 'Buenas noches';
}

function render() {
  if (!root || root.hidden) return;
  clock();
  const data = live.data, pts = win ? data.slice(-win) : data, last = data[data.length - 1], ago = data[Math.max(0, data.length - 61)];
  const P = config.panel, A = config.alertas;

  Object.entries(M).forEach(([k, m]) => {
    tween($('#kv-' + k, root), last[k], m.dec);
    spark($('#sp-' + k, root), data.slice(-60), d => d[k], '--c-' + k);
    const ch = ago[k] ? (last[k] - ago[k]) / Math.abs(ago[k]) * 100 : 0;
    const dir = Math.abs(ch) < .5 ? 'flat' : ch > 0 ? 'up' : 'down';
    const good = dir === 'flat' ? null : (dir === 'up') === m.upGood;
    const c = good === null ? 'var(--ink-3)' : good ? 'var(--good)' : 'var(--serious)';
    $('#kd-' + k, root).innerHTML = `<svg style="color:${c}"><use href="#i-${dir}"/></svg><span class="tnum">${ch >= 0 ? '+' : ''}${fmt(ch, 1)} %</span> · 1 min`;
  });

  lineChart($('#ch-p', root), { series: [{ data: pts, y: d => d.p, color: '--c-p' }], unit: 'mW', dec: 0, zero: true, aria: 'Potencia en el tiempo' });
  lineChart($('#ch-v', root), { series: [{ data: pts, y: d => d.v, color: '--c-v' }], unit: 'V', dec: 2, aria: 'Voltaje en el tiempo' });
  lineChart($('#ch-i', root), { series: [{ data: pts, y: d => d.i, color: '--c-i' }], unit: 'mA', dec: 1, aria: 'Corriente en el tiempo' });
  const fit = polyfit(pts.map(d => d.g), pts.map(d => d.p), 2);
  $('#r2', root).textContent = `· R² ${fmt(fit.r2, 2)}`;
  scatter($('#ch-s', root), {
    data: pts, x: d => d.g, y: d => d.p, color: '--c-p', fitFn: fit.f, lastLabel: 'ahora', yZero: true,
    xTick: v => fmt(v, 0) + ' %', tip: d => `${hhmmss(d.ts)}<b class="tnum">${fmt(d.p, 0)} mW · ${fmt(d.g, 1)} %</b>`, aria: 'Potencia contra irradiancia',
  });

  $('#peak', root).textContent = fmt(Math.max(...pts.map(d => d.p)), 0);
  $('#win-lbl', root).textContent = WIN_LBL[win];
  tween($('#energy', root), live.energyWh, 2);
  const up = Math.floor((last.ts - live.start) / 1000);
  $('#uptime', root).textContent = [up / 3600, up / 60 % 60, up % 60].map(x => String(Math.floor(x)).padStart(2, '0')).join(':');
  $('#samples', root).textContent = data.length.toLocaleString('es');

  // Ficha del panel (desde Configuración)
  $('#spec-nominal', root).textContent = fmt(P.nominal, 1) + ' W';
  $('#spec-voc', root).textContent = fmt(P.voc, 1) + ' V';
  $('#spec-area', root).textContent = fmt(P.area, 0);
  ring($('#ring', root), last.p / (P.nominal * 1000) * 100);
  $('#perf-note', root).textContent = `Potencia instantánea respecto a la nominal (${fmt(P.nominal, 1)} W)`;

  // Estado del sistema: ícono + texto, nunca solo color
  const sim = config.conexion.modo === 'sim';
  const rows = [
    live.paused ? ['warning', 'i-alert', 'Vista en pausa', 'Los datos siguen llegando; la vista está congelada']
      : sim ? ['good', 'i-wifi', 'Simulador activo', 'Datos sintéticos a 1 Hz · sin hardware']
        : ['good', 'i-wifi', 'Conexión estable', `TCP ${config.conexion.ip}:${config.conexion.puerto} · 0 tramas perdidas`],
    last.t > A.tMax ? ['warning', 'i-alert', 'Temperatura alta', `${fmt(last.t, 1)} °C · umbral ${fmt(A.tMax, 0)} °C`]
      : ['good', 'i-check', 'Temperatura en rango', `${fmt(last.t, 1)} °C · umbral ${fmt(A.tMax, 0)} °C`],
    last.p < A.pMin ? ['critical', 'i-alert', 'Sin potencia', 'Falta de irradiación o circuito abierto']
      : ['good', 'i-check', 'Generando', `${fmt(last.p, 0)} mW · ${fmt(last.g, 0)} % de irradiancia`],
  ];
  $('#status-list', root).innerHTML = rows.map(([s, i, t, d]) =>
    `<li class="row"><span class="row__icon st-${s}">${ic(i, 16)}</span><span class="row__main"><b>${t}</b><span>${d}</span></span></li>`).join('');

  // Predicción del modelo demo
  const mdl = getModel();
  const pred = mdl.predictEff(last.g, last.t), real = efficiency(last.p, last.g);
  $('#ml-fig', root).innerHTML = `${fmt(pred, 1)} <small style="font-size:16px">%</small>`;
  $('#ml-fig', root).style.color = 'var(--ink)';
  $('#ml-note', root).textContent = `Real: ${fmt(real, 1)} % · diferencia ${fmt(pred - real, 1)} pp`;
}

export default { mount, show: render, tick: render, render };
