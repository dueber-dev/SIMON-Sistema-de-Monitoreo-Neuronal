import { config, DEFAULTS, saveConfig } from '../store.js';
import { live, SESSIONS } from '../sim.js';
import { fmt } from '../charts.js';
import { $, $$, ic, viewHeader, toast } from '../ui.js';

let root, draft, dirty = false;
const clone = o => JSON.parse(JSON.stringify(o));
const get = (o, path) => path.split('.').reduce((a, k) => a[k], o);
const set = (o, path, v) => { const ks = path.split('.'), last = ks.pop(); ks.reduce((a, k) => a[k], o)[last] = v; };

const num = (path, label, unit, step, hint = '') => `<div class="field"><label for="f-${path}">${label}</label>
  <div class="affix"><input class="input tnum" type="number" id="f-${path}" data-path="${path}" step="${step}"><em>${unit}</em></div>${hint ? `<span class="hint">${hint}</span>` : ''}</div>`;
const text = (path, label, full = false, hint = '') => `<div class="field${full ? ' field--full' : ''}"><label for="f-${path}">${label}</label>
  <input class="input" type="text" id="f-${path}" data-path="${path}">${hint ? `<span class="hint">${hint}</span>` : ''}</div>`;
const select = (path, label, options, hint = '') => `<div class="field"><label for="f-${path}">${label}</label>
  <select class="select" id="f-${path}" data-path="${path}">${options.map(([v, t]) => `<option value="${v}">${t}</option>`).join('')}</select>${hint ? `<span class="hint">${hint}</span>` : ''}</div>`;
const toggle = (path, title, desc) => `<label class="toggle-row"><span><b>${title}</b><span class="d">${desc}</span></span>
  <span class="switch"><input type="checkbox" role="switch" data-path="${path}" aria-label="${title}"><span></span></span></label>`;
const card = (i, color, icon, title, sub, body) => `<article class="card glass cfg-card reveal" style="--i:${i}">
  <h2 class="card__title"><span class="badge" style="--mc:var(${color})">${ic(icon, 14)}</span>${title}</h2><p class="card__sub">${sub}</p>${body}</article>`;

