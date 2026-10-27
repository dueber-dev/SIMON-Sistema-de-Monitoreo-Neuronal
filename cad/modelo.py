"""SIMON — estación de inspección del panel solar, modelada en SolidWorks 2025.

Corre:  python modelo.py            -> crea todas las piezas y el ensamble en cad/solidworks/
        python modelo.py caja tapa  -> solo esas piezas

Convenciones (las de SolidWorks): Y arriba. En el ensamble, X = ancho, Z = hacia el
frente (donde se proyecta el panel). El eje del pivote del panel está en Y = PIVOTE_Y, Z = 0.

Croquis en planta:  (x, y) = (X, -Z)      Croquis en lateral: (x, y) = (-Z, Y)
"""
import math
import sys
from pathlib import Path

import swlib
from swlib import Pieza

AQUI = Path(__file__).parent
SALIDA = AQUI / "solidworks"
CAPTURAS = AQUI / "capturas"

# ------------------------------------------------------------------ medidas (mm)
PANEL = 145.0          # lado del panel solar
PANEL_T = 3.0          # espesor del panel
HOLG = 0.4             # holgura de impresión
PARED = 2.5

# Caja de la PCB (la PCB mide 88 x 50)
CAJA_L, CAJA_W, CAJA_H = 110.0, 65.0, 40.0
PCB_L, PCB_W, PCB_T = 88.0, 50.0, 1.6
PCB_ALTO = 6.0         # separación PCB-piso (soldaduras abajo)

# Base y pivote
BASE_X, BASE_Z0, BASE_Z1, BASE_T = 190.0, -75.0, 135.0, 5.0
PIVOTE_Y = 72.0
TORRE_T = 6.0
ARCO_R = 40.0          # radio de la ranura de bloqueo
ARCO_MAX = 60.0        # ángulo máximo del panel

# Marco del panel
MARCO_BORDE = 4.0
MARCO_W = PANEL + 2 * HOLG + 2 * MARCO_BORDE        # 153.8
MARCO_Z0 = 4.0                                      # el marco empieza 4 mm delante del eje
COSTILLA_T = 6.0
X_COSTILLA_EXT = MARCO_W / 2                        # 76.9
X_TORRE_INT = X_COSTILLA_EXT + HOLG                 # 77.3

# Cámara
MASTIL_D, MASTIL_DI, MASTIL_L = 16.0, 13.0, 300.0
MASTIL_X, MASTIL_Z = 75.0, -55.0
BRAZO_L = 155.0

# Posición de la PCB dentro de la caja (girada 180° para que USB y bornera den atrás)
def pcb_a_caja(x, y):
    return PCB_L / 2 - x, y - PCB_W / 2      # (X, Z)


# ------------------------------------------------------------------ piezas
def caja(sw):
    p = Pieza(sw, "caja_pcb")
    L, W, H, t = CAJA_L, CAJA_W, CAJA_H, PARED
    p.croquis(p.planta); p.rect(0, 0, L, W); s = p.cerrar_croquis("Croquis_contorno")
    p.extruir(s, H, "Cuerpo")
    p.croquis(p.planta, H); p.rect(0, 0, L - 2 * t, W - 2 * t); s = p.cerrar_croquis("Croquis_vaciado")
    p.cortar(s, H - t, "Vaciado", sentido=-1)
    # Apoyos de la PCB en las esquinas
    p.croquis(p.planta, t)
    for sx in (-1, 1):
        for sz in (-1, 1):
            p.rect(sx * (PCB_L / 2 - 3), -sz * (PCB_W / 2 - 3), 6, 6, cotar=(sx == 1 and sz == 1))
    s = p.cerrar_croquis("Croquis_apoyos_pcb")
    p.extruir(s, PCB_ALTO, "Apoyos_PCB")
    # Salida USB del ESP32 y cable del panel (pared trasera, -Z)
    usb_x, _ = pcb_a_caja(34.7, 0)
    j1_x, _ = pcb_a_caja(57.46, 0)
    pcb_top = t + PCB_ALTO + PCB_T
    p.croquis(p.alzado)
    p.rect(usb_x, pcb_top + 11.6, 13, 8)
    p.rect(j1_x, pcb_top + 5, 11, 7)
    s = p.cerrar_croquis("Croquis_salidas")
    p.cortar(s, None, "Salidas_USB_y_panel", sentido=-1)
    # Ventilación en las paredes cortas
    p.croquis(p.lateral)
    for k in range(-2, 3):
        p.ranura(k * 7.0, 25, 20, 2.4, vertical=True)
    s = p.cerrar_croquis("Croquis_ventilas")
    p.cortar(s, None, "Ventilas_laterales", ambos=True)
    # Tornillos a la base
    p.croquis(p.planta)
    p.circulo(-30, 0, 3.4); p.circulo(30, 0, 3.4, cotar=False)
    s = p.cerrar_croquis("Croquis_tornillos")
    p.cortar(s, None, "Agujeros_M3", ambos=True)
    return p


