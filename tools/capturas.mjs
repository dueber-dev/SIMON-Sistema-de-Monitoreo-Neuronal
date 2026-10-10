// Capturas del dashboard empaquetado vía CDP (Edge o Chrome headless en el puerto 9334).
// 1. Abrir el navegador en modo depuración (ajusta la ruta a tu navegador):
//      msedge --headless=new --disable-gpu --hide-scrollbars --remote-debugging-port=9334 --user-data-dir=%TEMP%\simon-capturas about:blank
// 2. node tools/capturas.mjs entrega/SIMON-dashboard-interactivo.html <carpeta-salida>
// Las capturas salen en PNG; tools/build_entrega.py espera WebP en entrega/capturas/.
import { writeFileSync, mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const [,, file, outDir] = process.argv;
mkdirSync(outDir, { recursive: true });
const BASE = pathToFileURL(file).href;
const keep = setInterval(() => {}, 1000);
const sleep = ms => new Promise(r => setTimeout(r, ms));

const target = await (await fetch('http://127.0.0.1:9334/json/new?about:blank', { method: 'PUT' })).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => (ws.onopen = r));
let id = 0; const pend = new Map(); const errors = [];
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
  if (pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
};
const send = (method, params = {}) => new Promise(r => { pend.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
const js = async expr => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
await send('Runtime.enable'); await send('Page.enable');

async function view({ width = 1440, height = 900, dark = false }) {
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1.5, mobile: width < 760 });
  await send('Emulation.setEmulatedMedia', { features: [
    { name: 'prefers-reduced-motion', value: 'reduce' },
    { name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' },
  ] });
}
async function open(hash, { config, theme = 'system', bg = 'foto' } = {}) {
  await send('Page.navigate', { url: BASE + '#/en-vivo' }); await sleep(800);
  await js(`localStorage.clear(); localStorage.setItem('simon.theme', '"${theme}"'); localStorage.setItem('simon.bg', '"${bg}"');
    ${config ? `localStorage.setItem('simon.config', ${JSON.stringify(JSON.stringify(config))});` : ''} 1`);
  await send('Page.navigate', { url: BASE + '#/' + hash }); await sleep(250);
  await send('Page.reload'); await sleep(1800);
}
async function shot(name, { full = false, width = 1440, height = 900, dark = false } = {}) {
  if (full) {
    const h = await js('document.documentElement.scrollHeight');
    await view({ width, height: h, dark }); await sleep(900);
  }
  const r = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(`${outDir}/${name}.png`, Buffer.from(r.result.data, 'base64'));
  console.log('ok', name);
  await view({ width, height, dark });
}

const scenes = [
  ['01-en-vivo', 'en-vivo', {}, { full: true }],
  ['02-en-vivo-oscuro', 'en-vivo', { dark: true }, { full: true, dark: true }],
  ['03-justificacion', 'en-vivo', {}, {}, `document.querySelector('[data-info=e]').click()`],
  ['05-analisis', 'analisis/v3', {}, { full: true }, `document.querySelector('[data-metric=e]').click()`],
  ['06-prediccion', 'prediccion', {}, { full: true }],
  ['07-sesiones', 'sesiones', {}, { full: true }],
  ['08-configuracion', 'configuracion', {}, { full: true }],
  ['09-fondo', 'en-vivo', { dark: true, bg: 'atardecer' }, { dark: true }, `document.querySelector('.js-bg-btn').click()`],
  ['10-movil-en-vivo', 'en-vivo', { width: 390, height: 844 }, { width: 390, height: 844 }],
  ['11-movil-sesiones', 'sesiones', { width: 390, height: 844, dark: true }, { width: 390, height: 844, dark: true }],
];
for (const [name, hash, v, s, prep] of scenes) {
  await view(v);
  await open(hash, { theme: v.dark ? 'dark' : 'light', bg: v.bg || 'foto' });
  if (prep) { await js(prep); await sleep(500); }
  await shot(name, s);
}

// Alerta de mantenimiento: escenario «Panel sucio» con ventana de 1 min
await view({});
await open('en-vivo', { theme: 'light', config: { conexion: { escenario: 'sucio' }, alertas: { mantMin: 1 } } });
for (let k = 0; k < 24; k++) {
  await sleep(5000);
  if (await js(`document.querySelector('#status-list').textContent.includes('Revisar o limpiar')`)) break;
}
await sleep(15000);
await shot('04-alerta-mantenimiento', { full: true });

console.log('errores:', JSON.stringify(errors));
clearInterval(keep); ws.close(); process.exit(0);
