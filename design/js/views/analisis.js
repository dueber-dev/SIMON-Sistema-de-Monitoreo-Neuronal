import { METRICS as M, SESSIONS, getSession, sessionData, summarize, toCSV, val } from '../sim.js';
import { config } from '../store.js';
import { lineChart, scatter, bars, histogram, fmt, hhmmss } from '../charts.js';
import { polyfit, lstsq } from '../ml.js';
import { irradiance, efficiency, etaNominal, etaThreshold, pTheory, maintenance } from '../physics.js';
import { $, $$, ic, viewHeader, download, relDay, durFmt, timeFmt, toast, infoBtn } from '../ui.js';

let root, sid = 'v7', metric = 'p', page = 0, ticks = 0;
const PAGE = 12;
const COLS = [['v', 'Voltaje (V)', 3], ['i', 'Corriente (mA)', 2], ['t', 'Temperatura (°C)', 1], ['ldr', 'Luz LDR (%)', 1], ['g', 'Irradiancia (W/m²)', 0], ['e', 'Eficiencia (%)', 2], ['p', 'Potencia (mW)', 1]];

function mount(el) {
  root = el;
  const opts = SESSIONS.map(s => `<option value="${s.id}">Sesión ${s.id} · ${s.live ? 'en curso' : relDay(s.start) + ' ' + timeFmt(s.start)}</option>`).join('');
  const metricBtns = Object.entries(M).map(([k, m]) =>
    `<button data-metric="${k}" aria-pressed="${k === metric}"><i style="--mc:var(--c-${k})"></i>${m.label}</button>`).join('');
  el.innerHTML = viewHeader({
    eyebrow: 'Análisis', icon: 'i-analysis', title: 'Análisis de sesión', sub: 'Explora cualquier registro guardado, segundo a segundo',
    tools: `<select class="select" id="an-sel" aria-label="Sesión">${opts}</select>
      <button class="btn" id="an-export">${ic('i-download')} Exportar CSV</button>`,
  }) + `
  <div class="view-body">
    <div class="grid g-6" id="an-stats"></div>
    <div class="grid g-21">
      <article class="card glass reveal" style="--i:2">
        <div class="card__head" style="flex-wrap:wrap">
          <div><h2 class="card__title">Serie temporal <span id="an-ts-info"></span></h2><div class="card__sub" id="an-ts-sub"></div></div>
          <div class="seg seg--flat seg--metric" role="group" aria-label="Variable">${metricBtns}</div>
        </div>
        <div class="chart" id="an-ts"></div>
      </article>
      <article class="card glass reveal" style="--i:3">
        <h2 class="card__title">Distribución de potencia</h2>
        <p class="card__sub">Segundos de la sesión en cada rango de potencia (mW)</p>
        <div class="chart" id="an-hist"></div>
      </article>
    </div>
    <div class="grid g-2">
      <article class="card glass reveal" style="--i:4">
        <h2 class="card__title">Potencia vs irradiancia ${infoBtn('pg', 'potencia vs irradiancia')}</h2>
        <p class="card__sub" id="an-pg-sub"></p>
        <div class="chart" id="an-pg"></div>
      </article>
      <article class="card glass reveal" style="--i:5">
        <h2 class="card__title">Efecto de la temperatura ${infoBtn('t', 'temperatura')}</h2>
        <p class="card__sub" id="an-te-sub"></p>
        <div class="chart" id="an-te"></div>
      </article>
    </div>
    <article class="card glass reveal" style="--i:6">
      <div class="card__head"><div><h2 class="card__title">Datos</h2><p class="card__sub" id="an-tab-sub"></p></div></div>
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Hora</th><th>Segundo</th>${COLS.map(([k, l]) => `<th>${M[k] ? `<i style="--mc:var(--c-${k})"></i>` : ''}${l}</th>`).join('')}</tr></thead>
        <tbody id="an-tbody"></tbody>
      </table></div>
      <div class="pager"><span id="an-page"></span><div>
        <button class="btn" id="an-prev">${ic('i-left', 12)} Más recientes</button>
        <button class="btn" id="an-next">Anteriores ${ic('i-right', 12)}</button>
      </div></div>
    </article>
  </div>`;

  $('#an-sel', el).addEventListener('change', e => { location.hash = `#/analisis/${e.target.value}`; });
  $$('[data-metric]', el).forEach(b => b.addEventListener('click', () => {
    metric = b.dataset.metric;
    $$('[data-metric]', el).forEach(x => x.setAttribute('aria-pressed', x === b));
    renderSeries();
  }));
  $('#an-export', el).addEventListener('click', () => {
    const s = getSession(sid);
    download(s.file, toCSV(sessionData(s), config.datos.timestamp));
    toast(`Descargando ${s.file}`);
  });
  $('#an-prev', el).addEventListener('click', () => { page = Math.max(0, page - 1); renderTable(); });
  $('#an-next', el).addEventListener('click', () => { page++; renderTable(); });
}

