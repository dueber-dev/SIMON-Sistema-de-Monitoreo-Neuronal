"""Genera SIMON.brd: PCB de una cara (cobre abajo) para planchado/transferencia de tóner.

Todo es THT. Las piezas van arriba y el cobre en la capa Bottom (16).
Unidades en mm. Origen en la esquina inferior izquierda de la placa.

Uso:  python generar_brd.py   ->  escribe SIMON.brd junto a este archivo
"""
import re
from pathlib import Path
from xml.sax.saxutils import escape

import geometria as geo

ANCHO, ALTO = 88.0, 50.0
DRILL_HDR = 1.0      # pines de headers (patas ~0.64 mm cuadradas)
PAD_HDR = 1.8        # pads ovalados 1.8 x ~2.8 mm
W_SIG = 1.0          # pistas de señal
W_PWR = 1.5          # pistas de potencia / GND
W_3V3 = 1.2

# --------------------------------------------------------------- paquetes
# Cada paquete: lista de pads (nombre, x, y, drill, diámetro, forma, rot) y
# dibujo de serigrafía (tPlace) para la guía de montaje.

def pad(name, x, y, drill, dia, shape="round", rot="R0"):
    return f'<pad name="{name}" x="{x:.3f}" y="{y:.3f}" drill="{drill}" diameter="{dia}" shape="{shape}" rot="{rot}"/>'

def wire(x1, y1, x2, y2, w, layer):
    return f'<wire x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" width="{w}" layer="{layer}"/>'

def rect_silk(x1, y1, x2, y2, w=0.2):
    return "".join([wire(x1, y1, x2, y1, w, 21), wire(x2, y1, x2, y2, w, 21),
                    wire(x2, y2, x1, y2, w, 21), wire(x1, y2, x1, y1, w, 21)])

def text(s, x, y, size, layer, align="center", rot="R0", ratio=12):
    return (f'<text x="{x:.3f}" y="{y:.3f}" size="{size}" layer="{layer}" font="vector" '
            f'ratio="{ratio}" rot="{rot}" align="{align}">{escape(s)}</text>')

ESP_IZQ = ["EN", "VP", "VN", "D34", "D35", "D32", "D33", "D25", "D26", "D27",
           "D14", "D12", "D13", "GND_L", "VIN"]
ESP_DER = ["D23", "D22", "TX0", "RX0", "D21", "D19", "D18", "D5", "TX2", "RX2",
           "D4", "D2", "D15", "GND_R", "3V3"]

def pkg_esp32():
    # DOIT ESP32 DevKit V1 de 30 pines, vista superior, antena arriba, USB abajo.
    # Columnas a 25.4 mm. Origen al centro de la huella.
    p = []
    for i, (a, b) in enumerate(zip(ESP_IZQ, ESP_DER)):
        y = (7 - i) * 2.54
        p.append(pad(a, -12.7, y, DRILL_HDR, PAD_HDR, "long"))
        p.append(pad(b, 12.7, y, DRILL_HDR, PAD_HDR, "long"))
    s = rect_silk(-14.15, -23.3, 14.15, 26.2)
    s += text("ESP32 DevKit V1 (30)", 0, 4, 1.6, 21)
    s += text("USB", 0, -21.5, 1.6, 21)
    s += text("ANTENA", 0, 23.5, 1.4, 21)
    for i, (a, b) in enumerate(zip(ESP_IZQ, ESP_DER)):
        y = (7 - i) * 2.54
        if a in ("D32", "D33", "GND_L", "VIN"):
            s += text(a.replace("_L", ""), -10.6, y, 1.0, 21, "center-left")
        if b in ("D22", "D21", "GND_R", "3V3"):
            s += text(b.replace("_R", ""), 10.6, y, 1.0, 21, "center-right")
    return "".join(p) + s

INA_PINS = ["VCC", "GND", "SCL", "SDA", "VINN", "VINP"]

