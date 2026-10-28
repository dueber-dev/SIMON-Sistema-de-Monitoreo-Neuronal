import { SESSIONS, getSession, sessionData, sessionStart, summarize, toCSV } from '../sim.js';
import { config } from '../store.js';
import { lineChart, spark, fmt } from '../charts.js';
import { maintenance } from '../physics.js';
import { $, $$, ic, viewHeader, download, toast, relDay, durFmt, timeFmt, dayKey, dateFmt } from '../ui.js';

let root, query = '', selDay = null, cmpA = 'v6', cmpB = 'v5', ticks = 0;
const now = new Date();
let calY = now.getFullYear(), calM = now.getMonth();

function mount(el) {
  root = el;
  const opts = sel => SESSIONS.map(s => `<option value="${s.id}" ${s.id === sel ? 'selected' : ''}>Sesión ${s.id}</option>`).join('');
  el.innerHTML = viewHeader({
    eyebrow: 'Sesiones', icon: 'i-sessions', title: 'Historial de sesiones', sub: 'Cada sesión es un archivo CSV guardado por el sistema',
    tools: `<div class="affix"><input class="input" type="search" id="se-q" placeholder="Buscar sesión o fecha" aria-label="Buscar sesión"></div>`,
  }) + `
  <div class="view-body">
    <div class="grid g-4" id="se-stats"></div>
    <div class="grid g-12">
      <article class="card glass reveal" style="--i:2">
        <h2 class="card__title">Calendario</h2>
        <p class="card__sub">Toca un día con registros para filtrar la lista</p>
        <div class="cal" id="se-cal"></div>
      </article>
      <article class="card glass reveal" style="--i:3">
        <div class="card__head" style="flex-wrap:wrap">
          <div><h2 class="card__title">Comparar sesiones</h2>
            <div class="legend"><span><i style="--mc:var(--c-p)"></i>Sesión A</span><span><i style="--mc:var(--c-ref)"></i>Sesión B</span><span style="color:var(--ink-3)">mW según el tiempo desde el inicio</span></div></div>
          <div style="display:flex;gap:8px">
            <select class="select" id="se-a" aria-label="Sesión A">${opts(cmpA)}</select>
            <select class="select" id="se-b" aria-label="Sesión B">${opts(cmpB)}</select>
          </div>
        </div>
        <div class="chart" id="se-cmp"></div>
        <div class="table-wrap"><table class="table" id="se-cmp-tab"></table></div>
      </article>
    </div>
    <article class="card glass reveal" style="--i:4">
      <div class="card__head"><div><h2 class="card__title">Todas las sesiones</h2><p class="card__sub" id="se-count"></p></div>
        <button class="link" id="se-clear" hidden>Quitar filtro</button></div>
      <div style="margin-top:12px">
        <div class="srow srow--head"><span></span><span>Sesión</span><span>Fecha</span><span class="h-spark">Potencia</span>
          <span class="num">Duración</span><span class="num">Muestras</span><span class="num">Energía</span><span></span></div>
        <div id="se-list"></div>
        <p class="empty" id="se-empty" hidden>Ninguna sesión coincide con el filtro.</p>
      </div>
    </article>
  </div>`;

  $('#se-q', el).addEventListener('input', e => { query = e.target.value.trim().toLowerCase(); filter(); });
  $('#se-clear', el).addEventListener('click', () => { query = ''; selDay = null; $('#se-q', el).value = ''; renderCal(); filter(); });
  $('#se-a', el).addEventListener('change', e => { cmpA = e.target.value; renderCompare(); });
  $('#se-b', el).addEventListener('change', e => { cmpB = e.target.value; renderCompare(); });
  el.addEventListener('click', e => {
    const dl = e.target.closest('[data-dl]');
    if (dl) { const s = getSession(dl.dataset.dl); download(s.file, toCSV(sessionData(s), config.datos.timestamp)); toast(`Descargando ${s.file}`); }
    const day = e.target.closest('[data-day]');
    if (day) { selDay = selDay === day.dataset.day ? null : day.dataset.day; renderCal(); filter(); }
    const nav = e.target.closest('[data-cal]');
    if (nav) { calM += +nav.dataset.cal; if (calM < 0) { calM = 11; calY--; } if (calM > 11) { calM = 0; calY++; } renderCal(); }
  });
}

