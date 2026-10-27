"""Caja de la PCB de SIMON, con labio (lip) en la caja y escalón (groove) en la tapa.

Pensada para imprimirse en una Flashforge Adventurer 5M con boquilla de 0.4 mm:
- La caja se imprime con el piso en la cama; la tapa, con su cara superior plana en la cama.
- Ninguna de las dos necesita soportes.

Corre:  python caja_simon.py           -> con labio/escalón ya modelados (lista para imprimir)
        python caja_simon.py --plano   -> variante sin labio, tapa apoyada sobre la caja, para
                                          aplicar el Lip/Groove nativo de SolidWorks en el ensamble
Genera: caja_simon_base.SLDPRT, caja_simon_tapa.SLDPRT, caja_simon.SLDASM, stl/ y capturas/
        (la variante plana agrega el sufijo _plano y no exporta STL).

Coordenadas (las de SolidWorks): Y arriba, Z hacia el frente. La pared trasera (-Z) lleva
las salidas del USB del ESP32 y del cable del panel. Croquis en planta: (x, y) = (X, -Z).
"""
import math
import struct
import sys
from pathlib import Path

import pythoncom
from win32com.client import VARIANT

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import swlib  # noqa: E402
from swlib import M, T, call  # noqa: E402

CAPTURAS = AQUI / "capturas"
STL = AQUI / "stl"
REF_PCB = AQUI.parent / "solidworks" / "ref_pcb_simon.SLDPRT"

# ------------------------------------------------------------------ medidas (mm)
HUECO_L, HUECO_W = 90.5, 52.5   # hueco de la PCB: medida real de la placa + ~0.3 de tolerancia
PARED = 2.5                     # paredes laterales
PISO = 2.0                      # piso y tapa en 2.0 para ahorrar filamento (10 capas de 0.2)
TAPA_T = 2.0
R_EXT = 4.0                     # radio de las esquinas por fuera

EXT_L, EXT_W = HUECO_L + 2 * PARED, HUECO_W + 2 * PARED      # 95.5 x 57.5

APOYO = 4.0                     # la PCB queda 4 mm sobre el piso (soldaduras por abajo)
PCB_T = 1.6
PCB_ABAJO = PISO + APOYO        # 6.0
PCB_ARRIBA = PCB_ABAJO + PCB_T  # 7.6
LIBRE = 23.4                    # espacio sobre la PCB (INA219 con su header ~20 mm)
TAPA_ABAJO = PCB_ARRIBA + LIBRE # 31.0: cara inferior de la tapa

# Labio / escalón. Anchos pensados en líneas de 0.42 mm: labio ~3 líneas, falda ~2.5.
LABIO_W, LABIO_H = 1.25, 2.4
HOLG_LG = 0.2                   # holgura por lado entre labio y falda (ajuste firme)
FALDA_W = PARED - LABIO_W - HOLG_LG   # 1.05
FALDA_H = 2.5
BORDE = TAPA_ABAJO - FALDA_H    # 28.5: altura del borde de la caja (donde asienta la tapa)

CHAFLAN = 0.6                   # bordes que tocan la cama (evita la "pata de elefante")

PLANO = False                   # True: sin labio ni escalón (ver --plano)
SUFIJO = ""


def alto_borde():
    """Altura de la caja donde asienta la tapa."""
    return TAPA_ABAJO if PLANO else BORDE


def pcb(x, y):
    """Coordenadas del diseño de la PCB (88 x 50, origen en su esquina) -> caja (X, Z).
    La placa va girada 180° para que USB y bornera den a la pared trasera."""
    return 44.0 - x, y - 25.0