def pkg_ina219():
    # Header 1x6 del módulo INA219 (orden tipo Adafruit). El cuerpo del módulo
    # queda a la derecha del header.
    p = [pad(n, 0, 6.35 - k * 2.54, DRILL_HDR, PAD_HDR, "long") for k, n in enumerate(INA_PINS)]
    s = rect_silk(-2.4, -10.15, 20.6, 10.15)
    etiquetas = ["VCC", "GND", "SCL", "SDA", "VIN-", "VIN+"]
    for k, e in enumerate(etiquetas):
        s += text(e, 2.2, 6.35 - k * 2.54, 1.0, 21, "center-left")
    s += text("INA219", 12, 0, 1.8, 21)
    return "".join(p) + s

def pkg_bornera():
    p = [pad("N", -2.54, 0, 1.3, 2.8), pad("P", 2.54, 0, 1.3, 2.8)]
    s = rect_silk(-5.0, -3.6, 5.0, 4.0)
    s += text("-", -2.54, 2.6, 1.6, 21) + text("+", 2.54, 2.6, 1.6, 21)
    s += text("PANEL", 0, -2.6, 1.0, 21)
    return "".join(p) + s

def pkg_res_vertical(sep):
    # Resistencia axial vertical (pads arriba/abajo).
    p = [pad("1", 0, sep / 2, 1.0, 2.4), pad("2", 0, -sep / 2, 1.0, 2.4)]
    s = rect_silk(-1.3, -sep / 2 + 2.2, 1.3, sep / 2 - 2.2)
    return "".join(p) + s

def pkg_to92():
    # LM35: 1=+Vs, 2=Vout, 3=GND. Cara plana hacia la izquierda.
    p = [pad(str(k + 1), 0, 2.54 - k * 2.54, 0.9, 1.6, "long") for k in range(3)]
    s = wire(-1.8, -3.6, -1.8, 3.6, 0.2, 21)
    s += f'<wire x1="-1.8" y1="3.6" x2="-1.8" y2="-3.6" width="0.2" layer="21" curve="-180"/>'
    s += text("1", -3.0, 2.54, 1.0, 21)
    return "".join(p) + s

def pkg_ldr():
    p = [pad("1", -2.54, 0, 0.9, 2.2), pad("2", 2.54, 0, 0.9, 2.2)]
    s = f'<circle x="0" y="0" radius="2.6" width="0.2" layer="21"/>'
    return "".join(p) + s

def pkg_cap():
    # Electrolítico radial paso 2.54 (patas dobladas si es 2.0/3.5).
    p = [pad("N", -1.27, 0, 0.9, 1.8, "long", "R90"), pad("P", 1.27, 0, 0.9, 1.8, "long", "R90")]
    s = f'<circle x="0" y="0" radius="3.2" width="0.2" layer="21"/>'
    s += text("+", 2.6, 2.6, 1.2, 21)
    return "".join(p) + s

PAQUETES = {
    "ESP32_DEVKIT_30": pkg_esp32(),
    "INA219_HDR6": pkg_ina219(),
    "BORNERA_2_508": pkg_bornera(),
    "R_15_24": pkg_res_vertical(15.24),
    "R_10_16": pkg_res_vertical(10.16),
    "TO92_LM35": pkg_to92(),
    "LDR_5_08": pkg_ldr(),
    "CPOL_2_54": pkg_cap(),
}

# --------------------------------------------------------------- elementos
# nombre, paquete, valor, x, y
ELEMENTOS = [
    ("U1", "ESP32_DEVKIT_30", "ESP32", 34.7, 23.78),
    ("U2", "INA219_HDR6", "INA219", 60.0, 37.75),
    ("U3", "TO92_LM35", "LM35", 9.0, 26.32),
    ("J1", "BORNERA_2_508", "PANEL", 57.46, 5.0),
    ("R1", "R_15_24", "10", 68.0, 16.38),
    ("R2", "R_15_24", "10", 74.0, 16.38),
    ("R3", "R_15_24", "10", 80.0, 16.38),
    ("R4", "R_10_16", "10k", 16.0, 25.92),
    ("LDR1", "LDR_5_08", "LDR", 10.54, 36.0),
    ("C1", "CPOL_2_54", "100uF", 14.73, 5.0),
]

