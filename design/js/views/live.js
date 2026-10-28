import { live, METRICS as M, SESSIONS, SCENARIOS, sessionData, summarize, val, decOf } from '../sim.js';
import { config } from '../store.js';
import { NUBE, nube } from '../nube.js';
import { lineChart, scatter, spark, ring, fmt, hhmmss } from '../charts.js';
import { polyfit, getModel } from '../ml.js';
import { irradiance, efficiency, etaNominal, etaThreshold, pTheory, maintenance } from '../physics.js';
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
      <div class="kpi__top"><span class="kpi__label">${m.label} <button class="info-btn" data-info="${k}" aria-label="Qué es: ${m.label.toLowerCase()}">i</button></span>
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
}

function renderSessions() {
  $('#live-sessions', root).innerHTML = SESSIONS.slice(0, 3).map(s => {
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
  if (!last) return;
  const P = config.panel, A = config.alertas, etaN = etaNominal(), thr = etaThreshold();

  Object.entries(M).forEach(([k, m]) => {
    const now = val(last, k), before = val(ago, k);
    tween($('#kv-' + k, root), now, decOf(k, now));
    spark($('#sp-' + k, root), data.slice(-60), d => val(d, k), '--c-' + k);
    const ch = before ? (now - before) / Math.abs(before) * 100 : 0;
    const dir = Math.abs(ch) < .5 ? 'flat' : ch > 0 ? 'up' : 'down';
    const good = dir === 'flat' ? null : (dir === 'up') === m.upGood;
    const c = good === null ? 'var(--ink-3)' : good ? 'var(--good)' : 'var(--serious)';
    $('#kd-' + k, root).innerHTML = k === 'e'
      ? `<span class="tnum">nominal ${fmt(etaN, 1)} %</span>`
      : `<svg style="color:${c}"><use href="#i-${dir}"/></svg><span class="tnum">${ch >= 0 ? '+' : ''}${fmt(ch, 1)} %</span> · 1 min`;
  });

  // Potencia medida vs teórica (cálculo con la ficha técnica)
  lineChart($('#ch-p', root), {
    series: [
      { data: pts, y: d => d.p, color: '--c-p', name: 'Medida' },
      { data: pts, y: d => pTheory(d.g, d.t), color: '--c-th', name: 'Teórica' },
    ],
    unit: 'mW', dec: decOf('p', Math.max(...pts.map(d => d.p))), zero: true, aria: 'Potencia medida y teórica en el tiempo',
  });
  const recent = data.slice(-60), sumP = recent.reduce((a, d) => a + d.p, 0), sumT = recent.reduce((a, d) => a + pTheory(d.g, d.t), 0);
  $('#ratio-th', root).textContent = sumT > 0 ? fmt(sumP / sumT * 100, 0) + ' %' : '—';

  // Eficiencia real vs nominal, con el umbral de mantenimiento
  const lit = pts.filter(d => irradiance(d.g) >= 50);
  lineChart($('#ch-e', root), {
    series: [{ data: lit, y: d => efficiency(d.p, d.g), color: '--c-e' }], unit: '%', dec: 2, area: false,
    ref: [
      { y: etaN, label: `nominal ${fmt(etaN, 1)} %`, align: 'right' },
      { y: thr, label: `mantenimiento ${fmt(thr, 1)} %`, color: '--warning' },
    ],
    bands: [{ to: thr, color: '--warning' }], aria: 'Eficiencia real frente a la nominal y al umbral de mantenimiento',
  });
  $('#eta-now', root).textContent = fmt(efficiency(last.p, last.g), 2);

  lineChart($('#ch-t', root), {
    series: [{ data: pts, y: d => d.t, color: '--c-t' }], unit: '°C', dec: 1,
    ref: [{ y: A.tMax, label: `umbral ${fmt(A.tMax, 0)} °C`, color: '--warning' }],
    bands: [{ from: A.tMax, color: '--warning' }], aria: 'Temperatura del panel y umbral de alerta',
  });
  lineChart($('#ch-v', root), { series: [{ data: pts, y: d => d.v, color: '--c-v' }], unit: 'V', dec: 2, aria: 'Voltaje en el tiempo' });
  lineChart($('#ch-i', root), { series: [{ data: pts, y: d => d.i, color: '--c-i' }], unit: 'mA', dec: 1, aria: 'Corriente en el tiempo' });
  const gs = pts.map(d => irradiance(d.g)), fit = polyfit(gs.map(g => g / 1000), pts.map(d => d.p), 2);
  $('#r2', root).textContent = `· R² ${fmt(fit.r2, 2)}`;
  scatter($('#ch-s', root), {
    data: pts, x: d => irradiance(d.g), y: d => d.p, color: '--c-p', fitFn: G => fit.f(G / 1000), lastLabel: 'ahora', yZero: true,
    xTick: v => fmt(v, 0), tip: d => `${hhmmss(d.ts)}<b class="tnum">${fmt(d.p, 0)} mW · ${fmt(irradiance(d.g), 0)} W/m²</b>`, aria: 'Potencia contra irradiancia',
  });

  $('#win-lbl', root).textContent = WIN_LBL[win];
  tween($('#energy', root), live.energyWh, 2);
  const up = Math.floor((last.ts - live.start) / 1000);
  $('#uptime', root).textContent = [up / 3600, up / 60 % 60, up % 60].map(x => String(Math.floor(x)).padStart(2, '0')).join(':');
  $('#peak', root).textContent = fmt(Math.max(...data.map(d => d.p)), 0);

  // Ficha del panel (desde Configuración)
  $('#spec-nominal', root).textContent = fmt(P.nominal, 1) + ' W';
  $('#spec-eta', root).textContent = fmt(etaN, 1) + ' %';
  $('#spec-area', root).textContent = fmt(P.area, 0);
  $('#panel-src', root).innerHTML = P.verificado ? 'Ficha técnica verificada' : '<span class="tag tag--warn">Datos de ejemplo</span>';

  // Rendimiento vs nominal y mantenimiento
  const mt = maintenance(data);
  const ratio = mt.state === 'sin-luz' ? efficiency(last.p, last.g) / etaN * 100 : mt.ratio;
  ring($('#ring', root), ratio, '--c-e', A.mant);
  $('#perf-note', root).textContent = mt.state === 'sin-luz'
    ? `Poca luz para evaluar: valor instantáneo. La marca es el umbral de ${fmt(A.mant, 0)} %.`
    : `Mediana de ${fmt(A.mantMin, 0)} min con buena luz. La marca es el umbral de mantenimiento (${fmt(A.mant, 0)} %).`;

  // Estado del sistema: ícono + texto, nunca solo color
  const sim = config.conexion.modo === 'sim', esc = SCENARIOS[config.conexion.escenario] || SCENARIOS.normal;
  const seg = Math.round((Date.now() - last.ts) / 1000);
  const rows = [
    live.paused ? ['warning', 'i-alert', 'Vista en pausa', 'Los datos siguen llegando; la vista está congelada']
      : NUBE ? (nube.error ? ['critical', 'i-alert', 'Sin conexión a la nube', 'Reintentando cada 3 s']
        : nube.vivo ? ['good', 'i-wifi', 'ESP32 en línea', `Nube · última lectura hace ${seg} s`]
          : ['warning', 'i-alert', 'ESP32 sin transmitir', `Se muestra la sesión v${nube.sesion?.id} · última lectura ${hhmmss(last.ts)}`])
      : sim ?['good', 'i-wifi', 'Simulador activo', `Escenario: ${esc.label} · 1 Hz · sin hardware`]
        : ['good', 'i-wifi', 'Conexión estable', `TCP ${config.conexion.ip}:${config.conexion.puerto} · 0 tramas perdidas`],
    mt.state === 'revisar' ? ['warning', 'i-wrench', 'Revisar o limpiar el panel', `η ${fmt(mt.median, 2)} % bajo el umbral de ${fmt(thr, 2)} % (últimos ${fmt(A.mantMin, 0)} min)`]
      : mt.state === 'ok' ? ['good', 'i-wrench', 'Mantenimiento al día', `η ${fmt(mt.median, 2)} % · umbral ${fmt(thr, 2)} %`]
        : ['muted', 'i-wrench', 'Mantenimiento sin evaluar', `Se evalúa con irradiancia ≥ ${fmt(A.mantGmin, 0)} W/m²`],
    last.t > A.tMax ? ['warning', 'i-alert', 'Temperatura alta', `${fmt(last.t, 1)} °C · umbral ${fmt(A.tMax, 0)} °C`]
      : ['good', 'i-check', 'Temperatura en rango', `${fmt(last.t, 1)} °C · umbral ${fmt(A.tMax, 0)} °C`],
    last.p < A.pMin ? ['critical', 'i-alert', 'Sin potencia', 'Falta de irradiación o circuito abierto']
      : ['good', 'i-check', 'Generando', `${fmt(last.p, decOf('p', last.p))} mW · ${fmt(irradiance(last.g), 0)} W/m²`],
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

export default { mount, show: () => { renderSessions(); render(); }, tick: render, render: () => { renderSessions(); render(); } };
