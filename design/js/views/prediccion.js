import { live } from '../sim.js';
import { config } from '../store.js';
import { lineChart, scatter, bars, hbars, histogram, fmt, hhmmss } from '../charts.js';
import { getModel, train, efficiency, effNube, pedirPredicciones, nubeModelo, revisarLocal, reentrenarLocal, pronostico } from '../ml.js';
import { irradiance, pTheory, areaM2 } from '../physics.js';
import { $, ic, viewHeader, tween, toast, timeFmt, infoBtn } from '../ui.js';

let root, wiG = 800, wiT = 35, pron = null, pronDias = 3;

function mount(el) {
  root = el;
  el.innerHTML = viewHeader({
    eyebrow: 'Predicción ML', icon: 'i-ml', title: 'Eficiencia del panel', sub: 'Lo que mide el panel frente a lo que predice el modelo',
    tools: `<button class="btn" id="ml-train">${ic('i-refresh')} Reentrenar</button>`,
  }) + `
  <div class="view-body">
    <div class="banner glass reveal">${ic('i-info', 18)}<div id="ml-banner"><b>Modelo en la nube.</b> La eficiencia predicha sale del <b>gradient boosting</b> entrenado con <code>ml/entrenar_modelo.py</code> (luz de la LDR, temperatura, hora y ángulo → potencia del panel limpio). Corre dentro del <b>Worker de Cloudflare</b> en <code>/simon/api/predecir</code>. «Reentrenar» ajusta en este navegador el modelo local (regresión polinómica) con los últimos 30 min; ese es el que usa el simulador de escenarios.</div></div>

    <div class="grid g-3">
      <article class="hero-ml reveal" style="--i:1">
        <span class="hero__tag" style="position:static;align-self:flex-start">${ic('i-ml', 13)} Ahora</span>
        <div><span class="hero__label">Eficiencia predicha</span>
          <div class="hero__fig"><span id="ml-pred">—</span><small>%</small></div></div>
        <div class="hero__stats">
          <div class="hero__stat"><b class="tnum" id="ml-real">—</b><span>Eficiencia real</span></div>
          <div class="hero__stat"><b class="tnum" id="ml-diff">—</b><span>Diferencia</span></div>
        </div>
      </article>
      <article class="card glass reveal" style="--i:2">
        <div class="card__head"><div><h2 class="card__title">Modelo</h2><p class="card__sub" id="ml-sub">Gradient boosting · Cloudflare Worker</p></div>
          <span class="badge" style="--mc:var(--c-ml)">${ic('i-ml', 15)}</span></div>
        <div class="kv">
          <div><b id="ml-r2">—</b><span>R²</span></div>
          <div><b id="ml-mae">—</b><span>MAE (pp)</span></div>
          <div><b id="ml-rmse">—</b><span>RMSE (pp)</span></div>
        </div>
        <div class="feat"><span>Luz (LDR)</span><span>Temperatura</span><span>Hora</span><span>Ángulo 50°</span></div>
        <p class="card__sub" id="ml-trained" style="margin-top:12px"></p>
      </article>
      <article class="card glass reveal" style="--i:3">
        <h2 class="card__title">Importancia de variables</h2>
        <p class="card__sub">Modelo local (regresión) · |β| × desviación estándar</p>
        <div id="ml-imp" style="margin-top:12px"></div>
      </article>
    </div>

    <div class="grid g-21">
      <article class="card glass reveal" style="--i:4">
        <h2 class="card__title">Eficiencia real vs predicha ${infoBtn('ml', 'eficiencia predicha')}</h2>
        <div class="legend"><span><i style="--mc:var(--c-e)"></i>Real (medida)</span><span><i style="--mc:var(--c-ref)"></i>Predicha por el modelo</span><span style="color:var(--ink-3)">% · últimos 5 min</span></div>
        <div class="chart" id="ml-line"></div>
      </article>
      <article class="card glass reveal" style="--i:5">
        <h2 class="card__title">Distribución del error</h2>
        <p class="card__sub">Predicha − real, en puntos porcentuales</p>
        <div class="chart" id="ml-err"></div>
      </article>
    </div>

    <article class="card glass reveal" style="--i:5.4" id="ml-deg-card" hidden>
      <div class="card__head" style="flex-wrap:wrap">
        <div><h2 class="card__title">Proyección de mantenimiento</h2>
          <p class="card__sub">Rendimiento relativo diario = potencia medida ÷ potencia que predice el modelo para el panel limpio</p></div>
        <span class="badge" style="--mc:var(--warning)">${ic('i-wrench', 15)}</span>
      </div>
      <div class="pron-dias" id="ml-deg-kpis"></div>
      <div class="legend"><span><i style="--mc:var(--c-e)"></i>Día de operación normal</span><span><i style="--mc:var(--warning)"></i>Día con polvo o sombra (bitácora)</span><span><i style="--mc:var(--c-ref)"></i>Tendencia proyectada</span></div>
      <div class="chart" id="ml-deg-ch"></div>
      <p class="card__sub" id="ml-deg-note" style="margin-top:10px"></p>
    </article>

    <article class="card glass reveal" style="--i:5.5" id="ml-pron-card" hidden>
      <div class="card__head" style="flex-wrap:wrap">
        <div><h2 class="card__title">Pronóstico de los próximos días</h2>
          <p class="card__sub" id="ml-pron-sub">Clima pronosticado (Open-Meteo) → modelo local</p></div>
        <div style="display:flex;gap:6px" role="group" aria-label="Días">
          <button class="btn btn--sm" data-pdias="1" aria-pressed="false">1 día</button>
          <button class="btn btn--sm" data-pdias="3" aria-pressed="true">3 días</button>
          <button class="btn btn--sm" data-pdias="7" aria-pressed="false">7 días</button>
        </div>
      </div>
      <div class="pron-dias" id="ml-pron-dias"></div>
      <div class="legend"><span><i style="--mc:var(--c-p)"></i>Potencia predicha (panel limpio)</span><span style="color:var(--ink-3)">mW · cada 15 min</span></div>
      <div class="chart" id="ml-pron-p"></div>
      <div class="pron-2">
        <div><div class="legend"><span><i style="--mc:var(--c-e)"></i>Eficiencia predicha</span><span style="color:var(--ink-3)">%</span></div><div class="chart chart--sm" id="ml-pron-e"></div></div>
        <div><div class="legend"><span><i style="--mc:var(--c-g)"></i>Irradiancia pronosticada</span><span style="color:var(--ink-3)">W/m² en el plano del panel</span></div><div class="chart chart--sm" id="ml-pron-g"></div></div>
      </div>
    </article>

    <div class="grid g-12">
      <article class="card glass reveal" style="--i:6">
        <h2 class="card__title">Predicha vs real</h2>
        <p class="card__sub">La diagonal es la predicción perfecta</p>
        <div class="chart" id="ml-sc"></div>
      </article>
      <article class="card glass reveal" style="--i:7">
        <h2 class="card__title">Simulador de escenarios</h2>
        <p class="card__sub">Prueba otras condiciones y contrasta el modelo con el cálculo teórico ${infoBtn('teorica', 'cálculo teórico')}</p>
        <div class="whatif">
          <div>
            <div class="field"><span class="lbl">Irradiancia</span><div class="range-row"><input type="range" id="wi-g" min="50" max="1000" step="10" value="${wiG}" aria-label="Irradiancia"><output id="wi-g-v"></output></div></div>
            <div class="field" style="margin-top:14px"><span class="lbl">Temperatura del panel</span><div class="range-row"><input type="range" id="wi-t" min="15" max="70" value="${wiT}" aria-label="Temperatura"><output id="wi-t-v"></output></div></div>
            <div class="whatif__out">
              <div><b class="tnum" id="wi-p">—</b><span>Potencia · modelo</span></div>
              <div><b class="tnum" id="wi-e">—</b><span>Eficiencia · modelo</span></div>
              <div><b class="tnum" id="wi-pt">—</b><span>Potencia · teórica</span></div>
              <div><b class="tnum" id="wi-et">—</b><span>Eficiencia · teórica</span></div>
            </div>
          </div>
          <div><div class="legend" style="margin:0"><span><i style="--mc:var(--c-ref)"></i>Modelo</span><span><i style="--mc:var(--c-th)"></i>Teórica</span><span style="color:var(--ink-3)">eficiencia según la temperatura, a la irradiancia elegida</span></div><div class="chart chart--sm" id="ml-curve"></div></div>
        </div>
      </article>
    </div>
  </div>`;

  $('#ml-train', el).addEventListener('click', async e => {
    const btn = e.currentTarget;
    if (nubeModelo.local) {
      btn.disabled = true; toast('Reentrenando con todas las sesiones de la nube…');
      try {
        const j = await reentrenarLocal();
        toast(`Modelo reentrenado en tu computadora: ${j.sesiones} sesiones, ${j.minutos.toLocaleString('es')} min · R² ${fmt(j.gb.R2, 2)}`);
        cargarPronostico(true);
      } catch (err) { toast('No se pudo reentrenar: ' + err.message); }
      btn.disabled = false; render(); return;
    }
    const m = train(live.data.slice(-1800));
    render();
    toast(`Modelo local reentrenado con ${m.metrics.n.toLocaleString('es')} muestras · R² ${fmt(m.metrics.r2, 2)}`);
  });
  el.addEventListener('click', e => {
    const b = e.target.closest('[data-pdias]');
    if (!b) return;
    pronDias = +b.dataset.pdias;
    el.querySelectorAll('[data-pdias]').forEach(x => x.setAttribute('aria-pressed', x === b));
    cargarPronostico(true);
  });
  // ¿Se abrió desde ml/servidor_local.py? Entonces el modelo corre en esta computadora.
  const sondeo = async () => {
    const j = await revisarLocal();
    if (!j) return;
    try { render(); } catch {}
    if (j.listo) cargarPronostico(); else setTimeout(sondeo, 3000);
  };
  sondeo();
  $('#wi-g', el).addEventListener('input', e => { wiG = +e.target.value; renderWhatIf(); });
  $('#wi-t', el).addEventListener('input', e => { wiT = +e.target.value; renderWhatIf(); });
}

