import test from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULTS, config, saveConfig } from '../design/js/store.js';
import { maintenance, efficiency, etaNominal, pTheory } from '../design/js/physics.js';

const cfg = structuredClone(DEFAULTS);
const series = (n, step = 1000, p = 400) => Array.from({length: n}, (_, i) => ({ts: i * step, g: 80, p}));
test('unidades de eficiencia y potencia teórica', () => {
  assert.ok(Math.abs(etaNominal(cfg) - 100 / 11) < 1e-10);
  assert.ok(Math.abs(efficiency(800, 80, cfg) - 100 / 11) < 1e-10);
  assert.equal(pTheory(80, 25, cfg), 800);
});
test('un minuto no acredita una ventana de cinco minutos', () => {
  assert.equal(maintenance(series(60), cfg).state, 'sin-luz');
});
test('cinco minutos de baja eficiencia generan revisión', () => {
  assert.equal(maintenance(series(300), cfg).state, 'revisar');
  assert.equal(maintenance(series(300, 1000, 800), cfg).state, 'ok');
});
test('muestras antiguas o escasas no acreditan cobertura', () => {
  assert.equal(maintenance(series(300, 10000), cfg).state, 'sin-luz');
  assert.equal(maintenance(Array(300).fill({ts:0, g:80, p:400}), cfg).state, 'sin-luz');
});
test('oscuridad actual impide evaluar mantenimiento', () => {
  const data = series(300); data.at(-1).g = 0;
  assert.equal(maintenance(data, cfg).state, 'sin-luz');
});
test('mediana par promedia los dos valores centrales', () => {
  const data = series(60, 1000, 400); data.slice(30).forEach(d => {d.p = 800;});
  assert.ok(Math.abs(maintenance(data, cfg, 60).median - efficiency(600, 80, cfg)) < 1e-10);
});
test('historial completo y datos inválidos', () => {
  assert.equal(maintenance(series(600), cfg, Infinity).state, 'revisar');
  assert.equal(maintenance([], cfg).state, 'sin-luz');
  assert.equal(maintenance([{ts:0, p:NaN, g:80}], cfg).state, 'sin-luz');
});
test('la configuración no puede declarar una conexión inexistente', () => {
  saveConfig({conexion: {modo: 'esp32'}});
  assert.equal(config.conexion.modo, 'sim');
});