# ------------------------------------------------------------------ caja
def caja(sw):
    p = swlib.Pieza(sw, "caja_simon_base" + SUFIJO)
    h = alto_borde()
    p.croquis(p.planta); p.rect_redondeado(0, 0, EXT_L, EXT_W, R_EXT)
    s = p.cerrar_croquis("Croquis_contorno")
    p.extruir(s, h, "Cuerpo")

    p.croquis(p.planta, h); p.rect(0, 0, HUECO_L, HUECO_W)
    s = p.cerrar_croquis("Croquis_hueco_PCB")
    p.cortar(s, h - PISO, "Hueco_PCB", sentido=-1)

    if not PLANO:
        # Labio: la franja interior de la pared sube por encima del borde
        r_labio = R_EXT - FALDA_W - HOLG_LG
        p.croquis(p.planta, BORDE)
        p.rect_redondeado(0, 0, HUECO_L + 2 * LABIO_W, HUECO_W + 2 * LABIO_W, r_labio)
        p.rect(0, 0, HUECO_L, HUECO_W, cotar=False)
        s = p.cerrar_croquis("Croquis_labio")
        p.extruir(s, LABIO_H, "Labio_lip")

    # Apoyos de la PCB en las 4 esquinas (la PCB no tiene agujeros; las paredes la ubican)
    p.croquis(p.planta, PISO)
    for sx in (-1, 1):
        for sz in (-1, 1):
            p.rect(sx * (HUECO_L / 2 - 2.5), sz * (HUECO_W / 2 - 2.5), 5, 5, cotar=(sx > 0 and sz > 0))
    s = p.cerrar_croquis("Croquis_apoyos")
    p.extruir(s, APOYO, "Apoyos_PCB")

    # Alivios en las esquinas interiores: la impresora redondea las esquinas y la PCB,
    # que es cuadrada, se trabaría. Con un alivio de Ø2 la esquina de la placa entra libre.
    p.croquis(p.planta, PISO)
    for sx in (-1, 1):
        for sz in (-1, 1):
            p.circulo(sx * HUECO_L / 2, sz * HUECO_W / 2, 2.0, cotar=(sx > 0 and sz > 0))
    s = p.cerrar_croquis("Croquis_alivios")
    p.cortar(s, PCB_ARRIBA + 2.5 - PISO, "Alivios_esquinas", sentido=1)

    # Salidas en la pared trasera: USB del ESP32 y cable del panel (bornera J1)
    usb_x, _ = pcb(34.7, 0)
    j1_x, _ = pcb(57.46, 0)
    usb_y = PCB_ARRIBA + 8.5 + 1.6 + 1.4      # header hembra + placa del ESP32 + medio conector
    j1_y = PCB_ARRIBA + 4.5
    p.croquis(p.alzado)
    p.ranura(usb_x, usb_y, 13, 8)
    p.ranura(j1_x, j1_y, 12, 7)
    s = p.cerrar_croquis("Croquis_salidas")
    p.cortar(s, None, "Salidas_USB_y_panel", sentido=-1)

    # Ventilación en las paredes cortas (ranuras verticales: se imprimen sin soporte)
    p.croquis(p.lateral)
    for k in range(-15, 16, 5):
        p.ranura(k, PCB_ARRIBA + 10, 14, 2.2, vertical=True)
    s = p.cerrar_croquis("Croquis_ventilas")
    p.cortar(s, None, "Ventilas_laterales", ambos=True)

    # Rejilla en el piso: el aire entra por abajo y sale por las ventilas de la tapa (efecto
    # chimenea). Mismo paso que las ranuras de la tapa. Al imprimir son huecos en las
    # primeras capas, así que no llevan soporte; queda lejos de los apoyos de las esquinas.
    p.croquis(p.planta)
    for k in range(-7, 8):
        p.ranura(4 * k, 0, 34, 2, vertical=True)
    s = p.cerrar_croquis("Croquis_rejilla_piso")
    p.cortar(s, PISO, "Rejilla_piso", sentido=1)

    p.chaflan_contorno((0, -1, 0), 0.0, CHAFLAN, "Chaflan_base")
    return p


