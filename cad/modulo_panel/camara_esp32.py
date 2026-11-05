"""Soporte de la ESP32-CAM que se acopla al marco del panel de SIMON.

Una sola pieza que se imprime acostada y sin soportes:
- Clip:  una "C" que abraza el borde libre del marco (el labio de 3 x 6.5 donde entra el
         panel) y se desliza por el extremo -X, el mismo lado por donde entra el panel.
- Brazo: sale por fuera del panel (lado -X, el de la tuerca) y sube hasta la cuna.
- Cuna:  canal con dos ranuras donde entra la placa ESP32-CAM-MB de canto, como una tarjeta;
         la cámara queda mirando al centro del panel, unos 50° fuera de su normal.

Todo va en coordenadas del marco: X a lo largo del eje de la bisagra, u desde el eje hacia
el borde libre, n normal al panel (hacia la cara que recibe el sol). Como el soporte va
pegado al marco, gira con él: a cualquier inclinación la cámara ve lo mismo, y con el panel
apuntado al sol su sombra cae fuera del panel.

Corre:  python camara_esp32.py
Genera: camara_esp32.SLDPRT, esp32cam_ref.SLDPRT (solo referencia), stl/camara_esp32.STL
        (ya orientado) y capturas/camara_*.png.
"""
import math
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import swlib  # noqa: E402

CAPTURAS = AQUI / "capturas"
STL = AQUI / "stl"

# ------------------------------------------------------------------ marco (medido de tu SLDPRT)
Y_EJE, YS_EJE = 80.0, 56.0
LABIO_U0, LABIO_U1 = 69.0, 72.0         # borde libre: labio de 3 mm (el panel entra 1.5 en él)
LABIO_N0, LABIO_N1 = -3.5, 3.0          # 6.5 de alto
PANEL_X = 54.0                          # medio largo del panel (108)
PANEL_U0, PANEL_U1 = 8.5, 70.0

# ------------------------------------------------------------------ medidas (mm)
HOLG = 0.1                              # por lado, clip sobre el labio (ajuste fijo)
MORD_T = 1.6                            # grosor de las mordazas
MORD_PUNTA = 69.2                       # hasta dónde llegan las mordazas (no pasan del labio)
CLIP_X0, CLIP_X1 = -54.0, -24.0         # 30 mm de clip sobre el labio
PLACA_T = 5.0                           # grosor del brazo (a 90° queda a ~3 mm de la mesa)
U_PLACA = LABIO_U1 + HOLG               # 72.1: cara interior de la placa
BRAZO_W = 10.0
BRAZO_P1 = (-50.0, 0.0)                 # (X, n) donde el brazo sale del clip

# ESP32-CAM sobre la placa ESP32-CAM-MB (medir y ajustar)
MB_W = 27.0                             # ancho de la MB
MB_L = 40.5                             # largo de la MB
MB_PCB = 1.6
HOLG_MB = 0.15                          # por lado en las ranuras
PINES = 3.0                             # aire bajo la MB para los pines soldados
PISO_T = 1.6
PARED = 1.6                             # pared por fuera de la ranura
LABIO_ABAJO, LABIO_ARRIBA = 0.8, 0.6    # cuánto entran las ranuras en la placa (arriba hay headers)
SOBRE_PARED = 1.6                       # pared por encima de la ranura
ALTO_LENTE = 24.0                       # del piso de la cuna al frente del lente (MB + CAM + lente)

# Dónde va la cámara (frente del lente) y adónde apunta
LENTE = (-100.0, 85.0)                  # (X, n)
OBJETIVO = (0.0, 1.5)                   # centro del panel, en su cara

# ------------------------------------------------------------------ geometría derivada
dx, dn = OBJETIVO[0] - LENTE[0], OBJETIVO[1] - LENTE[1]
_l = math.hypot(dx, dn)
D = (dx / _l, dn / _l)                  # dirección de vista (en X, n)
W = (-D[1], D[0])                       # ancho de la placa, perpendicular a la vista
B = (LENTE[0] - D[0] * ALTO_LENTE, LENTE[1] - D[1] * ALTO_LENTE)  # centro de la cara de atrás del piso

