// Copia este archivo como secrets.h (junto al .ino) y llena los valores.
// secrets.h está en .gitignore: la contraseña y el token no se suben al repo.

#define WIFI_SSID  "nombre de la red (solo 2.4 GHz)"
#define WIFI_PASS  "contraseña"

// API del Worker y el mismo token que se guardó con: npx wrangler secret put TOKEN_ESP32
#define API_URL    "https://simon.<tu-subdominio>.workers.dev/simon/api/lecturas"
#define API_TOKEN  "token"
