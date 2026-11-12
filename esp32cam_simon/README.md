# Módulo de Inspección Visual (ESP32-CAM + OV3660) — SIMON

Este módulo captura periódicamente fotos de inspección en alta resolución (VGA 640×480) del panel solar para monitoreo de suciedad, sombras, polvo o anomalías físicas, y las transmite a la nube (`dueber.dev/simon`) y a un visor web local.

---

## 🛠️ Configuración en Arduino IDE

Para compilar y grabar en la placa sin errores:

1. **Gestor de Tarjetas:** Instalar `esp32` de Espressif (versión recomendada: Core v2.x o v3.x).
2. **Parámetros en el menú Herramientas (Tools):**
   * **Placa (Board):** `AI Thinker ESP32-CAM` (o `ESP32 Dev Module`).
   * **CPU Frequency:** `160MHz (WiFi/BT)`. *(No usar 240 MHz por inestabilidad, ni menos de 80 MHz porque apaga la radio Wi-Fi)*.
   * **Flash Frequency:** `80MHz`.
   * **Partition Scheme:** `Huge APP (3MB No OTA / 1MB SPIFFS)`.
   * **PSRAM:** `Enabled` **(¡CRUCIAL! Sin esto el sensor OV3660 desborda memoria y falla con FB-OVF)**.
   * **Core Debug Level:** `None` o `Info`.

---

## 🔑 Configuración de Credenciales (`secrets.h`)

Por seguridad, las contraseñas no se suben al repositorio.

1. En esta carpeta (`esp32cam_simon/`), copia el archivo `secrets.example.h` y renómbralo como **`secrets.h`**.
2. Rellena tus datos:

```cpp
#ifndef SECRETS_H
#define SECRETS_H

// 1. Redes Wi-Fi (busca ambas automáticamente)
#define WIFI_SSID_CASA    "Tu_Wifi_Casa"
#define WIFI_PASS_CASA    "Tu_Password_Casa"

#define WIFI_SSID_U       "Alumnos-Docs - Key"
#define WIFI_PASS_U       "@lumnoK3y2025$"

// 2. URLs de la API
// Para subir a la nube oficial:
#define API_FOTO_URL      "https://dueber.dev/simon/api/foto"
#define API_URL           "https://dueber.dev/simon/api/lecturas"

// 3. Token de autenticación del Worker
#define API_TOKEN         "token"

#endif
```

---

## 📡 Modos de Funcionamiento

1. **Modo Nube (Automático):**
   * Se conecta a la red Wi-Fi disponible (Casa o Universidad).
   * Sube una foto cada 5 minutos al endpoint `https://dueber.dev/simon/api/foto`.
   * Sirve una página web local en su IP asignada (ejemplo: `http://192.168.0.X` o `http://10.74.X.X`) para encuadre en tiempo real.

2. **Modo Autónomo / Exteriores (Sin Wi-Fi):**
   * Si no detecta ninguna red conocida, levanta su propio punto de acceso Wi-Fi: **`SIMON_CAM`** (red abierta).
   * Te conectas con cualquier celular o laptop a la red `SIMON_CAM`.
   * Abres en el navegador: **`http://192.168.4.1`** para ver el visor local e inspeccionar el panel sin requerir internet.

---

## 🔬 Solución al Error `cam_hal: FB-OVF` con el Sensor OV3660
El sensor OV3660 de 3 MP genera un flujo masivo de datos al iniciar en su resolución nativa. Para evitar que desborde el DMA:
* La estructura `camera_config_t` se limpia con `memset(&config, 0, sizeof(camera_config_t))` para evitar campos basura en Core 3.x.
* Se inicializa el hardware reservando búfer en PSRAM con `FRAMESIZE_UXGA` y reloj XCLK a 20 MHz.
* Inmediatamente después del `esp_camera_init()`, se reduce por software a `FRAMESIZE_VGA` (640×480) y se drenan los descriptores DMA viejos.