# --------------------------------------------------------------- señales
# Cada señal: (ancho, [pads], [polilíneas de pistas])
SENALES = {
    "GND": (W_PWR,
            [("U1", "GND_L"), ("U1", "GND_R"), ("U2", "GND"), ("U3", "3"),
             ("R4", "2"), ("C1", "N"), ("J1", "N"), ("R3", "2")],
            [[(9, 23.78), (9, 8.54)],
             [(9, 8.54), (13.46, 8.54)], [(13.46, 8.54), (16, 8.54)], [(16, 8.54), (22, 8.54)],
             [(13.46, 5), (13.46, 8.54)],
             [(16, 20.84), (16, 8.54)],
             [(22, 8.54), (47.4, 8.54)],
             [(47.4, 8.54), (51.5, 8.54), (54.92, 5)],
             [(54.92, 5), (54.92, 1.9), (80, 1.9)],
             [(80, 1.9), (85, 1.9), (85, 41.56), (60, 41.56)],
             [(80, 8.76), (80, 1.9)]]),
    "3V3": (W_3V3,
            [("U1", "3V3"), ("U2", "VCC"), ("U3", "1"), ("LDR1", "1")],
            [[(47.4, 6), (47.4, 1.9), (2.5, 1.9), (2.5, 28.86)],
             [(2.5, 28.86), (2.5, 36)],
             [(2.5, 36), (2.5, 47), (57.5, 47), (60, 44.1)],
             [(2.5, 28.86), (9, 28.86)],
             [(2.5, 36), (8, 36)]]),
    "VIN": (W_PWR, [("U1", "VIN"), ("C1", "P")],
            [[(22, 6), (18, 6), (16, 5)]]),
    "SCL": (W_SIG, [("U1", "D22"), ("U2", "SCL")],
            [[(47.4, 39.02), (60, 39.02)]]),
    "SDA": (W_SIG, [("U1", "D21"), ("U2", "SDA")],
            [[(47.4, 31.40), (50.8, 31.40), (50.8, 36.48), (60, 36.48)]]),
    "TEMP": (W_SIG, [("U1", "D33"), ("U3", "2")],
             [[(22, 26.32), (9, 26.32)]]),
    "LUZ": (W_SIG, [("U1", "D32"), ("R4", "1"), ("LDR1", "2")],
            [[(22, 28.86), (18, 28.86), (16, 31)],
             [(13.08, 36), (16, 33), (16, 31)]]),
    "VSOLAR": (W_PWR, [("U2", "VINP"), ("J1", "P")],
               [[(60, 31.40), (60, 5)]]),
    "VCARGA": (W_PWR, [("U2", "VINN"), ("R1", "1")],
               [[(60, 33.94), (64, 33.94), (64, 27), (68, 24)]]),
    "N_R1R2": (W_PWR, [("R1", "2"), ("R2", "2")],
               [[(68, 8.76), (74, 8.76)]]),
    "N_R2R3": (W_PWR, [("R2", "1"), ("R3", "1")],
               [[(74, 24), (80, 24)]]),
}

# --------------------------------------------------------------- capas
CAPAS = [
    (1, "Top", 4), (16, "Bottom", 1), (17, "Pads", 2), (18, "Vias", 2),
    (19, "Unrouted", 6), (20, "Dimension", 15), (21, "tPlace", 7), (22, "bPlace", 7),
    (23, "tOrigins", 15), (24, "bOrigins", 15), (25, "tNames", 7), (26, "bNames", 7),
    (27, "tValues", 7), (28, "bValues", 7), (29, "tStop", 7), (30, "bStop", 7),
    (31, "tCream", 7), (32, "bCream", 7), (35, "tGlue", 7), (36, "bGlue", 7),
    (39, "tKeepout", 4), (40, "bKeepout", 1), (41, "tRestrict", 4), (42, "bRestrict", 1),
    (43, "vRestrict", 2), (44, "Drills", 7), (45, "Holes", 7), (46, "Milling", 3),
    (47, "Measures", 7), (48, "Document", 7), (49, "Reference", 7), (51, "tDocu", 7),
    (52, "bDocu", 7),
]

