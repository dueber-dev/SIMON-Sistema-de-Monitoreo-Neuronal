// Cálculos físicos del panel. Todo lo que depende de la ficha técnica o de la
// calibración sale de la configuración, así que cambia si el equipo la edita.
import { config } from './store.js';

// Irradiancia estimada (W/m²) a partir del % de luz del LDR calibrado
export const irradiance = (g, cfg = config) => (cfg.sensores.ldrInvertir ? 100 - g : g) * cfg.sensores.ldrFactor;

/* ---------------------------------------------------------------------------
 * IRRADIANCIA MEDIDA CON EL PROPIO PANEL (el panel como celda de referencia)
 *
 * Física: en una celda de silicio cada fotón absorbido genera un par
 * electrón-hueco, así que la corriente de cortocircuito es proporcional a la luz:
 *     I_sc = I_sc,STC · (G / 1000) · [1 + α · (T − 25)]      α ≈ +0.05 %/°C
 *
 * Nuestro panel no está en cortocircuito: tiene la carga fija de 30 Ω. Pero a
 * pleno sol 30 Ω × 151 mA = 4.53 V, que queda por DEBAJO de Vmp ≈ 5.2 V. El panel
 * trabaja en la zona plana de la curva I-V (se comporta como fuente de
 * corriente), así que la corriente que mide el INA219 es casi la I_sc:
 *     I_carga ≈ k · I_sc       (k ≈ 0.95; se obtiene de la curva I-V medida)
 *
 * Despejando G:
 *     G ≈ 1000 · I_carga / ( k · I_sc,STC · [1 + α · (T − 25)] )
 * ------------------------------------------------------------------------- */
export function irradiancePanel(iMa, t, cfg = config) {
  const { isc } = cfg.panel;                 // I_sc,STC de la ficha (mA)
  const { kCarga, alfaIsc } = cfg.sensores;  // k de la curva I-V y α en %/°C
  const den = kCarga * isc * (1 + alfaIsc / 100 * (t - 25));
  return den > 0 ? Math.max(0, 1000 * iMa / den) : 0;
}

/* ---------------------------------------------------------------------------
 * ÍNDICE DE SUCIEDAD   S = G_panel / G_LDR
 *
 * ¿Por qué NO usamos solo G_panel para todo? Porque el razonamiento se vuelve
 * circular: η = P/(G·A) = (V·I)/(c·I·A) = V/(c·A). La corriente se cancela y la
 * eficiencia ya no ve el polvo: el polvo baja I y el sistema lo leería como
 * «hay menos sol».
 *
 * Solución: comparar DOS sensores que ven la misma luz.
 *   - La LDR (en la caja, limpia) mide la luz que LLEGA.
 *   - El panel mide la luz que logra ATRAVESAR el polvo.
 * Con el panel limpio S ≈ 1. Si S baja de forma sostenida (p. ej. < 0.85),
 * el panel está sucio o sombreado. Es el mismo principio de las plantas solares:
 * una celda de referencia limpia contra los paneles en operación.
 *
 * Se usa la MEDIANA de la ventana y solo con buena luz, porque la LDR y el panel
 * responden a velocidades distintas: una nube rápida no debe disparar la alerta.
 * ------------------------------------------------------------------------- */
export function soiling(data, cfg = config, windowS = cfg.alertas.mantMin * 60) {
  const win = data.slice(-windowS).filter(d => irradiance(d.g, cfg) >= cfg.alertas.mantGmin);
  if (win.length < 60) return { state: 'sin-luz', n: win.length };
  const ratios = win.map(d => irradiancePanel(d.i, d.t, cfg) / irradiance(d.g, cfg)).sort((a, b) => a - b);
  const S = ratios[ratios.length >> 1];
  return { state: S < cfg.alertas.suciedad / 100 ? 'sucio' : 'limpio', S, n: win.length };
}

/* ---------------------------------------------------------------------------
 * CALIBRACIÓN DE LA LDR USANDO EL PANEL LIMPIO COMO REFERENCIA
 *
 * Con el panel recién limpio, G_panel es la irradiancia «verdadera». Buscamos el
 * factor f (W/m² por cada 1 % de la LDR) que mejor cumple G_panel = f · %LDR.
 * Mínimos cuadrados con la recta por el origen:
 *     f = Σ(x · y) / Σ(x²)        x = % LDR,  y = G_panel
 * R² indica qué tan bien se ajusta. Si es bajo, la LDR no es lineal en ese rango
 * (se satura al sol): es una limitación que se documenta.
 * ------------------------------------------------------------------------- */
export function calibrateLdr(data, cfg = config) {
  const pts = data
    .map(d => ({ x: cfg.sensores.ldrInvertir ? 100 - d.g : d.g, y: irradiancePanel(d.i, d.t, cfg) }))
    .filter(p => p.x > 2 && p.y > 20);       // ignora oscuridad y ruido
  if (pts.length < 30) return null;
  const sxy = pts.reduce((a, p) => a + p.x * p.y, 0), sxx = pts.reduce((a, p) => a + p.x * p.x, 0);
  const f = sxy / sxx;
  const my = pts.reduce((a, p) => a + p.y, 0) / pts.length;
  const ssRes = pts.reduce((a, p) => a + (p.y - f * p.x) ** 2, 0), ssTot = pts.reduce((a, p) => a + (p.y - my) ** 2, 0);
  return { factor: f, n: pts.length, r2: ssTot > 0 ? 1 - ssRes / ssTot : 0 };
}

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
  const win = data.slice(-windowS).filter(d => irradiance(d.g, cfg) >= cfg.alertas.mantGmin);
  if (win.length < 60) return { state: 'sin-luz', n: win.length };
  const effs = win.map(d => efficiency(d.p, d.g, cfg)).sort((a, b) => a - b);
  const median = effs[effs.length >> 1], thr = etaThreshold(cfg);
  return {
    state: median < thr ? 'revisar' : 'ok',
    median, n: win.length,
    ratio: median / etaNominal(cfg) * 100,
    below: effs.filter(e => e < thr).length / effs.length,
  };
}
