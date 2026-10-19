"""Geometría de cobre con shapely: relleno de GND y ubicación de etiquetas.

La usan generar_brd.py (para ubicar las etiquetas sin tocar cobre) y render.py
(para dibujar el relleno igual que lo calcula Fusion con el polígono).
"""
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union
from shapely import affinity
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties

ELONG = 0.55          # psElongationLong de las reglas
AISLAMIENTO = 0.8     # separación del relleno contra todo lo que no es GND
MARGEN_BORDE = 1.0    # el relleno no llega al borde
MARGEN_CAJA = 0.7     # aire entre el texto y el borde de su recuadro blanco
FUENTE = FontProperties(family="DejaVu Sans", weight="bold")


def forma_pad(x, y, d, shape, vertical):
    r = d / 2
    if shape == "long":
        L = d * (1 + ELONG) / 2 - r
        a, b = ((x, y - L), (x, y + L)) if vertical else ((x - L, y), (x + L, y))
        return LineString([a, b]).buffer(r, quad_segs=12)
    return Point(x, y).buffer(r, quad_segs=12)


def forma_pista(x1, y1, x2, y2, w):
    return LineString([(x1, y1), (x2, y2)]).buffer(w / 2, quad_segs=12)


def caja_texto(s, x, y, size, rot="R0"):
    """Recuadro (ya rotado) que ocupa un texto centrado en (x, y)."""
    tp = TextPath((0, 0), s, size=size * 1.38, prop=FUENTE)
    bb = tp.get_extents()
    w = max(bb.width, len(s) * size * 0.95) + 2 * MARGEN_CAJA
    h = size + 2 * MARGEN_CAJA
    c = box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    ang = float(rot.lstrip("SMR") or 0)
    return affinity.rotate(c, ang, origin=(x, y)) if ang else c


def colocar(etiquetas, cobre, ancho, alto, ocupadas=(), paso=0.25, radio=12.0):
    """Para cada (texto, x, y, size, rot) busca el punto más cercano al ancla
    donde su recuadro no toque cobre (con AISLAMIENTO) ni otras etiquetas."""
    obst = unary_union(cobre)
    interior = box(MARGEN_BORDE, MARGEN_BORDE, ancho - MARGEN_BORDE, alto - MARGEN_BORDE)
    puestas = list(ocupadas)
    salida = []
    n = int(radio / paso)
    offsets = sorted((i * i + j * j, i * paso, j * paso)
                     for i in range(-n, n + 1) for j in range(-n, n + 1)
                     if (i * i + j * j) * paso * paso <= radio * radio)
    for et in etiquetas:
        s, ax, ay, size, rot = et[:5]
        r_max = et[5] if len(et) > 5 else radio
        # Primero horizontal al tamaño pedido; si no cabe, vertical; luego más chico.
        vertical = rot[:-1] + "90" if rot.endswith("0") and not rot.endswith("90") else rot
        intentos = [(size, rot), (size, vertical), (size * 0.8, rot), (size * 0.8, vertical)]
        hecho = False
        for sz, rr in intentos:
            for d2, dx, dy in offsets:
                if d2 * paso * paso > r_max * r_max:
                    break
                x, y = ax + dx, ay + dy
                c = caja_texto(s, x, y, sz, rr)
                if not interior.contains(c) or c.distance(obst) < AISLAMIENTO:
                    continue
                if any(c.distance(p) < 0.4 for p in puestas):
                    continue
                puestas.append(c)
                salida.append((s, round(x, 2), round(y, 2), sz, rr, c))
                hecho = True
                break
            if hecho:
                break
        if not hecho:
            raise RuntimeError(f"no encontré lugar para la etiqueta {s!r}")
    return salida


def relleno(cobre_gnd, cobre_otros, cajas, ancho, alto):
    """Relleno de GND: placa menos (otras señales + aislamiento) menos recuadros,
    sin islas sueltas (orphans=no)."""
    base = box(MARGEN_BORDE, MARGEN_BORDE, ancho - MARGEN_BORDE, alto - MARGEN_BORDE)
    huecos = unary_union([g.buffer(AISLAMIENTO, quad_segs=12) for g in cobre_otros] + list(cajas))
    r = base.difference(huecos)
    gnd = unary_union(cobre_gnd)
    partes = getattr(r, "geoms", [r])
    vivas = [p for p in partes if p.intersects(gnd)]
    return unary_union(vivas + [gnd])
