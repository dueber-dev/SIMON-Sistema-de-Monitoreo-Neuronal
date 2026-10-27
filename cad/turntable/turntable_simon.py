"""Turntable (base giratoria) de SIMON, inspirado en el LEGO Turntable 4x4.

Una sola pieza de SolidWorks con tres cuerpos separados (no se fusionan):
- Base_fija:  disco de Ø100 que va sobre la mesa, con el núcleo del mecanismo al centro.
- Plato_gira: disco de Ø100 con falda. Gira sobre la base y se encaja a presión con 8 dedos.
- Seguro:     pasador que corre en un canal de la base y traba el plato en una muesca.

Sin balero: el plato desliza sobre la base por el borde de su falda (plástico contra
plástico, en el diámetro más grande posible, así no cabecea). Los dedos centran el plato y
lo retienen; dos de ellos llevan una costilla que cae en las 24 ranuras del núcleo: un clic
cada 15°. Las 24 muescas de la falda coinciden con esos clics, así el seguro entra en
cualquier posición.

Corre:  python turntable_simon.py
Genera: turntable_simon.SLDPRT, stl/ (un STL por cuerpo, ya orientado) y capturas/.

Coordenadas (las de SolidWorks): Y arriba. Croquis en planta: (x, y) = (X, -Z); en alzado:
(x, y) = (X, Y); en lateral: (x, y) = (-Z, Y). El seguro está sobre +X.

Orden de modelado: primero el plato (mientras es el único cuerpo, sus operaciones se
fusionan solas), después la base y al final el seguro. Desde que hay dos cuerpos, cada
operación que agrega material nace como cuerpo aparte y se suma a mano (Combinar) al
cuerpo que le toca: la fusión automática de SolidWorks juntaría cuerpos que solo están
cerca. Los cortes nunca alcanzan a los otros cuerpos (siempre queda una holgura).
"""
import math
import sys
from pathlib import Path

import pythoncom
from win32com.client import VARIANT

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import swlib  # noqa: E402
from swlib import T, call  # noqa: E402

CAPTURAS = AQUI / "capturas"
STL = AQUI / "stl"
NOMBRE = "turntable_simon"

# ------------------------------------------------------------------ medidas (mm)
R_EXT = 50.0                    # base y plato de Ø100
BASE_T = 4.0                    # espesor de la base
PLATO_T = 3.0                   # espesor del plato
Y_PLATO = 16.0                  # cara inferior del plato: la falda mide Y_PLATO - BASE_T = 12
FALDA_RI = 47.5                 # falda de 2.5 de pared, como la caja
R_CABLES = 12.0                 # paso de cables de Ø24 por el centro (cabe un conector USB)

# Núcleo (en la base) y dedos (en el plato): la "rueda" del mecanismo, Ø49
NUCLEO_RI, NUCLEO_R = 16.0, 23.0      # tubo del núcleo
CUELLO_R, Y_CUELLO = 21.5, 5.0        # garganta bajo el núcleo, donde se enganchan los dedos
Y_NUCLEO = Y_PLATO - 0.4              # tope del núcleo (no toca el plato)
HOLG = 0.3                            # holgura entre lo que se mueve
DEDO_T = 1.2                          # dedos flexibles (~3 líneas de 0.42)
GANCHO = 0.7                          # lo que el gancho se mete bajo el núcleo
Y_PIE = BASE_T + 0.5                  # pie de los dedos (no roza la base)
N_DEDOS, DEDO_ANG = 8, 24.0           # 8 dedos de 24° (~10 mm de ancho)
ESPIGA_R, ESPIGA_L = NUCLEO_RI - 0.25, 6.0   # tubo del plato que lo centra dentro del núcleo

# Clics cada 15°: 24 ranuras en V en el núcleo y una costilla en los dedos de 90° y 270°
N_CLICS = 24
RANURA_P = 0.5                        # profundidad de las ranuras del núcleo
COSTILLA = 0.3                        # lo que la costilla entra en el núcleo (lo que flexiona el dedo)
COSTILLA_H = 2.5

# Seguro: 24 muescas en el borde de la falda y un pasador en cola de milano en la base
MUESCA_W, MUESCA_H = 3.2, 3.0
CANAL_W, CANAL_P = 8.0, 2.0           # ancho abajo y profundidad del canal
CANAL_X0 = 37.3                       # fondo del canal (tope del seguro al trabarlo)
COLA = math.tan(math.radians(30))     # paredes de la cola de milano a 30° de la vertical
HOLG_SEG = 0.2
SALE = 1.8                            # lo que el seguro sobresale del borde, para jalarlo
DIENTE_W, DIENTE_L = 2.6, 4.5

