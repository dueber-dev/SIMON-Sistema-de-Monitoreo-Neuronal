// Datos reales desde la API en la nube (Cloudflare Worker + D1).
// Cuando la dashboard se abre desde dueber.dev/simon reemplaza al simulador:
// llena live.data con la sesión más reciente y SESSIONS con las guardadas.
// En local se puede probar con ?api=https://…/simon/api/
import { live, SESSIONS } from './sim.js';
import { bus } from './store.js';

const q = new URLSearchParams(location.search).get('api');
export const API = q ? q.replace(/\/?$/, '/') : location.pathname.startsWith('/simon') ? new URL('api/', location.href.split(/[?#]/)[0]).href : null;
export const NUBE = !!API;

// Estado de la conexión, lo leen el encabezado y la tarjeta «Estado del sistema»
export const nube = { sesion: null, vivo: false, error: false, ultimoId: 0 };

const SONDEO_MS = 3000;    // el ESP32 manda un lote cada 5 s
const MAX_PUNTOS = 4 * 3600;

async function get(ruta) {
  const r = await fetch(API + ruta, { cache: 'no-store' });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}
const punto = ([ts, v, i, p, t, g]) => ({ ts, v, i, p, t, g });
const nombre = id => 'v' + id;
const avisar = () => bus.dispatchEvent(new Event('config'));

// Sesión con la forma que esperan las vistas; sus filas se piden la primera vez que se usan
function aSesion(s) {
  const id = nombre(s.id);
  const ses = { id, num: s.id, start: s.inicio, n: s.n, estado: 'completa', file: `datos_panel_solar_wifi_${id}.csv`, datos: null };
  ses.cargar = () => {
    if (ses.datos) return;
    ses.datos = [];
    get('sesiones/' + s.id)
      .then(r => { for (const f of r.filas) ses.datos.push(punto(f)); avisar(); })
      .catch(() => { ses.datos = null; });
  };
  return ses;
}

async function cargarSesiones() {
  const lista = await get('sesiones');
  const antes = new Map(SESSIONS.map(s => [s.id, s]));
  SESSIONS.length = 0;
  for (const s of lista) {
    const enVivo = s.vivo && s.id === nube.sesion?.id;
    const prev = antes.get(nombre(s.id));
    // Una sesión terminada ya no cambia: se reutiliza con sus filas ya descargadas
    const ses = prev && !prev.live && !enVivo ? prev : aSesion(s);
    ses.n = s.n;
    if (enVivo) Object.assign(ses, { live: true, estado: 'en vivo' });
    SESSIONS.push(ses);
  }
}

// Trae las filas nuevas de la sesión más reciente. Devuelve true si llegó algo.
async function sondear() {
  try {
    const r = await get('vivo?desde=' + nube.ultimoId);
    nube.error = false;
    if (!r.sesion) return false;
    const nueva = r.sesion.id !== nube.sesion?.id, cambioVivo = r.sesion.vivo !== nube.vivo;
    if (nueva) { live.data.length = 0; live.energyWh = 0; live.start = r.sesion.inicio; }
    nube.sesion = r.sesion; nube.vivo = r.sesion.vivo;
    for (const f of r.filas) {
      nube.ultimoId = f[0];
      const d = punto(f.slice(1));
      live.data.push(d);
      live.energyWh += d.p / 1000 / 3600;
    }
    if (live.data.length > MAX_PUNTOS) live.data.splice(0, live.data.length - MAX_PUNTOS);
    if (nueva || cambioVivo) { await cargarSesiones(); avisar(); }
    return r.filas.length > 0;
  } catch {
    nube.error = true;
    return false;
  }
}

export async function iniciarNube() {
  live.data.length = 0; live.energyWh = 0; SESSIONS.length = 0;
  await sondear();   // si hay una sesión, ya carga la lista
  if (!nube.sesion) await cargarSesiones().catch(() => { nube.error = true; });
  setInterval(sondear, SONDEO_MS);
  setInterval(() => cargarSesiones().then(avisar).catch(() => {}), 60000);
}
