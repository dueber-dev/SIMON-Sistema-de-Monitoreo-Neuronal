"""Servidor local de SIMON: el modelo corre completo en tu computadora.

    python ml/servidor_local.py            -> abre http://localhost:8790/simon/

Qué hace:
- Sirve la dashboard (carpeta design/) en /simon/ y reenvía /simon/api/* a la nube
  (dueber.dev), así la dashboard ve las mismas lecturas en vivo que la versión web.
- Descarga TODAS las sesiones de la nube, entrena el modelo con toda esa data y
  responde predicciones en /simon/api/local/predecir.
- /simon/api/local/reentrenar vuelve a bajar las sesiones (incluida la que está en
  curso) y reentrena. Es lo que hace el botón «Reentrenar» de la dashboard.
- /simon/api/local/pronostico pide el pronóstico del clima (Open-Meteo, sin clave)
  para los próximos días y lo pasa por el modelo: potencia y eficiencia predichas.

Modelo: gradient boosting (HistGradientBoostingRegressor), entradas = luz de la LDR,
temperatura del panel, hora (seno y coseno) y ángulo. Salida = potencia del panel
limpio en mW. Se compara con la fórmula física k·G·(1+γΔT) dejando fuera una
sesión real a la vez (validación con datos no usados en el ajuste).
Solo usa la librería estándar + numpy, pandas y scikit-learn.
"""
import json
import mimetypes
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from solar import g_desde_ldr, ldr_pct, LAT, LON   # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DISENO = RAIZ / 'design'
CACHE = RAIZ / 'datos' / 'reales'
NUBE = 'https://dueber.dev/simon/api/'
PUERTO = 8790
X_COLS = ['Luz_Pct', 'Temperatura_C', 'hora_sin', 'hora_cos', 'angulo']
ANGULO = 50
AREA_M2 = 110e-4                 # 110 cm²
CALENTAMIENTO = 0.0275           # °C por W/m² (ml/calibrar.py, sesión 35)
MIN_LECTURAS = 120               # sesiones más cortas son pruebas de conexión
EXCLUIR = ('polvo', 'sombra', 'sucio')   # el modelo aprende el panel LIMPIO


def bajar(ruta, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(NUBE + ruta, headers={'User-Agent': 'simon-local'}), timeout=timeout) as r:
        return json.loads(r.read())


def features(ts_ms, luz, t):
    h = ((np.asarray(ts_ms, float) / 3.6e6 - 6) % 24)          # hora de El Salvador
    return pd.DataFrame({'Luz_Pct': luz, 'Temperatura_C': t, 'hora_sin': np.sin(2 * np.pi * h / 24),
                         'hora_cos': np.cos(2 * np.pi * h / 24), 'angulo': ANGULO})


class Fisico:
    """Referencia física: P = k·G·(1 + γ·(T − 25)), G estimada con la LDR."""
    def fit(self, X, y):
        g = g_desde_ldr(X.Luz_Pct.values)
        A = np.c_[g, g * (X.Temperatura_C.values - 25)]
        self.c, *_ = np.linalg.lstsq(A, np.asarray(y), rcond=None)
        return self

    def predict(self, X):
        g = g_desde_ldr(X.Luz_Pct.values)
        return np.maximum(np.c_[g, g * (X.Temperatura_C.values - 25)] @ self.c, 0)


def nuevo_gb():
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, random_state=0)


def metricas(y, p):
    m = y > 50
    return {'MAE_mW': round(float(mean_absolute_error(y, p)), 2), 'RMSE_mW': round(float(mean_squared_error(y, p) ** 0.5), 2),
            'R2': round(float(r2_score(y, p)), 3),
            'MAPE_%': round(float(np.mean(np.abs((y[m] - p[m]) / y[m])) * 100), 1) if m.any() else None}