H_ASIENTO = PISO_T + PINES              # donde apoya la MB
H_TECHO = H_ASIENTO + MB_PCB + 0.2
H_PARED = H_TECHO + SOBRE_PARED
W_RANURA = MB_W / 2 + HOLG_MB           # fondo de la ranura
W_EXT = W_RANURA + PARED
CUNA_L = MB_L + 1.0                     # largo del canal (la MB entra hasta el tope)
U_CUNA_FIN = U_PLACA - CUNA_L


def wh(w, h):
    """(w, h) de la cuna -> (X, n)."""
    return (B[0] + w * W[0] + h * D[0], B[1] + w * W[1] + h * D[1])


def XY(X, n):
    """(X, n) del marco a 0° -> (x, y) de un croquis en un plano paralelo al alzado."""
    return (X, Y_EJE + n)


def Z(u):
    return -(YS_EJE + u)


def perfil_cuna():
    w0, w1, wl_ab, wl_ar = W_EXT, W_RANURA, W_RANURA - LABIO_ABAJO, W_RANURA - LABIO_ARRIBA
    lado = [(w0, 0), (w0, H_PARED), (wl_ar, H_PARED), (wl_ar, H_TECHO), (w1, H_TECHO),
            (w1, H_ASIENTO), (wl_ab, H_ASIENTO), (wl_ab, PISO_T)]
    izq = [(-w, h) for w, h in reversed(lado)]
    return [XY(*wh(w, h)) for w, h in lado + izq]


