// Gráficas en SVG a mano para la maqueta (en la app final → ECharts).
// Reglas: línea 2 px, puntos ≥ 8 px con anillo de superficie, rejilla hairline sólida,
// un solo eje Y, texto con tinta (nunca con el color de la serie), tooltip en hover.

const DOC = document.documentElement;
export const css = n => getComputedStyle(DOC).getPropertyValue(n).trim();
const col = c => (c.startsWith('--') ? css(c) : c);
export const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
export const fmt = (x, d = 0) => {
  if (!Number.isFinite(x)) return '—';
  const r = +x.toFixed(d) || 0; // evita «-0,0»
  return r.toLocaleString('es', { minimumFractionDigits: d, maximumFractionDigits: d });
};
export const hhmmss = ts => new Date(ts).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
export const hhmm = ts => new Date(ts).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit', hour12: false });
export const elapsed = s => {
  s = Math.round(s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), ss = s % 60;
  return h ? `${h}:${String(m).padStart(2, '0')} h` : `${m}:${String(ss).padStart(2, '0')}`;
};

export function niceTicks(min, max, count = 4) {
  if (!(max - min > 1e-9)) { max += 1; min -= 1; }
  const step0 = (max - min) / count, mag = 10 ** Math.floor(Math.log10(step0)), e = step0 / mag;
  const step = (e >= 7.5 ? 10 : e >= 3.5 ? 5 : e >= 1.5 ? 2 : 1) * mag;
  const lo = Math.floor(min / step + 1e-9) * step, hi = Math.ceil(max / step - 1e-9) * step, t = [];
  for (let v = lo; v <= hi + step / 2; v += step) t.push(+v.toFixed(10));
  return { lo, hi, t, step };
}
const decFor = step => step >= 1 ? 0 : step >= .1 ? 1 : 2;

export function monotone(xs, ys) {
  const n = xs.length; if (n < 2) return n ? `M${xs[0]},${ys[0]}` : '';
  const dx = [], m = [];
  for (let k = 0; k < n - 1; k++) { dx[k] = xs[k + 1] - xs[k] || 1e-6; m[k] = (ys[k + 1] - ys[k]) / dx[k]; }
  const t = [m[0]];
  for (let k = 1; k < n - 1; k++) {
    if (m[k - 1] * m[k] <= 0) t[k] = 0;
    else { const w1 = 2 * dx[k] + dx[k - 1], w2 = dx[k] + 2 * dx[k - 1]; t[k] = (w1 + w2) / (w1 / m[k - 1] + w2 / m[k]); }
  }
  t[n - 1] = m[n - 2];
  let d = `M${xs[0].toFixed(1)},${ys[0].toFixed(1)}`;
  for (let k = 0; k < n - 1; k++) {
    const h = dx[k] / 3;
    d += `C${(xs[k] + h).toFixed(1)},${(ys[k] + t[k] * h).toFixed(1)} ${(xs[k + 1] - h).toFixed(1)},${(ys[k + 1] - t[k + 1] * h).toFixed(1)} ${xs[k + 1].toFixed(1)},${ys[k + 1].toFixed(1)}`;
  }
  return d;
}

// Promedia en cubetas para no dibujar más puntos que píxeles útiles
function downsample(xs, ys, maxN) {
  if (xs.length <= maxN) return [xs, ys];
  const size = xs.length / maxN, ox = [], oy = [];
  for (let b = 0; b < maxN; b++) {
    const s = Math.floor(b * size), e = Math.max(s + 1, Math.floor((b + 1) * size));
    let sx = 0, sy = 0; for (let k = s; k < e; k++) { sx += xs[k]; sy += ys[k]; }
    ox.push(sx / (e - s)); oy.push(sy / (e - s));
  }
  ox[ox.length - 1] = xs[xs.length - 1]; oy[oy.length - 1] = ys[ys.length - 1];
  return [ox, oy];
}

function nearest(xs, x) {
  let lo = 0, hi = xs.length - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (xs[mid] < x) lo = mid; else hi = mid; }
  return Math.abs(xs[lo] - x) <= Math.abs(xs[hi] - x) ? lo : hi;
}

