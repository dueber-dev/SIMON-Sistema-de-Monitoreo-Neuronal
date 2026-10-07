# SIMON — Sistema de Monitoreo Neuronal

Monitoreo de un panel solar con ESP32: voltaje, corriente, temperatura e irradiancia, más un dashboard en tiempo real. Los datos se guardan en CSV y alimentarán un modelo de machine learning que prediga la eficiencia del panel.

## Contenido

| Archivo | Qué es |
|---|---|
| `preuba_adentro_esp32normal.ino` | Firmware del ESP32. Lee el INA219 (V, I, P), un LM35 (temperatura) y un LDR (luz). Crea la red Wi‑Fi `ESP32_Panel_Solar` y envía `seg,V,mA,mW,°C,luz%` por TCP (puerto 8080) una vez por segundo. |
| `codigo_esp32_prueba2.py` | Cliente TCP que recibe las tramas y las guarda en `datos_panel_solar_wifi_vN.csv`. |
| `dashboard.py` | Dashboard de prueba en Streamlit (prototipo original). |
| `design/` | Rediseño del dashboard: maqueta navegable con datos simulados (ver abajo). |

## Ver la maqueta del nuevo dashboard

```bash
python -m http.server 5510 --directory design
```

Abre `http://localhost:5510`. Se tiene que servir por HTTP: abriendo el archivo directamente no cargan las imágenes ni los módulos JS.

La maqueta tiene cinco vistas, todas con datos simulados con el mismo formato que manda el ESP32:

| Vista | Qué muestra |
|---|---|
| **En vivo** | Métricas en tiempo real, potencia, voltaje, corriente, potencia vs irradiancia, estado del sistema |
| **Análisis** | Cualquier sesión guardada: resumen, serie temporal por variable, distribución, efecto de la temperatura, tabla de datos y exportación a CSV |
| **Predicción ML** | Eficiencia real vs predicha, métricas del modelo, importancia de variables, error y simulador de escenarios. Usa un modelo de demostración que se reemplazará por el del equipo |
| **Sesiones** | Historial de CSV con calendario, búsqueda, comparación entre sesiones y descarga |
| **Configuración** | Panel, calibración de sensores, conexión, alertas, archivos de datos y apariencia (tema y fondo) |

Estructura: `design/index.html` (esqueleto y router), `design/css/`, `design/js/` (`sim.js` simulador y sesiones, `charts.js` gráficas SVG, `ml.js` modelo demo, `store.js` configuración) y `design/js/views/` (una vista por archivo).

## Usar el prototipo original

1. Conecta la laptop a la red Wi‑Fi `ESP32_Panel_Solar`.
2. `python codigo_esp32_prueba2.py`
3. En otra terminal: `streamlit run dashboard.py`

## Hoja de ruta

- [x] Fase 1 — Maqueta visual de la vista "En vivo"
- [x] Vistas restantes: Análisis, Predicción ML, Sesiones, Configuración
- [ ] Backend FastAPI: puente TCP → CSV → WebSocket, con simulador
- [ ] Frontend Astro + TypeScript + Tailwind conectado al backend
- [ ] Modelo de predicción de eficiencia