class Modelo:
    def __init__(self):
        self.lock = threading.Lock()
        self.gb = None
        self.info = {'listo': False, 'estado': 'sin entrenar'}

    def datos(self, refrescar_ultimas=True):
        """Todas las sesiones de la nube, promediadas a 1 minuto."""
        lista = bajar('sesiones')
        ultimas = {s['id'] for s in sorted(lista, key=lambda s: -s['fin'])[:2]}
        tablas, usadas = [], []
        for s in lista:
            if s['n'] < MIN_LECTURAS or any(w in (s.get('nombre') or '').lower() for w in EXCLUIR):
                continue
            f = CACHE / f"sesion_{s['id']}.json"
            if not f.exists() or (refrescar_ultimas and (s['id'] in ultimas or s.get('vivo'))):
                f.write_text(json.dumps(bajar(f"sesiones/{s['id']}", timeout=60)))
            filas = json.loads(f.read_text()).get('filas') or []
            if not filas:
                continue
            raw = pd.DataFrame(filas, columns=['ts', 'V', 'I', 'P', 'T', 'Luz'])
            raw['t'] = pd.to_datetime(raw.ts, unit='ms')
            m = raw.set_index('t').resample('1min')
            df = m.mean().assign(n=m.size()).dropna()
            df = df[df.n >= 6]
            # Fuera: panel desconectado (hay luz pero 0 mW) y noche
            df = df[~((df.P < 0.5) & (df.Luz > 60)) & (df.Luz > 20)]
            if len(df) < 5:
                continue
            X = features(df.ts.values, df.Luz.values, df['T'].values)
            X['Potencia_mW'] = df.P.values
            X['sesion'] = s['id']
            tablas.append(X)
            usadas.append(s['id'])
        return pd.concat(tablas, ignore_index=True), usadas

    def entrenar(self):
        with self.lock:
            self.info.update(estado='descargando sesiones de la nube…')
            t0 = time.time()
            df, usadas = self.datos()
            self.info.update(estado='entrenando…')
            y = df.Potencia_mW.values
            # Validación: dejar fuera una sesión real a la vez (datos que el modelo nunca vio)
            pred_gb, pred_fis = np.zeros(len(df)), np.zeros(len(df))
            grupos = df.sesion.values
            for sid in np.unique(grupos):
                tr, te = grupos != sid, grupos == sid
                pred_gb[te] = nuevo_gb().fit(df[X_COLS][tr], y[tr]).predict(df[X_COLS][te])
                pred_fis[te] = Fisico().fit(df[X_COLS][tr], y[tr]).predict(df[X_COLS][te])
            gb = nuevo_gb().fit(df[X_COLS], y)
            # Importancia por permutación (cuánto empeora el MAE si se revuelve cada variable)
            base = mean_absolute_error(y, gb.predict(df[X_COLS]))
            rng = np.random.default_rng(0)
            imp = {}
            for c in X_COLS[:4]:
                Xp = df[X_COLS].copy(); Xp[c] = rng.permutation(Xp[c].values)
                imp[c] = max(0.0, mean_absolute_error(y, gb.predict(Xp)) - base)
            tot = sum(imp.values()) or 1
            self.gb = gb
            self.info = {
                'listo': True, 'estado': 'listo', 'donde': 'Tu computadora (ml/servidor_local.py)',
                'nombre': 'gradient boosting', 'sesiones': len(usadas), 'minutos': int(len(df)),
                'entrenado': int(time.time() * 1000), 'segundos': round(time.time() - t0, 1),
                'validacion': 'dejando fuera una sesión a la vez',
                'gb': metricas(y, pred_gb), 'fisico': metricas(y, pred_fis),
                'importancia': [{'label': {'Luz_Pct': 'Luz (LDR)', 'Temperatura_C': 'Temperatura', 'hora_sin': 'Hora (seno)', 'hora_cos': 'Hora (coseno)'}[k],
                                 'value': round(v / tot * 100, 1)} for k, v in sorted(imp.items(), key=lambda kv: -kv[1])],
            }
            print(f"[modelo] {len(usadas)} sesiones, {len(df)} min | GB {self.info['gb']} | física {self.info['fisico']}")
            return self.info

    def predecir(self, filas):
        if self.gb is None:
            raise RuntimeError('el modelo todavía no está entrenado')
        a = np.array([[float(f[0]), float(f[1]), float(f[2])] for f in filas]) if filas else np.zeros((0, 3))
        if not len(a):
            return []
        return np.round(np.maximum(self.gb.predict(features(a[:, 0], a[:, 1], a[:, 2])[X_COLS]), 0), 2).tolist()


MODELO = Modelo()
_pron = {'t': 0, 'datos': None}


