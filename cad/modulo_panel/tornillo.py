"""Alarga el tornillo de perilla original (tablet_bolt.stl) sin tocar su rosca.

El tornillo está parado sobre Z: perilla abajo (z = 0) y rosca de paso 2 arriba. Entre
z ≈ 48 y z ≈ 76 el cuerpo es un cilindro liso cuyas caras van de punta a punta, así que
basta con subir `delta` mm todos los vértices que estén arriba de un plano a media altura:
el cilindro se estira y la perilla y la rosca quedan idénticas (la tuerca original sigue
sirviendo). El hilo de Ø0.4 por el eje (para que el slicer haga paredes adentro) se
estira igual.

Uso suelto:  python tornillo.py 123.2   -> stl/tornillo.stl para un agarre de 123.2 mm
"""
import math
import struct
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ORIGINAL = AQUI / "originales" / "tablet_bolt.stl"
TUERCA = AQUI / "originales" / "nut.stl"

LARGO_ORIGINAL = 100.63   # tornillo original
AGARRE_ORIGINAL = 90.0    # entre caras de afuera del stand original (asientos cónicos)
Z_CORTE = 60.0            # plano dentro del tramo liso: ahí no hay vértices


def leer_stl(ruta):
    datos = Path(ruta).read_bytes()
    n = struct.unpack_from("<I", datos, 80)[0]
    tris = []
    for i in range(n):
        v = struct.unpack_from("<12f", datos, 84 + 50 * i)
        tris.append([v[3:6], v[6:9], v[9:12]])
    return tris


def escribir_stl(ruta, tris, titulo=b"SIMON"):
    salida = bytearray(titulo.ljust(80, b" ")[:80])
    salida += struct.pack("<I", len(tris))
    for a, b, c in tris:
        u = [b[k] - a[k] for k in range(3)]
        w = [c[k] - a[k] for k in range(3)]
        nrm = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        largo = math.sqrt(sum(x * x for x in nrm)) or 1.0
        salida += struct.pack("<12fH", *[x / largo for x in nrm], *a, *b, *c, 0)
    Path(ruta).write_bytes(bytes(salida))


def alargar(origen, destino, delta, z_corte=Z_CORTE):
    """Sube `delta` mm todo lo que está arriba de z_corte. Devuelve el largo nuevo."""
    tris = leer_stl(origen)
    cerca = [p[2] for t in tris for p in t if abs(p[2] - z_corte) < 5]
    if cerca:
        raise ValueError(f"hay vértices a menos de 5 mm de z={z_corte}: el corte no cae en el tramo liso")
    nuevos = [[(x, y, z + delta if z > z_corte else z) for x, y, z in t] for t in tris]
    escribir_stl(destino, nuevos, b"SIMON tornillo de perilla alargado")
    return max(p[2] for t in nuevos for p in t)


def largo_para(agarre):
    """Largo del tornillo para apretar `agarre` mm entre las caras de afuera de las torres."""
    return LARGO_ORIGINAL + (agarre - AGARRE_ORIGINAL)


if __name__ == "__main__":
    agarre = float(sys.argv[1]) if len(sys.argv) > 1 else AGARRE_ORIGINAL
    (AQUI / "stl").mkdir(exist_ok=True)
    largo = alargar(ORIGINAL, AQUI / "stl" / "tornillo.stl", agarre - AGARRE_ORIGINAL)
    print(f"tornillo de {largo:.2f} mm para un agarre de {agarre} mm")
