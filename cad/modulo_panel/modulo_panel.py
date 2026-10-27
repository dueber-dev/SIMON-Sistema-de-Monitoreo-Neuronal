"""Módulo del panel de SIMON: turntable + soporte de la caja + bisagra del panel.

Una sola pieza de SolidWorks con cuerpos separados (no se fusionan):
- Base_fija, Plato_gira, Seguro: el turntable (cad/turntable), con el hexágono del buje.
- Buje:        hexágono que entra a presión en el plato (0.1 por lado) y en el soporte.
- Soporte:     una pieza: aro con esquineros que abrazan la caja, travesaño y dos torres
               con el agujero del tornillo y su asiento cónico. Índice del transportador.
- Marco_panel: hueco de 108 x 61.5 (acostado: el 108 corre a lo largo del eje), tubo de
               la bisagra, cejas, lengüeta que traba el panel y transportador de 0 a 90°.
- Tornillo, Tuerca: el tornillo de perilla y su tuerca, simplificados (sin rosca) con el
               perfil del original. Se imprimen los STL originales (tornillo.py lo alarga).
- Caja_ref, Tapa_ref, Panel_ref: solo de referencia (no se imprimen).

El panel cuelga de la bisagra como en un phone holder: se afloja la perilla, se inclina y
se aprieta. El transportador va pegado al marco y gira con él; el índice está fijo en la
torre de la perilla y marca la inclinación respecto a la horizontal.

Corre:  python modulo_panel.py
Genera: modulo_panel.SLDPRT, stl/ (lo que se imprime, ya orientado) y capturas/.

Coordenadas (las de SolidWorks): Y arriba, X a lo largo del eje de la bisagra. "Afuera"
(hacia donde cuelga el panel) es -Z; aquí se usa `ys` = -Z. Croquis en planta:
(x, y) = (X, ys); en lateral: (x, y) = (ys, Y); en alzado: (x, y) = (X, Y).
El marco se modela horizontal (0°) y al final se inclina con una operación Mover que se
puede editar para ver cualquier ángulo.
"""
import math
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI.parent / "turntable"))
sys.path.insert(0, str(AQUI.parent / "caja_pcb"))
import swlib  # noqa: E402
from swlib import T, call  # noqa: E402
import turntable_simon as tt  # noqa: E402
import caja_simon as cj  # noqa: E402
import tornillo  # noqa: E402

CAPTURAS = AQUI / "capturas"
STL = AQUI / "stl"
NOMBRE = "modulo_panel"

# ------------------------------------------------------------------ medidas (mm)
Y_SUP = tt.Y_PLATO + tt.PLATO_T         # 19: cara de arriba del plato del turntable

# Buje: centra el soporte en el plato y no lo deja girar
HOLG_BUJE = 0.1                         # por lado, en el plato
APRIETE_BUJE = 0.05                     # por lado, en el soporte (ahí se queda puesto)
BUJE_HEX = tt.HEX_PLATO - 2 * HOLG_BUJE           # 23.8 entre caras
HEX_SOPORTE = BUJE_HEX + 2 * APRIETE_BUJE         # 23.9
BUJE_D_INT = BUJE_HEX - 2 * 2.5                   # pared de 2.5 en las caras
PROF_SOPORTE = 5.0                      # lo que el buje entra en el soporte
JUEGO_BUJE = 0.2                        # en cada punta, para que no toque fondo

# Caja de la PCB (cad/caja_pcb): USB y bornera hacia afuera, frente pegado a la bisagra
CAJA_L, CAJA_W = cj.EXT_L, cj.EXT_W               # 95.5 x 62
CAJA_H = cj.TAPA_ABAJO + cj.TAPA_T                # 33 con la tapa
HOLG_CAJA = 0.15                        # por lado entre la caja y los esquineros
CAJA_FRENTE = 12.0                      # ys del frente de la caja
CAJA_ATRAS = CAJA_FRENTE - CAJA_W       # -50: USB y bornera
PATAS = 4.0                             # aire bajo la rejilla del piso (en vez de patitas de hule)
BASE_T = 2.0                            # base del soporte
ARO_W = 5.0                             # aro bajo el borde de la caja
NERVIO_W = 4.0                          # cruz que une el aro con el collar del buje
COLLAR_D = 32.0
ESQ_T, ESQ_H, ESQ_L = 2.0, 8.0, 14.0    # esquineros: pared, alto sobre la caja, largo de cada brazo
PATA_L = 8.0
TRAV_W = 16.0                           # travesaño que une las torres
ALMA_T, ALMA_H = 2.5, 8.0               # nervio vertical del travesaño

# Bisagra: el tornillo atraviesa torre - tubo del marco - torre
Y_EJE, YS_EJE = 80.0, 56.0              # a 90° el marco cuelga por fuera del turntable
PANEL_L, PANEL_W = 108.0, 61.5          # hueco del panel (ya trae la tolerancia)
GROSOR_PANEL = 3.0                      # variable global "Grosor_panel" en el modelo
PARED = 1.5                             # paredes del marco
TUBO_D, TUBO_HUECO = 14.0, 10.25       # tubo de la bisagra; Ø10.25 como el original (tornillo Ø9.56)
TUBO_L = PANEL_L + 2 * PARED            # 111
HOLG_TORRE = 0.1                        # por lado entre el tubo y las torres (el tornillo aprieta)
TORRE_IN = TUBO_L / 2 + HOLG_TORRE      # 55.6
TORRE_T = 6.0                           # jefe del agujero: aloja el asiento cónico
TORRE_OUT = TORRE_IN + TORRE_T          # 61.6
JEFE_R = 11.0
POSTE_T = 2.5
# Asiento cónico del stand original: de r 8.5 en la cara a r 5.125 a 2.5 de hondo. La
# perilla y la tuerca tienen el mismo cono (empieza en r 8.5 a z = 5.25 y z = 9.19).
AVELL_R, AVELL_P = 8.5, 2.5
Z_ASIENTO_TORNILLO, Z_ASIENTO_TUERCA = 5.25, 9.19
AGARRE = 2 * TORRE_OUT                  # 123.2 entre caras de afuera: largo del tornillo

