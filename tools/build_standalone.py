"""Empaqueta la maqueta del dashboard en un solo HTML que se abre con doble clic.

La maqueta normal usa módulos ES e imágenes relativas, que los navegadores
bloquean al abrir un archivo local (file://). Este script junta todo el JS en
un solo bloque (esbuild), incrusta el CSS y la foto de fondo, y deja el
resultado en entrega/SIMON-dashboard-interactivo.html.

Uso (desde la raíz del repo, requiere Node.js):
    python tools/build_standalone.py
"""
import base64
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design"
OUT = ROOT / "entrega" / "SIMON-dashboard-interactivo.html"


def bundle_js() -> str:
    result = subprocess.run(
        "npx --yes esbuild js/app.js --bundle --format=iife --minify --target=es2020 --charset=utf8",
        cwd=DESIGN, capture_output=True, text=True, encoding="utf-8", shell=True, check=True,
    )
    return result.stdout


def main() -> None:
    photo = base64.b64encode((DESIGN / "assets" / "fondo-campo-solar.webp").read_bytes()).decode()
    css = "\n".join((DESIGN / "css" / name).read_text(encoding="utf-8") for name in ("maqueta.css", "vistas.css"))
    # La foto se usa en varias reglas: se declara una sola vez como variable para no duplicarla
    css = css.replace('url("../assets/fondo-campo-solar.webp")', "var(--photo)")
    css = f':root {{ --photo: url("data:image/webp;base64,{photo}"); }}\n' + css

    html = (DESIGN / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'\s*<link rel="stylesheet" href="css/[^"]+">', "", html)
    html = html.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)
    js = bundle_js().replace("</script", "<\\/script")
    html = html.replace('<script type="module" src="js/app.js"></script>', f"<script>\n{js}\n</script>", 1)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
