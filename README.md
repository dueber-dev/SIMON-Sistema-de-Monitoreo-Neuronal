# SIMON — Sistema de Monitoreo Neuronal

Monitoreo de un panel solar con ESP32: voltaje, corriente, temperatura e irradiancia, más un dashboard en tiempo real. Los datos se guardan en CSV y alimentarán un modelo de machine learning que prediga la eficiencia del panel.

## Contenido

| Archivo | Qué es |
|---|---|
| `preuba_adentro_esp32normal.ino` | Firmware del ESP32. Lee el INA219 (V, I, P), un LM35 (temperatura) y un LDR (luz). Crea la red Wi‑Fi `ESP32_Panel_Solar` y envía `seg,V,mA,mW,°C,luz%` por TCP (puerto 8080) una vez por segundo. |
| `codigo_esp32_prueba2.py` | Cliente TCP que recibe las tramas y las guarda en `datos_panel_solar_wifi_vN.csv`. |
| `dashboard.py` | Dashboard de prueba en Streamlit (prototipo original). |
| `design/` | Rediseño del dashboard: maqueta navegable con datos simulados (ver abajo). |
| `docs/justificacion-dashboard.md` | Usuario final, indicadores elegidos y su justificación, lógica de las alertas y relación con la rúbrica. |

## Ver la maqueta del nuevo dashboard

```bash
python -m http.server 5510 --directory design
```

Abre `http://localhost:5510`. Se tiene que servir por HTTP: abriendo el archivo directamente no cargan las imágenes ni los módulos JS.

La maqueta tiene cinco vistas, todas con datos simulados con el mismo formato que manda el ESP32:

| Vista | Qué muestra |
|---|---|
| **En vivo** | Potencia, voltaje, corriente, temperatura, irradiancia (W/m²) y eficiencia en tiempo real; potencia medida vs teórica; eficiencia real vs nominal con umbral de mantenimiento; temperatura con umbral de alerta; estado del sistema |
| **Análisis** | Cualquier sesión guardada: resumen, serie temporal por variable, distribución, efecto de la temperatura, tabla de datos y exportación a CSV |
| **Predicción ML** | Eficiencia real vs predicha, métricas del modelo, importancia de variables, error y simulador de escenarios. Usa un modelo de demostración que se reemplazará por el del equipo |
| **Sesiones** | Historial de CSV con calendario, búsqueda, comparación entre sesiones y descarga |
| **Configuración** | Ficha técnica del panel, calibración de sensores, conexión y escenarios del simulador (normal, nublado, panel sucio, calor extremo), alertas y mantenimiento, archivos de datos y apariencia |

Cada indicador tiene un botón **i** que explica qué mide, por qué está en el dashboard, cómo se calcula y su umbral.

Estructura: `design/index.html` (esqueleto y router), `design/css/`, `design/js/` (`sim.js` simulador y sesiones, `physics.js` irradiancia, eficiencias, potencia teórica y mantenimiento, `charts.js` gráficas SVG, `ml.js` modelo demo, `info.js` fichas de indicadores, `store.js` configuración) y `design/js/views/` (una vista por archivo).

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

## Auditoría y pruebas de software

La maqueta siempre identifica sus datos como sintéticos, incluso si existían preferencias antiguas de conexión al ESP32. La entrada de hardware permanece deshabilitada hasta implementar un puente real. Las alertas usan timestamps y cobertura temporal; una sola ráfaga de muestras no representa cinco minutos.

Ejecutar con Node.js 22.7 o posterior: `node --test tests/physics.test.mjs`. Estas pruebas verifican cálculos y estados del software; no certifican calibración, cableado ni exactitud experimental. Consultar `docs/auditoria-rubrica.md` para evidencias y pendientes.

El cliente TCP valida los seis campos, rechaza valores no finitos, limita tramas y reconecta si pasan 10 segundos sin datos. Un retroceso en el reloj del ESP32 inicia otro CSV; las lecturas válidas mantienen su representación original. Pruebas del receptor: `python -m unittest discover -s tests -p "test_*.py"`. No recupera muestras perdidas durante una desconexión.