CHAFLAN = 0.6                         # bordes que tocan la cama (evita la "pata de elefante")


# ------------------------------------------------------------------ croquis auxiliares
def _polar(r, t, ang):
    """Punto a r del centro y t de lado, en la dirección `ang` (grados)."""
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    return r * c - t * s, r * s + t * c


def rect_radial(p, ang, r0, r1, ancho):
    p.polilinea([_polar(r, t, ang) for r, t in ((r0, -ancho / 2), (r1, -ancho / 2),
                                                 (r1, ancho / 2), (r0, ancho / 2))])


def triangulo_v(p, ang, r_punta, r_base):
    """Triángulo en V a 90° con la punta hacia el centro (ranura o costilla de clic)."""
    m = r_base - r_punta
    p.polilinea([_polar(r_punta, 0, ang), _polar(r_base, -m, ang), _polar(r_base, m, ang)])


def sector_anular(p, ri, re, a0, a1):
    p.arco(0, 0, re, a0, a1)
    p.arco(0, 0, ri, a0, a1)
    for a in (a0, a1):
        p.linea(*_polar(ri, 0, a), *_polar(re, 0, a))


# ------------------------------------------------------------------ cuerpos
def plato(p):
    """Plato que gira. Se modela primero, mientras es el único cuerpo."""
    p.croquis(p.planta, Y_PLATO); p.circulo(0, 0, 2 * R_EXT)
    s = p.cerrar_croquis("Croquis_plato")
    f_plato = p.extruir(s, PLATO_T, "Plato")

    # Falda: el plato apoya en la base por su borde (Ø100 sobre Ø100, no cabecea)
    p.croquis(p.planta, Y_PLATO); p.circulo(0, 0, 2 * R_EXT, cotar=False); p.circulo(0, 0, 2 * FALDA_RI)
    s = p.cerrar_croquis("Croquis_falda")
    p.extruir(s, Y_PLATO - BASE_T, "Falda", sentido=-1)

    # Dedos: anillo con gancho al pie, revolucionado y luego partido en 8. La cara de
    # enganche es paralela al chaflán del núcleo y queda HOLG más abajo.
    punta = NUCLEO_R - GANCHO
    dedo_ri, dedo_re = NUCLEO_R + HOLG, NUCLEO_R + HOLG + DEDO_T
    enganche = lambda r: r - CUELLO_R + Y_CUELLO - HOLG
    p.croquis(p.alzado)
    p.linea_constructiva(0, 0, 0, 20)
    p.polilinea([(dedo_ri, Y_PLATO + 0.5), (dedo_re, Y_PLATO + 0.5), (dedo_re, Y_PIE),
                 (punta + 0.7, Y_PIE), (punta, Y_PIE + 0.7), (punta, enganche(punta)),
                 (dedo_ri, enganche(dedo_ri))])
    s = p.cerrar_croquis("Croquis_dedos")
    p.revolucion(s, "Anillo_dedos")

    p.croquis(p.planta, Y_PLATO); p.circulo(0, 0, 2 * ESPIGA_R); p.circulo(0, 0, 2 * R_CABLES, cotar=False)
    s = p.cerrar_croquis("Croquis_espiga")
    p.extruir(s, ESPIGA_L, "Espiga_centrado", sentido=-1)

    p.croquis(p.planta); p.circulo(0, 0, 2 * R_CABLES)
    s = p.cerrar_croquis("Croquis_paso_cables")
    p.cortar(s, None, "Paso_cables", ambos=True)

    paso = 360 / N_DEDOS
    p.croquis(p.planta, BASE_T)
    for k in range(N_DEDOS):
        a0 = k * paso + DEDO_ANG / 2
        sector_anular(p, punta - 0.4, dedo_re + 0.5, a0, a0 + paso - DEDO_ANG)
    s = p.cerrar_croquis("Croquis_separar_dedos")
    p.cortar(s, Y_PLATO - BASE_T, "Separar_dedos")

    # Muescas del seguro, una cada 15° (las mismas posiciones que los clics)
    p.croquis(p.planta, BASE_T)
    for k in range(N_CLICS):
        rect_radial(p, k * 360 / N_CLICS, FALDA_RI - 1, R_EXT + 1, MUESCA_W)
    s = p.cerrar_croquis("Croquis_muescas")
    p.cortar(s, MUESCA_H, "Muescas_seguro")

    p.chaflan_contorno((0, 1, 0), Y_PLATO + PLATO_T, CHAFLAN, "Chaflan_cara_superior")
    return f_plato