const data = () => sessionData(getSession(sid));

function show(param) {
  if (param && SESSIONS.some(s => s.id === param)) { if (param !== sid) page = 0; sid = param; }
  $('#an-sel', root).value = sid;
  render();
}

function stat(label, color, value, unit, note, info = '') {
  return `<article class="card glass stat"><div class="stat__label"><i style="--mc:var(${color})"></i>${label}${info}</div>
    <div class="stat__value tnum">${value}<small>${unit}</small></div><div class="stat__note">${note}</div></article>`;
}

// Cada variable con su referencia: media, y además umbrales o valor teórico cuando aplica
function renderSeries() {
  const all = data(), m = M[metric], A = config.alertas;
  const pts = metric === 'e' ? all.filter(d => irradiance(d.g) >= 50) : all;
  const mean = pts.reduce((a, d) => a + val(d, metric), 0) / (pts.length || 1);
  const o = {
    series: [{ data: pts, y: d => val(d, metric), color: '--c-' + metric, name: 'Medida' }], unit: m.unit, dec: m.dec,
    zero: metric === 'p', ref: [{ y: mean, label: `media ${fmt(mean, m.dec)} ${m.unit}` }], aria: `${m.label} durante la sesión`,
  };
  let legend = '';
  if (metric === 'p') {
    o.series.push({ data: pts, y: d => pTheory(d.g, d.t), color: '--c-th', name: 'Teórica' });
    o.ref = [];
    legend = `<span><i style="--mc:var(--c-p)"></i>Medida</span><span><i style="--mc:var(--c-th)"></i>Teórica (ficha técnica)</span>`;
  }
  if (metric === 't') {
    o.ref.push({ y: A.tMax, label: `umbral ${fmt(A.tMax, 0)} °C`, color: '--warning', align: 'right' });
    o.bands = [{ from: A.tMax, color: '--warning' }];
    legend = `<span><i style="--mc:var(--warning)"></i>Umbral de alerta</span>`;
  }
  if (metric === 'e') {
    const thr = etaThreshold();
    o.ref = [{ y: etaNominal(), label: `nominal ${fmt(etaNominal(), 1)} %`, align: 'right' }, { y: thr, label: `mantenimiento ${fmt(thr, 1)} %`, color: '--warning' }];
    o.bands = [{ to: thr, color: '--warning' }];
    legend = `<span><i style="--mc:var(--ink-3)"></i>Nominal</span><span><i style="--mc:var(--warning)"></i>Umbral de mantenimiento</span>`;
  }
  $('#an-ts-info', root).innerHTML = infoBtn(metric === 'p' ? 'teorica' : metric, m.label.toLowerCase());
  $('#an-ts-sub', root).innerHTML = `<div class="legend">${legend}<span style="color:var(--ink-3)">${m.label} (${m.unit}) · ${pts.length.toLocaleString('es')} muestras</span></div>`;
  if (metric === 'e' || metric === 't') o.area = false; // que la franja de alerta se lea sin relleno encima
  lineChart($('#an-ts', root), o);
}

function renderTable() {
  const pts = data(), pages = Math.ceil(pts.length / PAGE);
  page = Math.min(page, pages - 1);
  const t0 = pts[0].ts, end = pts.length - page * PAGE, rows = pts.slice(Math.max(0, end - PAGE), end).reverse();
  const cell = (d, k, dec) => fmt(k === 'ldr' ? d.g : val(d, k), dec);
  $('#an-tbody', root).innerHTML = rows.map(d => `<tr><td>${hhmmss(d.ts)}</td><td>${Math.round((d.ts - t0) / 1000)}</td>
    ${COLS.map(([k, , dec]) => `<td>${k === 'p' ? `<b>${cell(d, k, dec)}</b>` : cell(d, k, dec)}</td>`).join('')}</tr>`).join('');
  $('#an-page', root).textContent = `Página ${page + 1} de ${pages.toLocaleString('es')} · más recientes primero`;
  $('#an-prev', root).disabled = page === 0;
  $('#an-next', root).disabled = page >= pages - 1;
}