def tapa(sw):
    p = Pieza(sw, "tapa_caja")
    L, W, t = CAJA_L, CAJA_W, PARED
    p.croquis(p.planta); p.rect(0, 0, L, W); s = p.cerrar_croquis("Croquis_tapa")
    p.extruir(s, t, "Tapa")
    # Pestaña que entra en la caja
    li, lw = L - 2 * t - 2 * 0.3, W - 2 * t - 2 * 0.3
    p.croquis(p.planta); p.rect(0, 0, li, lw); s = p.cerrar_croquis("Croquis_pestana")
    p.extruir(s, 4, "Pestana", sentido=-1)
    p.croquis(p.planta); p.rect(0, 0, li - 3, lw - 3); s = p.cerrar_croquis("Croquis_pestana_hueco")
    p.cortar(s, 4, "Pestana_hueco", sentido=-1)
    # Postes que sujetan la PCB contra sus apoyos
    largo = CAJA_H - (PARED + PCB_ALTO + PCB_T)
    p.croquis(p.planta)
    for sx in (-1, 1):
        for sz in (-1, 1):
            p.circulo(sx * (PCB_L / 2 - 3), -sz * (PCB_W / 2 - 3), 5, cotar=(sx == 1 and sz == 1))
    s = p.cerrar_croquis("Croquis_postes")
    p.extruir(s, largo, "Postes_PCB", sentido=-1)
    # Ventana para la LDR y ventilación sobre el LM35, el INA219 y las resistencias
    ldr_x, ldr_z = pcb_a_caja(10.54, 36)
    lm_x, lm_z = pcb_a_caja(9.0, 26.32)
    p.croquis(p.planta)
    p.circulo(ldr_x, -ldr_z, 7)
    for k in range(3):
        p.ranura(lm_x - 4 + 4 * k, -(lm_z - 6), 10, 2, vertical=True)
    for k in range(7):
        p.ranura(-18 - 4 * k, 0, 32, 2, vertical=True)
    s = p.cerrar_croquis("Croquis_ventana_y_ventilas")
    p.cortar(s, None, "Ventana_LDR_y_ventilas", ambos=True)
    return p


def base(sw):
    p = Pieza(sw, "base_y_torres")
    zc = (BASE_Z0 + BASE_Z1) / 2
    p.croquis(p.planta); p.rect(0, -zc, BASE_X, BASE_Z1 - BASE_Z0); s = p.cerrar_croquis("Croquis_base")
    p.extruir(s, BASE_T, "Placa_base")
    # Tornillos de la caja
    caja_z = BASE_Z0 + 2 + CAJA_W / 2
    p.croquis(p.planta); p.circulo(-30, -caja_z, 3.4); p.circulo(30, -caja_z, 3.4, cotar=False)
    s = p.cerrar_croquis("Croquis_tornillos_caja")
    p.cortar(s, None, "Agujeros_caja", ambos=True)
    # Zócalo del mástil de la cámara
    p.croquis(p.planta, BASE_T); p.circulo(MASTIL_X, -MASTIL_Z, 28); s = p.cerrar_croquis("Croquis_zocalo")
    p.extruir(s, 25, "Zocalo_mastil")
    p.croquis(p.planta, BASE_T + 25); p.circulo(MASTIL_X, -MASTIL_Z, MASTIL_D + HOLG); s = p.cerrar_croquis("Croquis_zocalo_hueco")
    p.cortar(s, 22, "Zocalo_hueco", sentido=-1)
    # Torres del pivote (perfil en el plano lateral: x = -Z, y = Y)
    def perfil_torre(nombre, x):
        p.croquis(p.lateral, x)
        p.linea(-10, 0.0, 10, 0.0)
        p.linea(10, 0.0, 10, PIVOTE_Y)
        p.arco(0, PIVOTE_Y, 10, 0, 180)
        p.linea(-10, PIVOTE_Y, -10, 0.0)
        return p.cerrar_croquis(nombre)
    s = perfil_torre("Croquis_torre_der", X_TORRE_INT)
    p.extruir(s, TORRE_T, "Torre_derecha")
    s = perfil_torre("Croquis_torre_izq", -X_TORRE_INT)
    p.extruir(s, TORRE_T, "Torre_izquierda", sentido=-1)
    # Abanico de bloqueo en la torre izquierda: ángulo del panel a (desde +Z hacia +Y)
    # equivale en el croquis lateral a 180° - a.
    p.croquis(p.lateral, -X_TORRE_INT); p.sector(0, PIVOTE_Y, 52, 180 - (ARCO_MAX + 15), 180 + 15)
    s = p.cerrar_croquis("Croquis_abanico")
    p.extruir(s, TORRE_T, "Abanico", sentido=-1)
    p.croquis(p.lateral); p.ranura_arco(0, PIVOTE_Y, ARCO_R, 4.4, 180 - ARCO_MAX, 180)
    s = p.cerrar_croquis("Croquis_ranura_arco")
    p.cortar(s, None, "Ranura_arco", ambos=True)
    # Marcas cada 15°
    p.croquis(p.lateral)
    for a in range(0, int(ARCO_MAX) + 1, 15):
        b = math.radians(180 - a)
        ux, uy = math.cos(b), math.sin(b)
        nx, ny = -uy * 0.6, ux * 0.6
        r0, r1 = 46.0, 52.5
        p.polilinea([(r0 * ux + nx, PIVOTE_Y + r0 * uy + ny), (r1 * ux + nx, PIVOTE_Y + r1 * uy + ny),
                     (r1 * ux - nx, PIVOTE_Y + r1 * uy - ny), (r0 * ux - nx, PIVOTE_Y + r0 * uy - ny)])
    s = p.cerrar_croquis("Croquis_marcas_15")
    p.cortar(s, None, "Marcas_angulo", ambos=True)
    # Eje del pivote (M5)
    p.croquis(p.lateral); p.circulo(0, PIVOTE_Y, 5.3); s = p.cerrar_croquis("Croquis_pivote")
    p.cortar(s, None, "Agujero_pivote_M5", ambos=True)
    return p


