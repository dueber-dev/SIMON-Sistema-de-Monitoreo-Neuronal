"""Arma el ensamble SIMON_estacion.SLDASM con las piezas de modelo.py.

Uso:  python ensamble.py [angulo_panel]      (por defecto 30°)

Cada pieza se ubica con una transformación (rotación + traslación) y queda fija.
Para mover el panel en SolidWorks: liberar (Float) el marco y su perilla.
"""
import math
import sys
from pathlib import Path

import pythoncom
from win32com.client import VARIANT

import modelo as m
import swlib
from swlib import M, T, call

CAD = m.SALIDA


def matriz(ejes, t):
    """ejes = imágenes de los ejes locales X, Y, Z (filas); t en mm."""
    (a, b, c), (d, e, f), (g, h, i) = ejes
    datos = [a, b, c, d, e, f, g, h, i, t[0] * M, t[1] * M, t[2] * M, 1.0, 0.0, 0.0, 0.0]
    return datos


def rot_x(th):
    """Gira alrededor de X llevando +Z hacia +Y (lo que hace el panel al levantarse)."""
    c, s = math.cos(th), math.sin(th)
    return [(1, 0, 0), (0, c, -s), (0, s, c)]


def rot_y_hacia(dx, dz):
    """Gira alrededor de Y para que el +Z local apunte a (dx, 0, dz)."""
    n = math.hypot(dx, dz)
    a, b = dx / n, dz / n
    return [(b, 0, -a), (0, 1, 0), (a, 0, b)]


def componer(R1, R2):
    """Ejes de R2 expresados en el marco R1 (R2 se aplica primero, luego R1)."""
    return [tuple(sum(R2[i][k] * R1[k][j] for k in range(3)) for j in range(3)) for i in range(3)]


def aplicar(R, t, p):
    """Lleva el punto p (coords locales) al ensamble con rotación R y traslación t."""
    return tuple(t[j] + sum(p[k] * R[k][j] for k in range(3)) for j in range(3))


I = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]


def main(angulo=30.0):
    th = math.radians(angulo)
    sw = swlib.sw_app()
    swlib.cerrar_de_carpeta(sw, CAD)
    mu = T(sw.GetMathUtility(), "IMathUtility")
    tpl = sw.GetUserPreferenceStringValue(9)
    doc = swlib.SL.IModelDoc2(sw.NewDocument(tpl, 0, 0, 0)._oleobj_)
    asm = T(doc, "IAssemblyDoc")

    abiertos = {}

    def poner(nombre_archivo, R, t):
        ruta = str(CAD / f"{nombre_archivo}.SLDPRT")
        if ruta not in abiertos:
            abiertos[ruta] = sw.OpenDoc(ruta, 1)
        comp = asm.AddComponent5(ruta, 0, "", False, "", 0, 0, 0)
        comp = T(comp, "IComponent2")
        xf = mu.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, matriz(R, t)))
        comp.Transform2 = xf
        b = comp.GetBox(False, False)
        print(f"  {nombre_archivo:16s}", [round(v * 1000) for v in b] if b else "SIN CAJA")
        return comp

    caja_z = m.BASE_Z0 + 2 + m.CAJA_W / 2
    comps = []
    comps.append(poner("base_y_torres", I, (0, 0, 0)))
    comps.append(poner("caja_pcb", I, (0, m.BASE_T, caja_z)))
    comps.append(poner("ref_pcb_simon", I, (0, m.BASE_T + m.PARED + m.PCB_ALTO, caja_z)))
    comps.append(poner("tapa_caja", I, (0, m.BASE_T + m.CAJA_H, caja_z)))

    # Panel y su marco, girados alrededor del eje del pivote
    Rp, tp = rot_x(th), (0, m.PIVOTE_Y, 0)
    comps.append(poner("marco_panel", Rp, tp))
    centro_panel = (0, 8.0, m.MARCO_Z0 + m.MARCO_BORDE + m.HOLG + m.PANEL / 2)
    comps.append(poner("ref_panel_solar", Rp, aplicar(Rp, tp, centro_panel)))

    # Perilla de bloqueo sobre el abanico (eje local Y -> -X del ensamble)
    x_cara = -(m.X_TORRE_INT + m.TORRE_T)
    R_per = [(0, 1, 0), (-1, 0, 0), (0, 0, 1)]
    comps.append(poner("perilla_M4", R_per,
                       (x_cara - 2, m.PIVOTE_Y + m.ARCO_R * math.sin(th), m.ARCO_R * math.cos(th))))

    # Mástil, brazo y base de la webcam
    y_mastil = m.BASE_T + 25 - 22
    comps.append(poner("mastil_tubo", I, (m.MASTIL_X, y_mastil, m.MASTIL_Z)))
    objetivo_z = centro_panel[2]
    Rb = rot_y_hacia(0 - m.MASTIL_X, objetivo_z - m.MASTIL_Z)
    tb = (m.MASTIL_X, y_mastil + m.MASTIL_L - 27, m.MASTIL_Z)
    comps.append(poner("brazo_camara", Rb, tb))
    bisagra_local = (0, 21, m.BRAZO_L + 6)
    tw = aplicar(Rb, tb, bisagra_local)
    Rw = componer(Rb, rot_x(-math.radians(70)))          # la placa baja 70° hacia el panel
    comps.append(poner("base_webcam", Rw, tw))
    R_per2 = componer(Rb, [(0, 1, 0), (1, 0, 0), (0, 0, -1)])
    comps.append(poner("perilla_M4", R_per2, aplicar(Rb, tb, (8 + 2, 21, m.BRAZO_L + 6))))

    # Todo fijo en su lugar
    doc.ClearSelection2(True)
    for c in comps:
        c.Select4(True, None, False)
    asm.FixComponent()
    doc.ClearSelection2(True)
    doc.ForceRebuild3(False)

    ruta = str(CAD / "SIMON_estacion.SLDASM")
    err = doc.SaveAs3(ruta, 0, 1)
    m.CAPTURAS.mkdir(exist_ok=True)
    for vista, archivo in (("*Isometric", "ensamble_iso"), ("*Right", "ensamble_lateral"),
                           ("*Front", "ensamble_frente"), ("*Top", "ensamble_planta")):
        doc.ShowNamedView2(vista, -1)
        call(doc, "ViewZoomtofit2")
        doc.SaveBMP(str(m.CAPTURAS / f"{archivo}.bmp"), 0, 0)
        swlib.a_png(m.CAPTURAS / f"{archivo}.bmp")
    print("ensamble guardado", ruta, "err", err)
    print("STEP", doc.SaveAs3(str(m.AQUI / "SIMON_estacion.STEP"), 0, 2))
    return doc


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 30.0)
