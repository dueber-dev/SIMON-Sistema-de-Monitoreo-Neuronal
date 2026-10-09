// Modelo de DEMOSTRACIÓN: regresión polinómica entrenada en el navegador.
// Sustituto temporal del modelo del equipo, que llegará por /api/predict.
import { live } from './sim.js';
import { efficiency } from './physics.js';
export { efficiency };

// Mínimos cuadrados por ecuaciones normales + eliminación gaussiana con pivoteo
export function lstsq(rows, y) {
  const k = rows[0].length, A = Array.from({ length: k }, () => new Array(k).fill(0)), b = new Array(k).fill(0);
  rows.forEach((r, n) => { for (let p = 0; p < k; p++) { b[p] += r[p] * y[n]; for (let q = 0; q < k; q++) A[p][q] += r[p] * r[q]; } });
  for (let p = 0; p < k; p++) A[p][p] += 1e-9;
  for (let c = 0; c < k; c++) {
    let piv = c; for (let r = c + 1; r < k; r++) if (Math.abs(A[r][c]) > Math.abs(A[piv][c])) piv = r;
    [A[c], A[piv]] = [A[piv], A[c]]; [b[c], b[piv]] = [b[piv], b[c]];
    for (let r = c + 1; r < k; r++) { const f = A[r][c] / A[c][c]; for (let q = c; q < k; q++) A[r][q] -= f * A[c][q]; b[r] -= f * b[c]; }
  }
  const x = new Array(k).fill(0);
  for (let r = k - 1; r >= 0; r--) { let s = b[r]; for (let q = r + 1; q < k; q++) s -= A[r][q] * x[q]; x[r] = s / A[r][r]; }
  return x;
}

export function r2score(y, yhat) {
  const m = y.reduce((a, v) => a + v, 0) / y.length;
  let ssr = 0, sst = 0; y.forEach((v, k) => { ssr += (v - yhat[k]) ** 2; sst += (v - m) ** 2; });
  return 1 - ssr / (sst || 1);
}

export function polyfit(xs, ys, deg = 2) {
  const beta = lstsq(xs.map(x => Array.from({ length: deg + 1 }, (_, j) => x ** j)), ys);
  const f = x => beta.reduce((s, b, j) => s + b * x ** j, 0);
  return { beta, f, r2: r2score(ys, xs.map(f)) };
}

const FEATS = ['Irradiancia', 'Irradiancia²', 'Temperatura'];
const feats = (g, t) => [1, g / 100, (g / 100) ** 2, (t - 25) / 10];

let model = null;
export function train(pts) {
  const beta = lstsq(pts.map(d => feats(d.g, d.t)), pts.map(d => d.p));
  const predictP = (g, t) => Math.max(0, feats(g, t).reduce((s, x, j) => s + x * beta[j], 0));
  const predictEff = (g, t) => efficiency(predictP(g, t), g);
  const ok = pts.filter(d => d.g > 5);
  const real = ok.map(d => efficiency(d.p, d.g)), pred = ok.map(d => predictEff(d.g, d.t));
  const err = real.map((v, k) => pred[k] - v);
  const mae = err.reduce((a, e) => a + Math.abs(e), 0) / err.length;
  const rmse = Math.sqrt(err.reduce((a, e) => a + e * e, 0) / err.length);
  // Importancia: |β| × desviación estándar de cada variable, normalizada a 100 %
  const sd = j => { const v = pts.map(d => feats(d.g, d.t)[j]), m = v.reduce((a, x) => a + x, 0) / v.length; return Math.sqrt(v.reduce((a, x) => a + (x - m) ** 2, 0) / v.length); };
  const raw = [1, 2, 3].map(j => Math.abs(beta[j]) * sd(j)), tot = raw.reduce((a, x) => a + x, 0) || 1;
  model = {
    beta, predictP, predictEff,
    metrics: { r2: r2score(real, pred), mae, rmse, n: pts.length },
    importance: FEATS.map((label, k) => ({ label, value: raw[k] / tot * 100 })).sort((a, b) => b.value - a.value),
    trainedAt: Date.now(),
  };
  return model;
}

export function getModel() {
  return model || train(live.data.slice(-1800));
}