# Marco, en coordenadas propias: u a lo largo del marco desde el eje, n hacia la cara del panel
N_FONDO, FONDO_T = -1.5, 2.0            # el panel apoya en n = -1.5 sobre un fondo de 2
U_PARED0 = 5.0                          # la pared de arriba nace dentro del tubo
U_HUECO0 = TUBO_D / 2 + PARED           # 8.5: borde de arriba del panel
U_HUECO1 = U_HUECO0 + PANEL_W           # 70
U_FIN = U_HUECO1 + 2.0                  # 72: labio de abajo
CEJA_T, CEJA_W = 1.5, 1.5
VENTANA_X0, VENTANA_X1 = -30.0, 48.0    # ventanas del fondo (cables del panel y menos filamento)
LENG_U0, LENG_U1, LENG_X = 34.0, 44.0, -42.0      # lengüeta que traba el panel (punta en -X)
RANURA_LENG = 1.0
DIENTE_H, DIENTE_L = 1.0, 1.3

# Transportador (en el marco) e índice (en la torre de +X)
DIAL_T, DIAL_R = 2.5, 37.0
MARCA_R1, MARCA_R0, MARCA_R0_CHICA = 31.0, 26.0, 28.0
NUM_R, NUM_H = 34.0, 4.0
GRABADO = 0.5
INDICE_T, INDICE_PUNTA = 2.5, 25.0
ANGULO_VISTA = 30.0

Y_FONDO_PANEL = Y_EJE + N_FONDO         # 78.5
ys = lambda u: YS_EJE + u               # u del marco -> ys


def nuevo(p, lista, f):
    lista.extend(p.cuerpos_de(f))
    return f


def sumar_como(p, piezas, operacion, nombre, viejos):
    """Combina `piezas` y le pone `nombre` al cuerpo que resulta (el único que no estaba
    entre `viejos`; la operación Combinar no tiene caras propias para encontrarlo)."""
    p.sumar(piezas, operacion)
    return nombrar_nuevo(p, nombre, viejos)


def nombrar_nuevo(p, nombre, viejos):
    """Le pone `nombre` al único cuerpo que no estaba entre `viejos`. Si ya se llamaba así
    (nombre automático heredado), se renombra dos veces: si no, SolidWorks lo sigue
    renombrando con cada operación nueva."""
    nuevos = [b for b in p.cuerpos() if b.Name not in viejos]
    if len(nuevos) != 1:
        raise RuntimeError(f"{nombre}: hay {len(nuevos)} cuerpos nuevos en vez de 1")
    if nuevos[0].Name == nombre:
        nuevos[0].Name = nombre + "_"
    nuevos[0].Name = nombre
    return nuevos[0]


def polar(r, ang, c=(YS_EJE, Y_EJE)):
    return c[0] + r * math.cos(math.radians(ang)), c[1] + r * math.sin(math.radians(ang))


# Dígitos de siete segmentos: cada segmento es un rectángulo suelto (con aire entre ellos,
# así el croquis no tiene contornos encimados). Medidas en mm.
SEG_W, SEG_H, SEG_T, SEG_AIRE, SEG_ESP = 2.8, NUM_H, 0.7, 0.1, 0.8
SEGMENTOS = {"0": "abcdef", "1": "bc", "3": "abcdg", "4": "bcfg", "5": "acdfg",
             "6": "acdefg", "7": "abc", "9": "abcdfg"}


def _segmento(letra):
    """Rectángulo (x0, y0, x1, y1) del segmento, con el dígito en [0, SEG_W] x [0, SEG_H]."""
    w, h, t, e = SEG_W, SEG_H, SEG_T, SEG_AIRE
    xh0, xh1 = t + e, w - t - e                     # horizontales: entre las verticales
    return {"a": (xh0, h - t, xh1, h), "g": (xh0, h / 2 - t / 2, xh1, h / 2 + t / 2),
            "d": (xh0, 0, xh1, t), "f": (0, h / 2 + e, t, h), "b": (w - t, h / 2 + e, w, h),
            "e": (0, 0, t, h / 2 - e), "c": (w - t, 0, w, h / 2 - e)}[letra]


def numero_7seg(p, txt, centro, ang):
    """Dibuja `txt` centrado en `centro`, girado `ang` grados (antihorario)."""
    ancho = len(txt) * SEG_W + (len(txt) - 1) * SEG_ESP
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    for k, ch in enumerate(txt):
        dx = k * (SEG_W + SEG_ESP) - ancho / 2
        for letra in SEGMENTOS[ch]:
            x0, y0, x1, y1 = _segmento(letra)
            esquinas = [(x0 + dx, y0 - SEG_H / 2), (x1 + dx, y0 - SEG_H / 2),
                        (x1 + dx, y1 - SEG_H / 2), (x0 + dx, y1 - SEG_H / 2)]
            p.polilinea([(centro[0] + x * c - y * s, centro[1] + x * s + y * c) for x, y in esquinas])