function mount(el) {
  root = el;
  el.innerHTML = viewHeader({ eyebrow: 'Configuración', icon: 'i-settings', title: 'Ajustes del sistema', sub: 'Panel, sensores, conexión, alertas, datos y apariencia' }) + `
  <div class="view-body">
    <div class="cfg-grid">
      <div class="view-body">
        ${card(1, '--c-p', 'i-bolt', 'Panel solar', 'Datos de la ficha técnica del panel', `
          <div class="form">
            ${text('panel.nombre', 'Nombre', true)}
            ${num('panel.nominal', 'Potencia nominal', 'W', .1)}
            ${num('panel.voc', 'Voltaje de circuito abierto', 'V', .1)}
            ${num('panel.isc', 'Corriente de cortocircuito', 'mA', 1)}
            ${num('panel.area', 'Área', 'cm²', 1)}
            ${num('panel.coefT', 'Coeficiente de temperatura', '%/°C', .01, 'Pérdida de potencia por cada °C sobre 25 °C')}
          </div>
          <div class="preview-note" id="pv-panel"></div>`)}
        ${card(3, '--c-v', 'i-wifi', 'Conexión', 'Origen de los datos en tiempo real', `
          <div class="field" style="margin-top:14px"><span class="lbl">Fuente de datos</span>
            <div class="seg seg--flat" role="group" aria-label="Fuente de datos" style="align-self:flex-start">
              <button data-mode="esp32">ESP32 por Wi‑Fi</button><button data-mode="sim">Simulador</button></div></div>
          <div class="form">
            ${text('conexion.ip', 'IP del ESP32', false, 'Red ESP32_Panel_Solar')}
            ${num('conexion.puerto', 'Puerto TCP', '', 1)}
          </div>
          <div style="margin-top:6px">${toggle('conexion.reconectar', 'Reconexión automática', 'Reintenta cada 2 s si se pierde el enlace')}</div>
          <button class="btn" id="cfg-test" style="margin-top:6px">${ic('i-plug')} Probar conexión</button>`)}
        ${card(5, '--c-i', 'i-folder', 'Datos', 'Archivos CSV que alimentan el modelo', `
          <div class="form">${text('datos.base', 'Nombre base del archivo', true)}</div>
          <div style="margin-top:6px">${toggle('datos.timestamp', 'Agregar columna timestamp', 'Fecha y hora ISO de cada muestra, útil para el modelo')}</div>
          <div class="preview-note" id="pv-datos"></div>`)}
      </div>
      <div class="view-body">
        ${card(2, '--c-g', 'i-sun', 'Sensores y calibración', 'Convierte las lecturas crudas en unidades físicas', `
          <div class="form">
            ${num('sensores.ldrFactor', 'Calibración del LDR', 'W/m²', 1, 'W/m² por cada 1 % de luz')}
            ${num('sensores.lm35Offset', 'Ajuste del LM35', '°C', .1, 'Se suma a la temperatura medida')}
            ${num('sensores.iMin', 'Corriente mínima', 'mA', .01, 'Por debajo se considera 0 (oscuridad)')}
            ${select('sensores.ina', 'Rango del INA219', [['32V_1A', '32 V · 1 A (alta precisión)'], ['32V_2A', '32 V · 2 A'], ['16V_400mA', '16 V · 400 mA']])}
          </div>
          <div style="margin-top:6px">${toggle('sensores.ldrInvertir', 'Invertir lectura del LDR', 'Si el divisor está cableado al revés (más luz = menos %)')}</div>
          <div class="preview-note" id="pv-sens"></div>`)}
        ${card(4, '--serious', 'i-alert', 'Alertas', 'Cuándo avisar en la vista En vivo', `
          <div class="form">
            ${num('alertas.tMax', 'Temperatura alta', '°C', 1)}
            ${num('alertas.pMin', 'Potencia mínima', 'mW', 1, 'Por debajo: «Sin potencia»')}
            ${num('alertas.sinDatos', 'Tiempo sin datos', 's', 1, 'Marca la conexión como perdida')}
          </div>
          <div style="margin-top:6px">${toggle('alertas.sonido', 'Aviso sonoro', 'Reproduce un tono al entrar en alerta')}</div>`)}
        ${card(6, '--c-ml', 'i-image', 'Apariencia', 'Tema y fondo se aplican al instante en este navegador', `
          <div class="form">${text('ui.equipo', 'Nombre en el saludo', true, 'Ej.: «Buenos días, equipo SIMON»')}</div>
          <div class="field" style="margin-top:14px"><span class="lbl">Tema</span>
            <div class="seg seg--flat" role="group" aria-label="Tema" style="align-self:flex-start">
              <button data-theme-choice="light">Claro</button><button data-theme-choice="dark">Oscuro</button><button data-theme-choice="system">Sistema</button></div></div>
          <div class="field" style="margin-top:14px"><span class="lbl">Fondo</span>
            <div class="bg-opts bg-opts--wide">
              <button class="bg-opt bg-opt--foto" data-bg-set="foto" aria-pressed="false">Campo solar</button>
              <button class="bg-opt bg-opt--atardecer" data-bg-set="atardecer" aria-pressed="false">Atardecer</button>
              <button class="bg-opt bg-opt--noche" data-bg-set="noche" aria-pressed="false">Noche</button>
              <label class="bg-opt bg-opt--custom" tabindex="0">+ Tu imagen<input type="file" accept="image/*" class="sr js-bg-file"></label>
            </div></div>
          <div class="slider"><label>Desenfoque <span class="tnum js-blur-v"></span></label><input type="range" class="js-blur" min="0" max="24" aria-label="Desenfoque"></div>
          <div class="slider"><label>Atenuar fondo <span class="tnum js-dim-v"></span></label><input type="range" class="js-dim" min="0" max="70" aria-label="Atenuar fondo"></div>`)}
      </div>
    </div>
    <div class="savebar glass" id="cfg-bar">
      <p><i></i><span id="cfg-state">Todo guardado</span></p>
      <div class="actions">
        <button class="btn" id="cfg-defaults">Valores de fábrica</button>
        <button class="btn" id="cfg-discard" disabled>Descartar</button>
        <button class="btn btn--accent" id="cfg-save" disabled>${ic('i-check')} Guardar cambios</button>
      </div>
    </div>
  </div>`;

  el.addEventListener('input', e => {
    const f = e.target.closest('[data-path]'); if (!f) return;
    const path = f.dataset.path, cur = get(draft, path);
    const v = f.type === 'checkbox' ? f.checked : typeof cur === 'number' ? parseFloat(f.value) : f.value;
    if (typeof cur === 'number' && !Number.isFinite(v)) return;
    set(draft, path, v); markDirty();
  });
  $$('[data-mode]', el).forEach(b => b.addEventListener('click', () => { draft.conexion.modo = b.dataset.mode; fillMode(); markDirty(); }));
  $('#cfg-save', el).addEventListener('click', () => { saveConfig(clone(draft)); dirty = false; updateBar(); toast('Configuración guardada'); });
  $('#cfg-discard', el).addEventListener('click', () => { draft = clone(config); fill(); dirty = false; updateBar(); });
  $('#cfg-defaults', el).addEventListener('click', () => { draft = clone(DEFAULTS); fill(); markDirty(); toast('Valores de fábrica cargados: pulsa Guardar para aplicarlos'); });
  $('#cfg-test', el).addEventListener('click', () => {
    const c = draft.conexion;
    toast(c.modo === 'sim' ? 'El simulador está activo: no hace falta conexión' : `La maqueta no tiene backend: la prueba real a ${c.ip}:${c.puerto} llega con FastAPI`);
  });
}

