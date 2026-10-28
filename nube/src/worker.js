// API de SIMON en Cloudflare Workers + D1.
// El ESP32 manda lecturas por POST y la dashboard las consulta desde cualquier lugar.
// Los archivos de la dashboard se sirven desde /simon/ con los assets del Worker;
// aquí solo llega lo que no es un archivo, o sea /simon/api/*.

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization, Content-Type',
};
const VIVO_MS = 20000;      // sin lecturas en 20 s, la sesión ya no está en vivo
const MAX_LOTE = 120;       // filas por POST (el ESP32 manda ~5)
const INICIO_VIVO = 3600;   // al abrir la dashboard se cargan las últimas 1 h

const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', ...CORS },
});

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (!url.pathname.startsWith('/simon/api/')) return env.ASSETS.fetch(req);
    if (req.method === 'OPTIONS') return new Response(null, { headers: CORS });

    const ruta = url.pathname.slice('/simon/api'.length);
    try {
      if (req.method === 'POST' && ruta === '/lecturas') return await recibir(req, env);
      if (req.method !== 'GET') return json({ error: 'método no permitido' }, 405);
      if (ruta === '/vivo') return await vivo(env, url);
      if (ruta === '/sesiones') return await sesiones(env);
      let m = ruta.match(/^\/sesiones\/(\d+)$/);
      if (m) return await datosSesion(env, +m[1]);
      m = ruta.match(/^\/sesiones\/(\d+)\.csv$/);
      if (m) return await csvSesion(env, +m[1]);
      return json({ error: 'ruta no encontrada' }, 404);
    } catch (e) {
      return json({ error: String(e?.message || e) }, 500);
    }
  },
};

// POST /simon/api/lecturas  { clave, filas: [[seg, V, mA, mW, °C, luz%], ...] }
// «clave» la genera el ESP32 al arrancar: cada encendido es una sesión nueva.
async function recibir(req, env) {
  if (!env.TOKEN_ESP32 || req.headers.get('Authorization') !== `Bearer ${env.TOKEN_ESP32}`) {
    return json({ error: 'token inválido' }, 401);
  }
  const body = await req.json().catch(() => null);
  const clave = typeof body?.clave === 'string' ? body.clave.slice(0, 32) : '';
  const filas = Array.isArray(body?.filas) ? body.filas : [];
  if (!clave || !filas.length || filas.length > MAX_LOTE) return json({ error: 'formato inválido' }, 400);
  const limpias = filas.map(f => Array.isArray(f) ? f.slice(0, 6).map(Number) : []);
  if (limpias.some(f => f.length !== 6 || !f.every(Number.isFinite))) return json({ error: 'fila inválida' }, 400);

  // El ESP32 no tiene reloj: la hora de cada fila sale de la hora de llegada
  // y de los segundos que la separan de la última del lote.
  const ahora = Date.now(), ultSeg = limpias[limpias.length - 1][0];
  let ses = await env.DB.prepare('SELECT id FROM sesiones WHERE clave = ?').bind(clave).first();
  if (!ses) {
    ses = await env.DB.prepare('INSERT INTO sesiones (clave, inicio, fin, n) VALUES (?, ?, ?, 0) RETURNING id')
      .bind(clave, ahora - (ultSeg - limpias[0][0]) * 1000, ahora).first();
  }
  const ins = env.DB.prepare('INSERT INTO lecturas (sesion, ts, seg, v, i, p, t, luz) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
  await env.DB.batch([
    ...limpias.map(f => ins.bind(ses.id, ahora - (ultSeg - f[0]) * 1000, ...f)),
    env.DB.prepare('UPDATE sesiones SET fin = ?, n = n + ? WHERE id = ?').bind(ahora, limpias.length, ses.id),
  ]);
  return json({ ok: true, sesion: ses.id });
}

const sesionPublica = (s, ahora = Date.now()) => s && ({ id: s.id, inicio: s.inicio, fin: s.fin, n: s.n, vivo: ahora - s.fin < VIVO_MS });

// GET /simon/api/vivo?desde=<id>  -> filas nuevas de la sesión más reciente
// Cada fila: [id, ts, V, mA, mW, °C, luz%]
async function vivo(env, url) {
  const s = await env.DB.prepare('SELECT id, inicio, fin, n FROM sesiones ORDER BY id DESC LIMIT 1').first();
  if (!s) return json({ sesion: null, filas: [] });
  const desde = Number(url.searchParams.get('desde')) || 0;
  const q = desde
    ? env.DB.prepare('SELECT id, ts, v, i, p, t, luz FROM lecturas WHERE sesion = ? AND id > ? ORDER BY id LIMIT 600').bind(s.id, desde)
    : env.DB.prepare('SELECT * FROM (SELECT id, ts, v, i, p, t, luz FROM lecturas WHERE sesion = ? ORDER BY id DESC LIMIT ?) ORDER BY id').bind(s.id, INICIO_VIVO);
  return json({ sesion: sesionPublica(s), filas: await q.raw() });
}

// GET /simon/api/sesiones -> las 100 más recientes
async function sesiones(env) {
  const { results } = await env.DB.prepare('SELECT id, inicio, fin, n FROM sesiones ORDER BY id DESC LIMIT 100').all();
  const ahora = Date.now();
  return json(results.map(s => sesionPublica(s, ahora)));
}

// GET /simon/api/sesiones/<id> -> todas las filas: [ts, V, mA, mW, °C, luz%]
async function datosSesion(env, id) {
  const filas = await env.DB.prepare('SELECT ts, v, i, p, t, luz FROM lecturas WHERE sesion = ? ORDER BY id').bind(id).raw();
  return json({ id, filas });
}

// GET /simon/api/sesiones/<id>.csv -> mismo formato que el CSV del script de Python, más la hora
async function csvSesion(env, id) {
  const filas = await env.DB.prepare('SELECT seg, v, i, p, t, luz, ts FROM lecturas WHERE sesion = ? ORDER BY id').bind(id).raw();
  const lineas = ['Segundos,V_Panel_V,Corriente_mA,Potencia_mW,Temperatura_C,Luz_Pct,timestamp',
    ...filas.map(([seg, v, i, p, t, luz, ts]) => [seg, v, i, p, t, luz, new Date(ts).toISOString()].join(','))];
  return new Response(lineas.join('\n'), {
    headers: { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': `attachment; filename="datos_panel_solar_wifi_v${id}.csv"`, ...CORS },
  });
}