# ------------------------------------------------------------------ tapa
def tapa(sw):
    """Origen en la cara inferior de la placa de la tapa; la cara superior (Y = TAPA_T)
    es la que va contra la cama al imprimir."""
    p = swlib.Pieza(sw, "caja_simon_tapa" + SUFIJO)
    p.croquis(p.planta); p.rect_redondeado(0, 0, EXT_L, EXT_W, R_EXT)
    s = p.cerrar_croquis("Croquis_tapa")
    p.extruir(s, TAPA_T, "Tapa")

    if not PLANO:
        # Escalón (groove): falda exterior que baja y abraza el labio de la caja
        p.croquis(p.planta)
        p.rect_redondeado(0, 0, EXT_L, EXT_W, R_EXT, cotar=False)
        p.rect_redondeado(0, 0, EXT_L - 2 * FALDA_W, EXT_W - 2 * FALDA_W, R_EXT - FALDA_W)
        s = p.cerrar_croquis("Croquis_falda")
        p.extruir(s, FALDA_H, "Escalon_groove", sentido=-1)

    # Postes que aprietan la PCB contra sus apoyos (0.1 mm de aire)
    p.croquis(p.planta)
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = pcb(44 + sx * 41, 25 + sz * 22)
            p.circulo(x, -z, 5, cotar=(sx > 0 and sz > 0))
    s = p.cerrar_croquis("Croquis_postes")
    p.extruir(s, TAPA_ABAJO - PCB_ARRIBA - 0.1, "Postes_PCB", sentido=-1)

    # Ventana de la LDR, ventilas sobre las resistencias/INA219 y junto al LM35
    ldr_x, ldr_z = pcb(10.54, 36)
    lm_x, lm_z = pcb(9.0, 26.32)
    p.croquis(p.planta)
    p.circulo(ldr_x, -ldr_z, 6)
    for k in range(6):
        p.ranura(-16 - 4 * k, 0, 34, 2, vertical=True)
    for k in (-4, 0, 4):
        p.ranura(lm_x + k, -(lm_z - 5.5), 8, 2, vertical=True)
    s = p.cerrar_croquis("Croquis_ventana_y_ventilas")
    p.cortar(s, None, "Ventana_LDR_y_ventilas", ambos=True)

    # SIMON en bajo relieve sobre la cara de arriba (queda contra la cama: sale nítido)
    p.croquis(p.planta, TAPA_T); p.texto(-10, -6, "SIMON", 7)
    s = p.cerrar_croquis("Croquis_texto")
    p.cortar(s, 0.6, "Texto_SIMON", sentido=-1)

    p.chaflan_contorno((0, 1, 0), TAPA_T, CHAFLAN, "Chaflan_cara_superior")
    return p


# ------------------------------------------------------------------ STL para imprimir
def orientar_stl(ruta, tapa_boca_abajo):
    """SolidWorks exporta con Y arriba; los slicers esperan Z arriba. Gira la malla y
    la apoya en Z = 0. La tapa se voltea para que su cara superior quede en la cama."""
    datos = Path(ruta).read_bytes()
    n = struct.unpack_from("<I", datos, 80)[0]
    if tapa_boca_abajo:
        f = lambda x, y, z: (x, z, -y)   # +Y local -> -Z (cara superior abajo)
    else:
        f = lambda x, y, z: (x, -z, y)   # +Y local -> +Z
    tris = []
    for i in range(n):
        v = struct.unpack_from("<12f", datos, 84 + 50 * i)
        tris.append([f(*v[0:3]), f(*v[3:6]), f(*v[6:9]), f(*v[9:12])])
    mins = [min(t[k][c] for t in tris for k in (1, 2, 3)) for c in range(3)]
    salida = bytearray(datos[:84])
    for t in tris:
        nrm = t[0]
        pts = [tuple(p[c] - mins[c] for c in range(3)) for p in t[1:]]
        salida += struct.pack("<12fH", *nrm, *pts[0], *pts[1], *pts[2], 0)
    Path(ruta).write_bytes(bytes(salida))
    maxs = [max(t[k][c] for t in tris for k in (1, 2, 3)) - mins[c] for c in range(3)]
    return maxs


