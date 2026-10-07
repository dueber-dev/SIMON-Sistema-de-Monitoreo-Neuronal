import { METRICS as M, SESSIONS, getSession, sessionData, summarize, toCSV } from '../sim.js';
import { config } from '../store.js';
import { lineChart, scatter, bars, histogram, fmt, hhmmss } from '../charts.js';
import { polyfit, lstsq, efficiency } from '../ml.js';
import { $, $$, ic, viewHeader, download, relDay, durFmt, timeFmt, toast } from '../ui.js';

let root, sid = 'v7', metric = 'p', page = 0, ticks = 0;
const PAGE = 12;

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
          <div><h2 class="card__title">Serie temporal</h2><p class="card__sub" id="an-ts-sub"></p></div>
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
        <h2 class="card__title">Potencia vs irradiancia</h2>
        <p class="card__sub" id="an-pg-sub"></p>
        <div class="chart" id="an-pg"></div>
      </article>
      <article class="card glass reveal" style="--i:5">
        <h2 class="card__title">Efecto de la temperatura</h2>
        <p class="card__sub" id="an-te-sub"></p>
        <div class="chart" id="an-te"></div>
      </article>
    </div>
    <article class="card glass reveal" style="--i:6">
      <div class="card__head"><div><h2 class="card__title">Datos</h2><p class="card__sub" id="an-tab-sub"></p></div></div>
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Hora</th><th>Segundo</th>${Object.entries(M).filter(([k]) => k !== 'p').concat([['p', M.p]]).map(([k, m]) => `<th><i style="--mc:var(--c-${k})"></i>${m.label} (${m.unit})</th>`).join('')}</tr></thead>
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

function stat(label, color, value, unit, note) {
  return `<article class="card glass stat"><div class="stat__label"><i style="--mc:var(${color})"></i>${label}</div>
    <div class="stat__value tnum">${value}<small>${unit}</small></div><div class="stat__note">${note}</div></article>`;
}

function renderSeries() {
  const pts = data(), m = M[metric], mean = pts.reduce((a, d) => a + d[metric], 0) / pts.length;
  $('#an-ts-sub', root).textContent = `${m.label} (${m.unit}) · ${pts.length.toLocaleString('es')} muestras`;
  lineChart($('#an-ts', root), {
    series: [{ data: pts, y: d => d[metric], color: '--c-' + metric }], unit: m.unit, dec: m.dec,
    zero: metric === 'p', ref: [{ y: mean, label: `media ${fmt(mean, m.dec)} ${m.unit}` }], aria: `${m.label} durante la sesión`,
  });
}

function renderTable() {
  const pts = data(), pages = Math.ceil(pts.length / PAGE);
  page = Math.min(page, pages - 1);
  const t0 = pts[0].ts, end = pts.length - page * PAGE, rows = pts.slice(Math.max(0, end - PAGE), end).reverse();
  $('#an-tbody', root).innerHTML = rows.map(d => `<tr><td>${hhmmss(d.ts)}</td><td>${Math.round((d.ts - t0) / 1000)}</td>
    <td>${fmt(d.v, 3)}</td><td>${fmt(d.i, 2)}</td><td>${fmt(d.t, 1)}</td><td>${fmt(d.g, 1)}</td><td><b>${fmt(d.p, 1)}</b></td></tr>`).join('');
  $('#an-page', root).textContent = `Página ${page + 1} de ${pages.toLocaleString('es')} · más recientes primero`;
  $('#an-prev', root).disabled = page === 0;
  $('#an-next', root).disabled = page >= pages - 1;
}

function render() {
  if (!root || root.hidden) return;
  const s = getSession(sid), pts = data(), sm = summarize(pts), P = config.panel;
  const effs = pts.filter(d => d.g > 5).map(d => efficiency(d.p, d.g));
  const effMean = effs.reduce((a, v) => a + v, 0) / (effs.length || 1);
  $('#an-stats', root).innerHTML = [
    stat('Energía', '--c-p', fmt(sm.energyWh, 2), 'Wh', `en ${durFmt(sm.dur)}`),
    stat('Potencia media', '--c-p', fmt(sm.meanP, 0), 'mW', `pico ${fmt(sm.peak, 0)} mW`),
    stat('Rendimiento medio', '--c-p', fmt(sm.meanP / (P.nominal * 10), 0), '%', `de ${fmt(P.nominal, 1)} W nominal`),
    stat('Eficiencia media', '--c-ml', fmt(effMean, 1), '%', 'η = P / (G · A)'),
    stat('Temperatura máx.', '--c-t', fmt(sm.maxT, 1), '°C', `media ${fmt(sm.meanT, 1)} °C`),
    stat('Irradiancia media', '--c-g', fmt(sm.meanG, 0), '%', `≈ ${fmt(sm.meanG * config.sensores.ldrFactor, 0)} W/m²`),
  ].join('');

  renderSeries();

  const hist = histogram(pts.map(d => d.p), 14);
  bars($('#an-hist', root), {
    color: '--c-p', aria: 'Distribución de potencia',
    bins: hist.map(b => ({ label: fmt(b.lo, 0), value: b.count, tip: `${fmt(b.lo, 0)}–${fmt(b.hi, 0)} mW<b class="tnum">${b.count.toLocaleString('es')} s · ${fmt(b.count / pts.length * 100, 1)} %</b>` })),
  });

  const fit = polyfit(pts.map(d => d.g), pts.map(d => d.p), 2);
  $('#an-pg-sub', root).textContent = `Cada punto = 1 s · ajuste cuadrático · R² ${fmt(fit.r2, 2)}`;
  scatter($('#an-pg', root), {
    data: pts, x: d => d.g, y: d => d.p, color: '--c-p', fitFn: fit.f, last: false, recency: false, yZero: true,
    xTick: v => fmt(v, 0) + ' %', tip: d => `${hhmmss(d.ts)}<b class="tnum">${fmt(d.p, 0)} mW · ${fmt(d.g, 1)} %</b>`, aria: 'Potencia contra irradiancia',
  });

  // Residuo de potencia (descontando la irradiancia) contra temperatura
  const res = pts.map(d => ({ ...d, r: d.p - fit.f(d.g) }));
  const [b0, b1] = lstsq(res.map(d => [1, d.t]), res.map(d => d.r));
  $('#an-te-sub', root).textContent = `Potencia sobre/bajo lo esperado por la irradiancia · pendiente ${fmt(b1, 1)} mW por °C`;
  scatter($('#an-te', root), {
    data: res, x: d => d.t, y: d => d.r, color: '--c-t', fitFn: t => b0 + b1 * t, last: false, recency: false,
    xTick: v => fmt(v, 0) + ' °C', tip: d => `${hhmmss(d.ts)}<b class="tnum">${d.r >= 0 ? '+' : ''}${fmt(d.r, 0)} mW · ${fmt(d.t, 1)} °C</b>`, aria: 'Residuo de potencia contra temperatura',
  });

  $('#an-tab-sub', root).textContent = `${s.file} · ${pts.length.toLocaleString('es')} muestras · 1 por segundo`;
  renderTable();
}

// La sesión en curso se refresca cada 10 s; las guardadas no cambian
function tick() { if (sid === 'v7' && ++ticks % 10 === 0) render(); }

export default { mount, show, tick, render };
