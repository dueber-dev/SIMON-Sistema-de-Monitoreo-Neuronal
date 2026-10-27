"""Mini librería para modelar en SolidWorks por su API COM desde Python.

Todas las medidas de esta librería están en mm; la API de SolidWorks usa metros,
así que aquí se convierte. Cada croquis queda acotado (anchos, altos, diámetros)
y cada operación con su profundidad, para que las piezas sean editables.

Convención de planos (la de SolidWorks):
  alzado  (Front, XY): croquis x = X, y = Y
  planta  (Top,   XZ): croquis x = X, y = -Z
  lateral (Right, YZ): croquis x = -Z, y = Y
La pieza "crece" en +Y (arriba).
"""
import atexit
import math
import struct
from pathlib import Path

import pythoncom
import win32com.client
from win32com.client import VARIANT, gencache

# Envoltorios tipados generados con makepy desde sldworks.tlb (ver README)
SL = gencache.GetModuleForTypelib("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 33, 0)


def T(obj, interfaz):
    """Vista tipada de un objeto COM (p. ej. T(doc, 'IPartDoc'))."""
    return getattr(SL, interfaz)(obj._oleobj_ if hasattr(obj, "_oleobj_") else obj)


def TF(obj):
    return None if obj is None else T(obj, "IFeature")


def TS(obj):
    return None if obj is None else T(obj, "ISketchSegment")


def call(obj, nombre, *args):
    """Invoca un miembro sin importar si pywin32 lo expone como método o como
    propiedad (en objetos dinámicos los métodos sin argumentos se evalúan solos)."""
    a = getattr(obj, nombre)
    if isinstance(a, win32com.client.CDispatch) or not callable(a):
        return a
    return a(*args)

M = 0.001  # mm -> m
NADA = None  # los envoltorios tipados aceptan None para objetos opcionales

# Constantes de la API (swconst)
END_BLIND, END_THROUGH_ALL, END_MIDPLANE = 0, 1, 6
REFPLANE_DISTANCE = 8
INPUT_DIM_ON_CREATE = 10


def sw_app():
    sw = SL.ISldWorks(win32com.client.Dispatch("SldWorks.Application")._oleobj_)
    sw.Visible = True
    # Sin diálogos al acotar mientras corre el script; al salir se deja como estaba,
    # para que al acotar a mano vuelva a abrirse la ventana de la medida.
    antes = sw.GetUserPreferenceToggle(INPUT_DIM_ON_CREATE)
    sw.SetUserPreferenceToggle(INPUT_DIM_ON_CREATE, False)
    atexit.register(sw.SetUserPreferenceToggle, INPUT_DIM_ON_CREATE, antes)
    return sw


def a_png(ruta_bmp):
    """Convierte la captura BMP de SolidWorks a PNG recortando el fondo sobrante."""
    from PIL import Image, ImageChops
    ruta_bmp = Path(ruta_bmp)
    im = Image.open(ruta_bmp).convert("RGB")
    fondo = Image.new("RGB", im.size, im.getpixel((5, 5)))
    caja = ImageChops.difference(im, fondo).convert("L").point(lambda v: 255 if v > 40 else 0).getbbox()
    if caja:
        m = 30
        im = im.crop((max(caja[0] - m, 0), max(caja[1] - m, 0),
                      min(caja[2] + m, im.width), min(caja[3] + m, im.height)))
    im.save(ruta_bmp.with_suffix(".png"))
    ruta_bmp.unlink()


def orientar_stl(ruta, boca_abajo):
    """SolidWorks exporta con Y arriba; los slicers esperan Z arriba. Gira la malla y
    la apoya en Z = 0. Con boca_abajo, la cara superior de la pieza queda en la cama.
    Devuelve las medidas (x, y, z) de la malla en mm."""
    datos = Path(ruta).read_bytes()
    n = struct.unpack_from("<I", datos, 80)[0]
    if boca_abajo:
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


def cerrar_de_carpeta(sw, carpeta):
    """Cierra solo los documentos abiertos que vivan en `carpeta` (para poder sobrescribirlos)."""
    carpeta = str(Path(carpeta).resolve()).lower()
    cerrados = []
    for _ in range(3):  # el ensamble mantiene piezas abiertas: varias pasadas
        docs = [T(d, "IModelDoc2") for d in (sw.GetDocuments() or [])]
        # primero ensambles (retienen sus piezas abiertas), luego piezas
        for d in sorted(docs, key=lambda d: -call(d, "GetType")):
            try:
                ruta = (call(d, "GetPathName") or "").lower()
                if ruta.startswith(carpeta):
                    sw.CloseDoc(call(d, "GetTitle"))
                    cerrados.append(ruta)
            except pythoncom.com_error:
                pass  # ya se cerró junto con su ensamble
    return cerrados


class Pieza:
    def __init__(self, sw, nombre):
        self.sw = sw
        self.nombre = nombre
        tpl = sw.GetUserPreferenceStringValue(8)
        self.doc = SL.IModelDoc2(sw.NewDocument(tpl, 0, 0, 0)._oleobj_)
        self.ext = T(self.doc.Extension, "IModelDocExtension")
        self.sk = T(self.doc.SketchManager, "ISketchManager")
        self.fm = T(self.doc.FeatureManager, "IFeatureManager")
        planos = []
        f = TF(call(self.doc, "FirstFeature"))
        while f is not None:
            if call(f, "GetTypeName2") == "RefPlane":
                planos.append(f)
            f = TF(call(f, "GetNextFeature"))
        self.alzado, self.planta, self.lateral = planos[:3]
        self._planos = {}
        self.sk.AddToDB = True
        self.sk.DisplayWhenAdded = False

    # ------------------------------------------------------------ selección
    def limpiar(self):
        self.doc.ClearSelection2(True)

    def sel_cara(self, x, y, z, append=False):
        """Selecciona la cara que pasa por el punto (mm, coords de pieza)."""
        ok = self.ext.SelectByID2("", "FACE", x * M, y * M, z * M, append, 0, NADA, 0)
        if not ok:
            raise RuntimeError(f"{self.nombre}: no hay cara en ({x}, {y}, {z})")

    def sel_arista(self, x, y, z, append=False):
        ok = self.ext.SelectByID2("", "EDGE", x * M, y * M, z * M, append, 1, NADA, 0)
        if not ok:
            raise RuntimeError(f"{self.nombre}: no hay arista en ({x}, {y}, {z})")

    def plano_desfasado(self, base, dist):
        """Plano paralelo a `base` a `dist` mm (negativo = lado opuesto a su normal).
        La normal del plano nuevo sigue apuntando igual que la de `base`."""
        clave = (base.Name, round(dist, 4))
        if clave in self._planos:
            return self._planos[clave]
        self.limpiar()
        base.Select2(False, 0)
        r = self.fm.InsertRefPlane(REFPLANE_DISTANCE | (256 if dist < 0 else 0), abs(dist) * M, 0, 0, 0, 0)
        if r is None:
            raise RuntimeError(f"{self.nombre}: no pude crear plano a {dist} de {base.Name}")
        f = TF(self.doc.FeatureByPositionReverse(0))
        f.Name = f"Plano_{base.Name}_{dist:+g}".replace(".", "_")
        self._planos[clave] = f
        self.limpiar()
        f.Select2(False, 0)
        call(self.doc, "BlankRefGeom")   # que no aparezca en pantalla ni en capturas
        self.limpiar()
        return f

    # ------------------------------------------------------------ croquis
    def croquis(self, plano=None, desfase=0.0, cara=None):
        """Abre un croquis en un plano de referencia (opcionalmente desfasado) o en una cara."""
        self.limpiar()
        if cara is not None:
            self.sel_cara(*cara)
        else:
            if desfase:
                plano = self.plano_desfasado(plano, desfase)
            self.limpiar()
            plano.Select2(False, 0)
        self.sk.InsertSketch(True)

    def _cota(self, seg, x, y):
        self.limpiar()
        seg.Select4(False, NADA)
        d = self.doc.AddDimension2(x * M, y * M, 0)
        self.limpiar()
        return d

    def rect(self, cx, cy, w, h, cotar=True):
        segs = self.sk.CreateCenterRectangle(cx * M, cy * M, 0, (cx + w / 2) * M, (cy + h / 2) * M, 0)
        if cotar and segs:
            lineas = [TS(s) for s in segs if s is not None]
            lineas = [s for s in lineas if call(s, "GetType") == 0][:4]
            # identificar una horizontal y una vertical
            hor = ver = None
            for s in lineas:
                ln = T(s, "ISketchLine")
                p0 = T(call(ln, "GetStartPoint2"), "ISketchPoint")
                p1 = T(call(ln, "GetEndPoint2"), "ISketchPoint")
                if abs(p0.Y - p1.Y) < 1e-9 and hor is None:
                    hor = s
                elif abs(p0.X - p1.X) < 1e-9 and ver is None:
                    ver = s
            if hor is not None:
                self._cota(hor, cx, cy + h / 2 + 4)
            if ver is not None:
                self._cota(ver, cx + w / 2 + 4, cy)
        return segs

    def ranura(self, cx, cy, largo, ancho, vertical=False, angulo=None):
        """Ranura recta (oblonga) centrada. `angulo` (grados desde el eje x del croquis)
        la inclina; si se da, manda sobre `vertical`."""
        if angulo is not None:
            a = math.radians(angulo)
            dx, dy = (largo - ancho) / 2 * math.cos(a), (largo - ancho) / 2 * math.sin(a)
            x1, y1, x2, y2 = cx - dx, cy - dy, cx + dx, cy + dy
        elif vertical:
            x1, y1, x2, y2 = cx, cy - (largo - ancho) / 2, cx, cy + (largo - ancho) / 2
        else:
            x1, y1, x2, y2 = cx - (largo - ancho) / 2, cy, cx + (largo - ancho) / 2, cy
        return self.sk.CreateSketchSlot(0, 0, ancho * M, x1 * M, y1 * M, 0, x2 * M, y2 * M, 0,
                                        0, 0, 0, 1, False)

    def circulo(self, cx, cy, d, cotar=True):
        c = TS(self.sk.CreateCircleByRadius(cx * M, cy * M, 0, d / 2 * M))
        if cotar and c is not None:
            self._cota(c, cx + d * 0.6, cy + d * 0.6)
        return c

    def linea(self, x1, y1, x2, y2):
        return TS(self.sk.CreateLine(x1 * M, y1 * M, 0, x2 * M, y2 * M, 0))

    def polilinea(self, pts, cerrar=True):
        segs = []
        pts = list(pts)
        if cerrar:
            pts = pts + [pts[0]]
        for (a, b), (c, d) in zip(pts, pts[1:]):
            segs.append(self.linea(a, b, c, d))
        return segs

    def arco(self, cx, cy, r, a0, a1):
        """Arco por centro, radio y ángulos en grados (antihorario)."""
        x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
        x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
        return self.sk.CreateArc(cx * M, cy * M, 0, x0 * M, y0 * M, 0, x1 * M, y1 * M, 0, 1)

    def rect_redondeado(self, cx, cy, w, h, r, cotar=True):
        """Rectángulo centrado con esquinas redondeadas de radio r (r=0 -> rect normal).
        Acota ancho, alto y radio para que se pueda editar en SolidWorks."""
        if r <= 0:
            return self.rect(cx, cy, w, h, cotar)
        x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
        abajo = self.linea(x0 + r, y0, x1 - r, y0)
        der = self.linea(x1, y0 + r, x1, y1 - r)
        arriba = self.linea(x1 - r, y1, x0 + r, y1)
        izq = self.linea(x0, y1 - r, x0, y0 + r)
        arcos = [TS(self.arco(x1 - r, y0 + r, r, -90, 0)), TS(self.arco(x1 - r, y1 - r, r, 0, 90)),
                 TS(self.arco(x0 + r, y1 - r, r, 90, 180)), TS(self.arco(x0 + r, y0 + r, r, 180, 270))]
        if cotar:
            for a, b, px, py in ((izq, der, cx, y1 + 5), (abajo, arriba, x1 + 5, cy)):
                self.limpiar()
                a.Select4(False, NADA)
                b.Select4(True, NADA)
                self.doc.AddDimension2(px * M, py * M, 0)
            self._cota(arcos[1], x1 + r, y1 + r)
            self.limpiar()
        return [abajo, der, arriba, izq] + arcos

    def texto(self, x, y, txt, alto, fuente="Arial Black"):
        """Texto de croquis (para grabar en bajo relieve), empezando en (x, y)."""
        st = self.doc.InsertSketchText(x * M, y * M, 0, txt, 0, 0, 0, 100, 100)
        if st is None:
            raise RuntimeError(f"{self.nombre}: no pude crear el texto {txt!r}")
        st = T(st, "ISketchText")
        tf = T(call(st, "GetTextFormat"), "ITextFormat")
        tf.CharHeight = alto * M
        tf.TypeFaceName = fuente
        st.SetTextFormat(False, tf)
        return st

    def hexagono(self, cx, cy, entre_caras):
        """Hexágono para alojar tuercas, con dos caras horizontales."""
        r = entre_caras / math.sqrt(3)
        pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
               for a in range(0, 360, 60)]
        return self.polilinea(pts)

    def ranura_arco(self, cx, cy, r, ancho, a0, a1):
        """Ranura curva centrada en el radio r entre los ángulos a0..a1 (grados)."""
        ri, re = r - ancho / 2, r + ancho / 2
        self.arco(cx, cy, re, a0, a1)
        self.arco(cx, cy, ri, a0, a1)
        for a, sentido in ((a1, 1), (a0, -1)):
            ex, ey = cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))
            # semicírculo de punta, por fuera del rango angular
            b0 = a if sentido > 0 else a + 180
            self.arco(ex, ey, ancho / 2, b0, b0 + 180)

    def sector(self, cx, cy, r, a0, a1):
        """Sector circular (abanico) cerrado."""
        x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
        x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
        self.linea(cx, cy, x0, y0)
        self.arco(cx, cy, r, a0, a1)
        self.linea(x1, y1, cx, cy)

    def linea_constructiva(self, x1, y1, x2, y2):
        l = self.linea(x1, y1, x2, y2)
        if l is not None:
            l.ConstructionGeometry = True
        return l

    def cerrar_croquis(self, nombre=None):
        self.sk.InsertSketch(True)
        f = TF(self.doc.FeatureByPositionReverse(0))
        if nombre and f is not None:
            f.Name = nombre
        return f

    # ------------------------------------------------------------ operaciones
    def _sel_croquis(self, croquis):
        self.limpiar()
        croquis.Select2(False, 0)

    def extruir(self, croquis, prof, nombre=None, sentido=1, medio=False, fusionar=True):
        """Extruye `prof` mm desde el plano del croquis; sentido=+1 a lo largo de su normal."""
        self._sel_croquis(croquis)
        t1 = END_MIDPLANE if medio else END_BLIND
        f = TF(self.fm.FeatureExtrusion3(True, False, sentido < 0, t1, END_BLIND,
                                         prof * M, 0.0, False, False, False, False,
                                         0, 0, False, False, False, False, fusionar, True, True,
                                         0, 0, False))
        if f is None:
            raise RuntimeError(f"{self.nombre}: falló extruir {nombre or croquis.Name}")
        if nombre:
            f.Name = nombre
        return f

    def cortar(self, croquis, prof=None, nombre=None, sentido=1, ambos=False, medio=False):
        """Corta `prof` mm (None = por todo). sentido=+1 a lo largo de la normal del plano.
        (En FeatureCut4 la dirección por defecto es la contraria a la de la extrusión.)"""
        self._sel_croquis(croquis)
        if medio:
            t1, d1 = END_MIDPLANE, prof
        elif prof is None:
            t1, d1 = END_THROUGH_ALL, 0.01
        else:
            t1, d1 = END_BLIND, prof
        t2 = END_THROUGH_ALL if ambos else END_BLIND
        f = TF(self.fm.FeatureCut4(not ambos, False, sentido > 0, t1, t2, d1 * M, 0.01 * M,
                                   False, False, False, False, 0, 0, False, False, False, False,
                                   False, True, True, True, True, False, 0, 0, False, False))
        if f is None:
            raise RuntimeError(f"{self.nombre}: falló cortar {nombre or croquis.Name}")
        if nombre:
            f.Name = nombre
        return f

    def revolucion(self, croquis, nombre=None, angulo=360.0, cortar=False, fusionar=True):
        """El croquis debe incluir una línea constructiva como eje (se selecciona sola)."""
        self._sel_croquis(croquis)
        f = TF(self.fm.FeatureRevolve2(True, True, False, cortar, False, False, 0, 0,
                                    math.radians(angulo), 0, False, False, 0, 0, 0, 0, 0,
                                    fusionar, True, True))
        if f is None:
            raise RuntimeError(f"{self.nombre}: falló revolución {nombre}")
        if nombre:
            f.Name = nombre
        return f

    # ------------------------------------------------------------ piezas multicuerpo
    # En una pieza con varios cuerpos, "fusionar" con selección automática también junta
    # cuerpos que solo están cerca (sin tocarse). Por eso ahí cada operación nueva nace
    # como cuerpo aparte (fusionar=False) y se suma a mano al cuerpo que le toca.
    def cuerpos_de(self, feat):
        """Cuerpos sólidos a los que pertenecen las caras de una operación (sin repetir;
        una operación con varios contornos sueltos deja varios cuerpos)."""
        vistos = {}
        for cara in feat.GetFaces() or []:
            b = T(T(cara, "IFace2").GetBody(), "IBody2")
            vistos.setdefault(b.Name, b)
        return list(vistos.values())

    def sumar(self, cuerpos, nombre=None):
        """Combinar (sumar) exactamente esos cuerpos."""
        herr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(cuerpos))
        f = TF(self.fm.InsertCombineFeature(15903, NADA, herr))  # 15903 = swBodyOperationType ADD
        if f is None:
            raise RuntimeError(f"{self.nombre}: falló combinar {nombre}")
        if nombre:
            f.Name = nombre
        return f

    def redondear(self, aristas, r, nombre=None):
        """aristas: lista de puntos (x, y, z) sobre las aristas."""
        self.limpiar()
        for i, p in enumerate(aristas):
            self.sel_arista(*p, append=i > 0)
        f = TF(self.fm.FeatureFillet3(195, r * M, 0, 0, 0, 0, 0, NADA, NADA, NADA, NADA, NADA, NADA, NADA))
        if f is not None and nombre:
            f.Name = nombre
        return f

    def chaflan_contorno(self, normal, nivel, d, nombre=None):
        """Chaflán a 45° de d mm en el contorno exterior de la cara plana con esa normal
        (p. ej. (0, -1, 0)) que está a `nivel` mm sobre su eje. No toca agujeros ni textos
        de esa cara. Se eligen las aristas por geometría, no por clic, así no depende de la vista."""
        eje = [abs(c) for c in normal].index(1)
        pd = T(self.doc, "IPartDoc")
        aristas = []
        for b in pd.GetBodies2(0, True) or []:
            for cara in T(b, "IBody2").GetFaces() or []:
                cara = T(cara, "IFace2")
                n = cara.Normal
                if any(abs(n[i] - normal[i]) > 1e-6 for i in range(3)):
                    continue
                caja = cara.GetBox()
                if abs(caja[eje] * 1000 - nivel) > 1e-3:
                    continue
                for lazo in cara.GetLoops() or []:
                    lazo = T(lazo, "ILoop2")
                    if call(lazo, "IsOuter"):
                        aristas += list(lazo.GetEdges() or [])
        if not aristas:
            raise RuntimeError(f"{self.nombre}: no encontré la cara {normal} a {nivel} mm")
        self.limpiar()
        for i, a in enumerate(aristas):
            T(a, "IEntity").Select4(i > 0, NADA)
        f = TF(self.fm.InsertFeatureChamfer(0, 1, d * M, math.radians(45), d * M, 0, 0, 0))
        if f is None:
            raise RuntimeError(f"{self.nombre}: falló el chaflán del contorno {normal}")
        if nombre:
            f.Name = nombre
        return f

    def chaflan(self, punto, d, nombre=None):
        """Chaflán a 45° de d mm sobre la arista que pasa por `punto`, propagado a las
        aristas tangentes (todo el contorno redondeado de una vez)."""
        self.limpiar()
        self.sel_arista(*punto)
        f = TF(self.fm.InsertFeatureChamfer(4, 1, d * M, math.radians(45), d * M, 0, 0, 0))  # 4 = propagar a tangentes
        if f is None:
            raise RuntimeError(f"{self.nombre}: falló chaflán en {punto}")
        if nombre:
            f.Name = nombre
        return f

    def patron_circular(self, feats, eje_feat, n, nombre=None):
        self.limpiar()
        for i, f in enumerate(feats):
            f.Select2(i > 0, 4)
        eje_feat.Select2(True, 1)
        p = TF(self.fm.FeatureCircularPattern5(n, 2 * math.pi, False, "NULL", False, True, False,
                                               False, False, False, 1, 0, "NULL", False))
        if p is not None and nombre:
            p.Name = nombre
        return p

    # ------------------------------------------------------------ variables globales
    def variable(self, nombre, valor_mm):
        eq = T(call(self.doc, "GetEquationMgr"), "IEquationMgr")
        eq.Add2(-1, f'"{nombre}" = {valor_mm}', True)

    def ligar(self, cota_nombre, variable):
        eq = T(call(self.doc, "GetEquationMgr"), "IEquationMgr")
        eq.Add2(-1, f'"{cota_nombre}" = "{variable}"', True)

    def color(self, r, g, b, brillo=0.3):
        """Color de la pieza (0-1). Solo apariencia; no afecta la geometría."""
        vals = [r, g, b, 1.0, 1.0, brillo, 0.3, 0.0, 0.0]
        self.doc.MaterialPropertyValues = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, vals)

    # ------------------------------------------------------------ salida
    def guardar(self, carpeta):
        carpeta = Path(carpeta)
        self.doc.ForceRebuild3(False)
        ruta = str(carpeta / f"{self.nombre}.SLDPRT")
        err = self.doc.SaveAs3(ruta, 0, 1)  # 1 = silencioso (2 sería "guardar copia")
        return ruta, err

    def captura(self, ruta, vista="*Isometric", ancho=1200, alto=900):
        self.doc.ShowNamedView2(vista, -1)
        call(self.doc, "ViewZoomtofit2")
        self.doc.SaveBMP(str(ruta), 0, 0)
        a_png(ruta)

    def exportar(self, ruta):
        """STL o STEP según la extensión."""
        return self.doc.SaveAs3(str(ruta), 0, 2)

    def volumen_cm3(self):
        mp = call(self.ext, "CreateMassProperty")
        mp = T(mp, "IMassProperty") if mp is not None else None
        return mp.Volume * 1e6 if mp is not None else None

    def cerrar(self):
        self.sw.CloseDoc(call(self.doc, "GetTitle"))