function fillMode() {
  $$('[data-mode]', root).forEach(b => b.setAttribute('aria-pressed', b.dataset.mode === draft.conexion.modo));
  $$('[data-path^="conexion."]', root).forEach(i => { if (i.type !== 'checkbox') i.disabled = draft.conexion.modo === 'sim'; });
}

function fill() {
  $$('[data-path]', root).forEach(f => {
    const v = get(draft, f.dataset.path);
    if (f.type === 'checkbox') f.checked = v; else f.value = v;
  });
  fillMode(); previews();
}

function previews() {
  const p = draft.panel, s = draft.sensores, last = live.data[live.data.length - 1];
  const eta = p.nominal / (1000 * p.area / 1e4) * 100;
  $('#pv-panel', root).innerHTML = `Eficiencia nominal: <b>${fmt(eta, 1)} %</b> = ${fmt(p.nominal, 1)} W / (1000 W/m² × ${fmt(p.area / 1e4, 4)} m²)`;
  const g = s.ldrInvertir ? 100 - last.g : last.g;
  $('#pv-sens', root).innerHTML = `Lectura actual: <b>${fmt(g, 1)} %</b> de luz ≈ <b>${fmt(g * s.ldrFactor, 0)} W/m²</b> · temperatura <b>${fmt(last.t + s.lm35Offset, 1)} °C</b>`;
  $('#pv-datos', root).innerHTML = `Siguiente archivo: <b>${draft.datos.base}_v${SESSIONS.length + 1}.csv</b><br>Columnas: Segundos, V_Panel_V, Corriente_mA, Potencia_mW, Temperatura_C, Luz_Pct${draft.datos.timestamp ? ', timestamp' : ''}`;
}

function markDirty() { dirty = true; updateBar(); previews(); }
function updateBar() {
  $('#cfg-bar', root).classList.toggle('is-dirty', dirty);
  $('#cfg-state', root).textContent = dirty ? 'Cambios sin guardar' : 'Todo guardado';
  $('#cfg-save', root).disabled = !dirty;
  $('#cfg-discard', root).disabled = !dirty;
}

function show() {
  if (!dirty) draft = clone(config);
  fill(); updateBar();
}

export default { mount, show, render: () => {}, tick: () => { if (root && !root.hidden) previews(); } };