function renderStats() {
  const sums = SESSIONS.map(s => summarize(sessionData(s)));
  const secs = sums.reduce((a, s) => a + s.dur, 0);
  const tile = (label, value, unit, note) => `<article class="card glass stat"><div class="stat__label">${label}</div>
    <div class="stat__value tnum">${value}<small>${unit}</small></div><div class="stat__note">${note}</div></article>`;
  $('#se-stats', root).innerHTML = [
    tile('Sesiones', SESSIONS.length, '', '1 en curso'),
    tile('Tiempo registrado', fmt(secs / 3600, 1), 'h', durFmt(secs)),
    tile('Energía total', fmt(sums.reduce((a, s) => a + s.energyWh, 0), 2), 'Wh', 'suma de todas las sesiones'),
    tile('Muestras', sums.reduce((a, s) => a + s.n, 0).toLocaleString('es'), '', 'filas de CSV para el modelo'),
  ].join('');
}

function renderCal() {
  const days = new Set(SESSIONS.map(s => dayKey(sessionStart(s))));
  const first = new Date(calY, calM, 1), lead = (first.getDay() + 6) % 7, n = new Date(calY, calM + 1, 0).getDate();
  const todayK = dayKey(Date.now());
  let cells = ['L', 'M', 'X', 'J', 'V', 'S', 'D'].map(d => `<span class="cal__dow">${d}</span>`).join('');
  for (let k = 0; k < lead; k++) cells += '<span class="cal__day is-out"></span>';
  for (let d = 1; d <= n; d++) {
    const key = `${calY}-${calM}-${d}`, has = days.has(key);
    const cls = ['cal__day', has && 'has', key === todayK && 'is-today', key === selDay && 'is-sel'].filter(Boolean).join(' ');
    cells += has ? `<button class="${cls}" data-day="${key}" aria-pressed="${key === selDay}" aria-label="${d}: con registros">${d}</button>` : `<span class="${cls}">${d}</span>`;
  }
  const m = first.toLocaleDateString('es', { month: 'long' }), month = `${m[0].toUpperCase()}${m.slice(1)} ${calY}`;
  $('#se-cal', root).innerHTML = `<div class="cal__head"><b>${month}</b><div class="cal__nav">
      <button data-cal="-1" aria-label="Mes anterior">${ic('i-left', 12)}</button><button data-cal="1" aria-label="Mes siguiente">${ic('i-right', 12)}</button></div></div>
    <div class="cal__grid">${cells}</div>
    <div class="cal__legend"><span><i style="background:var(--c-p)"></i>Con registros</span><span><i style="box-shadow:inset 0 0 0 1.5px var(--ink-3)"></i>Hoy</span></div>`;
}