REGLAS = {
    # Una sola cara: todo el ruteo en Bottom.
    "layerSetup": "(1*16)",
    "mdWireWire": "0.5mm", "mdWirePad": "0.5mm", "mdWireVia": "0.5mm",
    "mdPadPad": "0.5mm", "mdPadVia": "0.5mm", "mdViaVia": "0.5mm",
    "mdCopperDimension": "1mm",
    "msWidth": "0.8mm", "msDrill": "0.8mm",
    "rvPadTop": "0.25", "rvPadInner": "0.25", "rvPadBottom": "0.25",
    "rlMinPadTop": "0.4mm", "rlMinPadBottom": "0.4mm", "rlMinPadInner": "0.4mm",
    "psElongationLong": "55",
}


# --------------------------------------------------------------- texto en cobre
# Como en las placas de la U: etiquetas de las piezas en cobre, cada una dentro
# de un recuadro sin relleno. Se escriben espejadas (MR) para leerse desde el
# lado del cobre. (texto, x_ancla, y_ancla, tamaño, rotación)
TITULO = ("SIMON", 34.7, 23.0, 5.0, "MR90")
ETIQUETAS = [
    # Polaridades primero, para que queden pegadas a su pad
    ("+", 63.6, 5.0, 1.8, "MR0", 2.5),   # panel +, a la derecha de su pad
    ("-", 51.4, 4.2, 1.8, "MR0", 2.5),   # panel -, a la izquierda de su pad
    ("U1", 34.7, 40.0, 2.0, "MR0"),
    ("U2", 72.0, 36.0, 2.0, "MR0"),
    ("U3", 9.0, 20.0, 2.0, "MR0"),
    ("J1", 57.46, 11.0, 2.0, "MR0"),
    ("R1", 68.0, 16.38, 2.0, "MR0"),
    ("R2", 74.0, 16.38, 2.0, "MR0"),
    ("R3", 80.0, 16.38, 2.0, "MR0"),
    ("R4", 16.0, 24.0, 2.0, "MR0"),
    ("LDR", 10.5, 40.0, 2.0, "MR0"),
    ("C1", 14.73, 10.5, 2.0, "MR0"),
]


def pads_absolutos():
    """[(elemento, pad, x, y, diámetro, forma, vertical)] en coordenadas de placa."""
    out = []
    for nom, pkg, _, ex, ey in ELEMENTOS:
        for m in re.finditer(r'<pad name="([^"]+)" x="([^"]+)" y="([^"]+)" drill="[^"]+" '
                             r'diameter="([^"]+)" shape="([^"]+)" rot="([^"]+)"', PAQUETES[pkg]):
            n, x, y, d, sh, rot = m.groups()
            out.append((nom, n, float(x) + ex, float(y) + ey, float(d), sh, rot == "R90"))
    return out


def cobre_por_senal():
    """{señal: [formas shapely]} con pads y pistas; pads sin señal van en 'NC'."""
    sig_de = {(el, pd): s for s, (_, lst, _) in SENALES.items() for el, pd in lst}
    out = {}
    for el, n, x, y, d, sh, vert in pads_absolutos():
        out.setdefault(sig_de.get((el, n), "NC"), []).append(geo.forma_pad(x, y, d, sh, vert))
    for s, (w, _, pistas) in SENALES.items():
        for poli in pistas:
            for (x1, y1), (x2, y2) in zip(poli, poli[1:]):
                out[s].append(geo.forma_pista(x1, y1, x2, y2, w))
    return out