function render() {
  if (!root || root.hidden) return;
  const s = getSession(sid), pts = data(), sm = summarize(pts), A = config.alertas;
  const mt = maintenance(pts, config, Infinity), etaN = etaNominal();
  const hot = pts.filter(d => d.t > A.tMax).length;
  const mtNote = mt.state === 'revisar' ? `<span class="st-warning">▲</span> Revisar o limpiar el panel`
    : mt.state === 'ok' ? `<span class="st-good">●</span> Mantenimiento al día` : 'Sin luz suficiente para evaluar';
  $('#an-stats', root).innerHTML = [
    stat('Energía', '--c-p', fmt(sm.energyWh, 2), 'Wh', `en ${durFmt(sm.dur)}`, infoBtn('energia', 'energía')),
    stat('Potencia media', '--c-p', fmt(sm.meanP, 0), 'mW', `pico ${fmt(sm.peak, 0)} mW`, infoBtn('p', 'potencia')),
    stat('Eficiencia', '--c-e', mt.median ? fmt(mt.median, 2) : '—', '%', `nominal ${fmt(etaN, 1)} % · mediana con buena luz`, infoBtn('e', 'eficiencia')),
    stat('Rendimiento vs nominal', '--c-e', mt.ratio ? fmt(mt.ratio, 0) : '—', '%', `${mtNote} · umbral ${fmt(A.mant, 0)} %`, infoBtn('mant', 'mantenimiento')),
    stat('Temperatura máx.', '--c-t', fmt(sm.maxT, 1), '°C', hot ? `<span class="st-warning">▲</span> ${durFmt(hot)} sobre ${fmt(A.tMax, 0)} °C` : `nunca sobre ${fmt(A.tMax, 0)} °C`, infoBtn('t', 'temperatura')),
    stat('Irradiancia media', '--c-g', fmt(irradiance(sm.meanG), 0), 'W/m²', `estimada · LDR ${fmt(sm.meanG, 0)} %`, infoBtn('g', 'irradiancia')),
  ].join('');

  renderSeries();

  const hist = histogram(pts.map(d => d.p), 14);
  bars($('#an-hist', root), {
    color: '--c-p', aria: 'Distribución de potencia',
    bins: hist.map(b => ({ label: fmt(b.lo, 0), value: b.count, tip: `${fmt(b.lo, 0)}–${fmt(b.hi, 0)} mW<b class="tnum">${b.count.toLocaleString('es')} s · ${fmt(b.count / pts.length * 100, 1)} %</b>` })),
  });

  const G = d => irradiance(d.g);
  const fit = polyfit(pts.map(d => G(d) / 1000), pts.map(d => d.p), 2), f = g => fit.f(g / 1000);
  $('#an-pg-sub', root).textContent = `mW vs W/m² · cada punto = 1 s · ajuste cuadrático · R² ${fmt(fit.r2, 2)}`;
  scatter($('#an-pg', root), {
    data: pts, x: G, y: d => d.p, color: '--c-p', fitFn: f, last: false, recency: false, yZero: true,
    xTick: v => fmt(v, 0), tip: d => `${hhmmss(d.ts)}<b class="tnum">${fmt(d.p, 0)} mW · ${fmt(G(d), 0)} W/m²</b>`, aria: 'Potencia contra irradiancia',
  });

  // Residuo de potencia (descontando la irradiancia) contra temperatura
  const res = pts.map(d => ({ ...d, r: d.p - f(G(d)) }));
  const [b0, b1] = lstsq(res.map(d => [1, d.t]), res.map(d => d.r));
  $('#an-te-sub', root).textContent = `Potencia sobre/bajo lo esperado por la irradiancia · pendiente ${fmt(b1, 1)} mW por °C`;
  scatter($('#an-te', root), {
    data: res, x: d => d.t, y: d => d.r, color: '--c-t', fitFn: t => b0 + b1 * t, last: false, recency: false,
    xTick: v => fmt(v, 0) + ' °C', tip: d => `${hhmmss(d.ts)}<b class="tnum">${d.r >= 0 ? '+' : ''}${fmt(d.r, 0)} mW · ${fmt(d.t, 1)} °C</b>`, aria: 'Residuo de potencia contra temperatura',
  });

  $('#an-tab-sub', root).textContent = `${s.file} · ${pts.length.toLocaleString('es')} muestras · 1 por segundo · irradiancia y eficiencia calculadas`;
  renderTable();
}

// La sesión en curso se refresca cada 10 s; las guardadas no cambian
function tick() { if (sid === 'v7' && ++ticks % 10 === 0) render(); }

export default { mount, show, tick, render };