def marco(sw):
    """Marco del panel. Origen en el eje del pivote, panel horizontal (0°)."""
    p = Pieza(sw, "marco_panel")
    w, z0 = MARCO_W, MARCO_Z0
    zc = z0 + w / 2
    hueco = PANEL / 2 + HOLG                    # 72.9
    y_placa, t_placa = 5.0, 3.0
    y_sup = y_placa + t_placa                   # 8
    p.croquis(p.planta, y_placa); p.rect(0, -zc, w, w); s = p.cerrar_croquis("Croquis_placa")
    p.extruir(s, t_placa, "Placa")
    # Bordes laterales y trasero (el frente queda abierto para deslizar el panel)
    alto = PANEL_T + 0.2
    for nombre, (cx, cz, ww, hh) in {
        "Borde_izq": (-(hueco + MARCO_BORDE / 2), zc, MARCO_BORDE, w),
        "Borde_der": (hueco + MARCO_BORDE / 2, zc, MARCO_BORDE, w),
        "Borde_tras": (0, z0 + MARCO_BORDE / 2, 2 * hueco, MARCO_BORDE),
    }.items():
        p.croquis(p.planta, y_sup); p.rect(cx, -cz, ww, hh, cotar=False); s = p.cerrar_croquis("Croquis_" + nombre)
        p.extruir(s, alto, nombre)
    # Ceja que retiene el panel (1.5 mm sobre él)
    ceja = 1.5
    for nombre, (cx, cz, ww, hh) in {
        "Ceja_izq": (-(hueco + MARCO_BORDE - (MARCO_BORDE + ceja) / 2), zc, MARCO_BORDE + ceja, w),
        "Ceja_der": (hueco + MARCO_BORDE - (MARCO_BORDE + ceja) / 2, zc, MARCO_BORDE + ceja, w),
        "Ceja_tras": (0, z0 + (MARCO_BORDE + ceja) / 2, 2 * hueco, MARCO_BORDE + ceja),
    }.items():
        p.croquis(p.planta, y_sup + alto); p.rect(cx, -cz, ww, hh, cotar=False); s = p.cerrar_croquis("Croquis_" + nombre)
        p.extruir(s, 1.2, nombre)
    # Paso del cable del panel
    p.croquis(p.planta); p.ranura(0, -(z0 + 26), 24, 8); s = p.cerrar_croquis("Croquis_cable")
    p.cortar(s, None, "Paso_cable", ambos=True)
    # Refuerzos bajo la placa
    p.croquis(p.planta, y_placa)
    p.rect(-40, -(z0 + 4 + 71), 3, 142); p.rect(40, -(z0 + 4 + 71), 3, 142, cotar=False)
    s = p.cerrar_croquis("Croquis_refuerzos")
    p.extruir(s, y_placa, "Refuerzos", sentido=-1)
    # Costillas laterales con el eje y el bloqueo
    x_int = X_COSTILLA_EXT - COSTILLA_T
    for lado, signo in (("der", 1), ("izq", -1)):
        p.croquis(p.lateral, signo * x_int); p.rect(-27.5, -1, 55, 12, cotar=(signo == 1))
        s = p.cerrar_croquis(f"Croquis_costilla_{lado}")
        p.extruir(s, COSTILLA_T, f"Costilla_{lado}", sentido=signo)
        p.croquis(p.lateral, signo * x_int); p.circulo(0, 0, 14, cotar=(signo == 1))
        s = p.cerrar_croquis(f"Croquis_buje_{lado}")
        p.extruir(s, COSTILLA_T, f"Buje_{lado}", sentido=signo)
    p.croquis(p.lateral); p.circulo(0, 0, 5.3); p.circulo(-ARCO_R, 0, 4.3)
    s = p.cerrar_croquis("Croquis_agujeros_eje")
    p.cortar(s, None, "Agujeros_pivote_y_bloqueo", ambos=True)
    # Alojamientos de tuerca en la cara interior de las costillas
    p.croquis(p.lateral, x_int); p.hexagono(0, 0, 8.2); s = p.cerrar_croquis("Croquis_tuerca_M5_der")
    p.cortar(s, 4, "Tuerca_M5_der", sentido=1)
    p.croquis(p.lateral, -x_int); p.hexagono(0, 0, 8.2); p.hexagono(-ARCO_R, 0, 7.2)
    s = p.cerrar_croquis("Croquis_tuercas_izq")
    p.cortar(s, 4, "Tuercas_M5_M4_izq", sentido=-1)
    return p