# ------------------------------------------------------------------ soporte
def soporte(p):
    viejos = {b.Name for b in p.cuerpos()}
    piezas = []
    xb, yf, yr = CAJA_L / 2 + HOLG_CAJA, CAJA_FRENTE + HOLG_CAJA, CAJA_ATRAS - HOLG_CAJA
    xa, yfa, yra = xb + ESQ_T, yf + ESQ_T, yr - ESQ_T   # borde de afuera del aro
    cy = (yfa + yra) / 2

    p.croquis(p.planta, Y_SUP)
    p.rect(0, cy, 2 * xa, yfa - yra)
    p.rect(0, cy, 2 * (xa - ARO_W), yfa - yra - 2 * ARO_W, cotar=False)
    s = p.cerrar_croquis("Croquis_aro")
    nuevo(p, piezas, p.extruir(s, BASE_T, "Aro", fusionar=False))

    # Cruz que une el aro con el collar del buje (el buje queda en el centro del turntable)
    a, w, x1, y0, y1 = NERVIO_W / 2, NERVIO_W / 2, xa - ARO_W, yra + ARO_W, yfa - ARO_W
    p.croquis(p.planta, Y_SUP)
    p.polilinea([(-x1, -w), (-a, -w), (-a, y0), (a, y0), (a, -w), (x1, -w),
                 (x1, w), (a, w), (a, y1), (-a, y1), (-a, w), (-x1, w)])
    s = p.cerrar_croquis("Croquis_cruz")
    nuevo(p, piezas, p.extruir(s, BASE_T, "Cruz", fusionar=False))

    p.croquis(p.planta, Y_SUP); p.circulo(0, 0, COLLAR_D)
    s = p.cerrar_croquis("Croquis_collar")
    nuevo(p, piezas, p.extruir(s, PROF_SOPORTE, "Collar_buje", fusionar=False))

    # Travesaño que une las dos torres, con un nervio vertical para que no se doble
    p.croquis(p.planta, Y_SUP); p.rect(0, yfa + TRAV_W / 2, 2 * TORRE_OUT, TRAV_W)
    s = p.cerrar_croquis("Croquis_travesano")
    nuevo(p, piezas, p.extruir(s, BASE_T, "Travesano", fusionar=False))
    p.croquis(p.planta, Y_SUP + BASE_T)
    p.rect(0, yfa + TRAV_W - ALMA_T / 2, 2 * TORRE_OUT, ALMA_T)
    s = p.cerrar_croquis("Croquis_alma")
    nuevo(p, piezas, p.extruir(s, ALMA_H, "Alma_travesano", fusionar=False))

    # Esquineros (L) y patas en las 4 esquinas de la caja
    p.croquis(p.planta, Y_SUP + BASE_T)
    for sx in (1, -1):
        for sy, c_y in ((1, yf), (-1, yr)):
            cx = sx * xb
            p.polilinea([(cx, c_y - sy * ESQ_L), (cx + sx * ESQ_T, c_y - sy * ESQ_L),
                         (cx + sx * ESQ_T, c_y + sy * ESQ_T), (cx - sx * ESQ_L, c_y + sy * ESQ_T),
                         (cx - sx * ESQ_L, c_y), (cx, c_y)])
    s = p.cerrar_croquis("Croquis_esquineros")
    nuevo(p, piezas, p.extruir(s, PATAS + ESQ_H, "Esquineros", fusionar=False))

    # (como polígonos: con cuatro rectángulos centrados SolidWorks no termina de definir el croquis)
    p.croquis(p.planta, Y_SUP + BASE_T)
    for sx in (1, -1):
        for sy, c_y in ((1, yf), (-1, yr)):
            x0, y0 = sx * xb, c_y
            x1, y1 = x0 - sx * PATA_L, y0 - sy * PATA_L
            p.polilinea([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    s = p.cerrar_croquis("Croquis_patas")
    nuevo(p, piezas, p.extruir(s, PATAS, "Patas_caja", fusionar=False))

    # Torres: jefe del agujero (6 mm, aloja el asiento cónico) y poste inclinado de 2.5
    for sx in (1, -1):
        lado = "der" if sx > 0 else "izq"
        p.croquis(p.lateral, sx * TORRE_OUT); p.circulo(YS_EJE, Y_EJE, 2 * JEFE_R)
        s = p.cerrar_croquis(f"Croquis_jefe_{lado}")
        nuevo(p, piezas, p.extruir(s, TORRE_T, f"Jefe_{lado}", sentido=-sx, fusionar=False))
        p.croquis(p.lateral, sx * TORRE_OUT)
        p.polilinea([(yfa, Y_SUP), (yfa + TRAV_W, Y_SUP), (YS_EJE + 8, Y_EJE - 2), (YS_EJE - 8, Y_EJE - 2)])
        s = p.cerrar_croquis(f"Croquis_poste_{lado}")
        nuevo(p, piezas, p.extruir(s, POSTE_T, f"Poste_{lado}", sentido=-sx, fusionar=False))

    # Índice del transportador: dedo fijo que sube del jefe de +X y apunta a las marcas
    x_ind = TORRE_IN + 1.0 + INDICE_T
    p.croquis(p.lateral, x_ind)
    p.polilinea([(YS_EJE - 2, Y_EJE + 9), (YS_EJE + 2, Y_EJE + 9), (YS_EJE + 2, Y_EJE + INDICE_PUNTA - 2),
                 (YS_EJE, Y_EJE + INDICE_PUNTA), (YS_EJE - 2, Y_EJE + INDICE_PUNTA - 2)])
    s = p.cerrar_croquis("Croquis_indice")
    nuevo(p, piezas, p.extruir(s, INDICE_T, "Indice", sentido=-1, fusionar=False))

    sumar_como(p, piezas, "Sumar_soporte", "Soporte", viejos)

    # Hexágono del buje (el buje se queda puesto aquí)
    p.croquis(p.planta, Y_SUP + PROF_SOPORTE); p.hexagono(0, 0, HEX_SOPORTE)
    s = p.cerrar_croquis("Croquis_hexagono_soporte")
    p.cortar(s, PROF_SOPORTE, "Hexagono_soporte", sentido=-1)

    # Agujeros del tornillo: Ø10 con techo en punta (se imprimen acostados, sin soporte)
    r = TUBO_HUECO / 2
    for sx in (1, -1):
        lado = "der" if sx > 0 else "izq"
        p.croquis(p.lateral, sx * TORRE_OUT)
        p.arco(YS_EJE, Y_EJE, r, 135, 405)
        p.linea(*polar(r, 45), YS_EJE, Y_EJE + r * math.sqrt(2))
        p.linea(YS_EJE, Y_EJE + r * math.sqrt(2), *polar(r, 135))
        s = p.cerrar_croquis(f"Croquis_agujero_{lado}")
        p.cortar(s, TORRE_T, f"Agujero_tornillo_{lado}", sentido=-sx)

    # Avellanado cónico en las caras de afuera: ahí asientan los conos de la perilla y la tuerca
    pendiente = (AVELL_R - TUBO_HUECO / 2) / AVELL_P
    p.croquis(p.alzado, -YS_EJE)
    p.linea_constructiva(-1, Y_EJE, 1, Y_EJE)          # eje (corto, para no encimarse a los perfiles)
    for sx in (1, -1):
        x0, x1, x2 = sx * (TORRE_OUT - AVELL_P), sx * TORRE_OUT, sx * (TORRE_OUT + 1)
        p.polilinea([(x0, Y_EJE), (x0, Y_EJE + TUBO_HUECO / 2), (x1, Y_EJE + AVELL_R),
                     (x2, Y_EJE + AVELL_R + pendiente), (x2, Y_EJE)])
    s = p.cerrar_croquis("Croquis_avellanados")
    p.revolucion(s, "Avellanados", cortar=True)

    # Boca del hexágono (va en la cama): sin chaflán, la pata de elefante la cerraría. Al
    # contorno de afuera SolidWorks no le puede hacer chaflán (es muy quebrado); ahí basta
    # con la compensación de pata de elefante del slicer.
    p.chaflan_contorno((0, -1, 0), Y_SUP, 0.4, "Chaflan_hexagono_soporte", interior=True, cuerpo="Soporte")


# ------------------------------------------------------------------ marco del panel
def marco(p):
    viejos = {b.Name for b in p.cuerpos()}
    piezas = []
    p.croquis(p.lateral); p.circulo(YS_EJE, Y_EJE, TUBO_D)
    s = p.cerrar_croquis("Croquis_tubo")
    nuevo(p, piezas, p.extruir(s, TUBO_L, "Tubo_bisagra", medio=True, fusionar=False))

    p.croquis(p.planta, Y_FONDO_PANEL - FONDO_T)
    p.rect(0, ys(U_FIN / 2), TUBO_L, U_FIN)
    s = p.cerrar_croquis("Croquis_fondo")
    nuevo(p, piezas, p.extruir(s, FONDO_T, "Fondo_marco", fusionar=False))

    # Paredes alrededor del panel, abiertas en -X (por ahí entra el panel deslizándose).
    # Su alto sale de la variable Grosor_panel.
    xl, xe = -TUBO_L / 2, PANEL_L / 2
    plano_fondo = p.plano_desfasado(p.planta, Y_FONDO_PANEL)
    plano_fondo.Name = "Plano_fondo_panel"
    p.croquis(plano_fondo)
    p.polilinea([(xl, ys(U_PARED0)), (-xl, ys(U_PARED0)), (-xl, ys(U_FIN)), (xl, ys(U_FIN)),
                 (xl, ys(U_HUECO1)), (xe, ys(U_HUECO1)), (xe, ys(U_HUECO0)), (xl, ys(U_HUECO0))])
    s = p.cerrar_croquis("Croquis_paredes")
    nuevo(p, piezas, p.extruir(s, GROSOR_PANEL + CEJA_T, "Paredes_marco", fusionar=False))

    plano_cejas = p.plano_desfasado(p.planta, Y_FONDO_PANEL + GROSOR_PANEL)
    plano_cejas.Name = "Plano_cejas"
    p.croquis(plano_cejas)
    p.polilinea([(xl, ys(U_HUECO0)), (xe, ys(U_HUECO0)), (xe, ys(U_HUECO1)), (xl, ys(U_HUECO1)),
                 (xl, ys(U_HUECO1 - CEJA_W)), (xe - CEJA_W, ys(U_HUECO1 - CEJA_W)),
                 (xe - CEJA_W, ys(U_HUECO0 + CEJA_W)), (xl, ys(U_HUECO0 + CEJA_W))])
    s = p.cerrar_croquis("Croquis_cejas")
    nuevo(p, piezas, p.extruir(s, CEJA_T, "Cejas", fusionar=False))

    # Transportador: abanico pegado a la punta +X del tubo, del lado de la cara del panel
    p.croquis(p.lateral, -xl)
    c = (YS_EJE, Y_EJE)
    p.linea(*c, *polar(12, 20))
    p.arco(*c, 12, 20, 85)
    p.linea(*polar(12, 85), *polar(DIAL_R, 85))
    p.arco(*c, DIAL_R, 85, 185)
    p.linea(*polar(DIAL_R, 185), *c)
    s = p.cerrar_croquis("Croquis_transportador")
    nuevo(p, piezas, p.extruir(s, DIAL_T, "Transportador", sentido=-1, fusionar=False))

    # El nombre se pone una sola vez, al final: si se le pone a un cuerpo que después se
    # combina, SolidWorks ya no deja reusar el nombre en el cuerpo nuevo.
    p.sumar(piezas, "Sumar_marco")

    p.croquis(p.lateral); p.circulo(YS_EJE, Y_EJE, TUBO_HUECO)
    s = p.cerrar_croquis("Croquis_hueco_tubo")
    p.cortar(s, TUBO_L, "Hueco_tubo", medio=True)

    # Ventanas del fondo, con techo en punta del lado -X (el marco se imprime parado sobre +X)
    p.croquis(p.planta, Y_FONDO_PANEL - FONDO_T)
    for u0, u1 in ((14.0, 37.5), (40.5, 64.0)):
        m = (u1 - u0) / 2
        p.polilinea([(VENTANA_X1, ys(u0)), (VENTANA_X1, ys(u1)), (VENTANA_X0, ys(u1)),
                     (VENTANA_X0 - m, ys(u0 + m)), (VENTANA_X0, ys(u0))])
    s = p.cerrar_croquis("Croquis_ventanas")
    p.cortar(s, FONDO_T, "Ventanas_fondo")

    # Lengüeta: dos ranuras en el fondo dejan un resorte con un diente en la punta. El panel
    # entra empujándolo y el diente cae detrás de él; para sacarlo se aprieta desde atrás.
    p.croquis(p.planta, Y_FONDO_PANEL - FONDO_T)
    for u in (LENG_U0 - RANURA_LENG / 2, LENG_U1 + RANURA_LENG / 2):
        p.rect((xl - 1 + LENG_X) / 2, ys(u), LENG_X - xl + 1, RANURA_LENG, cotar=(u > LENG_U1))
    s = p.cerrar_croquis("Croquis_lengueta")
    p.cortar(s, FONDO_T, "Ranuras_lengueta")
    marco_b = [b for b in p.cuerpos() if b.Name not in viejos]
    p.croquis(p.alzado, -ys((LENG_U0 + LENG_U1) / 2))
    xd = -PANEL_L / 2 - 0.2
    p.polilinea([(xd - DIENTE_L, Y_FONDO_PANEL), (xd, Y_FONDO_PANEL), (xd, Y_FONDO_PANEL + DIENTE_H)])
    s = p.cerrar_croquis("Croquis_diente")
    f = p.extruir(s, LENG_U1 - LENG_U0, "Diente_lengueta", medio=True, fusionar=False)
    p.sumar(marco_b + p.cuerpos_de(f), "Sumar_diente")

    # Marcas cada 5° (largas cada 15°) y números, grabados en la cara +X del transportador.
    # La marca del ángulo t va a 90 + t grados del marco: queda bajo el índice (arriba)
    # cuando el panel está inclinado t grados.
    p.croquis(p.lateral, -xl)
    for t in range(0, 91, 5):
        a = 90 + t
        r0, w = (MARCA_R0, 1.0) if t % 15 == 0 else (MARCA_R0_CHICA, 0.7)
        d = (math.sin(math.radians(a)) * w / 2, -math.cos(math.radians(a)) * w / 2)
        p0, p1 = polar(r0, a), polar(MARCA_R1, a)
        p.polilinea([(p0[0] - d[0], p0[1] - d[1]), (p1[0] - d[0], p1[1] - d[1]),
                     (p1[0] + d[0], p1[1] + d[1]), (p0[0] + d[0], p0[1] + d[1])])
    s = p.cerrar_croquis("Croquis_marcas")
    p.cortar(s, GRABADO, "Marcas_grados", sentido=-1)

    # Números de siete segmentos (el texto girado de SolidWorks no sale bien), cada uno
    # girado para que se lea derecho cuando queda bajo el índice.
    p.croquis(p.lateral, -xl)
    for t in range(0, 91, 15):
        numero_7seg(p, str(t), polar(NUM_R, 90 + t), t)
    s = p.cerrar_croquis("Croquis_numeros")
    p.cortar(s, GRABADO, "Numeros_grados", sentido=-1)
    nombrar_nuevo(p, "Marco_panel", viejos)


def panel_ref(p):
    p.croquis(p.plano_desfasado(p.planta, Y_FONDO_PANEL))
    p.rect(0, ys((U_HUECO0 + U_HUECO1) / 2), PANEL_L, PANEL_W)
    s = p.cerrar_croquis("Croquis_panel_ref")
    f = p.extruir(s, GROSOR_PANEL, "Panel_referencia", fusionar=False)
    p.cuerpos_de(f)[0].Name = "Panel_ref"


def buje(p):
    y0 = Y_SUP - tt.HEX_PROF + JUEGO_BUJE
    alto = tt.HEX_PROF + PROF_SOPORTE - 2 * JUEGO_BUJE
    p.croquis(p.planta, y0); p.hexagono(0, 0, BUJE_HEX); p.circulo(0, 0, BUJE_D_INT)
    s = p.cerrar_croquis("Croquis_buje")
    f = p.extruir(s, alto, "Extruir_buje", fusionar=False)
    p.cuerpos_de(f)[0].Name = "Buje"
    for normal, nivel, nombre in (((0, -1, 0), y0, "Chaflan_buje_abajo"),
                                  ((0, 1, 0), y0 + alto, "Chaflan_buje_arriba")):
        p.chaflan_contorno(normal, nivel, 0.4, nombre, cuerpo="Buje")


# ------------------------------------------------------------------ cuerpos importados
def _girar_caja(caja, eje, ang):
    """Caja envolvente [x0, y0, z0, x1, y1, z1] girada `ang` grados (regla de la mano
    derecha) alrededor del eje 0, 1 o 2 que pasa por el origen."""
    c, s = round(math.cos(math.radians(ang))), round(math.sin(math.radians(ang)))
    i, j = [(1, 2), (2, 0), (0, 1)][eje]
    esquinas = []
    for x in (caja[0], caja[3]):
        for y in (caja[1], caja[4]):
            for z in (caja[2], caja[5]):
                v = [x, y, z]
                v[i], v[j] = v[i] * c - v[j] * s, v[i] * s + v[j] * c
                esquinas.append(v)
    return [min(e[k] for e in esquinas) for k in range(3)] + [max(e[k] for e in esquinas) for k in range(3)]


def ubicar(p, cuerpos, giros, trasl, nombre):
    """Gira (giros: lista de (eje, grados), en orden) y traslada los cuerpos recién
    insertados, y le pone `nombre` al primero. Cada giro se comprueba con la caja envolvente:
    si SolidWorks giró al revés, se rehace con el ángulo contrario."""
    nombres = [b.Name for b in cuerpos]
    for k, (eje, ang) in enumerate(giros):
        antes = caja_cuerpo(p, nombres[0])
        for intento in (ang, -ang):
            giro = [0, 0, 0]
            giro[eje] = intento
            f = p.mover([p.cuerpo(n) for n in nombres], giro=giro, nombre=f"Girar_{nombre}_{k + 1}")
            esperada = _girar_caja(antes, eje, ang)
            if all(abs(a - b) < 0.5 for a, b in zip(caja_cuerpo(p, nombres[0]), esperada)):
                break
            borrar(p, f)
        else:
            raise RuntimeError(f"no pude girar {nombre} alrededor del eje {eje}")
    p.mover([p.cuerpo(n) for n in nombres], trasl=trasl, nombre=f"Ubicar_{nombre}")
    p.cuerpo(nombres[0]).Name = nombre


def caja_ref(p):
    """La caja y su tapa (cad/caja_pcb), giradas 180° para que el USB y la bornera queden
    hacia afuera. Quedan ligadas a sus archivos: si la caja cambia, aquí se actualiza."""
    y0 = Y_SUP + BASE_T + PATAS
    dz = -(CAJA_FRENTE + CAJA_ATRAS) / 2 - cj.CY        # centro de la caja en Z
    for archivo, nombre, dy in (("caja_simon_base", "Caja_ref", 0.0), ("caja_simon_tapa", "Tapa_ref", cj.TAPA_ABAJO)):
        cs = p.insertar_pieza(AQUI.parent / "caja_pcb" / f"{archivo}.SLDPRT", f"Insertar_{nombre}")
        ubicar(p, cs, [(1, 180)], (0, y0 + dy, dz), nombre)


# Perfil del tornillo y la tuerca originales (medidos en sus STL), como (z, r) desde la
# cara de afuera de la perilla. Su perilla tiene 12 muescas.
PERILLA_R, PERILLA_L_TORNILLO, PERILLA_L_TUERCA = 10.0, 5.0, 7.5
MUESCA_R, MUESCA_C = 1.5, 10.4          # radio de cada muesca y distancia de su centro al eje
CUERPO_R = 4.78                         # cuerpo y rosca del tornillo (Ø9.56)


def tornilleria(p):
    """Tornillo y tuerca para ver el armado y revisar choques: sólidos simplificados (sin
    rosca) con el perfil del original. Lo que se imprime es stl/tornillo.stl (el original
    alargado, tornillo.py) y stl/tuerca.stl (el original tal cual)."""
    largo = tornillo.alargar(tornillo.ORIGINAL, STL / "tornillo.stl", AGARRE - tornillo.AGARRE_ORIGINAL)
    shutil.copy(tornillo.TUERCA, STL / "tuerca.stl")
    pendiente = (AVELL_R - TUBO_HUECO / 2) / AVELL_P
    # z -> X: la perilla del tornillo afuera de la torre +X, la tuerca afuera de la -X
    xt = TORRE_OUT + Z_ASIENTO_TORNILLO
    xn = -TORRE_OUT - Z_ASIENTO_TUERCA
    zc = Z_ASIENTO_TORNILLO + (AVELL_R - TUBO_HUECO / 2) / pendiente
    perfiles = {
        "Tornillo": (lambda z: xt - z, [(0, 0), (0, PERILLA_R), (PERILLA_L_TORNILLO, PERILLA_R),
                                        (PERILLA_L_TORNILLO, AVELL_R), (Z_ASIENTO_TORNILLO, AVELL_R),
                                        (zc, TUBO_HUECO / 2), (zc + 0.25, CUERPO_R),
                                        (largo - 0.9, CUERPO_R), (largo, CUERPO_R - 0.9), (largo, 0)]),
        "Tuerca": (lambda z: xn + z, [(0, 0), (0, PERILLA_R), (PERILLA_L_TUERCA, PERILLA_R),
                                      (PERILLA_L_TUERCA, AVELL_R), (Z_ASIENTO_TUERCA, AVELL_R),
                                      (Z_ASIENTO_TUERCA + 1.5, AVELL_R - 1.5 * pendiente),
                                      (Z_ASIENTO_TUERCA + 1.5, CUERPO_R + 0.12), (1.0, CUERPO_R + 0.12),
                                      (1.0, 0)]),
    }
    for nombre, (a_x, perfil) in perfiles.items():
        viejos = {b.Name for b in p.cuerpos()}
        afuera = -1 if a_x(1) > a_x(0) else 1     # hacia donde queda la perilla
        p.croquis(p.alzado, -YS_EJE)
        # eje fuera del perfil, para que la línea constructiva no se encime a su borde
        p.linea_constructiva(a_x(0) + 2 * afuera, Y_EJE, a_x(0) + 3 * afuera, Y_EJE)
        p.polilinea([(a_x(z), Y_EJE + r) for z, r in perfil])
        s = p.cerrar_croquis(f"Croquis_{nombre.lower()}")
        p.revolucion(s, f"Revolucion_{nombre.lower()}", fusionar=False)
        # 12 muescas en la perilla, a lo largo de toda la perilla
        lado = PERILLA_L_TORNILLO if nombre == "Tornillo" else PERILLA_L_TUERCA
        p.croquis(p.lateral, a_x(0))
        for k in range(12):
            p.circulo(*polar(MUESCA_C, k * 30), 2 * MUESCA_R, cotar=(k == 0))
        s = p.cerrar_croquis(f"Croquis_muescas_{nombre.lower()}")
        p.cortar(s, lado, f"Muescas_{nombre.lower()}", sentido=-afuera)
        nombrar_nuevo(p, nombre, viejos)
    return largo


# ------------------------------------------------------------------ revisión
COLORES = {"Soporte": ((0.93, 0.93, 0.92), 0.0), "Marco_panel": ((0.16, 0.17, 0.19), 0.0),
           "Buje": ((0.95, 0.45, 0.10), 0.0), "Tornillo": ((0.95, 0.45, 0.10), 0.0),
           "Tuerca": ((0.95, 0.45, 0.10), 0.0), "Panel_ref": ((0.10, 0.20, 0.45), 0.0),
           "Caja_ref": ((0.75, 0.80, 0.85), 0.6), "Tapa_ref": ((0.75, 0.80, 0.85), 0.6)}

PARES = [("Soporte", "Plato_gira"), ("Soporte", "Base_fija"), ("Soporte", "Seguro"),
         ("Soporte", "Caja_ref"), ("Soporte", "Tapa_ref"), ("Soporte", "Marco_panel"),
         ("Soporte", "Tornillo"), ("Soporte", "Tuerca"), ("Soporte", "Buje"),
         ("Buje", "Plato_gira"), ("Marco_panel", "Tornillo"), ("Marco_panel", "Panel_ref"),
         ("Marco_panel", "Plato_gira"), ("Marco_panel", "Base_fija"), ("Marco_panel", "Seguro"),
         ("Marco_panel", "Caja_ref"), ("Marco_panel", "Tapa_ref"), ("Panel_ref", "Soporte")]


def revisar(p, pares, titulo):
    malos = []
    for a, b in pares:
        v = p.choque(p.cuerpo(a), p.cuerpo(b))
        if v > 0.5:   # menos es el roce de una malla facetada en un asiento (tuerca contra su cono)
            malos.append(f"{a} x {b}: {v:.2f} mm3")
    print(f"  choques {titulo}: {'ninguno' if not malos else '; '.join(malos)}")
    return malos


SIGNO_INCLINAR = [-1]


def inclinar(p, angulo):
    """Inclina el marco y el panel `angulo` grados hacia abajo alrededor del eje de la
    bisagra. Si el marco subió en vez de bajar, se rehace con el giro contrario."""
    abajo = caja_cuerpo(p, "Marco_panel")[1]
    for _ in range(2):
        f = p.mover([p.cuerpo("Marco_panel"), p.cuerpo("Panel_ref")], punto=(0, Y_EJE, -YS_EJE),
                    giro=(SIGNO_INCLINAR[0] * angulo, 0, 0), nombre="Inclinar_marco")
        if caja_cuerpo(p, "Marco_panel")[1] < abajo - 1:
            return f
        borrar(p, f)
        SIGNO_INCLINAR[0] *= -1
    raise RuntimeError("no pude inclinar el marco")


def borrar(p, feat):
    p.limpiar()
    feat.Select2(False, 0)
    p.ext.DeleteSelection2(0)
    p.limpiar()


def caja_cuerpo(p, nombre):
    return [round(v * 1000, 2) for v in p.cuerpo(nombre).GetBodyBox()]


def ecuaciones(p):
    eq = T(call(p.doc, "GetEquationMgr"), "IEquationMgr")
    p.variable("Grosor_panel", GROSOR_PANEL)
    eq.Add2(-1, f'"D1@Paredes_marco" = "Grosor_panel" + {CEJA_T}', True)
    eq.Add2(-1, f'"D1@Plano_cejas" = "Grosor_panel" + {Y_FONDO_PANEL}', True)
    eq.Add2(-1, '"D1@Panel_referencia" = "Grosor_panel"', True)
    p.doc.ForceRebuild3(False)
    return eq


def probar_grosor(p, valor):
    """Cambia Grosor_panel, reconstruye y devuelve (cara del panel, volumen del marco)."""
    p.cambiar_variable("Grosor_panel", valor)
    return (caja_cuerpo(p, "Panel_ref")[4],
            round(p.cuerpo("Marco_panel").GetMassProperties(1.0)[3] * 1e9, 1))


def main():
    CAPTURAS.mkdir(exist_ok=True)
    STL.mkdir(exist_ok=True)
    sw = swlib.sw_app()
    swlib.cerrar_de_carpeta(sw, AQUI)
    p = swlib.Pieza(sw, NOMBRE)

    f_plato = tt.plato(p)
    tt.base(p)
    tt.costillas(p, f_plato)
    tt.seguro(p)
    tt.nombrar(p)
    print("turntable listo")
    soporte(p)
    print("soporte listo")
    marco(p)
    panel_ref(p)
    buje(p)
    print("marco y buje listos")
    caja_ref(p)
    largo = tornilleria(p)
    for nombre, (rgb, transp) in COLORES.items():
        p.color_cuerpo(p.cuerpo(nombre), rgb, transp)
    eq = ecuaciones(p)

    print(f"tornillo {largo:.2f} mm; cajas: tornillo {caja_cuerpo(p, 'Tornillo')}, "
          f"tuerca {caja_cuerpo(p, 'Tuerca')}, caja {caja_cuerpo(p, 'Caja_ref')}, tapa {caja_cuerpo(p, 'Tapa_ref')}")
    print(f"marco {caja_cuerpo(p, 'Marco_panel')}, soporte {caja_cuerpo(p, 'Soporte')}")
    print(f"Grosor_panel 3 -> 4 -> 3 mm (cara del panel, mm3 del marco): {probar_grosor(p, GROSOR_PANEL)}"
          f" -> {probar_grosor(p, 4.0)} -> {probar_grosor(p, GROSOR_PANEL)}")

    malos = revisar(p, PARES, "a 0°")
    for ang in (60, 90):
        f = inclinar(p, ang)
        print(f"  marco a {ang}°: {caja_cuerpo(p, 'Marco_panel')}")
        malos += revisar(p, [x for x in PARES if "Marco_panel" in x or "Panel_ref" in x], f"a {ang}°")
        if ang == 90:
            p.solo([b.Name for b in p.cuerpos()])
            p.captura(CAPTURAS / "modulo_90.bmp", vista="*Right")
        borrar(p, f)

    for b in p.cuerpos():
        vol = b.GetMassProperties(1.0)[3] * 1e6
        print(f"{b.Name:12s} vol={vol:5.1f} cm3")
    print("croquis sin definir:", p.sin_definir or "ninguno")

    # STL de lo nuevo, orientado para imprimir (el tornillo y la tuerca ya se copiaron). El
    # plato cambió (hexágono del buje): su STL va a turntable/stl, boca abajo como siempre.
    for nombre, stl, arriba in (("Soporte", STL / "soporte.stl", "+Y"),
                                ("Marco_panel", STL / "marco_panel.stl", "-X"),
                                ("Buje", STL / "buje.stl", "+Y"),
                                ("Plato_gira", tt.STL / "turntable_plato.STL", "-Y")):
        p.solo([nombre])
        p.exportar(stl)
        dims = swlib.girar_stl(stl, arriba)
        print(f"  STL {stl.stem:16s} {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm")

    todos = [b.Name for b in p.cuerpos()]
    p.solo(todos)
    inclinar(p, ANGULO_VISTA)
    ruta, err = p.guardar(AQUI)

    p.captura(CAPTURAS / "modulo_iso.bmp")
    p.captura(CAPTURAS / "modulo_lado.bmp", vista="*Right")
    p.solo([n for n in todos if n not in ("Caja_ref", "Tapa_ref")])
    p.captura(CAPTURAS / "modulo_sin_caja.bmp")
    p.solo(["Soporte", "Buje"])
    p.captura(CAPTURAS / "soporte.bmp")
    p.solo(["Marco_panel"])
    p.captura(CAPTURAS / "marco_frente.bmp", vista="*Right")
    p.doc.ShowNamedView2("*Isometric", -1)
    T(p.doc.ActiveView, "IModelView").RotateAboutCenter(math.pi, 0)
    call(p.doc, "ViewZoomtofit2")
    p.doc.SaveBMP(str(CAPTURAS / "marco_atras.bmp"), 0, 0)
    swlib.a_png(CAPTURAS / "marco_atras.bmp")
    p.solo(todos)
    p.doc.ShowNamedView2("*Isometric", -1)
    call(p.doc, "ViewZoomtofit2")
    p.doc.Save3(1, 0, 0)
    print(f"guardado {Path(ruta).name} err={err}; {'REVISAR CHOQUES' if malos else 'sin choques'}")


if __name__ == "__main__":
    main()
