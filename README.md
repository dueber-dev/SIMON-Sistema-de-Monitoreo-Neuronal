# SIMON — Sistema de Monitoreo Neuronal

Monitoreo de un panel solar con ESP32: voltaje, corriente, temperatura e irradiancia, más un dashboard en tiempo real. Los datos se guardan en CSV y alimentarán un modelo de machine learning que prediga la eficiencia del panel.

## Contenido

| Archivo | Qué es |
|---|---|
| `preuba_adentro_esp32normal.ino` | Firmware del ESP32. Lee el INA219 (V, I, P), un LM35 (temperatura) y un LDR (luz). Crea la red Wi‑Fi `ESP32_Panel_Solar` y envía `seg,V,mA,mW,°C,luz%` por TCP (puerto 8080) una vez por segundo. |
| `codigo_esp32_prueba2.py` | Cliente TCP que recibe las tramas y las guarda en `datos_panel_solar_wifi_vN.csv`. |
| `dashboard.py` | Dashboard de prueba en Streamlit (prototipo original). |
| `design/` | Rediseño del dashboard: maqueta estática con datos simulados. |

## Ver la maqueta del nuevo dashboard

```bash
python -m http.server 5510 --directory design
```

Abre `http://localhost:5510/maqueta-en-vivo.html`. Se tiene que servir por HTTP: abriendo el archivo directamente no cargan las imágenes.

## Usar el prototipo original

1. Conecta la laptop a la red Wi‑Fi `ESP32_Panel_Solar`.
2. `python codigo_esp32_prueba2.py`
3. En otra terminal: `streamlit run dashboard.py`

## Hoja de ruta

- [x] Fase 1 — Maqueta visual de la vista "En vivo"
- [ ] Vistas restantes: Análisis, Predicción ML, Sesiones, Configuración
- [ ] Backend FastAPI: puente TCP → CSV → WebSocket, con simulador
- [ ] Frontend Astro + TypeScript + Tailwind conectado al backend
- [ ] Modelo de predicción de eficiencia