def base(p):
    p.croquis(p.planta); p.circulo(0, 0, 2 * R_EXT)
    s = p.cerrar_croquis("Croquis_base")
    f_base = p.extruir(s, BASE_T, "Base", fusionar=False)

    # Núcleo: tubo con un chaflán a 45° abajo (se imprime sin soporte) bajo el que se
    # enganchan los dedos, y un chaflán arriba para que los dedos entren al encajarlo.
    p.croquis(p.alzado)
    p.linea_constructiva(0, 0, 0, 20)
    p.polilinea([(NUCLEO_RI, BASE_T - 0.5), (CUELLO_R, BASE_T - 0.5), (CUELLO_R, Y_CUELLO),
                 (NUCLEO_R, Y_CUELLO + NUCLEO_R - CUELLO_R), (NUCLEO_R, Y_NUCLEO - 1),
                 (NUCLEO_R - 1, Y_NUCLEO), (NUCLEO_RI, Y_NUCLEO)])
    s = p.cerrar_croquis("Croquis_nucleo")
    f_nucleo = p.revolucion(s, "Nucleo", fusionar=False)
    p.sumar(p.cuerpos_de(f_base) + p.cuerpos_de(f_nucleo), "Sumar_nucleo_a_base")

    p.croquis(p.planta, Y_NUCLEO)
    for k in range(N_CLICS):
        triangulo_v(p, k * 360 / N_CLICS, NUCLEO_R - RANURA_P, NUCLEO_R + 0.2)
    s = p.cerrar_croquis("Croquis_ranuras_clic")
    p.cortar(s, Y_NUCLEO - (Y_CUELLO + NUCLEO_R - CUELLO_R), "Ranuras_clic", sentido=-1)

    p.croquis(p.planta); p.circulo(0, 0, 2 * R_CABLES)
    s = p.cerrar_croquis("Croquis_paso_cables_base")
    p.cortar(s, None, "Paso_cables_base", ambos=True)

    # Canal en cola de milano para el seguro, abierto hacia el borde (+X)
    w0, w1 = CANAL_W / 2, CANAL_W / 2 - CANAL_P * COLA
    y0 = BASE_T - CANAL_P
    p.croquis(p.lateral, CANAL_X0)
    p.polilinea([(-w0, y0), (w0, y0), (w1, BASE_T), (-w1, BASE_T)])
    s = p.cerrar_croquis("Croquis_canal_seguro")
    p.cortar(s, None, "Canal_seguro")

    p.chaflan_contorno((0, -1, 0), 0.0, CHAFLAN, "Chaflan_base")


def costillas(p, f_plato):
    """Costillas de clic en los dedos de 90° y 270° (del plato). Van después de las
    ranuras del núcleo, porque caen dentro de ellas."""
    y0 = Y_CUELLO + NUCLEO_R - CUELLO_R + HOLG
    p.croquis(p.planta, y0)
    for a in (90, 270):
        triangulo_v(p, a, NUCLEO_R - COSTILLA, NUCLEO_R + HOLG + 0.1)
    s = p.cerrar_croquis("Croquis_costillas_clic")
    f = p.extruir(s, COSTILLA_H, "Costillas_clic", fusionar=False)
    p.sumar(p.cuerpos_de(f_plato) + p.cuerpos_de(f), "Sumar_costillas_a_plato")


def seguro(p):
    """Pasador del seguro, dibujado trabado (metido hasta 0.2 mm del fondo del canal)."""
    y0 = BASE_T - CANAL_P
    ys0, ys1 = y0 + 0.1, BASE_T - 0.1
    medio = lambda y: CANAL_W / 2 - (y - y0) * COLA - HOLG_SEG / math.cos(math.radians(30))
    x0 = CANAL_X0 + HOLG_SEG
    p.croquis(p.lateral, x0)
    p.polilinea([(-medio(ys0), ys0), (medio(ys0), ys0), (medio(ys1), ys1), (-medio(ys1), ys1)])
    s = p.cerrar_croquis("Croquis_seguro")
    f_pasador = p.extruir(s, R_EXT + SALE - x0, "Pasador_seguro", fusionar=False)

    # Diente: atraviesa la muesca de la falda y sobresale SALE mm para jalarlo
    p.croquis(p.planta, ys1)
    p.rect(R_EXT + SALE - DIENTE_L / 2, 0, DIENTE_L, DIENTE_W)
    s = p.cerrar_croquis("Croquis_diente")
    f_diente = p.extruir(s, BASE_T + MUESCA_H - 0.5 - ys1, "Diente_seguro", fusionar=False)
    p.sumar(p.cuerpos_de(f_pasador) + p.cuerpos_de(f_diente), "Sumar_diente_a_seguro")


