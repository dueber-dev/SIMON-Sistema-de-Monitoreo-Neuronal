"""Genera el documento de entrega: un solo HTML con las capturas y el dashboard interactivo.

Usa las capturas de entrega/capturas/*.webp (ver tools/capturas.mjs) y el dashboard
empaquetado por tools/build_standalone.py, que se vuelve a generar aquí.

Uso (desde la raíz del repo):
    python tools/build_entrega.py
"""
import base64
import datetime
import pathlib
import re

import build_standalone

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "tools" / "entrega_template.html"
SHOTS = ROOT / "entrega" / "capturas"
OUT = ROOT / "entrega" / "SIMON-entrega-dashboard.html"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
OK = ('<span class="ok"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
      'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m8.5 12 2.5 2.5 4.5-5"/></svg>Cumple</span>')
WARN = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>')


def data_uri(name: str) -> str:
    return "data:image/webp;base64," + base64.b64encode((SHOTS / f"{name}.webp").read_bytes()).decode()


def main() -> None:
    build_standalone.main()
    html = TEMPLATE.read_text(encoding="utf-8")
    hoy = datetime.date.today()
    html = html.replace("{{fecha}}", f"{hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}")
    html = html.replace("{{ok}}", OK).replace("{{warn}}", WARN)
    html = re.sub(r"\{\{img:([\w-]+)\}\}", lambda m: data_uri(m.group(1)), html)
    dashboard = build_standalone.OUT.read_bytes()
    html = html.replace("{{dashboard_b64}}", base64.b64encode(dashboard).decode())
    missing = re.findall(r"\{\{[^}]+\}\}", html)
    assert not missing, f"Marcadores sin reemplazar: {missing}"
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
