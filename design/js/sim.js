// Simulador: produce los mismos 6 campos que manda el ESP32
// (segundos, V, mA, mW, °C, luz %) a 1 Hz, más el timestamp.

export const METRICS = {
  p: { label: 'Potencia',    unit: 'mW', dec: 0, icon: 'i-bolt',    upGood: true,  csv: 'Potencia_mW' },
  v: { label: 'Voltaje',     unit: 'V',  dec: 2, icon: 'i-battery', upGood: true,  csv: 'V_Panel_V' },
  i: { label: 'Corriente',   unit: 'mA', dec: 1, icon: 'i-flow',    upGood: true,  csv: 'Corriente_mA' },
  t: { label: 'Temperatura', unit: '°C', dec: 1, icon: 'i-thermo',  upGood: false, csv: 'Temperatura_C' },
  g: { label: 'Irradiancia', unit: '%',  dec: 1, icon: 'i-sun',     upGood: true,  csv: 'Luz_Pct' },
};

export function mulberry32(a) {
  return () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

export function createSim(seed, { base = 80 } = {}) {
  const r = mulberry32(seed);
  const rnd = (a = 1) => (r() - .5) * 2 * a;
  const st = { cloud: .95, drift: 0, t: 22 + base * .2 }, phase = r() * 6.28;
  return ts => {
    st.drift = st.drift * .9 + rnd(.004);
    st.cloud += st.drift + (.95 - st.cloud) * .03;
    if (r() < .002) st.drift -= .025; // nube pasajera
    st.cloud = clamp(st.cloud, .35, 1);
    const gTrue = clamp((base + 6 * Math.sin(ts / 600000)) * st.cloud, 0, 100);
    const g = clamp(gTrue + rnd(1.6), 0, 100); // lectura del LDR (ruidosa)
    // El panel se calienta con la luz, pero el ambiente/viento también lo mueve (±4 °C)
    const amb = 4 * Math.sin(ts / 420000 + phase);
    st.t += (24 + .24 * gTrue + amb - st.t) * .01 + rnd(.06);
    const i = Math.max(0, 182 * gTrue / 100 * (1 + .0005 * (st.t - 25)) + rnd(.35));
    const voc = 6.4 * (1 - .0033 * (st.t - 25));
    const v = Math.max(0, Math.min(i * .0305, voc * .9) * (1 - .004 * (st.t - 35)) + rnd(.005));
    return { ts, v, i, p: v * i, t: st.t, g };
  };
}

/* ---------- Sesión en vivo (v7) ---------- */
const PRE = 4500; // la sesión en curso ya lleva 1 h 15 min
const liveNext = createSim(Date.now() % 1e9, { base: 80 });
export const live = { start: Date.now() - PRE * 1000, data: [], energyWh: 0, paused: false };
for (let k = 0; k < PRE; k++) pushLive(liveNext(live.start + k * 1000));

function pushLive(s) {
  live.data.push(s);
  live.energyWh += s.p / 1000 / 3600;
  if (live.data.length > 4 * 3600) live.data.shift();
}
export function stepLive() {
  const s = liveNext(Date.now());
  pushLive(s);
  return s;
}

/* ---------- Sesiones guardadas (CSV) ---------- */
const DAY = 864e5;
const today = new Date(); today.setHours(0, 0, 0, 0);
const at = (daysAgo, h, m) => today.getTime() - daysAgo * DAY + (h * 60 + m) * 60e3;

export const SESSIONS = [
  { id: 'v7', live: true, estado: 'en vivo' },
  { id: 'v6', start: at(1, 15, 10), n: 2518, base: 74, seed: 6, estado: 'completa' },
  { id: 'v5', start: at(4, 10, 20), n: 3912, base: 84, seed: 5, estado: 'completa' },
  { id: 'v4', start: at(5, 14, 5),  n: 1690, base: 62, seed: 4, estado: 'interrumpida' },
  { id: 'v3', start: at(7, 11, 30), n: 3301, base: 88, seed: 3, estado: 'completa' },
  { id: 'v2', start: at(8, 16, 45), n: 1080, base: 48, seed: 2, estado: 'completa' },
  { id: 'v1', start: at(11, 12, 0), n: 540,  base: 70, seed: 1, estado: 'completa', nota: 'Prueba inicial' },
].map(s => ({ ...s, file: `datos_panel_solar_wifi_${s.id}.csv` }));

const cache = new Map();
export function sessionData(s) {
  if (s.live) return live.data;
  if (!cache.has(s.id)) {
    const next = createSim(s.seed * 7919, { base: s.base }), out = [];
    for (let k = 0; k < s.n; k++) out.push(next(s.start + k * 1000));
    cache.set(s.id, out);
  }
  return cache.get(s.id);
}
export const sessionStart = s => s.live ? live.start : s.start;
export const getSession = id => SESSIONS.find(s => s.id === id) || SESSIONS[0];

export function summarize(pts) {
  let e = 0, peak = 0, sp = 0, st = 0, sg = 0, maxT = -Infinity;
  for (const d of pts) { e += d.p / 1000 / 3600; peak = Math.max(peak, d.p); sp += d.p; st += d.t; sg += d.g; maxT = Math.max(maxT, d.t); }
  const n = pts.length || 1;
  return { energyWh: e, peak, meanP: sp / n, meanT: st / n, meanG: sg / n, maxT, n: pts.length, dur: pts.length };
}

export function toCSV(pts, withTs = true) {
  const head = ['Segundos', 'V_Panel_V', 'Corriente_mA', 'Potencia_mW', 'Temperatura_C', 'Luz_Pct'].concat(withTs ? ['timestamp'] : []);
  const t0 = pts.length ? pts[0].ts : 0;
  const rows = pts.map(d => [Math.round((d.ts - t0) / 1000), d.v.toFixed(3), d.i.toFixed(2), d.p.toFixed(2), d.t.toFixed(1), d.g.toFixed(1)]
    .concat(withTs ? [new Date(d.ts).toISOString()] : []).join(','));
  return [head.join(','), ...rows].join('\n');
}