function xTicks(kind, x0, x1, iw, fmtNum) {
  const maxT = Math.max(2, Math.floor(iw / 76)), out = [];
  if (kind === 'num') {
    const nt = niceTicks(x0, x1, maxT);
    nt.t.forEach(v => { if (v >= x0 - 1e-9 && v <= x1 + 1e-9) out.push({ v, label: fmtNum(v, nt.step) }); });
    return out;
  }
  const span = (x1 - x0) / (kind === 'time' ? 1000 : 1);
  const steps = [5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800];
  const st = (steps.find(s => span / s <= maxT) || 10800) * (kind === 'time' ? 1000 : 1);
  for (let v = Math.ceil(x0 / st) * st; v <= x1; v += st) {
    out.push({ v, label: kind === 'time' ? (st < 60000 ? hhmmss(v) : hhmm(v)) : elapsed(v) });
  }
  return out;
}

function placeTip(tip, x, y, W) {
  tip.classList.add('show');
  const w = tip.offsetWidth;
  tip.style.left = (x + 14 + w > W ? Math.max(0, x - 14 - w) : x + 14) + 'px';
  tip.style.top = Math.max(0, y - 58) + 'px';
}

let uid = 0;

/**
 * Gráfica de líneas.
 * o.series: [{ data, y: d => valor, color: '--c-p', name }]
 * o.x: d => x (por defecto d.ts) · o.xKind: 'time' | 'elapsed' | 'num'
 * o.unit, o.dec, o.zero, o.ref: [{ y, label }], o.endLabels, o.xFmt (tooltip), o.xTickFmt
 */
