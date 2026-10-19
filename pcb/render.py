"""Dibuja SIMON.brd para imprimir y revisar, sin depender de Fusion.

Salidas (junto a este archivo):
  SIMON_cobre_1a1.pdf  capa Bottom a escala 1:1, negro sobre blanco, vista desde
                       arriba (así se imprime la capa inferior para planchar: SIN espejo)
  SIMON_montaje.pdf    guía de montaje (serigrafía + pads) vista desde arriba, 1:1
  SIMON_preview.png    vista combinada para revisar
"""
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, PathPatch, Polygon, Rectangle
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from matplotlib.transforms import Affine2D

AQUI = Path(__file__).parent
BRD = AQUI / "SIMON.brd"
ELONG = 0.55
FUENTE = FontProperties(family="DejaVu Sans", weight="bold")


def f(x):
    return float(x)


def rot_deg(r):
    return float(r.lstrip("SMR") or 0), "M" in r


def cargar():
    raiz = ET.parse(BRD).getroot()
    board = raiz.find("drawing/board")
    pkgs = {p.get("name"): p for p in board.iter("package")}
    pads, silk, cobre, textos = [], [], [], []
    for el in board.find("elements"):
        ex, ey = f(el.get("x")), f(el.get("y"))
        pk = pkgs[el.get("package")]
        for p in pk.findall("pad"):
            d = f(p.get("diameter"))
            pads.append(dict(x=ex + f(p.get("x")), y=ey + f(p.get("y")), d=d,
                             drill=f(p.get("drill")), shape=p.get("shape"),
                             vertical=p.get("rot") == "R90", el=el.get("name")))
        for w in pk.findall("wire"):
            if w.get("layer") == "21":
                silk.append(("wire", ex, ey, w))
        for c in pk.findall("circle"):
            if c.get("layer") == "21":
                silk.append(("circle", ex, ey, c))
        for t in pk.findall("text"):
            if t.get("layer") in ("21", "25"):
                s = t.text.replace(">NAME", el.get("name"))
                silk.append(("text", ex, ey, t, s))
    for s in board.find("signals"):
        for w in s.findall("wire"):
            cobre.append((f(w.get("x1")), f(w.get("y1")), f(w.get("x2")), f(w.get("y2")), f(w.get("width"))))
    for t in board.find("plain").findall("text"):
        textos.append(t)
    borde = [w for w in board.find("plain").findall("wire") if w.get("layer") == "20"]
    xs = [f(w.get(k)) for w in borde for k in ("x1", "x2")]
    ys = [f(w.get(k)) for w in borde for k in ("y1", "y2")]
    return dict(pads=pads, silk=silk, cobre=cobre, textos=textos,
                ancho=max(xs) - min(xs), alto=max(ys) - min(ys))


def dibujar_texto(ax, s, x, y, size, rot, color, centrado=True, alinear="center"):
    ang, espejo = rot_deg(rot)
    tp = TextPath((0, 0), s, size=size * 1.38, prop=FUENTE)
    bb = tp.get_extents()
    if alinear == "center-left":
        dx, dy = -bb.x0, -(bb.y0 + bb.y1) / 2
    elif alinear == "center-right":
        dx, dy = -bb.x1, -(bb.y0 + bb.y1) / 2
    elif alinear == "center":
        dx, dy = -(bb.x0 + bb.x1) / 2, -(bb.y0 + bb.y1) / 2
    else:
        dx, dy = 0, 0
    tr = Affine2D().translate(dx, dy)
    if espejo:
        tr = tr.scale(-1, 1)
    tr = tr.rotate_deg(ang).translate(x, y)
    ax.add_patch(PathPatch(tr.transform_path(tp), color=color, lw=0))


def dibujar_pad(ax, p, color, agujero):
    d = p["d"]
    if p["shape"] == "long":
        L = d * (1 + ELONG)
        w, h = (d, L) if p["vertical"] else (L, d)
        ax.add_patch(FancyBboxPatch((p["x"] - w / 2 + d / 2, p["y"] - h / 2 + d / 2),
                                    w - d, h - d, boxstyle=f"round,pad={d / 2}",
                                    color=color, lw=0))
    else:
        ax.add_patch(Circle((p["x"], p["y"]), d / 2, color=color, lw=0))
    if agujero:
        # Punto guía para la broca (más chico que la broca real, ayuda a centrar)
        ax.add_patch(Circle((p["x"], p["y"]), min(p["drill"], 0.8) / 2, color=agujero, lw=0))