function renderCompare() {
  const prep = id => { const s = getSession(id), d = sessionData(s), t0 = d[0]?.ts ?? 0; return { s, d, pts: d.map(x => ({ e: (x.ts - t0) / 1000, p: x.p })), sm: summarize(d), mt: maintenance(d, config, Infinity) }; };
  const A = prep(cmpA), B = prep(cmpB);
  lineChart($('#se-cmp', root), {
    series: [
      { data: A.pts, y: d => d.p, color: '--c-p', name: `Sesión ${A.s.id}` },
      { data: B.pts, y: d => d.p, color: '--c-ref', name: `Sesión ${B.s.id}` },
    ],
    x: d => d.e, xKind: 'elapsed', unit: 'mW', dec: 0, zero: true, density: 5, aria: 'Comparación de potencia entre sesiones',
  });
  const row = (label, a, b, dec, unit) => {
    const d = a - b;
    return `<tr><td>${label}</td><td>${fmt(a, dec)} ${unit}</td><td>${fmt(b, dec)} ${unit}</td><td>${d >= 0 ? '+' : ''}${fmt(d, dec)} ${unit}</td></tr>`;
  };
  $('#se-cmp-tab', root).innerHTML = `<thead><tr><th></th><th>Sesión ${A.s.id}</th><th>Sesión ${B.s.id}</th><th>Diferencia</th></tr></thead><tbody>
    ${row('Energía', A.sm.energyWh, B.sm.energyWh, 2, 'Wh')}
    ${row('Potencia media', A.sm.meanP, B.sm.meanP, 0, 'mW')}
    ${row('Potencia pico', A.sm.peak, B.sm.peak, 0, 'mW')}
    ${row('Eficiencia (mediana)', A.mt.median ?? NaN, B.mt.median ?? NaN, 2, '%')}
    ${row('Rendimiento vs nominal', A.mt.ratio ?? NaN, B.mt.ratio ?? NaN, 0, '%')}
    ${row('Temperatura media', A.sm.meanT, B.sm.meanT, 1, '°C')}</tbody>`;
}

function renderList() {
  $('#se-list', root).innerHTML = SESSIONS.map(s => {
    const d = sessionData(s), sm = summarize(d), start = sessionStart(s);
    const tag = (s.live ? '<span class="tag tag--live">En vivo</span>' : s.estado === 'interrumpida' ? '<span class="tag tag--warn">Interrumpida</span>' : s.nota ? `<span class="tag">${s.nota}</span>` : '')
      + (!s.live && maintenance(d, config, Infinity).state === 'revisar' ? `<span class="tag tag--warn">${ic('i-wrench', 11)} Revisar panel</span>` : '');
    const search = `${s.id} ${s.file} ${relDay(start)} ${dateFmt(start)}`.toLowerCase();
    return `<div class="srow" data-id="${s.id}" data-rowday="${dayKey(start)}" data-search="${search}">
      <span class="row__icon">${ic('i-sessions', 16, 'style="color:var(--ink-2)"')}</span>
      <span class="srow__name"><b>Sesión ${s.id} ${tag}</b><span>${s.file}</span></span>
      <span class="srow__date">${relDay(start)} · ${timeFmt(start)}</span>
      <span class="srow__spark" data-spark="${s.id}"></span>
      <span class="num">${durFmt(sm.dur)}</span>
      <span class="num">${sm.n.toLocaleString('es')}</span>
      <span class="num">${fmt(sm.energyWh, 2)}<small>Wh</small></span>
      <span class="srow__actions"><a class="btn" href="#/analisis/${s.id}">${ic('i-analysis')} Analizar</a><button class="btn" data-dl="${s.id}">${ic('i-download')} CSV</button></span>
    </div>`;
  }).join('');
  $$('[data-spark]', root).forEach(el => {
    const d = sessionData(getSession(el.dataset.spark)), step = Math.max(1, Math.floor(d.length / 60));
    spark(el, d.filter((_, k) => k % step === 0), x => x.p, '--c-p');
  });
  filter();
}

function filter() {
  let shown = 0;
  $$('.srow[data-id]', root).forEach(r => {
    const ok = (!query || r.dataset.search.includes(query)) && (!selDay || r.dataset.rowday === selDay);
    r.classList.toggle('is-hidden', !ok); if (ok) shown++;
  });
  $('#se-empty', root).hidden = shown > 0;
  $('#se-clear', root).hidden = !query && !selDay;
  const [y, m, d] = selDay ? selDay.split('-').map(Number) : [];
  $('#se-count', root).textContent = selDay ? `${shown} de ${SESSIONS.length} · ${dateFmt(new Date(y, m, d))}` : `${shown} de ${SESSIONS.length} sesiones`;
}

function render() {
  if (!root || root.hidden) return;
  renderStats(); renderCal(); renderCompare(); renderList();
}

export default { mount, show: render, render, tick: () => { if (root && !root.hidden && ++ticks % 10 === 0) { renderStats(); renderList(); } } };
