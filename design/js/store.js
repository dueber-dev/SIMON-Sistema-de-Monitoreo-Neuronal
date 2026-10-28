// Configuración del sistema y preferencias de apariencia.
// En la maqueta se guardan en localStorage; en la app final la configuración vivirá en el backend.

export const DEFAULTS = {
  // Datos de EJEMPLO: el equipo debe reemplazarlos con la ficha técnica del panel real
  panel: { nombre: 'Panel monocristalino', nominal: 1.0, voc: 6.0, isc: 200, area: 110, coefT: -0.40, verificado: false },
  // kCarga: I_carga / I_sc con la carga de 30 Ω (de la curva I-V); alfaIsc: coeficiente de temperatura de I_sc en %/°C
  sensores: { ldrFactor: 10, ldrCalibrado: false, ldrInvertir: false, lm35Offset: 0, iMin: 0.01, ina: '32V_1A', kCarga: 0.95, alfaIsc: 0.05 },
  conexion: { modo: 'sim', escenario: 'normal', ip: '192.168.4.1', puerto: 8080, reconectar: true },
  // mant: umbral de mantenimiento en % de la eficiencia nominal; se evalúa con G ≥ mantGmin durante mantMin minutos
  // suciedad: umbral del índice S = G_panel / G_LDR en % (debajo de él, panel sucio o sombreado)
  alertas: { tMax: 45, pMin: 1, sinDatos: 5, sonido: false, mant: 75, mantGmin: 300, mantMin: 5, suciedad: 85 },
  datos: { base: 'datos_panel_solar_wifi', timestamp: true },
  ui: { equipo: 'equipo SIMON' },
};

const safe = {
  get(k, d) { try { const v = localStorage.getItem('simon.' + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('simon.' + k, JSON.stringify(v)); } catch {} },
};
export const prefs = safe;

const clone = o => JSON.parse(JSON.stringify(o));
function merge(base, over) {
  const out = clone(base);
  for (const k in over) {
    if (k in out && typeof out[k] === 'object' && out[k] !== null) Object.assign(out[k], over[k]);
  }
  return out;
}

export const config = merge(DEFAULTS, safe.get('config', {}));

// Avisa a las vistas cuando cambia la configuración
export const bus = new EventTarget();

export function saveConfig(next) {
  for (const k in next) Object.assign(config[k], next[k]);
  safe.set('config', config);
  bus.dispatchEvent(new Event('config'));
}

export function resetConfig() {
  saveConfig(clone(DEFAULTS));
}
