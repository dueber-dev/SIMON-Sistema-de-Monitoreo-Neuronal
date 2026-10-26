"""Guía de montaje ilustrada: qué componente va en cada lugar de la placa.

Vista desde el lado de las piezas (arriba). El cobre está debajo y se ve tenue.
Salida: SIMON_guia_montaje.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle, Wedge, Polygon

import generar_brd as g

AQUI = Path(__file__).parent
ELONG = 0.55

# Colores por tipo de pieza
C_PLACA = "#2f6b45"
C_COBRE = "#c9a24a"
C_ESP = "#2b2b2b"
C_MOD = "#5b2a86"
C_RES = "#e8d3a6"
C_SENS = "#1f6fb2"
C_CAP = "#1b3f8f"
C_BORN = "#2c8fd6"
TXT = "white"

POS = {nom: (x, y) for nom, _, _, x, y in g.ELEMENTOS}


def pads():
    for el, n, x, y, d, sh, vert in g.pads_absolutos():
        yield el, n, x, y, d, sh, vert


def dibujar_pad(ax, x, y, d, sh, vert, color, z=3):
    if sh == "long":
        L = d * (1 + ELONG)
        w, h = (d, L) if vert else (L, d)
        ax.add_patch(FancyBboxPatch((x - w / 2 + d / 2, y - h / 2 + d / 2), w - d, h - d,
                                    boxstyle=f"round,pad={d / 2}", color=color, lw=0, zorder=z))
    else:
        ax.add_patch(Circle((x, y), d / 2, color=color, lw=0, zorder=z))
    ax.add_patch(Circle((x, y), 0.45, color="#1d1d1d", lw=0, zorder=z + 0.1))


def caja(ax, x1, y1, x2, y2, color, alpha=0.88, z=4, r=0.8):
    ax.add_patch(FancyBboxPatch((x1 + r, y1 + r), x2 - x1 - 2 * r, y2 - y1 - 2 * r,
                                boxstyle=f"round,pad={r}", color=color, alpha=alpha, lw=0, zorder=z))


def etiqueta(ax, x, y, s, size=9, color=TXT, z=8, **kw):
    ax.text(x, y, s, ha="center", va="center", fontsize=size, color=color, zorder=z,
            weight="bold", **kw)


def main():
    fig = plt.figure(figsize=(16, 9.6), dpi=150)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([0.02, 0.10, 0.66, 0.80])
    ax.set_xlim(-2, g.ANCHO + 2)
    ax.set_ylim(-6, g.ALTO + 2)
    ax.set_aspect("equal")
    ax.axis("off")

    # Placa y cobre tenue (se ve "a través" de la placa)
    ax.add_patch(Rectangle((0, 0), g.ANCHO, g.ALTO, color=C_PLACA, zorder=0))
    for _, (w, _, pistas) in g.SENALES.items():
        for poli in pistas:
            xs, ys = zip(*poli)
            ax.plot(xs, ys, color="#5f9a72", lw=w * 4.2, solid_capstyle="round", zorder=1)
    for el, n, x, y, d, sh, vert in pads():
        dibujar_pad(ax, x, y, d, sh, vert, C_COBRE)

    # ---- U1: ESP32
    x, y = POS["U1"]
    caja(ax, x - 14.15, y - 23.3, x + 14.15, min(y + 26.2, g.ALTO + 1.5), C_ESP, alpha=0.80)
    etiqueta(ax, x, y + 8, "U1", 16)
    etiqueta(ax, x, y + 3, "ESP32 DevKit V1\n(30 pines)", 11)
    etiqueta(ax, x, y - 6, "va sobre headers\nhembra 1x15", 8.5, color="#cfcfcf")
    etiqueta(ax, x, y + 22.5, "▲ ANTENA", 9, color="#cfcfcf")
    etiqueta(ax, x, y - 20.5, "▼ USB (hacia el borde)", 9, color="#ffd27a")
    for i, (a, b) in enumerate(zip(g.ESP_IZQ, g.ESP_DER)):
        yy = y + (7 - i) * 2.54
        if a in ("D32", "D33", "GND_L", "VIN"):
            etiqueta(ax, x - 9.4, yy, a.replace("_L", ""), 7.5, color="#ffd27a")
        if b in ("D22", "D21", "GND_R", "3V3"):
            etiqueta(ax, x + 9.4, yy, b.replace("_R", ""), 7.5, color="#ffd27a")

    # ---- U2: módulo INA219 (cuerpo a la derecha del header)
    x, y = POS["U2"]
    caja(ax, x - 2.4, y - 10.15, x + 20.6, y + 10.15, C_MOD, alpha=0.82)
    etiqueta(ax, x + 12.5, y + 3.5, "U2", 15)
    etiqueta(ax, x + 12.5, y - 1.5, "Módulo INA219", 10.5)
    etiqueta(ax, x + 12.5, y - 5.5, "header 1x6 a la izquierda", 8, color="#e2d3f0")
    for k, e in enumerate(["VCC", "GND", "SCL", "SDA", "VIN−", "VIN+"]):
        ax.text(x + 2.0, y + 6.35 - k * 2.54, e, ha="left", va="center", fontsize=7.5,
                color="#ffd27a", weight="bold", zorder=8)

    # ---- R1..R3: 10 Ω de carga (verticales)
    for r in ("R1", "R2", "R3"):
        x, y = POS[r]
        caja(ax, x - 1.5, y - 5.0, x + 1.5, y + 5.0, C_RES, alpha=1, r=0.6)
        for dy in (-2.6, 0, 2.6):
            ax.add_patch(Rectangle((x - 1.5, y + dy - 0.35), 3.0, 0.7, color="#8b5a2b", zorder=5))
        ax.plot([x, x], [y + 5, y + 7.62], color="#bbbbbb", lw=2, zorder=4)
        ax.plot([x, x], [y - 5, y - 7.62], color="#bbbbbb", lw=2, zorder=4)
        etiqueta(ax, x, y + 9.6, r, 10)
    etiqueta(ax, 74, 4.0, "R1 R2 R3 = 10 Ω  ½–1 W", 9, color="#ffd27a")

    # ---- R4: 10 kΩ
    x, y = POS["R4"]
    caja(ax, x - 1.1, y - 2.9, x + 1.1, y + 2.9, C_RES, alpha=1, r=0.5)
    for dy in (-1.4, 0, 1.4):
        ax.add_patch(Rectangle((x - 1.1, y + dy - 0.25), 2.2, 0.5, color="#c07a2c", zorder=5))
    ax.plot([x, x], [y + 2.9, y + 5.08], color="#bbbbbb", lw=2, zorder=4)
    ax.plot([x, x], [y - 2.9, y - 5.08], color="#bbbbbb", lw=2, zorder=4)
    etiqueta(ax, x + 3.4, y + 3.4, "R4", 10)
    etiqueta(ax, x + 3.4, y + 1.4, "10 kΩ", 8, color="#ffd27a")

    # ---- U3: LM35 (cara plana a la izquierda)
    x, y = POS["U3"]
    ax.add_patch(Wedge((x - 1.2, y), 3.6, -90, 90, color=C_SENS, alpha=0.95, zorder=4))
    ax.plot([x - 1.2, x - 1.2], [y - 3.6, y + 3.6], color="white", lw=2.5, zorder=5)
    fondo = dict(boxstyle="round,pad=0.2", fc=C_PLACA, ec="none")
    etiqueta(ax, x + 0.5, y - 6.2, "U3  LM35", 9.5, bbox=fondo)
    etiqueta(ax, x + 0.5, y - 8.6, "cara plana a la izq.", 7, color="#ffd27a", bbox=fondo)
    for k, e in enumerate(["+Vs", "Out", "GND"]):
        ax.text(x - 2.0, y + 2.54 - k * 2.54, e, ha="right", va="center", fontsize=6.5,
                color="white", weight="bold", zorder=8, bbox=fondo)

    # ---- LDR
    x, y = POS["LDR1"]
    ax.add_patch(Circle((x, y), 2.6, color="#d8572a", alpha=0.95, zorder=4))
    ax.plot([x - 1.6, x - 0.6, 0.4 + x, 1.4 + x], [y + 0.8, y - 0.8, y + 0.8, y - 0.8],
            color="#fff1c1", lw=1.5, zorder=5)
    etiqueta(ax, x, y + 4.4, "LDR (fotorresistencia)", 8.5)

    # ---- C1: 100 µF (+ a la derecha)
    x, y = POS["C1"]
    ax.add_patch(Circle((x, y), 3.2, color=C_CAP, alpha=0.95, zorder=4))
    ax.add_patch(Wedge((x, y), 3.2, 120, 240, color="#9fb6e8", zorder=5))
    etiqueta(ax, x - 1.9, y, "−", 11, color=C_CAP)
    etiqueta(ax, x + 1.4, y + 0.1, "+", 11)
    etiqueta(ax, x, y + 5.0, "C1  100 µF", 9)
    etiqueta(ax, x, y - 4.6, "+ hacia el ESP32", 7.5, color="#ffd27a")

    # ---- J1: bornera del panel
    x, y = POS["J1"]
    caja(ax, x - 5.0, y - 3.6, x + 5.0, y + 4.0, C_BORN, alpha=0.95, r=0.5)
    etiqueta(ax, x - 2.54, y + 2.3, "−", 13)
    etiqueta(ax, x + 2.54, y + 2.3, "+", 13)
    etiqueta(ax, x, y + 6.0, "J1  bornera panel solar", 8.5)
    etiqueta(ax, x, -2.6, "cable negro → −    cable rojo → +", 8, color="#1d1d1d")

    ax.text(g.ANCHO / 2, g.ALTO + 1.2, "", fontsize=1)
    ax.add_patch(Rectangle((0, 0), g.ANCHO, g.ALTO, fill=False, color="#1d1d1d", lw=1.2, zorder=9))

    # ---- Tabla de componentes
    fig.text(0.02, 0.955, "SIMON — guía de montaje", fontsize=20, weight="bold")
    fig.text(0.02, 0.925, "Vista desde el lado de los componentes (el cobre queda abajo). "
             "Placa de 88 × 50 mm.", fontsize=11, color="#444")
    filas = [
        ("U1", "ESP32 DevKit V1, 30 pines", "2 headers hembra 1x15; USB hacia el borde"),
        ("U2", "Módulo INA219", "header 1x6: VCC GND SCL SDA VIN− VIN+"),
        ("U3", "LM35 (TO-92)", "cara plana a la izquierda; patas +Vs, Out, GND"),
        ("R1–R3", "Resistencia 10 Ω, ½–1 W", "carga del panel, en serie"),
        ("R4", "Resistencia 10 kΩ, ¼ W", "divisor con la LDR"),
        ("LDR", "Fotorresistencia", "sin polaridad"),
        ("C1", "Electrolítico 100 µF ≥10 V", "+ hacia el ESP32 (pata larga)"),
        ("J1", "Bornera 2 tornillos, 5.08 mm", "− negro, + rojo del panel"),
    ]
    tx = 0.70
    fig.text(tx, 0.86, "Lista de piezas", fontsize=15, weight="bold")
    y0 = 0.82
    for k, (ref, pieza, nota) in enumerate(filas):
        yy = y0 - k * 0.085
        fig.text(tx, yy, ref, fontsize=12.5, weight="bold", color="#2f6b45")
        fig.text(tx + 0.06, yy, pieza, fontsize=11.5, weight="bold")
        fig.text(tx + 0.06, yy - 0.03, nota, fontsize=9.5, color="#555")
    fig.text(tx, 0.10, "Orden sugerido para soldar: R4 y R1–R3 → LDR → LM35 → C1 →\n"
             "bornera → headers del ESP32 y del INA219.\n"
             "Revisa con multímetro que 3V3 y GND no estén en corto\nantes de conectar el ESP32.",
             fontsize=9.5, color="#333", linespacing=1.5)

    fig.savefig(AQUI / "SIMON_guia_montaje.png", dpi=150, facecolor="white")
    print("listo: SIMON_guia_montaje.png")


if __name__ == "__main__":
    main()
