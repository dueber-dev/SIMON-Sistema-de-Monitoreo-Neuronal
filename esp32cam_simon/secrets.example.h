// Plantilla de configuración de red y credenciales para ESP32-CAM
// Copia este archivo como "secrets.h" y llena tus datos reales
#ifndef SECRETS_H
#define SECRETS_H

// Red 1 (Casa):
#define WIFI_SSID_CASA    "TU_WIFI_CASA"
#define WIFI_PASS_CASA    "TU_PASSWORD_CASA"

// Red 2 (Universidad / Trabajo):
#define WIFI_SSID_U       "TU_WIFI_U"
#define WIFI_PASS_U       "TU_PASSWORD_U"

// URLs de la API:
// Modo Nube Producción:
#define API_FOTO_URL      "https://dueber.dev/simon/api/foto"
#define API_URL           "https://dueber.dev/simon/api/lecturas"

// Modo Local (si pruebas en tu laptop):
// #define API_FOTO_URL   "http://TU_IP_LOCAL:8787/simon/api/foto"

// Token de autenticación del Worker:
#define API_TOKEN         "TU_TOKEN"

#endif