# ------------------------------------------------------------------ ensamble
def matriz(t, rot=None):
    R = rot or [1, 0, 0, 0, 1, 0, 0, 0, 1]
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                   R + [t[0] * M, t[1] * M, t[2] * M, 1.0, 0.0, 0.0, 0.0])


def ensamble(sw, rutas):
    mu = T(sw.GetMathUtility(), "IMathUtility")
    doc = swlib.SL.IModelDoc2(sw.NewDocument(sw.GetUserPreferenceStringValue(9), 0, 0, 0)._oleobj_)
    asm = T(doc, "IAssemblyDoc")
    comps = {}
    for nombre, ruta, t in (("base", rutas["base"], (0, 0, 0)),
                            ("pcb", str(REF_PCB), (0, PCB_ABAJO, 0)),
                            ("tapa", rutas["tapa"], (0, TAPA_ABAJO, 0))):
        sw.OpenDoc(ruta, 1)
        c = T(asm.AddComponent5(ruta, 0, "", False, "", 0, 0, 0), "IComponent2")
        c.Transform2 = mu.CreateTransform(matriz(t))
        comps[nombre] = c
    doc.ClearSelection2(True)
    for c in comps.values():
        c.Select4(True, None, False)
    asm.FixComponent()
    doc.ClearSelection2(True)
    doc.ForceRebuild3(False)

    def foto(vista, archivo):
        doc.ShowNamedView2(vista, -1)
        call(doc, "ViewZoomtofit2")
        doc.SaveBMP(str(CAPTURAS / f"{archivo}{SUFIJO}.bmp"), 0, 0)
        swlib.a_png(CAPTURAS / f"{archivo}{SUFIJO}.bmp")

    foto("*Isometric", "ensamble_cerrado")
    foto("*Back", "ensamble_trasera_usb")
    # Vista "abierta": la tapa levantada 35 mm para ver labio, escalón y PCB
    comps["tapa"].Transform2 = mu.CreateTransform(matriz((0, TAPA_ABAJO + 35, 0)))
    doc.GraphicsRedraw2()
    foto("*Isometric", "ensamble_abierto")
    comps["tapa"].Transform2 = mu.CreateTransform(matriz((0, TAPA_ABAJO, 0)))
    doc.ForceRebuild3(False)
    ruta = str(AQUI / f"caja_simon{SUFIJO}.SLDASM")
    err = doc.SaveAs3(ruta, 0, 1)
    if not PLANO:
        doc.SaveAs3(str(AQUI / "caja_simon.STEP"), 0, 2)
    return ruta, err


def main():
    global PLANO, SUFIJO
    if "--plano" in sys.argv:
        PLANO, SUFIJO = True, "_plano"
    CAPTURAS.mkdir(exist_ok=True)
    STL.mkdir(exist_ok=True)
    sw = swlib.sw_app()
    swlib.cerrar_de_carpeta(sw, AQUI)
    rutas = {}
    total = 0.0
    for clave, fabricar, color, boca_abajo in (("base", caja, (0.93, 0.93, 0.92), False),
                                               ("tapa", tapa, (0.16, 0.17, 0.19), True)):
        p = fabricar(sw)
        p.color(*color)
        ruta, err = p.guardar(AQUI)
        vol = p.volumen_cm3()
        total += vol
        if not PLANO:
            p.captura(CAPTURAS / f"{p.nombre}.bmp")
            p.captura(CAPTURAS / f"{p.nombre}_abajo.bmp", vista="*Bottom")
            stl = STL / f"{p.nombre}.stl"
            p.exportar(stl)
            dims = orientar_stl(stl, boca_abajo)
            print(f"{p.nombre:18s} vol={vol:5.1f} cm3 (~{vol * 1.24:4.0f} g PLA macizo)  "
                  f"STL {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm  err={err}")
        else:
            print(f"{p.nombre:18s} vol={vol:5.1f} cm3  err={err}")
        rutas[clave] = ruta
        p.cerrar()
    ruta, err = ensamble(sw, rutas)
    print(f"total {total:.1f} cm3 macizo; ensamble {Path(ruta).name} err={err}")


if __name__ == "__main__":
    main()