# ------------------------------------------------------------------ cuerpos: nombre, color, salida
COLORES = {"Base_fija": (0.93, 0.93, 0.92), "Plato_gira": (0.16, 0.17, 0.19),
           "Seguro": (0.95, 0.45, 0.10)}


def cuerpos(p):
    pd = T(p.doc, "IPartDoc")
    return [T(b, "IBody2") for b in (pd.GetBodies2(0, False) or [])]


def nombrar(p):
    """Nombra y colorea cada cuerpo según dónde está."""
    for b in cuerpos(p):
        caja = [v * 1000 for v in b.GetBodyBox()]
        if caja[4] > Y_PLATO + 1:
            nombre = "Plato_gira"
        elif caja[3] > R_EXT + 1:
            nombre = "Seguro"
        else:
            nombre = "Base_fija"
        b.Name = nombre
        b.MaterialPropertyValues2 = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                                            [*COLORES[nombre], 1.0, 1.0, 0.3, 0.3, 0.0, 0.0])


def solo(p, nombres):
    """Deja visibles solo los cuerpos con esos nombres."""
    for b in cuerpos(p):
        b.HideBody(b.Name not in nombres)
    p.doc.GraphicsRedraw2()


def main():
    CAPTURAS.mkdir(exist_ok=True)
    STL.mkdir(exist_ok=True)
    sw = swlib.sw_app()
    swlib.cerrar_de_carpeta(sw, AQUI)
    p = swlib.Pieza(sw, NOMBRE)
    f_plato = plato(p)
    base(p)
    costillas(p, f_plato)
    seguro(p)
    nombrar(p)
    ruta, err = p.guardar(AQUI)

    todos = [b.Name for b in cuerpos(p)]
    for b in cuerpos(p):
        vol = b.GetMassProperties(1.0)[3] * 1e6
        print(f"{b.Name:12s} vol={vol:5.1f} cm3 (~{vol * 1.24:4.0f} g PLA macizo)")

    # Un STL por cuerpo, orientado para imprimir: el plato boca abajo (cara de arriba en la cama)
    for nombre, archivo, boca_abajo in (("Base_fija", "turntable_base", False),
                                        ("Plato_gira", "turntable_plato", True),
                                        ("Seguro", "turntable_seguro", False)):
        solo(p, [nombre])
        stl = STL / f"{archivo}.stl"
        p.exportar(stl)
        dims = swlib.orientar_stl(stl, boca_abajo)
        print(f"  STL {archivo:18s} {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm")

    solo(p, todos)
    p.captura(CAPTURAS / "turntable_iso.bmp")
    solo(p, ["Base_fija", "Seguro"])
    p.captura(CAPTURAS / "base_y_seguro.bmp")
    solo(p, ["Plato_gira"])
    p.doc.ShowNamedView2("*Isometric", -1)
    T(p.doc.ActiveView, "IModelView").RotateAboutCenter(math.pi, 0)
    call(p.doc, "ViewZoomtofit2")
    p.doc.SaveBMP(str(CAPTURAS / "plato_abajo.bmp"), 0, 0)
    swlib.a_png(CAPTURAS / "plato_abajo.bmp")
    solo(p, todos)

    # Corte por la mitad (solo para la captura; el archivo ya quedó guardado sin él)
    p.croquis(p.planta); p.rect(0, -60, 140, 120, cotar=False)
    s = p.cerrar_croquis("Croquis_corte_vista")
    p.cortar(s, None, "Corte_vista", ambos=True)
    p.captura(CAPTURAS / "corte_iso.bmp")
    p.captura(CAPTURAS / "corte_frente.bmp", vista="*Front")
    p.cerrar()
    sw.OpenDoc(ruta, 1)
    print(f"guardado {Path(ruta).name} err={err}; cuerpos: {', '.join(todos)}")


if __name__ == "__main__":
    main()