def construir(sw):
    p = swlib.Pieza(sw, "camara_esp32")
    plano_ext = p.plano_desfasado(p.alzado, Z(U_PLACA + PLACA_T))
    plano_ext.Name = "Plano_cara_cama"
    plano_int = p.plano_desfasado(p.alzado, Z(U_PLACA))
    plano_int.Name = "Plano_cara_labio"

    # Placa del clip
    p.croquis(plano_ext)
    x0, y0 = XY(CLIP_X0, LABIO_N0 - HOLG - MORD_T)
    x1, y1 = XY(CLIP_X1, LABIO_N1 + HOLG + MORD_T)
    p.rect((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0)
    p.extruir(p.cerrar_croquis("Croquis_placa_clip"), PLACA_T, "Placa_clip")

    # Mordazas: abrazan el labio por arriba y por abajo
    p.croquis(plano_int)
    for na, nb in ((LABIO_N1 + HOLG, LABIO_N1 + HOLG + MORD_T),
                   (LABIO_N0 - HOLG - MORD_T, LABIO_N0 - HOLG)):
        xa, ya = XY(CLIP_X0, na)
        xb, yb = XY(CLIP_X1, nb)
        p.rect((xa + xb) / 2, (ya + yb) / 2, xb - xa, yb - ya)
    p.extruir(p.cerrar_croquis("Croquis_mordazas"), U_PLACA - MORD_PUNTA, "Mordazas")

    # Brazo: del clip a la cara de atrás de la cuna
    fin = (B[0] + D[0] * PISO_T / 2, B[1] + D[1] * PISO_T / 2)
    ax, an = fin[0] - BRAZO_P1[0], fin[1] - BRAZO_P1[1]
    la = math.hypot(ax, an)
    px, pn = -an / la * BRAZO_W / 2, ax / la * BRAZO_W / 2
    pts = [(BRAZO_P1[0] + px, BRAZO_P1[1] + pn), (fin[0] + px, fin[1] + pn),
           (fin[0] - px, fin[1] - pn), (BRAZO_P1[0] - px, BRAZO_P1[1] - pn)]
    p.croquis(plano_ext)
    p.polilinea([XY(*q) for q in pts])
    p.extruir(p.cerrar_croquis("Croquis_brazo", definir=False), PLACA_T, "Brazo")

    # Tope de la cuna (la MB llega hasta aquí) y canal con ranuras
    p.croquis(plano_ext)
    p.polilinea([XY(*wh(w, h)) for w, h in ((-W_EXT, 0), (W_EXT, 0), (W_EXT, H_PARED), (-W_EXT, H_PARED))])
    p.extruir(p.cerrar_croquis("Croquis_tope", definir=False), PLACA_T, "Tope_cuna")
    p.croquis(plano_ext)
    p.polilinea(perfil_cuna())
    p.extruir(p.cerrar_croquis("Croquis_cuna", definir=False), PLACA_T + CUNA_L, "Cuna")
    p.color(0.15, 0.45, 0.85)
    return p


def construir_ref(sw):
    """La ESP32-CAM sobre su MB, simplificada: placa + bloque de la CAM + lente."""
    p = swlib.Pieza(sw, "esp32cam_ref")
    plano = p.plano_desfasado(p.alzado, Z(U_PLACA))
    p.croquis(plano)
    p.polilinea([XY(*wh(w, h)) for w, h in ((-MB_W / 2, H_ASIENTO), (MB_W / 2, H_ASIENTO),
                                            (MB_W / 2, H_ASIENTO + MB_PCB), (-MB_W / 2, H_ASIENTO + MB_PCB))])
    p.extruir(p.cerrar_croquis("Croquis_mb", definir=False), MB_L, "MB")
    # headers + ESP32-CAM: más angostos que la MB (no tocan los labios de arriba)
    a = W_RANURA - LABIO_ARRIBA - 0.3
    p.croquis(plano)
    p.polilinea([XY(*wh(w, h)) for w, h in ((-a, H_ASIENTO + MB_PCB), (a, H_ASIENTO + MB_PCB),
                                            (a, ALTO_LENTE - 7), (-a, ALTO_LENTE - 7))])
    p.extruir(p.cerrar_croquis("Croquis_cam", definir=False), MB_L, "CAM")
    centro_u = U_PLACA - MB_L / 2
    p.croquis(p.alzado, Z(centro_u - 4))
    p.polilinea([XY(*wh(w, h)) for w, h in ((-4, ALTO_LENTE - 7), (4, ALTO_LENTE - 7),
                                            (4, ALTO_LENTE), (-4, ALTO_LENTE))])
    p.extruir(p.cerrar_croquis("Croquis_lente", definir=False), 8, "Lente", sentido=-1)
    p.color(0.1, 0.1, 0.1)
    return p


def reporte():
    """Ángulos de la vista y cuánto error al apuntar al sol aguanta sin hacer sombra."""
    esquinas = [wh(w, h) for w in (-W_EXT, W_EXT) for h in (0, H_PARED)]
    esquinas += [wh(w, h) for w in (-MB_W / 2, MB_W / 2) for h in (H_ASIENTO, ALTO_LENTE)]
    # la sombra de un punto a altura n se corre n*tan(e) hacia el panel
    tol = min(math.degrees(math.atan2(-PANEL_X - X, n)) for X, n in esquinas if n > 0)
    fuera_normal = math.degrees(math.atan2(-D[0], -D[1]))
    dist = math.hypot(*(LENTE[i] - OBJETIVO[i] for i in range(2)))
    cerca = math.degrees(math.atan2(OBJETIVO[1] - LENTE[1], -PANEL_X - LENTE[0]))
    lejos = math.degrees(math.atan2(OBJETIVO[1] - LENTE[1], PANEL_X - LENTE[0]))
    return {"fuera de la normal (°)": round(fuera_normal, 1), "distancia al centro (mm)": round(dist, 1),
            "panel a lo largo (°)": round(abs(lejos - cerca), 1),
            "error de apuntado sin sombra (°)": round(tol, 1),
            "cuna X más cercana al panel": round(max(X for X, n in esquinas), 1)}


def main():
    print(reporte())
    sw = swlib.sw_app()
    swlib.cerrar_de_carpeta(sw, AQUI / "camara_esp32.SLDPRT")
    swlib.cerrar_de_carpeta(sw, AQUI / "esp32cam_ref.SLDPRT")
    p = construir(sw)
    print("volumen", p.volumen_cm3(), "cm3; croquis sin definir:", p.sin_definir)
    print(p.guardar(AQUI))
    CAPTURAS.mkdir(exist_ok=True)
    p.captura(CAPTURAS / "camara_iso.bmp")
    p.captura(CAPTURAS / "camara_frente.bmp", vista="*Front")
    STL.mkdir(exist_ok=True)
    stl = STL / "camara_esp32.STL"
    p.exportar(stl)
    print("STL", swlib.girar_stl(stl, "+Z"))   # cara de la placa en la cama, cuna hacia arriba
    p.cerrar()
    r = construir_ref(sw)
    print(r.guardar(AQUI))
    r.cerrar()


if __name__ == "__main__":
    main()