def perilla(sw):
    """Perilla moleteada (como la del smart stand) con cabeza de tornillo M4 atrapada."""
    p = Pieza(sw, "perilla_M4")
    D, H = 24.0, 9.0
    p.croquis(p.planta); p.circulo(0, 0, D); s = p.cerrar_croquis("Croquis_perilla")
    p.extruir(s, H, "Cuerpo")
    p.croquis(p.planta)
    for k in range(12):
        a = math.radians(k * 30)
        p.circulo(D / 2 * math.cos(a), D / 2 * math.sin(a), 4, cotar=(k == 0))
    s = p.cerrar_croquis("Croquis_moleteado")
    p.cortar(s, None, "Moleteado", ambos=True)
    p.croquis(p.planta); p.circulo(0, 0, 11); s = p.cerrar_croquis("Croquis_arandela")
    p.extruir(s, 2, "Arandela", sentido=-1)
    p.croquis(p.planta); p.circulo(0, 0, 4.4); s = p.cerrar_croquis("Croquis_paso")
    p.cortar(s, None, "Paso_M4", ambos=True)
    p.croquis(p.planta, H); p.hexagono(0, 0, 7.2); s = p.cerrar_croquis("Croquis_cabeza")
    p.cortar(s, 3.5, "Cabeza_M4", sentido=-1)
    return p


def mastil(sw):
    p = Pieza(sw, "mastil_tubo")
    p.croquis(p.planta); p.circulo(0, 0, MASTIL_D); p.circulo(0, 0, MASTIL_DI)
    s = p.cerrar_croquis("Croquis_tubo")
    p.extruir(s, MASTIL_L, "Tubo")
    return p


def brazo(sw):
    """Brazo de la cámara. Origen en el eje del mástil, apunta hacia +Z."""
    p = Pieza(sw, "brazo_camara")
    L = BRAZO_L
    p.croquis(p.planta); p.circulo(0, 0, 26); s = p.cerrar_croquis("Croquis_zocalo")
    p.extruir(s, 30, "Zocalo")
    p.croquis(p.planta); p.circulo(0, 0, MASTIL_D + HOLG); s = p.cerrar_croquis("Croquis_zocalo_hueco")
    p.cortar(s, 27, "Zocalo_hueco", sentido=1)
    p.croquis(p.planta, 20); p.rect(0, -L / 2, 16, L); s = p.cerrar_croquis("Croquis_barra")
    p.extruir(s, 10, "Barra")
    p.croquis(p.planta, 12); p.rect(0, -(L + 6), 16, 16); s = p.cerrar_croquis("Croquis_horquilla")
    p.extruir(s, 18, "Horquilla")
    p.croquis(p.planta); p.rect(0, -(L + 6), 6.4, 20); s = p.cerrar_croquis("Croquis_horquilla_ranura")
    p.cortar(s, None, "Horquilla_ranura", ambos=True)
    p.croquis(p.lateral); p.circulo(-(L + 6), 21, 4.4); p.circulo(0, 10, 3.3)
    s = p.cerrar_croquis("Croquis_ejes")
    p.cortar(s, None, "Eje_camara_y_prisionero", ambos=True)
    return p


