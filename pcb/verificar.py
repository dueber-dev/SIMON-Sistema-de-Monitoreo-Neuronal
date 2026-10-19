"""Chequeo propio de SIMON antes de llevarlo a Fusion: conectividad y separaciones.

Modela pads como estadios/círculos y pistas como segmentos con ancho, y mide
la distancia mínima de cobre entre señales distintas y contra el borde.
"""
import math
import generar_brd as g

ELONG = 0.55
MIN_CLEAR = 0.5


def pads_absolutos():
    """[(elemento, pad, x, y, rx, ry)] — semiejes del pad (estadio si rx != ry)."""
    import re
    out = []
    for nom, pkg, _, ex, ey in g.ELEMENTOS:
        for m in re.finditer(r'<pad name="([^"]+)" x="([^"]+)" y="([^"]+)" drill="([^"]+)" diameter="([^"]+)" shape="([^"]+)" rot="([^"]+)"', g.PAQUETES[pkg]):
            n, x, y, dr, d, sh, rot = m.groups()
            x, y, d = float(x) + ex, float(y) + ey, float(d)
            rx = ry = d / 2
            if sh == "long":
                L = d * (1 + ELONG) / 2
                if rot == "R90":
                    ry = L
                else:
                    rx = L
            out.append((nom, n, x, y, rx, ry))
    return out


def seg_pad_axis(rx, ry, x, y):
    """Un pad como segmento central + radio."""
    r = min(rx, ry)
    if rx > ry:
        return (x - (rx - r), y, x + (rx - r), y, r)
    return (x, y - (ry - r), x, y + (ry - r), r)


def dist_pt_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def dist_seg_seg(a, b):
    (ax, ay, bx, by), (cx, cy, dx, dy) = a, b
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    A, B, C, D = (ax, ay), (bx, by), (cx, cy), (dx, dy)
    if (ccw(A, B, C) * ccw(A, B, D) < 0) and (ccw(C, D, A) * ccw(C, D, B) < 0):
        return 0.0
    return min(dist_pt_seg(ax, ay, cx, cy, dx, dy), dist_pt_seg(bx, by, cx, cy, dx, dy),
               dist_pt_seg(cx, cy, ax, ay, bx, by), dist_pt_seg(dx, dy, ax, ay, bx, by))


def main():
    pads = pads_absolutos()
    pad_sig = {}
    for s, (_, lst, _) in g.SENALES.items():
        for el, pd in lst:
            pad_sig[(el, pd)] = s
    # Objetos de cobre: (señal, segmento, radio, descripción)
    cobre = []
    for el, n, x, y, rx, ry in pads:
        ax, ay, bx, by, r = seg_pad_axis(rx, ry, x, y)
        cobre.append((pad_sig.get((el, n), f"NC:{el}.{n}"), (ax, ay, bx, by), r, f"pad {el}.{n}"))
    errores = 0
    for s, (w, lst, pistas) in g.SENALES.items():
        # Conectividad: unión de pads y extremos de pistas por coincidencia de puntos.
        nodos = {}
        def find(a):
            while nodos[a] != a:
                nodos[a] = nodos[nodos[a]]
                a = nodos[a]
            return a
        def union(a, b):
            nodos.setdefault(a, a); nodos.setdefault(b, b)
            nodos[find(a)] = find(b)
        pos_pad = {}
        for el, n, x, y, *_ in pads:
            if (el, n) in lst:
                k = (round(x, 3), round(y, 3))
                pos_pad[(el, n)] = k
                nodos.setdefault(k, k)
        for poli in pistas:
            for p, q in zip(poli, poli[1:]):
                kp, kq = (round(p[0], 3), round(p[1], 3)), (round(q[0], 3), round(q[1], 3))
                union(kp, kq)
                cobre.append((s, (p[0], p[1], q[0], q[1]), w / 2, f"pista {s} {p}->{q}"))
        for poli in pistas:
            for p in (poli[0], poli[-1]):
                k = (round(p[0], 3), round(p[1], 3))
                extremos = [kk for poli2 in pistas for kk in
                            [(round(poli2[0][0], 3), round(poli2[0][1], 3)), (round(poli2[-1][0], 3), round(poli2[-1][1], 3))]]
                if k not in pos_pad.values() and extremos.count(k) < 2:
                    print(f"[{s}] extremo suelto en {k}")
                    errores += 1
        raices = {find(k) for k in pos_pad.values()}
        if len(raices) != 1:
            print(f"[{s}] NO conectada: {len(raices)} islas")
            errores += 1
        else:
            print(f"[{s}] ok ({len(lst)} pads)")
    # Separaciones entre señales distintas
    peor = {}
    for i in range(len(cobre)):
        for j in range(i + 1, len(cobre)):
            si, ai, ri, di = cobre[i]
            sj, aj, rj, dj = cobre[j]
            if si == sj:
                continue
            gap = dist_seg_seg(ai, aj) - ri - rj
            if gap < MIN_CLEAR:
                print(f"  SEPARACIÓN {gap:.2f} mm: {di}  <->  {dj}")
                errores += 1
            key = "min"
            if key not in peor or gap < peor[key][0]:
                peor[key] = (gap, di, dj)
    print("separación mínima entre señales: %.2f mm (%s / %s)" % peor["min"])
    # Borde
    borde_min = min(min(a[0], a[2]) - r for _, a, r, _ in cobre)
    borde_min = min(borde_min, min(min(a[1], a[3]) - r for _, a, r, _ in cobre))
    borde_min = min(borde_min, min(g.ANCHO - max(a[0], a[2]) - r for _, a, r, _ in cobre))
    borde_min = min(borde_min, min(g.ALTO - max(a[1], a[3]) - r for _, a, r, _ in cobre))
    print("distancia mínima cobre-borde: %.2f mm" % borde_min)
    print("ERRORES:", errores)


if __name__ == "__main__":
    main()