def textos_en_cobre():
    """Título fijo + etiquetas ubicadas automáticamente lejos del cobre."""
    cobre = [g for lst in cobre_por_senal().values() for g in lst]
    s, x, y, size, rot = TITULO
    titulo = (s, x, y, size, rot, geo.caja_texto(s, x, y, size, rot))
    return [titulo] + geo.colocar(ETIQUETAS, cobre, ANCHO, ALTO, ocupadas=[titulo[5]])


def construir():
    o = ['<?xml version="1.0" encoding="utf-8"?>',
         '<!DOCTYPE eagle SYSTEM "eagle.dtd">',
         '<eagle version="9.6.2"><drawing>',
         '<settings><setting alwaysvectorfont="yes"/><setting verticaltext="up"/></settings>',
         '<grid distance="1.27" unitdist="mm" unit="mm" style="lines" multiple="1" display="yes" altdistance="0.635" altunitdist="mm" altunit="mm"/>',
         '<layers>']
    for n, nombre, color in CAPAS:
        o.append(f'<layer number="{n}" name="{nombre}" color="{color}" fill="1" visible="yes" active="yes"/>')
    o.append('</layers><board><plain>')
    o.append(rect_borde := "".join([wire(0, 0, ANCHO, 0, 0, 20), wire(ANCHO, 0, ANCHO, ALTO, 0, 20),
                                    wire(ANCHO, ALTO, 0, ALTO, 0, 20), wire(0, ALTO, 0, 0, 0, 20)]))
    # Texto en cobre con su recuadro en bRestrict (42) para que el relleno no entre
    for s, x, y, size, rot, caja in textos_en_cobre():
        o.append(text(s, x, y, size, 16, "center", rot, 18))
        x1, y1, x2, y2 = caja.bounds
        o.append(f'<rectangle x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" layer="42"/>')
    o.append(text("SIMON", 70, 48.6, 1.4, 21))
    o.append('</plain><libraries><library name="simon"><packages>')
    for nombre, cuerpo in PAQUETES.items():
        o.append(f'<package name="{nombre}">{cuerpo}'
                 f'<text x="0" y="0" size="1.27" layer="25">&gt;NAME</text></package>')
    o.append('</packages></library></libraries><attributes/><variantdefs/><classes>'
             '<class number="0" name="default" width="0" drill="0"/></classes>')
    o.append('<designrules name="simon_planchado">')
    for k, v in REGLAS.items():
        o.append(f'<param name="{k}" value="{v}"/>')
    o.append('</designrules><autorouter/><elements>')
    for nom, pkg, val, x, y in ELEMENTOS:
        o.append(f'<element name="{nom}" library="simon" package="{pkg}" value="{val}" x="{x}" y="{y}"/>')
    o.append('</elements><signals>')
    for nombre, (w, pads, pistas) in SENALES.items():
        o.append(f'<signal name="{nombre}">')
        for el, pd in pads:
            o.append(f'<contactref element="{el}" pad="{pd}"/>')
        for poli in pistas:
            for (x1, y1), (x2, y2) in zip(poli, poli[1:]):
                o.append(wire(x1, y1, x2, y2, w, 16))
        if nombre == "GND":
            # Relleno de cobre en toda la cara, como en las placas de la U
            m = geo.MARGEN_BORDE
            o.append(f'<polygon width="0.4" layer="16" isolate="{geo.AISLAMIENTO}" '
                     f'thermals="no" orphans="no" rank="1">'
                     f'<vertex x="{m}" y="{m}"/><vertex x="{ANCHO - m}" y="{m}"/>'
                     f'<vertex x="{ANCHO - m}" y="{ALTO - m}"/><vertex x="{m}" y="{ALTO - m}"/>'
                     '</polygon>')
        o.append('</signal>')
    o.append('</signals></board></drawing></eagle>')
    return "\n".join(o)


if __name__ == "__main__":
    salida = Path(__file__).with_name("SIMON.brd")
    salida.write_text(construir(), encoding="utf-8")
    print("escrito", salida)