def base_webcam(sw):
    """Placa donde engancha el clip de la webcam (o su rosca de 1/4"). Gira en la horquilla."""
    p = Pieza(sw, "base_webcam")
    p.croquis(p.lateral); p.circulo(0, 0, 12); s = p.cerrar_croquis("Croquis_lengueta_buje")
    p.extruir(s, 6, "Lengueta_buje", medio=True)
    p.croquis(p.lateral); p.rect(-9, 0, 18, 12); s = p.cerrar_croquis("Croquis_lengueta")
    p.extruir(s, 6, "Lengueta", medio=True)
    p.croquis(p.planta, -6); p.rect(0, -38.5, 60, 45); s = p.cerrar_croquis("Croquis_ceja")
    p.extruir(s, 12, "Ceja_monitor")
    p.croquis(p.planta); p.circulo(0, -40, 6.5); s = p.cerrar_croquis("Croquis_rosca")
    p.cortar(s, None, "Agujero_tripode_1_4", ambos=True)
    p.croquis(p.lateral); p.circulo(0, 0, 4.4); s = p.cerrar_croquis("Croquis_eje")
    p.cortar(s, None, "Eje_M4", ambos=True)
    return p


def panel_solar(sw):
    p = Pieza(sw, "ref_panel_solar")
    p.croquis(p.planta); p.rect(0, 0, PANEL, PANEL); s = p.cerrar_croquis("Croquis_panel")
    p.extruir(s, PANEL_T, "Panel")
    return p


def pcb(sw):
    p = Pieza(sw, "ref_pcb_simon")
    p.croquis(p.planta); p.rect(0, 0, PCB_L, PCB_W); s = p.cerrar_croquis("Croquis_pcb")
    p.extruir(s, PCB_T, "PCB")
    # ESP32 sobre headers y módulo INA219 (volúmenes de referencia)
    ex, ez = pcb_a_caja(34.7, 23.78)
    ix, iz = pcb_a_caja(69.1, 37.75)
    p.croquis(p.planta, PCB_T); p.rect(ex, -ez, 28.3, 51.5); s = p.cerrar_croquis("Croquis_esp32")
    p.extruir(s, 14, "ESP32")
    p.croquis(p.planta, PCB_T); p.rect(ix, -iz, 23, 20.3); s = p.cerrar_croquis("Croquis_ina219")
    p.extruir(s, 12, "INA219")
    return p


COLORES = {
    "caja": (0.93, 0.93, 0.92), "tapa": (0.93, 0.93, 0.92), "base": (0.22, 0.24, 0.27),
    "marco": (0.95, 0.55, 0.15), "perilla": (0.85, 0.12, 0.12), "mastil": (0.75, 0.77, 0.80),
    "brazo": (0.12, 0.12, 0.13), "base_webcam": (0.12, 0.12, 0.13),
    "panel": (0.08, 0.17, 0.42), "pcb": (0.10, 0.45, 0.22),
}

# Piezas que se imprimen (las "ref_" son solo de referencia; el mástil es tubo comprado)
IMPRIMIBLES = ["caja", "tapa", "base", "marco", "perilla", "brazo", "base_webcam"]

PIEZAS = {
    "caja": caja, "tapa": tapa, "base": base, "marco": marco, "perilla": perilla,
    "mastil": mastil, "brazo": brazo, "base_webcam": base_webcam,
    "panel": panel_solar, "pcb": pcb,
}


def main(nombres):
    SALIDA.mkdir(exist_ok=True)
    CAPTURAS.mkdir(exist_ok=True)
    sw = swlib.sw_app()
    swlib.cerrar_de_carpeta(sw, SALIDA)
    for n in nombres:
        p = PIEZAS[n](sw)
        p.color(*COLORES[n])
        ruta, err = p.guardar(SALIDA)
        vol = p.volumen_cm3()
        p.captura(CAPTURAS / f"{p.nombre}.bmp")
        if n in IMPRIMIBLES:
            (AQUI / "stl").mkdir(exist_ok=True)
            p.exportar(AQUI / "stl" / f"{p.nombre}.STL")
        print(f"{n:12s} -> {Path(ruta).name}  vol={vol:.1f} cm3  err={err}")
        p.cerrar()


if __name__ == "__main__":
    main(sys.argv[1:] or list(PIEZAS))