export function lineChart(el, o) {
  const W = el.clientWidth, H = el.clientHeight;
  if (!W || !H) return;
  const kind = o.xKind || 'time', getX = o.x || (d => d.ts), dec = o.dec ?? 1, unit = o.unit ? ' ' + o.unit : '';
  const endLabels = o.endLabels !== false;
  const pl = 44, pr = endLabels ? 76 : 16, pt = 10, pb = 24, iw = W - pl - pr, ih = H - pt - pb;
  const S = o.series.filter(s => s.data.length).map(s => {
    const [xs, ys] = downsample(s.data.map(getX), s.data.map(s.y), Math.max(30, Math.floor(iw / (o.density || 4))));
    return { ...s, xs, ys, c: col(s.color) };
  });
  if (!S.length) { el.innerHTML = '<p class="empty">Sin datos</p>'; return; }
  let ymn = Infinity, ymx = -Infinity, xmn = Infinity, xmx = -Infinity;
  S.forEach(s => { s.ys.forEach(v => { ymn = Math.min(ymn, v); ymx = Math.max(ymx, v); }); xmn = Math.min(xmn, s.xs[0]); xmx = Math.max(xmx, s.xs[s.xs.length - 1]); });
  (o.ref || []).forEach(r => { ymn = Math.min(ymn, r.y); ymx = Math.max(ymx, r.y); });
  const pad = (ymx - ymn) * .12 || Math.abs(ymx) * .05 || 1;
  let lo = o.yMin ?? ymn - pad, hi = o.yMax ?? ymx + pad;
  if (o.zero && ymn >= 0) lo = Math.max(0, lo);
  const nt = niceTicks(lo, hi, clamp(Math.floor(ih / 36), 2, 5));
  const X = v => pl + (xmx === xmn ? iw : (v - xmn) / (xmx - xmn) * iw);
  const Y = v => pt + ih - (v - nt.lo) / (nt.hi - nt.lo) * ih;
  const xTipFmt = o.xFmt || (kind === 'time' ? hhmmss : kind === 'elapsed' ? elapsed : v => fmt(v, 1));
  const xTickFmt = o.xTickFmt || ((v, step) => fmt(v, decFor(step)));
  const id = 'lc' + (++uid);

  let g = '';
  nt.t.forEach(v => { const y = Y(v); g += `<line x1="${pl}" x2="${pl + iw}" y1="${y}" y2="${y}" stroke="var(--grid)"/><text x="${pl - 8}" y="${y + 4}" text-anchor="end">${fmt(v, o.tickDec ?? decFor(nt.step))}</text>`; });
  xTicks(kind, xmn, xmx, iw, xTickFmt).forEach(t => {
    const x = X(t.v); if (x < pl + 14 || x > pl + iw - 14) return;
    g += `<text x="${x}" y="${H - 6}" text-anchor="middle">${t.label}</text>`;
  });
  let marks = '';
  S.forEach((s, k) => {
    const xs = s.xs.map(X), ys = s.ys.map(Y); s.px = xs; s.py = ys;
    const d = monotone(xs, ys);
    if (S.length === 1 && o.area !== false) {
      marks += `<defs><linearGradient id="${id}g${k}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${s.c}" stop-opacity=".22"/><stop offset="1" stop-color="${s.c}" stop-opacity="0"/></linearGradient></defs>
        <path d="${d}L${xs[xs.length - 1]},${pt + ih}L${xs[0]},${pt + ih}Z" fill="url(#${id}g${k})"/>`;
    }
    marks += `<path d="${d}" fill="none" stroke="${s.c}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
  });
  (o.ref || []).forEach(r => {
    const y = Y(r.y);
    marks += `<line x1="${pl}" x2="${pl + iw}" y1="${y}" y2="${y}" stroke="var(--ink-3)" stroke-opacity=".8"/>
      <text x="${pl + 6}" y="${y - 6}" font-size="11" font-weight="600" fill="var(--ink-2)" stroke="var(--ring)" stroke-width="3" paint-order="stroke">${r.label}</text>`;
  });
  (o.points || []).forEach(p => {
    marks += `<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="6" fill="${col(p.color)}" stroke="var(--ring)" stroke-width="2"/>`;
    if (p.label) marks += `<text x="${X(p.x)}" y="${Y(p.y) - 12}" text-anchor="middle" font-size="11.5" font-weight="600" fill="var(--ink)" class="tnum">${p.label}</text>`;
  });
  // Puntos finales y etiquetas (si chocan, se omiten: la leyenda y el tooltip las cubren)
  const ends = S.map(s => ({ s, x: s.px[s.px.length - 1], y: s.py[s.py.length - 1], v: s.ys[s.ys.length - 1] }));
  const sorted = [...ends].sort((a, b) => a.y - b.y);
  const collide = sorted.some((e, k) => k && e.y - sorted[k - 1].y < 15);
  ends.forEach(e => {
    marks += `<circle cx="${e.x}" cy="${e.y}" r="5" fill="${e.s.c}" stroke="var(--ring)" stroke-width="2"/>`;
    if (endLabels && !collide) marks += `<text x="${e.x + 10}" y="${e.y + 4}" font-size="12" font-weight="600" fill="var(--ink)" class="tnum">${fmt(e.v, dec)}${unit}</text>`;
  });
  const hov = S.map(s => `<circle r="5" fill="${s.c}" stroke="var(--ring)" stroke-width="2"/>`).join('');

  el.innerHTML = `<svg role="img" aria-label="${o.aria || ''}">
    <g font-size="11" fill="var(--ink-3)" class="tnum">${g}</g>
    <line x1="${pl}" x2="${pl + iw}" y1="${pt + ih}" y2="${pt + ih}" stroke="var(--axis)"/>
    ${marks}
    <g class="hover" style="display:none"><line y1="${pt}" y2="${pt + ih}" stroke="var(--axis)"/>${hov}</g>
    <rect x="${pl}" y="${pt}" width="${iw}" height="${ih}" fill="transparent"/>
  </svg><div class="tip"></div>`;

  const svg = el.querySelector('svg'), hg = svg.querySelector('.hover'), tip = el.querySelector('.tip'), rect = svg.querySelector('rect');
  const dots = hg.querySelectorAll('circle'), vline = hg.querySelector('line');
  rect.addEventListener('pointermove', e => {
    const mx = e.clientX - svg.getBoundingClientRect().left;
    const xv = xmn + (mx - pl) / iw * (xmx - xmn);
    let rows = '', ty = Infinity, tx = mx;
    S.forEach((s, k) => {
      const i = nearest(s.xs, xv);
      dots[k].setAttribute('cx', s.px[i]); dots[k].setAttribute('cy', s.py[i]);
      ty = Math.min(ty, s.py[i]); if (k === 0) tx = s.px[i];
      rows += `<b class="tnum"><span class="key" style="--mc:${s.c}"></span>${S.length > 1 ? `<span style="font-weight:500;color:var(--ink-2)">${s.name}</span> ` : ''}${fmt(s.ys[i], dec)}${unit}</b>`;
    });
    hg.style.display = ''; vline.setAttribute('x1', tx); vline.setAttribute('x2', tx);
    tip.innerHTML = `${xTipFmt(S[0].xs[nearest(S[0].xs, xv)])}${rows}`;
    placeTip(tip, tx, ty, W);
  });
  rect.addEventListener('pointerleave', () => { hg.style.display = 'none'; tip.classList.remove('show'); });
}

/**
 * Dispersión. o: { data, x, y, color, fitFn, identity, last, lastLabel, recency,
 *   xTick(v, step), yTick(v, step), tip(d), yZero, maxDots }
 */
export function scatter(el, o) {
  const W = el.clientWidth, H = el.clientHeight;
  if (!W || !H || !o.data.length) return;
  const pl = 44, pr = 16, pt = 10, pb = 24, iw = W - pl - pr, ih = H - pt - pb;
  const c = col(o.color), maxDots = o.maxDots || 260;
  const step = Math.ceil(o.data.length / maxDots);
  const pts = o.data.filter((_, k) => k % step === 0 || k === o.data.length - 1);
  const xs = pts.map(o.x), ys = pts.map(o.y);
  const ext = (a, padK) => { let mn = Math.min(...a), mx = Math.max(...a); const p = (mx - mn) * padK || 1; return [mn - p, mx + p]; };
  let [x0, x1] = o.xDomain || ext(xs, .06), [y0, y1] = o.yDomain || ext(ys, .1);
  if (o.yZero) y0 = Math.min(0, y0);
  const xt = niceTicks(x0, x1, clamp(Math.floor(iw / 76), 2, 5)), yt = niceTicks(y0, y1, clamp(Math.floor(ih / 36), 2, 5));
  const X = v => pl + (v - xt.lo) / (xt.hi - xt.lo) * iw, Y = v => pt + ih - (v - yt.lo) / (yt.hi - yt.lo) * ih;
  const xTick = o.xTick || ((v, s) => fmt(v, decFor(s))), yTick = o.yTick || ((v, s) => fmt(v, decFor(s)));
  let g = '';
  yt.t.forEach(v => { const y = Y(v); g += `<line x1="${pl}" x2="${pl + iw}" y1="${y}" y2="${y}" stroke="var(--grid)"/><text x="${pl - 8}" y="${y + 4}" text-anchor="end">${yTick(v, yt.step)}</text>`; });
  xt.t.forEach(v => { g += `<text x="${X(v)}" y="${H - 6}" text-anchor="middle">${xTick(v, xt.step)}</text>`; });
  let marks = '';
  if (o.identity) {
    const a = Math.max(xt.lo, yt.lo), b = Math.min(xt.hi, yt.hi);
    marks += `<line x1="${X(a)}" y1="${Y(a)}" x2="${X(b)}" y2="${Y(b)}" stroke="var(--ink-3)" stroke-width="1"/>`;
  }
  pts.forEach((d, k) => {
    const op = o.recency === false ? .45 : .15 + .55 * k / pts.length;
    marks += `<circle cx="${X(xs[k]).toFixed(1)}" cy="${Y(ys[k]).toFixed(1)}" r="4" fill="${c}" fill-opacity="${op.toFixed(2)}"/>`;
  });
  if (o.fitFn) {
    const N = 40, fx = [], fy = [];
    for (let k = 0; k <= N; k++) { const xv = xt.lo + (xt.hi - xt.lo) * k / N, yv = o.fitFn(xv); if (yv >= yt.lo && yv <= yt.hi) { fx.push(X(xv)); fy.push(Y(yv)); } }
    if (fx.length > 1) marks += `<path d="${monotone(fx, fy)}" fill="none" stroke="var(--ink-2)" stroke-width="1.5" stroke-opacity=".75"/>`;
  }
  if (o.last !== false) {
    const lx = X(xs[xs.length - 1]), ly = Y(ys[ys.length - 1]);
    marks += `<circle cx="${lx}" cy="${ly}" r="6" fill="${c}" stroke="var(--ring)" stroke-width="2"/>`;
    if (o.lastLabel) marks += `<text x="${lx - 10}" y="${ly - 10}" text-anchor="end" font-size="11.5" font-weight="600" fill="var(--ink)">${o.lastLabel}</text>`;
  }
  el.innerHTML = `<svg role="img" aria-label="${o.aria || ''}">
    <g font-size="11" fill="var(--ink-3)" class="tnum">${g}</g>
    <line x1="${pl}" x2="${pl + iw}" y1="${pt + ih}" y2="${pt + ih}" stroke="var(--axis)"/>
    ${marks}<circle class="hl" r="6" fill="none" stroke="var(--ink)" stroke-width="2" style="display:none"/>
    <rect x="${pl}" y="${pt}" width="${iw}" height="${ih}" fill="transparent"/>
  </svg><div class="tip"></div>`;
  const svg = el.querySelector('svg'), tip = el.querySelector('.tip'), hl = svg.querySelector('.hl'), rect = svg.querySelector('rect');
  rect.addEventListener('pointermove', e => {
    const r = svg.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top;
    let best = -1, bd = 900;
    pts.forEach((_, k) => { const dd = (X(xs[k]) - px) ** 2 + (Y(ys[k]) - py) ** 2; if (dd < bd) { bd = dd; best = k; } });
    if (best < 0) { tip.classList.remove('show'); hl.style.display = 'none'; return; }
    hl.style.display = ''; hl.setAttribute('cx', X(xs[best])); hl.setAttribute('cy', Y(ys[best]));
    tip.innerHTML = o.tip(pts[best]);
    placeTip(tip, X(xs[best]), Y(ys[best]), W);
  });
  rect.addEventListener('pointerleave', () => { tip.classList.remove('show'); hl.style.display = 'none'; });
}

export function histogram(values, nb = 12) {
  let lo = Math.min(...values), hi = Math.max(...values);
  if (hi - lo < 1e-9) { hi += 1; lo -= 1; }
  const w = (hi - lo) / nb, bins = Array.from({ length: nb }, (_, k) => ({ lo: lo + k * w, hi: lo + (k + 1) * w, count: 0 }));
  values.forEach(v => bins[Math.min(nb - 1, Math.floor((v - lo) / w))].count++);
  return bins;
}

// Columnas: ≤ 24 px, extremo de datos redondeado 4 px, base recta, 2 px de aire entre columnas
const colPath = (x, w, y, y0) => {
  const r = Math.min(4, w / 2, (y0 - y));
  return r < 1 ? `M${x},${y0}V${y}H${x + w}V${y0}Z` : `M${x},${y0}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y0}Z`;
};

/** Histograma / columnas. o: { bins: [{ label, value, tip }], color, yTick, center } */
export function bars(el, o) {
  const W = el.clientWidth, H = el.clientHeight;
  if (!W || !H) return;
  const pl = 40, pr = 10, pt = 10, pb = 24, iw = W - pl - pr, ih = H - pt - pb, n = o.bins.length;
  const c = col(o.color), mx = Math.max(...o.bins.map(b => b.value)) || 1;
  const yt = niceTicks(0, mx * 1.08, clamp(Math.floor(ih / 36), 2, 4)), Y = v => pt + ih - v / yt.hi * ih;
  const slot = iw / n, bw = Math.min(24, slot - 2), every = Math.ceil(n * 52 / iw);
  let g = '', m = '', hits = '';
  yt.t.forEach(v => { const y = Y(v); g += `<line x1="${pl}" x2="${pl + iw}" y1="${y}" y2="${y}" stroke="var(--grid)"/><text x="${pl - 8}" y="${y + 4}" text-anchor="end">${(o.yTick || (v => fmt(v, 0)))(v)}</text>`; });
  o.bins.forEach((b, k) => {
    const x = pl + k * slot + (slot - bw) / 2;
    if (b.value > 0) m += `<path d="${colPath(x, bw, Y(b.value), pt + ih)}" fill="${o.colorFn ? col(o.colorFn(b)) : c}"/>`;
    if (k % every === 0) g += `<text x="${x + bw / 2}" y="${H - 6}" text-anchor="middle">${b.label}</text>`;
    hits += `<rect data-k="${k}" x="${pl + k * slot}" y="${pt}" width="${slot}" height="${ih}" fill="transparent"/>`;
  });
  el.innerHTML = `<svg role="img" aria-label="${o.aria || ''}"><g font-size="11" fill="var(--ink-3)" class="tnum">${g}</g>
    <line x1="${pl}" x2="${pl + iw}" y1="${pt + ih}" y2="${pt + ih}" stroke="var(--axis)"/>${m}${hits}</svg><div class="tip"></div>`;
  const tip = el.querySelector('.tip');
  el.querySelectorAll('rect[data-k]').forEach(r => {
    r.addEventListener('pointerenter', () => { const k = +r.dataset.k, b = o.bins[k]; tip.innerHTML = b.tip; placeTip(tip, pl + (k + .5) * slot, Y(b.value), W); r.setAttribute('fill', 'var(--chip)'); });
    r.addEventListener('pointerleave', () => { tip.classList.remove('show'); r.setAttribute('fill', 'transparent'); });
  });
}

/** Barras horizontales con valor en la punta. o: { items: [{ label, value }], color, valueFmt, max } */
export function hbars(el, o) {
  const W = el.clientWidth; if (!W) return;
  const n = o.items.length, rowH = 40, H = n * rowH, lw = 96, vw = 52, iw = W - lw - vw - 8;
  const c = col(o.color), mx = o.max || Math.max(...o.items.map(i => i.value)) || 1, bh = 12;
  el.style.height = H + 'px';
  let s = '';
  o.items.forEach((it, k) => {
    const y = k * rowH + rowH / 2, w = Math.max(2, it.value / mx * iw), r = Math.min(4, w / 2);
    s += `<text x="0" y="${y + 4}" font-size="12" fill="var(--ink-2)">${it.label}</text>
      <rect x="${lw}" y="${y - bh / 2}" width="${iw}" height="${bh}" rx="4" fill="var(--chip)"/>
      <path d="M${lw},${y - bh / 2}H${lw + w - r}Q${lw + w},${y - bh / 2} ${lw + w},${y - bh / 2 + r}V${y + bh / 2 - r}Q${lw + w},${y + bh / 2} ${lw + w - r},${y + bh / 2}H${lw}Z" fill="${c}"/>
      <text x="${lw + iw + 8}" y="${y + 4}" font-size="12" font-weight="600" fill="var(--ink)" class="tnum">${(o.valueFmt || (v => fmt(v, 0)))(it.value)}</text>`;
  });
  el.innerHTML = `<svg role="img" aria-label="${o.aria || ''}" viewBox="0 0 ${W} ${H}">${s}</svg>`;
}

export function spark(el, data, y, color) {
  const W = el.clientWidth, H = el.clientHeight; if (!W || !H || data.length < 2) return;
  const c = col(color), ys = data.map(y);
  let mn = Math.min(...ys), mx = Math.max(...ys); if (mx - mn < 1e-6) { mx += 1; mn -= 1; }
  const xs = ys.map((_, k) => k / (ys.length - 1) * (W - 6)), yv = ys.map(v => 4 + (H - 8) * (1 - (v - mn) / (mx - mn)));
  const d = monotone(xs, yv), id = 'sp' + (++uid);
  el.innerHTML = `<svg aria-hidden="true"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c}" stop-opacity=".18"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></linearGradient></defs>
    <path d="${d}L${xs[xs.length - 1]},${H}L0,${H}Z" fill="url(#${id})"/>
    <path d="${d}" fill="none" stroke="${c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${xs[xs.length - 1]}" cy="${yv[yv.length - 1]}" r="4" fill="${c}" stroke="var(--ring)" stroke-width="2"/></svg>`;
}

export function ring(svg, pct, color = '--c-p') {
  const r = 34, C = 2 * Math.PI * r, f = clamp(pct, 0, 100) / 100, c = col(color);
  svg.innerHTML = `
    <circle cx="42" cy="42" r="${r}" fill="none" stroke="${c}" stroke-opacity=".18" stroke-width="8"/>
    <circle cx="42" cy="42" r="${r}" fill="none" stroke="${c}" stroke-width="8" stroke-linecap="round"
      stroke-dasharray="${C * f} ${C}" transform="rotate(-90 42 42)" style="transition: stroke-dasharray .6s ease"/>
    <text x="42" y="47" text-anchor="middle" font-size="17" font-weight="700" fill="var(--ink)">${Math.round(pct)}%</text>`;
}