def dibujar_cobre(ax, b, color, agujero):
    for x1, y1, x2, y2, w in b["cobre"]:
        ax.plot([x1, x2], [y1, y2], color=color, lw=w * 72 / 25.4, solid_capstyle="round",
                solid_joinstyle="round")
    for p in b["pads"]:
        dibujar_pad(ax, p, color, agujero)
    for t in b["textos"]:
        if t.get("layer") == "16":
            dibujar_texto(ax, t.text, f(t.get("x")), f(t.get("y")), f(t.get("size")),
                          t.get("rot", "R0"), color)


def dibujar_silk(ax, b, color):
    for item in b["silk"]:
        tipo, ex, ey, n = item[:4]
        if tipo == "wire":
            x1, y1, x2, y2 = (f(n.get(k)) for k in ("x1", "y1", "x2", "y2"))
            curva = n.get("curve")
            if curva:
                # Arco de 180° entre los extremos (contorno del TO-92)
                cx, cy = ex + (x1 + x2) / 2, ey + (y1 + y2) / 2
                r = math.hypot(x2 - x1, y2 - y1) / 2
                a0 = math.degrees(math.atan2(y1 - (y1 + y2) / 2, x1 - (x1 + x2) / 2))
                sentido = 1 if f(curva) > 0 else -1
                angs = [math.radians(a0 + sentido * k * 180 / 40) for k in range(41)]
                ax.plot([cx + r * math.cos(a) for a in angs], [cy + r * math.sin(a) for a in angs],
                        color=color, lw=0.6)
            else:
                ax.plot([ex + x1, ex + x2], [ey + y1, ey + y2], color=color, lw=0.6)
        elif tipo == "circle":
            ax.add_patch(Circle((ex + f(n.get("x")), ey + f(n.get("y"))), f(n.get("radius")),
                                fill=False, color=color, lw=0.6))
        elif tipo == "text":
            s = item[4]
            alinear = n.get("align", "bottom-left")
            dibujar_texto(ax, s, ex + f(n.get("x")), ey + f(n.get("y")), f(n.get("size")) * 0.8,
                          n.get("rot", "R0"), color, alinear=alinear)


def pagina_1a1(b, titulo, contenido, salida):
    """Hoja carta con la placa a escala exacta 1:1 y una regla de 50 mm."""
    W, H = 215.9, 279.4
    fig = plt.figure(figsize=(W / 25.4, H / 25.4))
    ox, oy = 20.0, H - 40.0 - b["alto"]
    ax = fig.add_axes([ox / W, oy / H, b["ancho"] / W, b["alto"] / H])
    ax.set_xlim(0, b["ancho"]); ax.set_ylim(0, b["alto"]); ax.axis("off")
    contenido(ax)
    ax.add_patch(Rectangle((0, 0), b["ancho"], b["alto"], fill=False, color="black", lw=0.5))
    # Regla de verificación
    rx = fig.add_axes([ox / W, (oy - 18) / H, 50 / W, 6 / H])
    rx.set_xlim(0, 50); rx.set_ylim(0, 6); rx.axis("off")
    rx.plot([0, 50], [1, 1], color="black", lw=1)
    for k in range(0, 51, 10):
        rx.plot([k, k], [1, 3], color="black", lw=1)
    fig.text(ox / W, (oy - 24) / H, "Debe medir 50 mm exactos. Imprimir al 100 % (sin 'ajustar a la página').",
             fontsize=8)
    fig.text(ox / W, (H - 20) / H, titulo, fontsize=11, weight="bold")
    fig.savefig(salida)
    plt.close(fig)


def main():
    b = cargar()
    pagina_1a1(b, "SIMON v1 - capa de cobre (Bottom) para planchado - vista superior, SIN espejo",
               lambda ax: dibujar_cobre(ax, b, "black", "white"), AQUI / "SIMON_cobre_1a1.pdf")

    def montaje(ax):
        dibujar_cobre(ax, b, "#d9d9d9", "white")
        dibujar_silk(ax, b, "black")
    pagina_1a1(b, "SIMON v1 - guía de montaje (componentes por arriba)", montaje,
               AQUI / "SIMON_montaje.pdf")

    fig = plt.figure(figsize=(b["ancho"] / 10, b["alto"] / 10), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, b["ancho"]); ax.set_ylim(0, b["alto"]); ax.axis("off")
    ax.add_patch(Rectangle((0, 0), b["ancho"], b["alto"], color="#1f5130"))
    dibujar_cobre(ax, b, "#d98c3a", "#1f5130")
    dibujar_silk(ax, b, "white")
    fig.savefig(AQUI / "SIMON_preview.png", dpi=200)
    plt.close(fig)
    print("listo: SIMON_cobre_1a1.pdf, SIMON_montaje.pdf, SIMON_preview.png")


if __name__ == "__main__":
    main()