def pronostico(dias):
    """Clima de Open-Meteo (irradiancia en el plano del panel a 50° al sur y temperatura) -> modelo."""
    if not _pron['datos'] or time.time() - _pron['t'] > 1800 or _pron['dias'] != dias:
        url = ('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s'
               '&minutely_15=global_tilted_irradiance,temperature_2m,cloud_cover'
               '&tilt=%d&azimuth=0&timezone=GMT&forecast_days=%d' % (LAT, LON, ANGULO, dias + 2))
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'simon-local'}), timeout=20) as r:
            j = json.loads(r.read())['minutely_15']
        _pron.update(t=time.time(), dias=dias, datos=j)
    j = _pron['datos']
    ts = np.array(j['time'], dtype='datetime64[ms]').astype('int64')
    G = np.nan_to_num(np.array(j['global_tilted_irradiance'], float))
    Ta = np.nan_to_num(np.array(j['temperature_2m'], float), nan=25)
    nubes = np.nan_to_num(np.array(j.get('cloud_cover') or [0] * len(ts), float))
    Tp = Ta + CALENTAMIENTO * G                       # temperatura del panel
    luz = ldr_pct(G)                                  # lo que marcaría la LDR
    P = np.array(MODELO.predecir(np.c_[ts, luz, Tp].tolist()))
    P[G < 5] = 0                                      # de noche no hay potencia
    with np.errstate(divide='ignore', invalid='ignore'):
        eff = np.where(G > 50, P / 1000 / (G * AREA_M2) * 100, np.nan)
    ahora = time.time() * 1000
    # Desde hace 1 h hasta el final del día local número «dias» (hoy cuenta como el día 0)
    hoy0 = (ahora - 6 * 3600e3) // 86400e3 * 86400e3 + 6 * 3600e3
    keep = (ts >= ahora - 3600e3) & (ts < hoy0 + (dias + 1) * 86400e3)
    filas = [[int(a), round(float(g), 1), round(float(t), 1), round(float(p), 1), None if np.isnan(e) else round(float(e), 3), int(n)]
             for a, g, t, p, e, n, k in zip(ts, G, Tp, P, eff, nubes, keep) if k]
    # Energía predicha por día (hora local)
    dias_e = {}
    for a, _, _, p, _, _ in filas:
        d = time.strftime('%Y-%m-%d', time.gmtime(a / 1000 - 6 * 3600))
        dias_e[d] = dias_e.get(d, 0) + p * 0.25 / 1000      # mW × 15 min -> Wh
    return {'fuente': 'Open-Meteo (pronóstico del clima) + modelo local',
            'columnas': ['ts', 'G_Wm2', 'T_panel_C', 'P_mW', 'eficiencia_pct', 'nubes_pct'],
            'filas': filas, 'energia_dia_Wh': {k: round(v, 2) for k, v in dias_e.items()}}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(DISENO), **k)

    def log_message(self, fmt, *args):
        if '/api/local/' in self.path:
            sys.stderr.write('[http] ' + (fmt % args) + '\n')

    def enviar(self, obj, status=200):
        b = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def cuerpo(self):
        n = int(self.headers.get('Content-Length') or 0)
        return self.rfile.read(n) if n else b''

    def local(self, metodo, ruta):
        try:
            if ruta == 'estado':
                return self.enviar(MODELO.info)
            if ruta == 'predecir' and metodo == 'POST':
                filas = (json.loads(self.cuerpo() or b'{}').get('filas') or [])[:20000]
                return self.enviar({**{k: MODELO.info.get(k) for k in ('nombre', 'donde')}, 'p': MODELO.predecir(filas)})
            if ruta == 'reentrenar' and metodo == 'POST':
                return self.enviar(MODELO.entrenar())
            if ruta.startswith('pronostico'):
                dias = 3
                if '?' in ruta:
                    q = dict(p.split('=') for p in ruta.split('?', 1)[1].split('&') if '=' in p)
                    dias = max(1, min(7, int(q.get('dias', 3))))
                return self.enviar(pronostico(dias))
            return self.enviar({'error': 'ruta no encontrada'}, 404)
        except Exception as e:      # noqa: BLE001
            return self.enviar({'error': str(e)}, 500)

    def proxy(self, metodo):
        url = NUBE + self.path[len('/simon/api/'):]
        req = urllib.request.Request(url, data=self.cuerpo() if metodo != 'GET' else None, method=metodo,
                                     headers={k: v for k, v in self.headers.items() if k.lower() in ('content-type', 'x-pin')} | {'User-Agent': 'simon-local'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                b, status, tipo = r.read(), r.status, r.headers.get('Content-Type', 'application/json')
        except urllib.error.HTTPError as e:
            b, status, tipo = e.read(), e.code, e.headers.get('Content-Type', 'application/json')
        except Exception as e:      # noqa: BLE001
            return self.enviar({'error': f'sin conexión a la nube: {e}'}, 502)
        self.send_response(status)
        self.send_header('Content-Type', tipo)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def manejar(self, metodo):
        if self.path.startswith('/simon/api/local/'):
            return self.local(metodo, self.path[len('/simon/api/local/'):])
        if self.path.startswith('/simon/api/'):
            return self.proxy(metodo)
        if metodo != 'GET':
            return self.enviar({'error': 'método no permitido'}, 405)
        if self.path in ('/', '/simon'):
            self.send_response(302); self.send_header('Location', '/simon/'); self.end_headers(); return
        if self.path.startswith('/simon/'):
            self.path = self.path[len('/simon'):]
        return super().do_GET()

    def do_GET(self): self.manejar('GET')
    def do_POST(self): self.manejar('POST')
    def do_DELETE(self): self.manejar('DELETE')

    def end_headers(self):
        if not self.path.startswith('/simon/api'):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


def main():
    mimetypes.add_type('text/javascript', '.js')
    srv = ThreadingHTTPServer(('127.0.0.1', PUERTO), Handler)
    print(f'SIMON local en http://localhost:{PUERTO}/simon/  (Ctrl+C para salir)')
    threading.Thread(target=MODELO.entrenar, daemon=True).start()
    if '--no-abrir' not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{PUERTO}/simon/#/prediccion')).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
