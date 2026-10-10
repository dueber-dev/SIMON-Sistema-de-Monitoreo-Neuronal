import { live } from '../sim.js';
import { config } from '../store.js';
import { lineChart, scatter, bars, hbars, histogram, fmt, hhmmss } from '../charts.js';
import { getModel, train, efficiency } from '../ml.js';
import { irradiance, pTheory, areaM2 } from '../physics.js';
import { $, ic, viewHeader, tween, toast, timeFmt, infoBtn } from '../ui.js';

let root, wiG = 800, wiT = 35;

function mount(el) {
  root = el;
  el.innerHTML = viewHeader({
    eyebrow: 'Predicción ML', icon: 'i-ml', title: 'Eficiencia del panel', sub: 'Lo que mide el panel frente a lo que predice el modelo',
    tools: `<button class="btn" id="ml-train">${ic('i-refresh')} Reentrenar</button>`,
  }) + `
  <div class="view-body">
    <div class="banner glass reveal">${ic('i-info', 18)}<div><b>Modelo de demostración.</b> Regresión polinómica (irradiancia, irradiancia², temperatura) entrenada en este navegador con los últimos 30 min de la sesión en curso. Se reemplazará por el modelo del equipo a través de <code>/api/predict</code>; la vista ya está lista para recibirlo.</div></div>

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
        <div class="card__head"><div><h2 class="card__title">Modelo</h2><p class="card__sub">Ajuste sobre datos sintéticos de entrenamiento; sin evaluación independiente</p></div>
          <span class="badge" style="--mc:var(--c-ml)">${ic('i-ml', 15)}</span></div>
        <div class="kv">
          <div><b id="ml-r2">—</b><span>R²</span></div>
          <div><b id="ml-mae">—</b><span>MAE (pp)</span></div>
          <div><b id="ml-rmse">—</b><span>RMSE (pp)</span></div>
        </div>
        <div class="feat"><span>Irradiancia</span><span>Irradiancia²</span><span>Temperatura</span></div>
        <p class="card__sub" id="ml-trained" style="margin-top:12px"></p>
      </article>
      <article class="card glass reveal" style="--i:3">
        <h2 class="card__title">Importancia de variables</h2>
        <p class="card__sub">|β| × desviación estándar, normalizada</p>
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

  $('#ml-train', el).addEventListener('click', () => {
    train(live.data.slice(-1800));
    render();
    toast('Modelo reentrenado con los últimos 30 min');
  });
  $('#wi-g', el).addEventListener('input', e => { wiG = +e.target.value; renderWhatIf(); });
  $('#wi-t', el).addEventListener('input', e => { wiT = +e.target.value; renderWhatIf(); });
}

function renderLive() {
  const mdl = getModel(), last = live.data[live.data.length - 1];
  const pred = mdl.predictEff(last.g, last.t), real = efficiency(last.p, last.g);
  tween($('#ml-pred', root), pred, 2, 'ml-pred');
  $('#ml-real', root).textContent = fmt(real, 2) + ' %';
  $('#ml-diff', root).textContent = `${pred - real >= 0 ? '+' : ''}${fmt(pred - real, 2)} pp`;
  const pts = live.data.slice(-300).filter(d => d.g > 5);
  lineChart($('#ml-line', root), {
    series: [
      { data: pts, y: d => efficiency(d.p, d.g), color: '--c-e', name: 'Real' },
      { data: pts, y: d => mdl.predictEff(d.g, d.t), color: '--c-ref', name: 'Predicha' },
    ],
    unit: '%', dec: 2, aria: 'Eficiencia real y predicha en el tiempo',
  });
}

function renderWhatIf() {
  const mdl = getModel(), g = wiG / config.sensores.ldrFactor; // W/m² → % del LDR, como lo vería el sensor
  const effTh = t => pTheory(g, t) / 1000 / (wiG * areaM2()) * 100;
  $('#wi-g-v', root).textContent = `${wiG} W/m²`;
  $('#wi-t-v', root).textContent = `${wiT} °C`;
  $('#wi-p', root).textContent = fmt(mdl.predictP(g, wiT), 0) + ' mW';
  $('#wi-e', root).textContent = fmt(mdl.predictEff(g, wiT), 2) + ' %';
  $('#wi-pt', root).textContent = fmt(pTheory(g, wiT), 0) + ' mW';
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
  $('#ml-r2', root).textContent = fmt(mdl.metrics.r2, 2);
  $('#ml-mae', root).textContent = fmt(mdl.metrics.mae, 2);
  $('#ml-rmse', root).textContent = fmt(mdl.metrics.rmse, 2);
  $('#ml-trained', root).textContent = `Entrenado con ${mdl.metrics.n.toLocaleString('es')} muestras · ${timeFmt(mdl.trainedAt)} · área ${fmt(config.panel.area, 0)} cm², LDR × ${fmt(config.sensores.ldrFactor, 0)} W/m²`;
  hbars($('#ml-imp', root), { items: mdl.importance, color: '--c-ml', valueFmt: v => fmt(v, 0) + ' %', max: 100, aria: 'Importancia de variables' });

  const pts = live.data.slice(-1800).filter(d => d.g > 5);
  const pairs = pts.map(d => ({ ts: d.ts, real: efficiency(d.p, d.g), pred: mdl.predictEff(d.g, d.t) }));
  const errs = pairs.map(p => p.pred - p.real);
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
}

export default { mount, show: render, tick: () => { if (root && !root.hidden) renderLive(); }, render };
