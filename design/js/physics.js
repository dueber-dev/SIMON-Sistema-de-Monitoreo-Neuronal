// Cálculos físicos del panel. Todo lo que depende de la ficha técnica o de la
// calibración sale de la configuración, así que cambia si el equipo la edita.
import { config } from './store.js';

// Irradiancia estimada (W/m²) a partir del % de luz del LDR calibrado
export const irradiance = (g, cfg = config) => (cfg.sensores.ldrInvertir ? 100 - g : g) * cfg.sensores.ldrFactor;

export const areaM2 = (cfg = config) => cfg.panel.area / 1e4;

// Eficiencia nominal en condiciones estándar (STC: 1000 W/m², 25 °C)
export const etaNominal = (cfg = config) => cfg.panel.nominal / (1000 * areaM2(cfg)) * 100;

// Eficiencia real: η = P / (G · A)
export function efficiency(pmW, g, cfg = config) {
  const G = irradiance(g, cfg), A = areaM2(cfg);
  return G > 1 && A > 0 ? (pmW / 1000) / (G * A) * 100 : 0;
}

// Potencia teórica (mW): P_nom · G / 1000 · [1 + γ · (T − 25)], con γ en %/°C
export const pTheory = (g, t, cfg = config) =>
  Math.max(0, cfg.panel.nominal * 1000 * irradiance(g, cfg) / 1000 * (1 + cfg.panel.coefT / 100 * (t - 25)));

// Umbral de mantenimiento expresado como eficiencia (% de la nominal)
export const etaThreshold = (cfg = config) => etaNominal(cfg) * cfg.alertas.mant / 100;

/**
 * Mantenimiento: compara la eficiencia mediana contra el umbral, pero solo con
 * buena luz (G ≥ mínimo) y sobre una ventana sostenida, para que una nube o el
 * atardecer no disparen falsas alarmas. Devuelve 'ok' | 'revisar' | 'sin-luz'.
 */
export function maintenance(data, cfg = config, windowS = cfg.alertas.mantMin * 60) {
  // ts está en milisegundos. No confundir segundos con número de muestras:
  // una pausa del navegador o un registro irregular no acredita una ventana.
  const valid = data.filter(d => Number.isFinite(d.ts) && Number.isFinite(d.p) && Number.isFinite(d.g));
  const end = valid.at(-1)?.ts;
  const recent = valid.filter(d => d.ts <= end && d.ts > end - windowS * 1000);
  const win = recent.filter(d => irradiance(d.g, cfg) >= cfg.alertas.mantGmin);
  const required = Number.isFinite(windowS) ? windowS : cfg.alertas.mantMin * 60;
  // Cobertura mínima del 90 % a 1 Hz, contando segundos distintos, y luz
  // suficiente en la muestra más reciente. Infinity resume toda la sesión.
  const seconds = new Set(win.map(d => Math.floor(d.ts / 1000)));
  if (!(required > 0) || !win.length ||
      irradiance(recent.at(-1)?.g, cfg) < cfg.alertas.mantGmin ||
      seconds.size < Math.ceil(required * .9) ||
      win.at(-1).ts - win[0].ts < (required - 1) * 1000) {
    return { state: 'sin-luz', n: win.length };
  }
  const effs = win.map(d => efficiency(d.p, d.g, cfg)).sort((a, b) => a - b);
  const middle = effs.length >> 1;
  const median = effs.length % 2 ? effs[middle] : (effs[middle - 1] + effs[middle]) / 2;
  const thr = etaThreshold(cfg);
  return {
    state: median < thr ? 'revisar' : 'ok',
    median, n: win.length,
    ratio: median / etaNominal(cfg) * 100,
    below: effs.filter(e => e < thr).length / effs.length,
  };
}