// Eficiencia predicha de una lectura: la del modelo de la nube; si todavía no llega, la del ajuste local
const predEff = (mdl, d) => effNube(d) ?? mdl.predictEff(d.g, d.t);

function renderLive() {
  const mdl = getModel(), last = live.data[live.data.length - 1];
  if (!last) return;
  pedirPredicciones(live.data.slice(-1800)).then(llego => { if (llego) render(); });
  const pred = predEff(mdl, last), real = efficiency(last.p, last.g);
  tween($('#ml-pred', root), pred, 2, 'ml-pred');
  $('#ml-real', root).textContent = fmt(real, 2) + ' %';
  $('#ml-diff', root).textContent = `${pred - real >= 0 ? '+' : ''}${fmt(pred - real, 2)} pp`;
  const pts = live.data.slice(-300).filter(d => d.g > 5);
  lineChart($('#ml-line', root), {
    series: [
      { data: pts, y: d => efficiency(d.p, d.g), color: '--c-e', name: 'Real' },
      { data: pts, y: d => predEff(mdl, d), color: '--c-ref', name: 'Predicha' },
    ],
    unit: '%', dec: 2, aria: 'Eficiencia real y predicha en el tiempo',
  });
}

async function cargarPronostico(forzar) {
  if (!nubeModelo.local?.listo || (pron && !forzar)) return renderPronostico();
  try { pron = await pronostico(pronDias); } catch (err) { pron = { error: err.message }; }
  renderPronostico();
}

