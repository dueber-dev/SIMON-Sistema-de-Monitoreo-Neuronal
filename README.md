# SIMON — Sistema de Monitoreo Neuronal ☀️

Sistema integral de telemetría y monitoreo visual para paneles solares (soporte a 50°). Mide en tiempo real voltaje, corriente, potencia, irradiancia y temperatura, capturando además inspecciones fotográficas periódicas para detectar suciedad, sombras o degradación física. Cuenta con un dashboard web en tiempo real alojado en Cloudflare Workers y soporte para predicción de eficiencia mediante Machine Learning.

---

## 🏗️ Arquitectura del Sistema

El sistema consta de **dos microcontroladores independientes** que operan en paralelo sin cables entre sí:

1. **ESP32 Principal (Telemetría de Sensores):**
   * **Firmware:** [`preuba_adentro_esp32normal.ino`](preuba_adentro_esp32normal.ino)
   * **Sensores:**
     * Sensor digital I2C **INA219** (mide Voltaje, Corriente y calcula Potencia).
     * Sensor analógico de Temperatura **LM35** (en GPIO 33).
     * Fotorresistencia **LDR** para estimación de Luz/Irradiancia (en GPIO 32).
   * **Transmisión:** Envía paquetes cada 5 segundos al endpoint `POST /simon/api/lecturas`. Si no hay Wi-Fi, crea la red `ESP32_Panel_Solar`.

2. **ESP32-CAM (Inspección Visual con Sensor OV3660 3MP):**
   * **Firmware:** [`esp32cam_simon/esp32cam_simon.ino`](esp32cam_simon/esp32cam_simon.ino)
   * **Sensor Óptico:** OmniVision **OV3660** (3 Megapíxeles) calibrado a 20 MHz con PSRAM habilitada.
   * **Resolución:** VGA (640×480) en formato JPEG.
   * **Transmisión:** Sube una fotografía cada 5 minutos a `POST /simon/api/foto`. Si no hay Wi-Fi, crea la red autónoma `SIMON_CAM` en `http://192.168.4.1`.

3. **Plataforma Nube & Dashboard:**
   * **Host:** Cloudflare Workers + base de datos SQLite D1 + Static Assets en `https://dueber.dev/simon`.

---

## 🔑 Archivos de Credenciales (`secrets.h`)

Por seguridad, las contraseñas Wi-Fi y tokens no se suben al repositorio (están en `.gitignore`). Para compilar, debes crear **dos archivos `secrets.h`**:

### 1. Para el ESP32 Normal de Sensores
Copia `secrets.example.h` y renómbralo como **`secrets.h`** en la raíz del proyecto:
```cpp
#ifndef SECRETS_H
#define SECRETS_H

#define WIFI_SSID         "Nombre_De_Tu_Wifi"
#define WIFI_PASS         "Password_De_Tu_Wifi"

#define API_URL           "https://dueber.dev/simon/api/lecturas"
#define API_FOTO_URL      "https://dueber.dev/simon/api/foto"
#define API_TOKEN         "token"

#endif
```

### 2. Para la ESP32-CAM
Copia `esp32cam_simon/secrets.example.h` y renómbralo como **`esp32cam_simon/secrets.h`**:
```cpp
#ifndef SECRETS_H
#define SECRETS_H

#define WIFI_SSID_CASA    "Wifi_Casa"
#define WIFI_PASS_CASA    "Password_Casa"

#define WIFI_SSID_U       "Alumnos-Docs - Key"
#define WIFI_PASS_U       "@lumnoK3y2025$"

#define API_FOTO_URL      "https://dueber.dev/simon/api/foto"
#define API_URL           "https://dueber.dev/simon/api/lecturas"
#define API_TOKEN         "token"

#endif
```

---

## 💻 Requisitos y Grabación en Arduino IDE

### Librerías Requeridas (instalar desde el Gestor de Librerías):
* **`Adafruit INA219`** (de Adafruit).
* **`WiFi`**, **`HTTPClient`**, **`WiFiClientSecure`**, **`Wire`** (vienen incluidas con el paquete de tarjetas ESP32).

### Configuración para el ESP32 Normal:
* **Placa:** `ESP32 Dev Module`.
* **Upload Speed:** `115200` o `921600`.
* **CPU Frequency:** `160MHz` o `240MHz`.

### Configuración para la ESP32-CAM (OV3660):
* **Placa:** `AI Thinker ESP32-CAM` (o `ESP32 Dev Module`).
* **CPU Frequency:** `160MHz (WiFi/BT)` *(obligatorio para estabilidad de Wi-Fi y reloj)*.
* **PSRAM:** `Enabled` **(¡OBLIGATORIO! Sin PSRAM el sensor OV3660 desborda la memoria interna y falla con FB-OVF)**.
* **Partition Scheme:** `Huge APP (3MB No OTA / 1MB SPIFFS)`.

---

## ☁️ Despliegue en la Nube (Cloudflare Workers + D1)

Todo el backend, la base de datos y la interfaz web del dashboard se despliegan en un solo comando:

```bash
cd nube
# Iniciar sesión en Cloudflare por primera vez:
npx wrangler login

# Desplegar dashboard y API a producción:
npm run deploy
```

El script `npm run deploy` ejecuta automáticamente `node build.mjs` (que copia la interfaz de `design/` a `public/simon/`) y luego publica el Worker en producción.

---

## 🌐 Ver el Dashboard

* **En la Nube Oficial:** [https://dueber.dev/simon](https://dueber.dev/simon)
* **Visor de última foto:** [https://dueber.dev/simon/api/foto/ultima](https://dueber.dev/simon/api/foto/ultima)
* **Visor local de la cámara (en la misma red):** `http://<IP_DE_LA_CAMARA>/`
* **Visor de emergencia (sin internet en campo):** Conectarse al Wi-Fi `SIMON_CAM` y entrar a `http://192.168.4.1`.