const diaKey = ts => { const d = new Date(ts); return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`; };
function renderPronostico() {
  const card = $('#ml-pron-card', root);
  if (!card) return;
  card.hidden = !nubeModelo.local;
  if (!nubeModelo.local || root.hidden) return;
  if (!pron) { $('#ml-pron-sub', root).textContent = nubeModelo.local.listo ? 'Pidiendo el pronóstico del clima…' : 'Esperando a que termine el entrenamiento…'; return; }
  if (pron.error) { $('#ml-pron-sub', root).textContent = 'Sin pronóstico: ' + pron.error; return; }
  const pts = pron.filas.map(([ts, g, t, p, e, n]) => ({ ts, g, t, p, e, n }));
  const xf = v => new Date(v).toLocaleString('es', { weekday: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  $('#ml-pron-sub', root).textContent = `${pron.fuente} · panel a 50° al sur · T del panel = ambiente + 0,0275 °C por W/m²`;
  $('#ml-pron-dias', root).innerHTML = Object.entries(pron.energia_dia_Wh).map(([d, wh]) => {
    const f = new Date(d + 'T12:00'), del = pts.filter(x => diaKey(x.ts) === diaKey(f)), pk = Math.max(0, ...del.map(x => x.p));
    const ef = del.filter(x => x.e != null && x.g > 200), em = ef.length ? ef.reduce((a, x) => a + x.e, 0) / ef.length : null;
    return `<div class="pron-dia"><span>${f.toLocaleDateString('es', { weekday: 'long', day: 'numeric', month: 'short' })}</span>
      <b class="tnum">${fmt(wh, 2)} <small>Wh</small></b><span>pico ${fmt(pk, 0)} mW · η ${em == null ? '—' : fmt(em, 2) + ' %'}</span></div>`;
  }).join('');
  lineChart($('#ml-pron-p', root), { series: [{ data: pts, y: d => d.p, color: '--c-p', name: 'Potencia' }], unit: 'mW', dec: 0, zero: true, xFmt: xf, aria: 'Potencia predicha para los próximos días' });
  lineChart($('#ml-pron-e', root), { series: [{ data: pts.filter(d => d.e != null && d.g > 200), y: d => d.e, color: '--c-e', name: 'Eficiencia' }], unit: '%', dec: 2, area: false, xFmt: xf, aria: 'Eficiencia predicha' });
  lineChart($('#ml-pron-g', root), { series: [{ data: pts, y: d => d.g, color: '--c-g', name: 'Irradiancia' }], unit: 'W/m²', dec: 0, zero: true, xFmt: xf, aria: 'Irradiancia pronosticada' });
}

function renderDegradacion() {
  const card = $('#ml-deg-card', root), D = nubeModelo.local?.degradacion;
  if (!card) return;
  card.hidden = !D;
  if (!D || root.hidden) return;
  const fecha = ms => new Date(ms).toLocaleDateString('es', { weekday: 'short', day: 'numeric', month: 'short' });
  const pct = v => fmt(v * 100, 1) + ' %';
  if (D.estado !== 'ok') { $('#ml-deg-note', root).textContent = 'Faltan días con buena luz para proyectar (mínimo 3 de operación normal).'; return; }
  const pend = D.pendiente_pct_dia, [rap, len] = D.banda_dias;
  const kpi = (lbl, val, nota) => `<div class="pron-dia"><span>${lbl}</span><b class="tnum">${val}</b><span>${nota}</span></div>`;
  $('#ml-deg-kpis', root).innerHTML = [
    kpi('Rendimiento hoy (tendencia)', pct(D.pr_hoy), `umbral de mantenimiento ${pct(D.umbral)}`),
    kpi('Tendencia', `${pend >= 0 ? '+' : ''}${fmt(pend, 2)} <small>% por día</small>`, `± ${fmt(D.se_pct_dia * 1.96, 2)} % (95 %) · ${D.dias_normales} días`),
    kpi('Cruce del umbral', D.dias_para_umbral == null ? 'sin cruce' : `${fmt(D.dias_para_umbral, 0)} <small>días</small>`,
      D.fecha_umbral_ms ? `≈ ${fecha(D.fecha_umbral_ms)} · banda ${rap == null ? '—' : fmt(rap, 0)} días a ${len == null ? 'sin cruce' : fmt(len, 0) + ' días'}` : 'la tendencia actual no baja'),
  ].join('');
  const pts = D.dias.map(d => ({ ts: d.dia, pr: d.pr * 100, tipo: d.tipo }));
  const r = D.recta, finTs = Math.max(D.fecha_umbral_ms || 0, Date.now() + 14 * 86400e3, ...pts.map(p => p.ts));
  const linea = [pts[0].ts, finTs].map(ts => ({ ts, pr: (r.b0 + r.b1_dia * (ts - r.x0_ms) / 86400e3) * 100 }));
  lineChart($('#ml-deg-ch', root), {
    series: [{ data: linea, y: d => d.pr, color: '--c-ref', name: 'Tendencia' }],
    points: pts.map(p => ({ x: p.ts, y: p.pr, color: p.tipo === 'operación normal' ? '--c-e' : '--warning' })),
    ref: [{ y: D.umbral * 100, label: `umbral ${fmt(D.umbral * 100, 0)} %`, color: '--warning' }],
    yMin: Math.min(D.umbral * 100, ...pts.map(p => p.pr), ...linea.map(p => p.pr)) - 4, yMax: Math.max(...pts.map(p => p.pr), ...linea.map(p => p.pr)) + 4,
    bands: [{ to: D.umbral * 100, color: '--warning' }], unit: '%', dec: 1, area: false, endLabels: false,
    xFmt: v => fecha(v), aria: 'Rendimiento relativo diario y su proyección',
  });
  const afect = D.dias.filter(d => d.tipo !== 'operación normal').map(d => `${fecha(d.dia)}: ${d.tipo} (${pct(d.pr)})`);
  $('#ml-deg-note', root).innerHTML = `${D.dias_para_umbral == null ? 'Con la tendencia actual el panel no llega al umbral.' : `<b>Alerta preventiva:</b> con la tendencia actual el rendimiento llega a ${pct(D.umbral)} en unos ${fmt(D.dias_para_umbral, 0)} días; programar limpieza antes del ${fecha(D.fecha_umbral_ms)}.`} `
    + `La banda es ancha porque hay pocos días: si la pendiente real fuera cero, no habría cruce. `
    + (afect.length ? `Los días marcados en la bitácora quedan bajo el umbral, como se espera: ${afect.join(' · ')}. ` : '')
    + `Umbral: el mismo del detector de suciedad (medida / predicha < ${fmt(D.umbral, 2)}), que en las pruebas detectó todas las ventanas sucias con 1 % de falsas alarmas.`;
}

function renderWhatIf() {
  const mdl = getModel(), g = wiG / config.sensores.ldrFactor; // W/m² → % del LDR, como lo vería el sensor
  const effTh = t => pTheory(wiG, t) / 1000 / (wiG * areaM2()) * 100;
  $('#wi-g-v', root).textContent = `${wiG} W/m²`;
  $('#wi-t-v', root).textContent = `${wiT} °C`;
  $('#wi-p', root).textContent = fmt(mdl.predictP(g, wiT), 0) + ' mW';
  $('#wi-e', root).textContent = fmt(mdl.predictEff(g, wiT), 2) + ' %';
  $('#wi-pt', root).textContent = fmt(pTheory(wiG, wiT), 0) + ' mW';
  $('#wi-et', root).textContent = fmt(effTh(wiT), 2) + ' %';
  const curve = []; for (let t = 15; t <= 70; t++) curve.push({ t, e: mdl.predictEff(g, t), th: effTh(t) });
  lineChart($('#ml-curve', root), {
    series: [
      { data: curve, y: d => d.e, color: '--c-ref', name: 'Modelo' },
      { data: curve, y: d => d.th, color: '--c-th', name: 'Teórica' },
    ],
    x: d => d.t, xKind: 'num', xFmt: v => `${fmt(v, 0)} °C`, xTickFmt: v => `${fmt(v, 0)} °C`, unit: '%', dec: 2, endLabels: false,
    points: [{ x: wiT, y: mdl.predictEff(g, wiT), color: '--c-ref' }, { x: wiT, y: effTh(wiT), color: '--c-th' }],
    aria: 'Eficiencia del modelo y teórica según la temperatura',
  });
}

function render() {
  if (!root || root.hidden) return;
  const mdl = getModel();
  const pts = live.data.slice(-1800).filter(d => d.g > 5);
  const pairs = pts.map(d => ({ ts: d.ts, real: efficiency(d.p, d.g), pred: predEff(mdl, d) }));
  const errs = pairs.map(p => p.pred - p.real);
  // Métricas del modelo de la nube contra lo que mide el panel en esta sesión (últimos 30 min)
  const yr = pairs.map(p => p.real), m = yr.reduce((a, v) => a + v, 0) / (yr.length || 1);
  const sst = yr.reduce((a, v) => a + (v - m) ** 2, 0), sse = errs.reduce((a, e) => a + e * e, 0);
  $('#ml-r2', root).textContent = pairs.length ? fmt(1 - sse / (sst || 1), 2) : '—';
  $('#ml-mae', root).textContent = pairs.length ? fmt(errs.reduce((a, e) => a + Math.abs(e), 0) / errs.length, 2) : '—';
  $('#ml-rmse', root).textContent = pairs.length ? fmt(Math.sqrt(sse / errs.length), 2) : '—';
  const inf = nubeModelo.info, L = nubeModelo.local;
  if (L?.listo) {
    // Métricas de validación: cada sesión se predice con un modelo que NO la vio al entrenar
    $('#ml-r2', root).textContent = fmt(L.gb.R2, 2);
    $('#ml-mae', root).textContent = fmt(L.gb.MAE_mW, 1);
    $('#ml-rmse', root).textContent = fmt(L.gb.RMSE_mW, 1);
    $('#ml-mae', root).nextElementSibling.textContent = 'MAE (mW)';
    $('#ml-rmse', root).nextElementSibling.textContent = 'RMSE (mW)';
    $('#ml-sub', root).textContent = 'Gradient boosting · corre en tu computadora';
    $('#ml-trained', root).textContent = `Entrenado con ${L.sesiones} sesiones (${L.minutos.toLocaleString('es')} min) a las ${timeFmt(L.entrenado)} · validado ${L.validacion} · fórmula física k·G·(1+γΔT): R² ${fmt(L.fisico.R2, 2)}, MAE ${fmt(L.fisico.MAE_mW, 1)} mW`;
    $('#ml-banner', root).innerHTML = `<b>Modelo en tu computadora.</b> El gradient boosting se entrenó aquí con <b>todas las sesiones de la nube</b> (${L.sesiones} sesiones, ${L.minutos.toLocaleString('es')} min; se excluyen las marcadas con polvo o sombra porque el modelo aprende el panel limpio). «Reentrenar» vuelve a bajar todo, incluida la sesión en curso, y entrena de nuevo. Abajo está el pronóstico de los próximos días.`;
    hbars($('#ml-imp', root), { items: L.importancia, color: '--c-ml', valueFmt: v => fmt(v, 0) + ' %', max: 100, aria: 'Importancia de variables' });
    $('#ml-imp', root).previousElementSibling.textContent = 'Permutación: cuánto empeora el error si se revuelve cada variable';
  } else {
    $('#ml-sub', root).textContent = L ? `Entrenando en tu computadora: ${L.estado}` : inf ? `Gradient boosting · ${inf.arboles} árboles · Cloudflare Worker` : nubeModelo.error ? 'Sin respuesta de la nube · usando ajuste local' : 'Gradient boosting · Cloudflare Worker';
    $('#ml-trained', root).textContent = `Métricas contra ${pairs.length.toLocaleString('es')} lecturas de los últimos 30 min · modelo local reentrenado ${timeFmt(mdl.trainedAt)} (R² ${fmt(mdl.metrics.r2, 2)})`;
    hbars($('#ml-imp', root), { items: mdl.importance, color: '--c-ml', valueFmt: v => fmt(v, 0) + ' %', max: 100, aria: 'Importancia de variables' });
  }

  bars($('#ml-err', root), {
    color: '--c-ml', aria: 'Distribución del error',
    bins: histogram(errs, 15).map(b => ({ label: fmt((b.lo + b.hi) / 2, 1), value: b.count, tip: `${fmt(b.lo, 2)} a ${fmt(b.hi, 2)} pp<b class="tnum">${b.count.toLocaleString('es')} muestras</b>` })),
  });
  // Mismo dominio en ambos ejes para que la diagonal sea de 45°
  const all = pairs.flatMap(p => [p.real, p.pred]), lo = Math.min(...all), hi = Math.max(...all), pad = (hi - lo) * .05;
  scatter($('#ml-sc', root), {
    data: pairs, x: d => d.real, y: d => d.pred, color: '--c-e', identity: true, lastLabel: 'ahora',
    xDomain: [lo - pad, hi + pad], yDomain: [lo - pad, hi + pad],
    xTick: v => fmt(v, 1) + ' %', yTick: v => fmt(v, 1), tip: d => `${hhmmss(d.ts)}<b class="tnum">real ${fmt(d.real, 2)} % · pred. ${fmt(d.pred, 2)} %</b>`,
    aria: 'Eficiencia predicha contra real',
  });
  renderLive();
  renderWhatIf();
  renderPronostico();
  renderDegradacion();
}

export default { mount, show: render, tick: () => { if (root && !root.hidden) renderLive(); }, render };
